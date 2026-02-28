#!/usr/bin/env python3
"""
Advanced BLE Scanner - Continuous monitoring with detailed decoding
Tracks devices over time, counts appearances, decodes manufacturer data

Quick start:
  python3 scan_h5194.py --usage    # Show comprehensive usage guide
  python3 scan_h5194.py --help     # Show quick argument reference
"""
import asyncio
import argparse
import sys
from bleak import BleakScanner
from datetime import datetime
from collections import defaultdict

USAGE_DOC = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                       BLE SCANNER - USAGE GUIDE                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

OPERATION MODES
───────────────────────────────────────────────────────────────────────────────

1. DEFAULT MODE (60-second scan)
   $ python3 scan_h5194.py
   
   • Scans for 60 seconds
   • Shows device summary table sorted by signal strength
   • Lists all discovered devices with MAC addresses, RSSI, and manufacturer IDs

2. QUICK MODE (20-second scan with interactive menu)
   $ python3 scan_h5194.py --quick
   
   • Faster 20-second scan
   • Interactive device selection menu
   • Choose a device to start deep monitoring

3. DEEP MODE (direct device monitoring)
   $ python3 scan_h5194.py --deep <MAC_or_UUID>
   
   • Skip discovery, go straight to monitoring a specific device
   • Shows every broadcast packet with change detection
   • Useful when you already know the device address
   
   Example:
   $ python3 scan_h5194.py --deep E1CFAB4D

4. LIVE MODE (real-time updating display)
   $ python3 scan_h5194.py --live
   
   • Continuously updating device list
   • Refreshes every second
   • Sorted by signal strength (closest devices at top)
   • Screen clears and updates in place

5. ANALYZE MODE (H5194 packet structure analyzer)
   $ python3 scan_h5194.py --analyze <MAC_or_UUID>
   
   • Decodes H5194 manufacturer packets
   • Shows status byte and two temperature positions per packet
   • Tracks patterns by status byte to identify probe mapping
   • Compare temps to physical setup to figure out which probe is which
   
   Example:
   $ python3 scan_h5194.py --analyze E1CFAB4D

UNIVERSAL OPTIONS
───────────────────────────────────────────────────────────────────────────────

Temperature Decoding (--decode)
   Add to any mode to enable H5194/H5051 temperature decoding:
   
   $ python3 scan_h5194.py --decode                    # Default mode with temps
   $ python3 scan_h5194.py --quick --decode            # Quick mode with temps
   $ python3 scan_h5194.py --deep E1CFAB4D --decode    # Deep mode with temps
   $ python3 scan_h5194.py --live --decode             # Live mode with temps

Logging (--log <filename>)
   Write output to a file:
   
   $ python3 scan_h5194.py --log scan.txt
   $ python3 scan_h5194.py --deep E1CFAB4D --decode --log temps.txt

COMPLETE EXAMPLES
───────────────────────────────────────────────────────────────────────────────

# Quick scan with temperatures displayed
$ python3 scan_h5194.py --quick --decode

# Monitor H5194 thermometer with logging
$ python3 scan_h5194.py --deep E1CFAB4D --decode --log h5194_temps.txt

# Live view of all devices with temperature decoding
$ python3 scan_h5194.py --live --decode

# Default 60s scan with full logging
$ python3 scan_h5194.py --decode --log full_scan.txt

DEVICE IDENTIFICATION
───────────────────────────────────────────────────────────────────────────────

Visual Markers:
   🔥 = H5194 thermometer (mfr ID 27229)
   🌡️ = Govee temp/humidity sensor (mfr ID 60552)
   ❓ = Unknown device with identified manufacturer
   📱 = Generic BLE device

The scanner automatically identifies devices by:
   • Device name (if broadcast)
   • Manufacturer ID (Apple, Govee, Samsung, etc.)
   • Known device patterns (H5194, H5051, etc.)

TEMPERATURE DECODING
───────────────────────────────────────────────────────────────────────────────

