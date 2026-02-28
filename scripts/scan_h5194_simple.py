#!/usr/bin/env python3
"""
Simple BLE Scanner - Quick 10-second snapshot
Shows all devices with basic info
"""
import asyncio
from bleak import BleakScanner

async def scan():
    print("Scanning for BLE devices (10 seconds)...")
    devices = await BleakScanner.discover(timeout=10.0, return_adv=True)

    print(f"\n📡 Found {len(devices)} BLE devices\n")
    
    for addr, (device, adv_data) in devices.items():
        name = device.name or "Unknown"
        # Show ALL devices, but highlight Govee ones
        marker = "🌡️ " if ("Govee" in name or "GVH" in name) else "   "
        print(f"{marker}Name: {name}")
        print(f"   Address: {addr}")
        print(f"   RSSI: {adv_data.rssi} dBm")
        if adv_data.manufacturer_data:
            print(f"   Manufacturer Data: {adv_data.manufacturer_data}")
        if adv_data.service_data:
            print(f"   Service Data: {adv_data.service_data}")
        print()

asyncio.run(scan())
