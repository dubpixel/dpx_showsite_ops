#!/usr/bin/env python3
"""
Advanced BLE Scanner - Continuous monitoring with detailed decoding
Tracks devices over time, counts appearances, decodes manufacturer data

Usage:
  python3 scan_h5194.py                    # Full 60-second scan with metadata
  python3 scan_h5194.py --quick            # Quick 20-second scan with device list
  python3 scan_h5194.py --direct <MAC>     # Direct deep scan of specific MAC address
"""
import asyncio
import argparse
import sys
from bleak import BleakScanner
from datetime import datetime
from collections import defaultdict

# Device tracking
device_tracker = defaultdict(lambda: {"count": 0, "last_seen": None, "rssi_history": [], "name": "Unknown"})

def decode_manufacturer_data(mfr_id, data):
    """Decode manufacturer-specific data formats"""
    hex_str = data.hex()
    
    # Govee devices (company ID 60552 / 0xEC88)
    if mfr_id == 60552:
        if len(data) >= 7:
            # H5051/H5075 format: bytes[2:4]=temp, bytes[4:6]=humidity (BIG endian)
            try:
                temp_raw = int.from_bytes(data[2:4], 'big', signed=True)
                humidity_raw = int.from_bytes(data[4:6], 'big')
                temp_c = temp_raw / 100.0
                temp_f = (temp_c * 9/5) + 32
                humidity = humidity_raw / 100.0
                battery = data[6] if len(data) > 6 and data[6] <= 100 else '??'
                return f"🌡️  {temp_f:.1f}°F / {temp_c:.1f}°C | {humidity:.1f}% | 🔋 {battery}%"
            except:
                return f"Govee (decode failed): {hex_str}"
    
    # Apple devices (company ID 76)
    elif mfr_id == 76:
        if len(data) >= 2:
            msg_type = data[0]
            if msg_type == 0x10:
                return "Apple: Proximity pairing"
            elif msg_type == 0x12:
                return "Apple: AirTag/FindMy"
            elif msg_type == 0x09:
                return "Apple: AirDrop"
    
    # Generic hex display for unknown formats
    return f"Raw: {hex_str}"

def detection_callback(device, advertisement_data):
    """Called each time a device is detected"""
    addr = device.address
    name = device.name or "Unknown"
    tracker = device_tracker[addr]
    
    # Update tracking
    tracker["count"] += 1
    tracker["name"] = name
    tracker["last_seen"] = datetime.now()
    tracker["rssi_history"].append(advertisement_data.rssi)
    
    # Store metadata (only on first detection to avoid cluttering)
    if tracker["count"] == 1:
        tracker["mfr_ids"] = list(advertisement_data.manufacturer_data.keys()) if advertisement_data.manufacturer_data else []
        tracker["mfr_data_sample"] = {k: v.hex() for k, v in advertisement_data.manufacturer_data.items()} if advertisement_data.manufacturer_data else {}
        tracker["service_uuids"] = advertisement_data.service_uuids or []
    
    # Keep only last 10 RSSI readings
    if len(tracker["rssi_history"]) > 10:
        tracker["rssi_history"].pop(0)
    
    avg_rssi = sum(tracker["rssi_history"]) / len(tracker["rssi_history"])
    
    # Determine device marker
    if "Govee" in name or "GVH" in name:
        marker = "🌡️ GOVEE"
    elif "H5194" in name or "5D6AD5" in name:
        marker = "🔥 H5194 FOUND!"
    elif "Unknown" in name and advertisement_data.manufacturer_data:
        marker = "❓"
    else:
        marker = "📱"
    
    # Print real-time update
    print(f"\n{marker} {name}")
    print(f"   MAC: {addr}")
    print(f"   RSSI: {advertisement_data.rssi} dBm (avg: {avg_rssi:.1f}) | Seen: {tracker['count']}x")
    print(f"   Time: {tracker['last_seen'].strftime('%H:%M:%S')}")
    
    # Decode manufacturer data
    if advertisement_data.manufacturer_data:
        for mfr_id, mfr_data in advertisement_data.manufacturer_data.items():
            decoded = decode_manufacturer_data(mfr_id, mfr_data)
            print(f"   Mfr ID: {mfr_id} (0x{mfr_id:04x}) → {decoded}")
    
    # Service data
    if advertisement_data.service_data:
        for uuid, data in advertisement_data.service_data.items():
            print(f"   Service: {uuid} → {data.hex()}")
    
    # Service UUIDs
    if advertisement_data.service_uuids:
        print(f"   Services: {', '.join(advertisement_data.service_uuids)}")

