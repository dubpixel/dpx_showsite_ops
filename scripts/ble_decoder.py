#!/usr/bin/env python3
"""Auto-discover Govee devices and decode BLE data from Theengs Gateway"""
import json
import urllib.request
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
API = "http://localhost:8056/api/devices"
SUB_TOPIC = "home/TheengsGateway/BTtoMQTT/#"
PUB_PREFIX = "govee/ble"

DECODERS = {
    "H5051": lambda b: decode_h5051(b),
    "H5074": lambda b: decode_h507x(b),
    "H5075": lambda b: decode_h507x(b),
    "H5072": lambda b: decode_h507x(b),
}

DEVICES = {}

def load_devices():
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
            print(f"  {mac} -> {info['name']} ({info['sku']}) room={info['room']}")
    except Exception as e:
        print(f"Failed to load devices: {e}")

def decode_h5051(b):
    if len(b) < 8:
        return None
    temp_raw = b[3] | (b[4] << 8)
    return {"temp_c": temp_raw / 100.0, "humidity": b[5] / 10.0, "battery": b[7]}

def decode_h507x(b):
    if len(b) < 6:
        return None
    raw = (b[3] << 16) | (b[4] << 8) | b[5]
    return {"temp_c": raw / 10000, "humidity": (raw % 1000) / 10.0, "battery": b[6]}

def on_message(client, userdata, msg):
    try:
        mac = msg.topic.split("/")[-1]
        device = None
        for suffix, info in DEVICES.items():
            if suffix.endswith(mac) or mac.endswith(suffix[-len(mac):]):
                device = info
                break
        if not device:
            return
        data = json.loads(msg.payload)
        mfr = data.get("manufacturerdata")
        if not mfr:
            return
        decoder = DECODERS.get(device["sku"])
        if not decoder:
            return
        b = bytes.fromhex(mfr)
        decoded = decoder(b)
        if not decoded:
            return
        room = device["room"]
        client.publish(f"{PUB_PREFIX}/{room}/temperature", decoded["temp_c"])
        client.publish(f"{PUB_PREFIX}/{room}/humidity", decoded["humidity"])
        if "battery" in decoded:
            client.publish(f"{PUB_PREFIX}/{room}/battery", decoded["battery"])
        print(f"[{device['name']}] Temp: {decoded['temp_c']:.2f}C  Hum: {decoded['humidity']:.1f}%  Batt: {decoded.get('battery', '?')}%")
    except Exception as e:
        print(f"Error: {e}")

load_devices()
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect(BROKER, PORT)
client.subscribe(SUB_TOPIC)
print(f"\nBLE decoder running, subscribed to {SUB_TOPIC}")
client.loop_forever()
