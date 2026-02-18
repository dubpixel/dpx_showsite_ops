#!/usr/bin/env python3
"""
BLE Decoder v2.0 - MQTT Payload Decoder
Decodes BLE manufacturer data from ESP32/Theengs gateways and publishes to normalized topics.

Topic Structure: {site}/{node}/{source_node}/{room}/{device}/{metric}
- site: SHOWSITE_NAME from environment (default: demo_showsite)
- node: dpx_ops_decoder (this service)
- source_node: Gateway that captured the BLE data (dpx_ops_1, TheengsGateway, etc)
- room: Physical location from Govee API
- device: Device name from Govee API
- metric: temperature, humidity, battery, rssi
"""

from datetime import datetime
import json
import os
import urllib.request
import paho.mqtt.client as mqtt
import sys
from datetime import datetime


# Configuration
BROKER = "localhost"
PORT = 1883
API = "http://localhost:8056/api/devices"

# Read showsite name from environment
SHOWSITE = os.getenv("SHOWSITE_NAME", "demo_showsite")
DECODER_NODE = "dpx_ops_decoder"

# Subscribe to both gateway types
SUB_TOPICS = [
    f"{SHOWSITE}/+/BTtoMQTT/#",        # ESP32 gateways
    "home/TheengsGateway/BTtoMQTT/#",  # Theengs gateway
]

# Decoder configuration per model
DECODERS = {
    "H5051": lambda b: decode_h5051(b),
    "H5074": lambda b: decode_h507x(b),
    "H5075": lambda b: decode_h507x(b),
    "H5072": lambda b: decode_h507x(b),
}

# Device mapping loaded from API
DEVICES = {}


def load_devices():
    """Load device info from govee2mqtt API."""
    try:
        resp = urllib.request.urlopen(API, timeout=5)
        devices = json.loads(resp.read())
        for d in devices:
            mac = d["id"].replace(":", "")
            suffix = mac[-12:]
            DEVICES[suffix] = {
                "name": d["name"].lower().replace(" ", "_"),
                "room": (d.get("room") or "unassigned").lower().replace(" ", "_"),
                "sku": d["sku"],
            }
        print(f"Loaded {len(DEVICES)} devices from API:")
        for mac, info in DEVICES.items():
            print(f"  {mac} -> {info['name']} ({info['sku']}) in {info['room']}")
    except Exception as e:
        print(f"Failed to load devices: {e}")
        print("Continuing with empty device map...")


def decode_h5051(b):
    """Decode Govee H5051 manufacturer data."""
    if len(b) < 8:
        return None
    temp_raw = b[3] | (b[4] << 8)
    return {
        "temp_f": (temp_raw / 100.0) * 9.0 / 5.0 + 32.0,  # Fahrenheit
        "humidity": b[5] / 10.0,
        "battery": b[7]
    }


def decode_h507x(b):
    """Decode Govee H5074/H5075/H5072 manufacturer data."""
    if len(b) < 8:
        return None
    # Reject iBeacon packets (start with 4c00) and other non-Govee packets
    if b[0] == 0x4c:  # Apple iBeacon
        return None
    # Validate Govee manufacturer header (88ec or 0188ec)
    if not (b[0] == 0x88 and b[1] == 0xec):
        return None
    # Little-endian 16-bit values in hundredths
    temp_raw = b[3] | (b[4] << 8)
    hum_raw = b[5] | (b[6] << 8)
    return {
        "temp_f": (temp_raw / 100.0) * 9.0 / 5.0 + 32.0,  # Fahrenheit
        "humidity": hum_raw / 100.0,
        "battery": b[7] if len(b) > 7 else 100
    }


def extract_source_node(topic):
    """
    Extract source node name from incoming topic.
    
    Topic formats:
    - demo_showsite/dpx_ops_1/BTtoMQTT/{MAC}
    - home/TheengsGateway/BTtoMQTT/{MAC}
    
    Returns: source_node name (e.g., "dpx_ops_1", "TheengsGateway")
    """
    parts = topic.split("/")
    
    if "TheengsGateway" in topic:
        return "TheengsGateway"
    elif len(parts) >= 2:
        return parts[1]
    else:
        return "unknown"


