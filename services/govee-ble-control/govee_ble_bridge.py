#!/usr/bin/env python3
"""
govee-ble-bridge — MQTT → BLE GATT write bridge.

Subscribes to the Theengs Gateway command topic and executes BLE GATT writes
using bleak. Runs on the VM where the BT adapter lives.

Topic: home/TheengsGateway/commands/MQTTtoBT
Payload: {"id": "AA:BB:CC:DD:EE:FF", "serviceUUID": "...",
          "characteristicUUID": "...", "value": "hex", "write": true}
"""

import asyncio
import json
import logging
import os
import threading

import paho.mqtt.client as mqtt
from bleak import BleakClient, BleakError

BROKER = os.getenv("BROKER", "mosquitto")
PORT = int(os.getenv("MQTT_PORT", "1883"))
COMMAND_TOPIC = os.getenv("COMMAND_TOPIC", "home/TheengsGateway/commands/MQTTtoBT")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(level=getattr(logging, LOG_LEVEL),
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("govee-ble-bridge")

_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)


async def ble_write(address: str, char_uuid: str, value_hex: str):
    value = bytes.fromhex(value_hex)
    try:
        async with BleakClient(address, timeout=10.0) as client:
            await client.write_gatt_char(char_uuid, value, response=False)
            log.info(f"✓ {address} ← {value_hex}")
    except BleakError as e:
        log.error(f"BLE error {address}: {e}")
    except Exception as e:
        log.error(f"Error {address}: {e}")


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload)
        if not data.get("write"):
            return
        address = data.get("id")
        char_uuid = data.get("characteristicUUID")
        value_hex = data.get("value")
        if not all([address, char_uuid, value_hex]):
            log.warning(f"Incomplete payload: {data}")
            return
        log.info(f"→ BLE write {address} {value_hex[:8]}...")
        asyncio.run_coroutine_threadsafe(
            ble_write(address, char_uuid, value_hex), _loop
        )
    except Exception as e:
        log.error(f"Message handler error: {e}")


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        log.info(f"MQTT connected {BROKER}:{PORT}")
        client.subscribe(COMMAND_TOPIC)
        log.info(f"Subscribed: {COMMAND_TOPIC}")
    else:
        log.error(f"MQTT connect failed rc={rc}")


def main():
    log.info("govee-ble-bridge starting")
    _loop_thread.start()

    client = mqtt.Client(client_id="govee-ble-bridge")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _loop.call_soon_threadsafe(_loop.stop)
        client.disconnect()
        log.info("Stopped")


if __name__ == "__main__":
    main()