async def scan_continuous(duration=60):
    """Run continuous scan for specified duration"""
    print(f"🔍 Starting continuous BLE scan for {duration} seconds...")
    print(f"⏰ Started at {datetime.now().strftime('%H:%M:%S')}")
    print(f"🎯 Looking for H5194 (GVH5194_5D6AD5) and other Govee devices")
    print("=" * 70)
    
    scanner = BleakScanner(detection_callback)
    await scanner.start()
    await asyncio.sleep(duration)
    await scanner.stop()
    
    # Summary
    print("\n" + "=" * 70)
    print(f"📊 SCAN SUMMARY - Found {len(device_tracker)} unique devices")
    print("=" * 70)
    
    # Sort by appearance count
    sorted_devices = sorted(device_tracker.items(), key=lambda x: x[1]["count"], reverse=True)
    
    print(f"\n{'Device Name/Address':<35} {'Count':>5} {'RSSI':>7} {'Mfr ID':>8} {'Sample Data'}")
    print("-" * 100)
    
    for addr, info in sorted_devices:
        avg_rssi = sum(info["rssi_history"]) / len(info["rssi_history"])
        name_display = info["name"] if info["name"] != "Unknown" else addr[:8]
        
        # Manufacturer info
        mfr_str = ", ".join([str(m) for m in info.get("mfr_ids", [])]) if info.get("mfr_ids") else "-"
        
        # Sample data (truncated)
        sample_str = ""
        if info.get("mfr_data_sample"):
            for mfr_id, hex_data in info["mfr_data_sample"].items():
                sample_str = hex_data[:20] + ("..." if len(hex_data) > 20 else "")
                break  # Just show first one
        
        print(f"{name_display:<35} {info['count']:>5}x {avg_rssi:>6.1f} {mfr_str:>8} {sample_str}")
    
    # Detailed metadata for top 5
    print("\n" + "=" * 70)
    print("🔍 DETAILED METADATA - Top 5 Most Active Devices")
    print("=" * 70)
    
    for addr, info in sorted_devices[:5]:
        avg_rssi = sum(info["rssi_history"]) / len(info["rssi_history"])
        print(f"\n📱 {info['name']}")
        print(f"   Address: {addr}")
        print(f"   Appearances: {info['count']}x")
        print(f"   Avg RSSI: {avg_rssi:.1f} dBm")
        
        if info.get("mfr_ids"):
            for mfr_id in info["mfr_ids"]:
                hex_data = info["mfr_data_sample"].get(mfr_id, "")
                print(f"   Manufacturer: {mfr_id} (0x{mfr_id:04x})")
                print(f"   Sample Data: {hex_data}")
        
        if info.get("service_uuids"):
            print(f"   Services: {', '.join(info['service_uuids'])}")

async def deep_scan_device(target_addr, device_info):
    """Deep scan of a specific device - shows every broadcast with change detection"""
    previous_data = {}
    change_count = 0
    scan_count = 0
    
    def deep_callback(device, advertisement_data):
        nonlocal change_count, scan_count
        
        if target_addr not in device.address:
            return
        
        scan_count += 1
        
        if not advertisement_data.manufacturer_data:
            print(f"[{scan_count}] No manufacturer data")
            return
        
        for mfr_id, mfr_data in advertisement_data.manufacturer_data.items():
            hex_str = mfr_data.hex()
            
            # Check if data changed
            changed = hex_str != previous_data.get(mfr_id)
            if changed:
                change_count += 1
                previous_data[mfr_id] = hex_str
                marker = "🔥 CHANGED!" if change_count > 1 else "📡 FIRST"
            else:
                marker = "   same   "
            
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"\n{marker} [{timestamp}] Packet #{scan_count} | RSSI: {advertisement_data.rssi} dBm")
            print(f"   Mfr ID: {mfr_id} (0x{mfr_id:04x})")
            print(f"   Hex: {hex_str}")
            print(f"   Changes: {change_count}")
            
            # Try to decode if it looks like H5194
            if mfr_id == 27229 and len(mfr_data) >= 20:
                print(f"   Decoded: {decode_h5194_packet(mfr_data)}")
    
    print("=" * 70)
    print("⏰ Deep scan running - watching for data changes")
    print("💡 Insert/remove probes or change temps to see updates")
    print("=" * 70)
    
    scanner = BleakScanner(deep_callback)
    await scanner.start()
    
    try:
        await asyncio.sleep(120)  # 2 minutes
    except KeyboardInterrupt:
        print("\n\n⚠️  Deep scan stopped")
    finally:
        await scanner.stop()
    
    print(f"\n📊 Received {scan_count} packets, {change_count} changes detected")