H5194 (4-probe meat thermometer)
   • Manufacturer ID: 27229
   • Decodes: P1, P2, P3, P4 temperatures in °F
   • Formula: P1 = byte[6] - 21, P2/3/4 = byte[9/13/17] + 33
   • Shows "No active probes" if sensors unplugged

H5051/H5075 (temp/humidity sensor)
   • Manufacturer ID: 60552
   • Decodes: Temperature (°F/°C), Humidity (%), Battery (%)
   • Format: bytes[2:4]=temp, bytes[4:6]=humidity (big-endian)

TIPS
───────────────────────────────────────────────────────────────────────────────

• Strongest signal = closest device
  RSSI values show signal strength (-30 is very close, -90 is far)

• Quick mode is best for discovery
  Interactive menu makes it easy to explore unknown devices

• Deep mode for monitoring
  Watch a specific device's broadcasts in real-time

• Live mode for tracking
  See which devices are nearby and how signal changes as you move

• Decoding is opt-in
  Use --decode only when you need temperatures to reduce clutter

• Logging captures everything
  Logs include timestamps and all decoded data

Press Ctrl+C to stop any scan mode gracefully.
"""

# Device tracking
device_tracker = defaultdict(lambda: {"count": 0, "last_seen": None, "rssi_history": [], "name": "Unknown"})

# Global flag to control detection_callback verbosity
silent_mode = False

def identify_manufacturer(mfr_id):
    """Identify manufacturer by company ID"""
    # Known manufacturer IDs from Bluetooth SIG
    manufacturers = {
        76: "Apple",
        6: "Microsoft",
        27229: "Govee (H5194)",
        60552: "Govee (H5051/H5075)",
        89: "Qualcomm",
        117: "Samsung",
        224: "Google",
        741: "Sonos",
        1452: "Roku",
        171: "Fitbit",
        2456: "Amazon (Echo)",
    }
    return manufacturers.get(mfr_id, f"Unknown (0x{mfr_id:04x})")

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
    
    # H5194 (company ID 27229)
    elif mfr_id == 27229:
        return f"Govee H5194 thermometer: {hex_str[:20]}..."
    
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
    
    # Determine device marker and improve name identification
    if "Govee" in name or "GVH" in name:
        marker = "🌡️ GOVEE"
    elif "H5194" in name or "5D6AD5" in name:
        marker = "🔥 H5194 FOUND!"
    elif "Unknown" == name and advertisement_data.manufacturer_data:
        # Try to identify by manufacturer ID
        for mfr_id in advertisement_data.manufacturer_data.keys():
            identified = identify_manufacturer(mfr_id)
            if "Unknown" not in identified:
                marker = f"❓ {identified}"
                name = identified  # Update display name
                tracker["name"] = name  # Store better name
                break
        else:
            marker = "❓"
    else:
        marker = "📱"
    
    # Print real-time update (only if not in silent mode)
    if not silent_mode:
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

async def scan_continuous(duration=60, decode_temps=False):
    """Run continuous scan for specified duration with device summary
    
    Args:
        duration: Scan duration in seconds (default 60)
        decode_temps: If True, decode H5194/H5051 temperatures
    """
    print(f"🔍 Starting continuous BLE scan for {duration} seconds...")
    print(f"⏰ Started at {datetime.now().strftime('%H:%M:%S')}")
    print(f"🎯 Looking for H5194 (GVH5194_5D6AD5) and other Govee devices")
    if decode_temps:
        print("🌡️  Temperature decoding: ENABLED")
    print("=" * 70)
    
    scanner = BleakScanner(detection_callback)
    await scanner.start()
    await asyncio.sleep(duration)
    await scanner.stop()
    
    # Summary table
    print("\n" + "=" * 90)
    print(f"📊 SCAN SUMMARY - Found {len(device_tracker)} unique devices")
    print("=" * 90)
    
    # Sort by signal strength (strongest first)
    sorted_devices = sorted(
        device_tracker.items(), 
        key=lambda x: sum(x[1]["rssi_history"]) / len(x[1]["rssi_history"]), 
        reverse=True
    )
    
    # Table header
    if decode_temps:
        print(f"\n{'MAC/UUID':<12} {'Device Name':<22} {'RSSI':>6} {'Count':>5} {'Decoded Data'}")
    else:
        print(f"\n{'MAC/UUID':<12} {'Device Name':<22} {'RSSI':>6} {'Count':>5} {'Mfr ID'}")
    print("-" * 90)
    
    # Device rows
    for addr, info in sorted_devices:
        avg_rssi = sum(info["rssi_history"]) / len(info["rssi_history"])
        mac_short = addr[:10] if len(addr) > 10 else addr
        name = info["name"][:21] if info["name"] != "Unknown" else "Unknown"
        
        # Marker for device type
        marker = ""
        if info.get("mfr_ids") and 27229 in info["mfr_ids"]:
            marker = "🔥"  # H5194
        elif "Govee" in info["name"] or "GVH" in info["name"]:
            marker = "🌡️"
        
        if decode_temps and info.get("mfr_data_sample"):
            # Show decoded temperature if available
            decoded_str = ""
            for mfr_id, hex_data in info["mfr_data_sample"].items():
                if mfr_id == 60552:  # Govee H5051
                    data = bytes.fromhex(hex_data)
                    decoded = decode_manufacturer_data(mfr_id, data)
                    decoded_str = decoded if decoded else hex_data[:20]
                    break
                elif mfr_id == 27229:  # H5194
                    data = bytes.fromhex(hex_data)
                    decoded_str = decode_h5194_packet(data)
                    break
            print(f"{marker}{mac_short:<11} {name:<22} {avg_rssi:>6.1f} {info['count']:>4}x {decoded_str}")
        else:
            # Show manufacturer ID
            mfr_str = ", ".join([str(m) for m in info.get("mfr_ids", [])]) if info.get("mfr_ids") else "-"
            print(f"{marker}{mac_short:<11} {name:<22} {avg_rssi:>6.1f} {info['count']:>4}x {mfr_str}")
    
    print("\n💡 TIP: Use --quick for interactive device selection")
    print("💡 TIP: Use --deep <MAC> to monitor a specific device")
    print("💡 TIP: Use --live for real-time updating display")
    print(f"💡 TIP: Add --decode to show temperature readings")

async def live_monitor(decode_temps=False, log_file=None):
    """Live-updating device list sorted by RSSI - updates in place
    
    Args:
        decode_temps: If True, decode H5194/H5051 temperatures
        log_file: Optional file handle for logging output
    """
    global silent_mode
    import sys
    
    # Enable silent mode to suppress detection_callback prints
    silent_mode = True
    
    # Start scanner
    scanner = BleakScanner(detection_callback)
    await scanner.start()
    
    print("📡 LIVE BLE DEVICE MONITOR")
    print("Updates every 2 seconds | Press Ctrl+C to stop\n")
    
    first_run = True
    
    try:
        while True:
            await asyncio.sleep(2)  # Update every 2 seconds
            
            # Move cursor to beginning of table (but not the header)
            if not first_run:
                # Move cursor up to redraw table
                sys.stdout.write('\033[F' * 15)  # Move up 15 lines to redraw table
            first_run = False
            
            # Sort by average RSSI (strongest first)
            sorted_devices = sorted(
                device_tracker.items(),
                key=lambda x: sum(x[1]["rssi_history"]) / len(x[1]["rssi_history"]) if x[1]["rssi_history"] else -999,
                reverse=True
            )
            
            # Header line
            header = f"⏰ {datetime.now().strftime('%H:%M:%S')} | {len(device_tracker)} devices | 🔥=H5194 🌡️=Govee"
            print(f"{header:<90}")
            print("=" * 90)
            
            # Table header
            if decode_temps:
                print(f"{'MAC/UUID':<12} {'Device Name':<22} {'RSSI':>6} {'Count':>5} {'Decoded Data':<30}")
            else:
                print(f"{'MAC/UUID':<12} {'Device Name':<22} {'RSSI':>6} {'Count':>5} {'Mfr ID':<8}")
            print("-" * 90)
            
            # Device rows (top 10, pad to 10 rows for consistent height)
            for i in range(10):
                if i < len(sorted_devices):
                    addr, info = sorted_devices[i]
                    avg_rssi = sum(info["rssi_history"]) / len(info["rssi_history"]) if info["rssi_history"] else -999
                    mac_short = addr[:10] if len(addr) > 10 else addr
                    name = info["name"][:21] if info["name"] != "Unknown" else "Unknown"
                    
                    # Marker for device type
                    marker = ""
                    if info.get("mfr_ids") and 27229 in info["mfr_ids"]:
                        marker = "🔥"  # H5194
                    elif "Govee" in info["name"] or "GVH" in info["name"]:
                        marker = "🌡️"
                    
                    if decode_temps and info.get("mfr_data_sample"):
                        # Show decoded temperature if available
                        decoded_str = ""
                        for mfr_id, hex_data in info["mfr_data_sample"].items():
                            if mfr_id == 60552:  # Govee H5051
                                data = bytes.fromhex(hex_data)
                                decoded = decode_manufacturer_data(mfr_id, data)
                                decoded_str = decoded[:30] if decoded else hex_data[:20]
                                break
                            elif mfr_id == 27229:  # H5194
                                data = bytes.fromhex(hex_data)
                                decoded_str = decode_h5194_packet(data)[:30]
                                break
                        print(f"{marker}{mac_short:<11} {name:<22} {avg_rssi:>6.1f} {info['count']:>4}x {decoded_str:<30}")
                    else:
                        # Show manufacturer ID
                        mfr_str = ", ".join([str(m) for m in info.get("mfr_ids", [])]) if info.get("mfr_ids") else "-"
                        print(f"{marker}{mac_short:<11} {name:<22} {avg_rssi:>6.1f} {info['count']:>4}x {mfr_str:<8}")
                else:
                    # Empty row to maintain consistent height
                    print(" " * 90)
            
            sys.stdout.flush()
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Live monitor stopped")
    finally:
        silent_mode = False  # Restore verbose mode
        await scanner.stop()
        print(f"📊 Tracked {len(device_tracker)} devices total")

async def deep_scan_device(target_addr, device_info, decode_temps=False, log_file=None):
    """Monitor a specific device in detail with change detection"""
    previous_data = {}
    change_count = 0
    scan_count = 0
    
    def log_print(msg):
        """Print and optionally log message"""
        print(msg)
        if log_file:
            log_file.write(msg + '\n')
    
    def deep_callback(device, advertisement_data):
        nonlocal change_count, scan_count
        
        if target_addr not in device.address:
            return
        
        scan_count += 1
        
        if not advertisement_data.manufacturer_data:
            log_print(f"[{scan_count}] No manufacturer data")
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
            log_print(f"\n{marker} [{timestamp}] Packet #{scan_count} | RSSI: {advertisement_data.rssi} dBm")
            log_print(f"   Mfr ID: {mfr_id} (0x{mfr_id:04x})")
            log_print(f"   Hex: {hex_str}")
            
            # Decode temperatures if requested
            if decode_temps and mfr_id == 27229 and len(mfr_data) >= 20:
                decoded = decode_h5194_packet(mfr_data)
                log_print(f"   🌡️  {decoded}")
            
            log_print(f"   Changes: {change_count}")
    
    log_print("=" * 70)
    log_print("⏰ Deep scan running - watching for data changes")
    log_print("💡 Insert/remove probes or change temps to see updates")
    log_print("=" * 70)
    
    scanner = BleakScanner(deep_callback)
    await scanner.start()
    
    try:
        await asyncio.sleep(120)  # 2 minutes
    except KeyboardInterrupt:
        log_print("\n\n⚠️  Deep scan stopped")
    finally:
        await scanner.stop()
    
    log_print(f"\n📊 Received {scan_count} packets, {change_count} changes detected")


def decode_h5194_packet(data):
    """Simple H5194 packet decoder for backward compatibility
    
    Shows status byte and two temperature positions.
    """
    if len(data) < 10:
        return "Packet too short"
    
    status = data[7]
    
    # Position 1: bytes 8-9 (Celsius * 100)
    pos1_str = "---"
    if len(data) > 9:
        temp_raw = int.from_bytes(data[8:10], 'big')
        if temp_raw != 0xffff and temp_raw > 0:
            temp_c = temp_raw / 100.0
            temp_f = (temp_c * 9/5) + 32
            pos1_str = f"{temp_f:.0f}°F"
    
    # Position 2: byte 6 (direct Fahrenheit)
    pos2_str = "---"
    if data[6] not in [0xff, 0xfc, 0x08, 0x00]:
        temp_f = data[6] - 24
        pos2_str = f"{temp_f}°F"
    
    return f"Status:0x{status:02x} Pos1:{pos1_str} Pos2:{pos2_str}"


async def packet_analyzer(target_addr):
    """Simple H5194 packet analyzer - shows all 4 probes"""
    packet_count = 0
    probes = {'P1': '---', 'P2': '---', 'P3': '---', 'P4': '---'}
    
    def analyzer_callback(device, advertisement_data):
        nonlocal packet_count
        
        if target_addr.upper() not in device.address.upper():
            return
        
        if packet_count == 0:
            print(f"✅ Found device! Address: {device.address}\n")
        
        mfr_data = advertisement_data.manufacturer_data
        if not mfr_data or 27229 not in mfr_data:
            return
        
        data = mfr_data[27229]
        if len(data) < 10:
            return
        
        packet_count += 1
        status = data[7]
        
        # Decode temps from packet
        temp1 = None
        if len(data) > 9:
            raw = int.from_bytes(data[8:10], 'big')
            if raw != 0xffff and raw > 0:
                temp1 = int((raw / 100.0) * 9/5 + 32)
        
        temp2 = None
        if data[6] not in [0xff, 0xfc, 0x08, 0x00]:
            temp2 = data[6] - 24
        
        # Map status byte to probe numbers
        if status == 0x04:
            if temp1: probes['P1'] = f"{temp1}°F"
            if temp2: probes['P2'] = f"{temp2}°F"
        elif status == 0x84:
            if temp1: probes['P3'] = f"{temp1}°F"
            if temp2: probes['P2'] = f"{temp2}°F"
        elif status == 0x0c:
            if temp1: probes['P2'] = f"{temp1}°F"
            if temp2: probes['P4'] = f"{temp2}°F"
        elif status == 0x8c:
            if temp1: probes['P4'] = f"{temp1}°F"
        
        # Fast display - single print with cursor positioning
        print(f"\033[H\033[J{'='*40}\n🔥 H5194 | Packets: {packet_count}\n{'='*40}\n\n  P1: {probes['P1']}\n  P2: {probes['P2']}\n  P3: {probes['P3']}\n  P4: {probes['P4']}\n\n  Status: 0x{status:02x}\n\nPress Ctrl+C to stop", flush=True)
    
    print("🔍 Starting BLE scanner...")
    print(f"   Looking for device: {target_addr}")
    print("   Waiting for H5194 packets (mfr ID 27229)...")
    print("   This may take a few seconds...\n")
    
    scanner = BleakScanner(analyzer_callback)
    await scanner.start()
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Analyzer stopped")
    finally:
        await scanner.stop()
        
        # Final summary
        print("\n" + "=" * 80)
        print("FINAL SUMMARY")
        print("=" * 80)
        for st in sorted(status_readings.keys()):
            sr = status_readings[st]
            print(f"\nStatus 0x{st:02x} (seen {sr['count']}x):")
            print(f"  Position 1 temps: {sorted(sr['pos1']) if sr['pos1'] else '(none)'}")
            print(f"  Position 2 temps: {sorted(sr['pos2']) if sr['pos2'] else '(none)'}")
            print(f"  Last packet: {sr['last_hex']}")


if __name__ == "__main__":
    # Parse arguments
    parser = argparse.ArgumentParser(description="BLE Scanner for Govee devices")
    
    # Help/documentation
    parser.add_argument("--usage", action="store_true", help="Show comprehensive usage guide")
    
    # Modes (mutually exclusive)
    parser.add_argument("--quick", "-q", action="store_true", help="Quick 20s scan with interactive menu")
    parser.add_argument("--deep", "-d", metavar="MAC", help="Deep monitor specific device (no discovery)")
    parser.add_argument("--live", "-l", action="store_true", help="Live-updating device list sorted by RSSI")
    parser.add_argument("--analyze", "-a", metavar="MAC", help="Analyze H5194 packet structure (figure out probe mapping)")
    
    # Options (work with any mode)
    parser.add_argument("--decode", action="store_true", help="Enable H5194/H5051 temperature decoding")
    parser.add_argument("--log", metavar="FILE", help="Write output to log file")
    
    args = parser.parse_args()
    
    # Handle --usage flag
    if args.usage:
        print(USAGE_DOC)
        sys.exit(0)
    
    # Setup logging if requested
    log_file = None
    if args.log:
        log_file = open(args.log, 'w', buffering=1)  # Line buffered
        print(f"📝 Logging to: {args.log}")
    
    try:
        # Mode: Deep monitor (skip discovery, go straight to monitoring)
        if args.deep:
            print(f"🔍 Deep monitoring: {args.deep}")
            if args.decode:
                print("🌡️  Temperature decoding: ENABLED")
            print("   Press Ctrl+C to stop\n")
            device_info = {"name": "Unknown", "count": 0, "rssi_history": []}
            asyncio.run(deep_scan_device(args.deep, device_info, decode_temps=args.decode, log_file=log_file))
            sys.exit(0)
        
        # Mode: Packet analyzer (figure out probe mapping)
        if args.analyze:
            print(f"🔥 H5194 Packet Analyzer")
            print(f"   Target device: {args.analyze}")
            print(f"   Compare temps to your physical setup to identify probe numbers")
            print(f"   Press Ctrl+C to stop\n")
            asyncio.run(packet_analyzer(args.analyze))
            sys.exit(0)
        
        # Mode: Live-updating device list
        if args.live:
            print("📡 Live device monitor - sorted by RSSI (Press Ctrl+C to stop)\n")
            asyncio.run(live_monitor(decode_temps=args.decode, log_file=log_file))
            sys.exit(0)
        
        # Normal or quick mode
        duration = 20 if args.quick else 60
        asyncio.run(scan_continuous(duration, decode_temps=args.decode))
        
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
            print(f"💨 Quick access: python3 scan_h5194.py --deep <MAC>")
            if args.decode:
                print("🌡️  Temperature decoding will be active for deep scan")
            
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
                        if args.decode:
                            print("🌡️  Temperature decoding: ENABLED")
                        print("   Press Ctrl+C to stop\n")
                        
                        # Start deep scan (respect --decode flag)
                        asyncio.run(deep_scan_device(selected_addr, selected_info, decode_temps=args.decode, log_file=log_file))
                    else:
                        print("Invalid device number")
            except ValueError:
                print("Invalid input")
            except KeyboardInterrupt:
                print("\n\nExiting...")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Scan interrupted by user")
        print(f"📊 Tracked {len(device_tracker)} devices before stopping")
    finally:
        if log_file:
            log_file.close()
            print(f"📝 Log saved to: {args.log}")