def on_message(client, userdata, msg):
    """Process incoming BLE message and publish decoded data."""
    try:
        # Parse JSON payload first
        data = json.loads(msg.payload)

        # Extract MAC - either from topic or from payload (if extDecoderEnable=true)
        topic_last = msg.topic.split("/")[-1]
        if topic_last == "undecoded":
            # extDecoderEnable mode: MAC is in the "id" field
            mac = data.get("id", "").replace(":", "").upper()
        else:
            # Normal mode: MAC is in the topic
            mac = topic_last.replace(":", "").upper()

        if os.getenv("DEBUG_DECODER"): print(f"DEBUG: Received from {msg.topic}, MAC: {mac}")

        # Match device by MAC suffix
        device = None
        for suffix, info in DEVICES.items():
            if suffix.endswith(mac) or mac.endswith(suffix[-len(mac):]):
                device = info
                break

        if not device:
            return  # Unknown device, skip
        
        # Debug: show device info and available data
        if os.getenv("DEBUG_DECODER"):
            print(f"  Device: {device['name']} ({device['sku']}), Room: {device['room']}")
            if "manufacturerdata" in data:
                print(f"  Raw hex: {data['manufacturerdata']}")
            if "tempf" in data:
                print(f"  Pre-decoded: {data['tempf']}°F, {data['hum']}%, batt: {data.get('batt')}%")
        
        # Prefer pre-decoded values (ESP32/Theengs firmware already decoded)
        if "tempf" in data and "hum" in data:
            decoded = {
                "temp_f": data["tempf"],
                "humidity": data["hum"],
                "battery": data.get("batt", 100)
            }
        else:
            # Fallback: manual decode of raw manufacturerdata
            mfr = data.get("manufacturerdata")
            if not mfr:
                return  # No data available
            
            # Get decoder for this device model
            decoder = DECODERS.get(device["sku"])
            if not decoder:
                return  # No decoder for this model
            
            # Decode the manufacturer data
            b = bytes.fromhex(mfr)
            decoded = decoder(b)
            
            if not decoded:
                return  # Decoding failed
        
        # Extract source node from incoming topic
        source_node = extract_source_node(msg.topic)
        
        # Build output topic path
        # Format: {site}/{node}/{source_node}/{room}/{device}/{mac}/{metric}
        room = device["room"]
        device_name = device["name"]
        base_topic = f"{SHOWSITE}/{DECODER_NODE}/{source_node}/{room}/{device_name}/{mac}"
        
        # Publish each metric
        client.publish(f"{base_topic}/temperature", decoded["temp_f"], retain=False)
        client.publish(f"{base_topic}/humidity", decoded["humidity"], retain=False)
        if "battery" in decoded:
            client.publish(f"{base_topic}/battery", decoded["battery"], retain=False)
        
        # Optional: Publish RSSI if available
        rssi = data.get("rssi")
        if rssi:
            client.publish(f"{base_topic}/rssi", rssi, retain=False)
        
        print(
            f"{datetime.now().strftime('%H:%M:%S')} [{source_node}] {room}/{device_name}: "
            f"{decoded['temp_f']:.2f}°F, {decoded['humidity']:.1f}%, "
            f"batt: {decoded.get('battery', '?')}%"
            )
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error on {msg.topic}: {e}")
    except Exception as e:
        print(f"Error processing {msg.topic}: {e}")


def on_connect(client, userdata, flags, rc):
    """Callback when client connects to MQTT broker."""
    if rc == 0:
        print(f"Connected to MQTT broker at {BROKER}:{PORT}")
        print(f"Showsite: {SHOWSITE}")
        print(f"Decoder node: {DECODER_NODE}")
        print()
        for topic in SUB_TOPICS:
            client.subscribe(topic)
            print(f"Subscribed to: {topic}")
        print()
    else:
        print(f"Failed to connect, return code {rc}")


def on_disconnect(client, userdata, rc):
    """Callback when client disconnects."""
    if rc != 0:
        print(f"Unexpected disconnect (code {rc}), reconnecting...")


def main():
    """Main entry point."""
    print("=" * 60)
    print("DPX BLE Decoder v2.0")
    print("=" * 60)
    print()
    
    # Load device mappings from API
    load_devices()
    print()
    
    # Create MQTT client (compatible with paho-mqtt 1.6.1)
    client = mqtt.Client(client_id="dpx_ops_decoder")
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    # Connect and start loop
    try:
        client.connect(BROKER, PORT, 60)
        print("Starting decoder loop...")
        print(f"Output: {SHOWSITE}/{DECODER_NODE}/{{source}}/{{room}}/{{device}}/{{mac}}/{{metric}}")
        print()
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        client.disconnect()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