def decode_h5194_packet(data):
    """Decode H5194 manufacturer data packet with temperature conversion"""
    if len(data) < 20:
        return "Packet too short"
    
    header = data[0]
    flags = data[1:5].hex()
    
    # Decode temperature for each probe (4-probe thermometer)
    # Probe positions: P1=bytes[5:9], P2=bytes[9:13], P3=bytes[13:17], P4=bytes[17:21]
    probes = []
    
    # Probe 1 - byte[6] encodes temp with offset -21
    if len(data) > 6 and data[5] == 0xe4:  # Valid probe 1 header
        temp_byte = data[6]
        if temp_byte not in [0xff, 0xfc]:  # Not unplugged
            temp_f = temp_byte - 21
            probes.append(f"P1:{temp_f}°F")
    
    # Probes 2, 3, 4 - first byte encodes temp with offset +33
    probe_positions = [(9, "P2"), (13, "P3"), (17, "P4")]
    for pos, label in probe_positions:
        if len(data) > pos:
            temp_byte = data[pos]
            # Check for unplugged patterns
            if temp_byte not in [0xff, 0xfc, 0x08] and data[pos:pos+4] != b'\xff\xff\xff\xff':
                temp_f = temp_byte + 33
                probes.append(f"{label}:{temp_f}°F")
    
    if probes:
        return f"Temps: {', '.join(probes)} | Raw: {data.hex()}"
    else:
        return f"No active probes | Raw: {data.hex()}"

if __name__ == "__main__":
    # Parse arguments
    parser = argparse.ArgumentParser(description="BLE Scanner for Govee H5194")
    parser.add_argument("--quick", "-q", action="store_true", help="Quick 20s scan with device selection")
    parser.add_argument("--direct", "-d", metavar="MAC", help="Direct deep scan of MAC address (prefix match)")
    args = parser.parse_args()
    
    try:
        # Direct mode - skip scan, go straight to deep scan
        if args.direct:
            print(f"🔍 Searching for device matching: {args.direct}")
            print("⏱️  Running 5-second discovery scan...\n")
            
            # Quick 5s scan to find the device
            asyncio.run(scan_continuous(5))
            
            # Find matching device
            matching = [(addr, info) for addr, info in device_tracker.items() 
                       if args.direct.upper() in addr.upper()]
            
            if not matching:
                print(f"❌ No device found matching '{args.direct}'")
                print(f"   Scanned {len(device_tracker)} devices")
                sys.exit(1)
            elif len(matching) > 1:
                print(f"⚠️  Multiple devices match '{args.direct}':")
                for addr, info in matching:
                    print(f"   {addr[:8]}... - {info['name']}")
                print("   Please be more specific")
                sys.exit(1)
            else:
                selected_addr, selected_info = matching[0]
                print(f"✅ Found: {selected_info['name']}")
                print(f"   MAC: {selected_addr[:8]}...")
                print("   Press Ctrl+C to stop\n")
                asyncio.run(deep_scan_device(selected_addr, selected_info))
                sys.exit(0)
        
        # Normal or quick mode
        duration = 20 if args.quick else 60
        asyncio.run(scan_continuous(duration))
        
        # In quick mode, offer interactive device selection for deep scan
        if args.quick and device_tracker:
            print("\n" + "=" * 70)
            print("📋 DEVICE SELECTION - Choose device for deep scan")
            print("=" * 70)
            
            # Show devices sorted by signal strength
            sorted_by_signal = sorted(device_tracker.items(), 
                                     key=lambda x: sum(x[1]["rssi_history"]) / len(x[1]["rssi_history"]), 
                                     reverse=True)
            
            print(f"\n{'#':<3} {'MAC':<10} {'Device Name':<22} {'RSSI':<7} {'Count':<6} {'Mfr ID'}")
            print("-" * 75)
            
            device_list = []
            for idx, (addr, info) in enumerate(sorted_by_signal, 1):
                avg_rssi = sum(info["rssi_history"]) / len(info["rssi_history"])
                mac_short = addr[:8] if len(addr) > 8 else addr  # First 8 chars of MAC/UUID
                name = info["name"][:21] if info["name"] != "Unknown" else "Unknown"
                mfr_ids = ", ".join([str(m) for m in info.get("mfr_ids", [])]) if info.get("mfr_ids") else "-"
                
                # Highlight likely candidates
                marker = ""
                if info.get("mfr_ids") and 27229 in info["mfr_ids"]:
                    marker = "🔥"  # Likely H5194
                elif "Govee" in info["name"] or "GVH" in info["name"]:
                    marker = "🌡️"
                
                print(f"{marker}{idx:<2} {mac_short:<10} {name:<22} {avg_rssi:>6.1f} {info['count']:>5}x {mfr_ids}")
                device_list.append((addr, info))
            
            print("\n💡 TIP: Strongest signal (highest RSSI) = closest device")
            print("🔥 = Likely H5194 (manufacturer ID 27229)")
            print(f"💨 Quick access: python3 scan_h5194.py --direct <MAC>")
            
            # Interactive selection
            try:
                choice = input("\nEnter device number for deep scan (or 'q' to quit): ").strip()
                
                if choice.lower() == 'q':
                    print("Exiting...")
                else:
                    device_num = int(choice)
                    if 1 <= device_num <= len(device_list):
                        selected_addr, selected_info = device_list[device_num - 1]
                        print(f"\n🔍 Starting deep scan of: {selected_info['name']}")
                        print(f"   Address: {selected_addr}")
                        print("   Press Ctrl+C to stop\n")
                        
                        # Start deep scan
                        asyncio.run(deep_scan_device(selected_addr, selected_info))
                    else:
                        print("Invalid device number")
            except ValueError:
                print("Invalid input")
            except KeyboardInterrupt:
                print("\n\nExiting...")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Scan interrupted by user")
        print(f"📊 Tracked {len(device_tracker)} devices before stopping")

async def deep_scan_device(target_addr, device_info):
    """Deep scan of a specific device - shows every broadcast with change detection"""
    previous_data = {}
    change_count = 0
    scan_count = 0
    
    def deep_callback(device, advertisement_data):
        nonlocal change_count, scan_count
        
        if target_addr not in device.address:
            return
        
        scan_count += 1
        
        if not advertisement_data.manufacturer_data:
            print(f"[{scan_count}] No manufacturer data")
            return
        
        for mfr_id, mfr_data in advertisement_data.manufacturer_data.items():
            hex_str = mfr_data.hex()
            
            # Check if data changed
            changed = hex_str != previous_data.get(mfr_id)
            if changed:
                change_count += 1
                previous_data[mfr_id] = hex_str
                marker = "🔥 CHANGED!" if change_count > 1 else "📡 FIRST"
            else:
                marker = "   same   "
            
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print(f"\n{marker} [{timestamp}] Packet #{scan_count} | RSSI: {advertisement_data.rssi} dBm")
            print(f"   Mfr ID: {mfr_id} (0x{mfr_id:04x})")
            print(f"   Hex: {hex_str}")
            print(f"   Changes: {change_count}")
            
            # Try to decode if it looks like H5194
            if mfr_id == 27229 and len(mfr_data) >= 20:
                print(f"   Decoded: {decode_h5194_packet(mfr_data)}")
    
    print("=" * 70)
    print("⏰ Deep scan running - watching for data changes")
    print("💡 Insert/remove probes or change temps to see updates")
    print("=" * 70)
    
    scanner = BleakScanner(deep_callback)
    await scanner.start()
    
    try:
        await asyncio.sleep(120)  # 2 minutes
    except KeyboardInterrupt:
        print("\n\n⚠️  Deep scan stopped")
    finally:
        await scanner.stop()
    
    print(f"\n📊 Received {scan_count} packets, {change_count} changes detected")

def decode_h5194_packet(data):
    """Decode H5194 manufacturer data packet"""
    if len(data) < 20:
        return "Packet too short"
    
    header = data[0]
    flags = data[1:5].hex()
    
    # Look for non-FF probe data
    probes = []
    for i in range(5, len(data) - 3, 4):
        chunk = data[i:i+4]
        if chunk != b'\xff\xff\xff\xff' and chunk != b'\x08\xfc\xff\xff':
            probes.append(f"@{i}:{chunk.hex()}")
    
    if probes:
        return f"Header:{header:02x} Flags:{flags} Probes:[{', '.join(probes)}]"
    else:
        return f"Header:{header:02x} Flags:{flags} No active probes"
