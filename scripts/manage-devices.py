#!/usr/bin/env python3
"""
Device Override Management Tool
Manages local device name/room overrides for govee2mqtt devices.
"""

import json
import os
import re
import sys
import urllib.request
import tempfile
from typing import Dict, List, Optional, Tuple


# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
OVERRIDE_FILE = os.path.join(REPO_ROOT, "telegraf", "conf.d", "device-overrides.json")
API_URL = "http://localhost:8056/api/devices"
API_TIMEOUT = 5


# ============================================================================
# Core Functions
# ============================================================================

def normalize_mac(mac_str: str) -> str:
    """Strip colons and uppercase MAC address."""
    return mac_str.replace(":", "").upper()


def get_mac_suffix(mac_str: str, length: int = 12) -> str:
    """Get last N characters of normalized MAC (for ble_decoder matching)."""
    normalized = normalize_mac(mac_str)
    return normalized[-length:]


def get_override_path() -> str:
    """Get path to override file."""
    return OVERRIDE_FILE


def load_overrides() -> Dict[str, Dict]:
    """Load device overrides from JSON file, create empty if missing."""
    override_path = get_override_path()
    
    # Create directory if needed
    os.makedirs(os.path.dirname(override_path), exist_ok=True)
    
    # Create empty file if missing
    if not os.path.exists(override_path):
        with open(override_path, 'w') as f:
            json.dump({}, f, indent=2)
        return {}
    
    # Load existing file
    try:
        with open(override_path, 'r') as f:
            data = json.load(f)
        # Filter out comment keys
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception as e:
        print(f"Error loading overrides: {e}", file=sys.stderr)
        return {}


def save_overrides(data: Dict[str, Dict]) -> bool:
    """Save device overrides to JSON file atomically."""
    override_path = get_override_path()
    
    try:
        # Write to temp file first
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(override_path), text=True)
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)
        
        # Atomic rename
        os.rename(temp_path, override_path)
        return True
    except Exception as e:
        print(f"Error saving overrides: {e}", file=sys.stderr)
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        return False


def load_api_devices() -> Optional[List[Dict]]:
    """Fetch devices from govee2mqtt API with timeout."""
    try:
        resp = urllib.request.urlopen(API_URL, timeout=API_TIMEOUT)
        devices = json.loads(resp.read())
        return devices if devices else None
    except Exception as e:
        print(f"API fetch failed: {e}", file=sys.stderr)
        return None


def merge_devices(api_data: Optional[List[Dict]], overrides: Dict[str, Dict]) -> List[Dict]:
    """
    Merge API data with local overrides.
    Override takes precedence for name/room.
    Returns list of device dicts with 'mac', 'name', 'room', 'sku', 'has_override' fields.
    """
    devices = []
    seen_macs = set()
    
    # Start with API devices
    if api_data:
        for d in api_data:
            mac = normalize_mac(d["id"])
            seen_macs.add(mac)
            
            device = {
                "mac": mac,
                "name": d["name"].lower().replace(" ", "_"),
                "room": (d.get("room") or "unassigned").lower().replace(" ", "_"),
                "sku": d.get("sku", "unknown"),
                "has_override": False
            }
            
            # Apply override if exists
            if mac in overrides:
                override = overrides[mac]
                if "name" in override:
                    device["name"] = override["name"]
                if "room" in override:
                    device["room"] = override["room"]
                if "sku" in override:
                    device["sku"] = override["sku"]
                device["has_override"] = True
            
            devices.append(device)
    
    # Add override-only devices (not in API)
    for mac, override in overrides.items():
        if mac not in seen_macs and "name" in override:
            devices.append({
                "mac": mac,
                "name": override["name"],
                "room": override.get("room", "unassigned"),
                "sku": override.get("sku", "unknown"),
                "has_override": True
            })
    
    return devices


def validate_device_name(name: str, all_devices: List[Dict], exclude_mac: Optional[str] = None) -> Tuple[bool, str]:
    """
    Validate device name against rules.
    Returns (valid: bool, error_msg: str).
    """
    # Length check
    if len(name) < 3:
        return (False, "Name too short (minimum 3 characters)")
    if len(name) > 50:
        return (False, "Name too long (maximum 50 characters)")
    
    # Character check
    if not re.match(r'^[a-z0-9_]+$', name):
        return (False, "Name must be lowercase letters, numbers, and underscores only")
    
    # Leading/trailing underscore check
    if name.startswith('_') or name.endswith('_'):
        return (False, "Name cannot start or end with underscore")
    
    # Check for bad name patterns (auto-generated garbage)
    bad_patterns = [
        r'^h\d{4}_[a-f0-9]{3,}$',  # h5075_5a9
        r'^(sensor|device)_[a-f0-9]+$',  # sensor_abc123
    ]
    for pattern in bad_patterns:
        if re.match(pattern, name):
            return (False, "Name appears auto-generated (avoid patterns like 'h5075_abc')")
    
    # Duplicate check
    for device in all_devices:
        if device["mac"] != exclude_mac and device["name"] == name:
            return (False, f"Name '{name}' already in use by {device['mac'][:12]}...")
    
    return (True, "")


def detect_bad_names(devices: List[Dict]) -> List[Dict]:
    """
    Detect devices with questionable auto-generated names.
    Returns list of devices that should probably be renamed.
    """
    bad_devices = []
    
    for device in devices:
        name = device["name"]
        
        # Pattern 1: Model + hex suffix (e.g., h5075_5a9)
        if re.match(r'^h\d{4}_[a-f0-9]{3,}$', name):
            bad_devices.append(device)
            continue
        
        # Pattern 2: Generic prefix + hex (e.g., sensor_abc123)
        if re.match(r'^(sensor|device)_[a-f0-9]+$', name):
            bad_devices.append(device)
            continue
        
        # Pattern 3: Short name with digits (likely auto-generated)
        if len(name) < 8 and re.search(r'\d', name):
            bad_devices.append(device)
            continue
        
        # Pattern 4: Contains 3+ consecutive hex chars
        if re.search(r'[a-f0-9]{3,}', name):
            bad_devices.append(device)
            continue
    
    return bad_devices


# ============================================================================
# Interactive UI Functions
# ============================================================================

def show_device_list(devices: List[Dict], verbose: bool = False) -> None:
    """Pretty-print device list."""
    if not devices:
        print("No devices found.")
        return
    
    # Header
    print("\nDevices:")
    print("=" * 80)
    
    for i, device in enumerate(devices, 1):
        mac_display = device["mac"][:12] + "..." if len(device["mac"]) > 12 else device["mac"]
        override_marker = " [OVERRIDE]" if device["has_override"] else ""
        
        print(f"[{i}] MAC: {mac_display} | Name: {device['name']} | "
              f"Room: {device['room']} | SKU: {device['sku']}{override_marker}")
    
    print("=" * 80)
    print()


def interactive_select_device(devices: List[Dict], allow_none: bool = True) -> Optional[Dict]:
    """
    Display numbered device list and prompt for selection.
    Returns selected device dict or None if cancelled.
    """
    if not devices:
        print("No devices available.")
        return None
    
    show_device_list(devices)
    
    if allow_none:
        print("[0] Cancel")
    
    while True:
        try:
            choice = input("\nSelect device number: ").strip()
            if not choice:
                continue
            
            num = int(choice)
            
            if num == 0 and allow_none:
                return None
            
            if 1 <= num <= len(devices):
                return devices[num - 1]
            
            print(f"Invalid selection. Please choose 1-{len(devices)}" + 
                  (" or 0 to cancel" if allow_none else ""))
        
        except ValueError:
            print("Please enter a number")
        except KeyboardInterrupt:
            print("\nCancelled")
            return None


def interactive_rename(device: Dict, all_devices: List[Dict]) -> bool:
    """
    Interactive rename prompt for a device.
    Returns True if override was saved, False if cancelled.
    """
    print(f"\nRenaming device:")
    print(f"  MAC: {device['mac']}")
    print(f"  Current name: {device['name']}")
    print(f"  Current room: {device['room']}")
    print(f"  SKU: {device['sku']}")
    print()
    
    # Get new name
    while True:
        try:
            new_name = input("Enter new name (or 'cancel' to abort): ").strip()
            
            if new_name.lower() in ['cancel', 'q', 'quit', '']:
                print("Cancelled")
                return False
            
            # Validate
            valid, error_msg = validate_device_name(new_name, all_devices, exclude_mac=device['mac'])
            if not valid:
                print(f"❌ {error_msg}")
                continue
            
            break
        
        except KeyboardInterrupt:
            print("\nCancelled")
            return False
    
    # Prompt for room change
    try:
        change_room = input(f"\nAlso change room? Current: '{device['room']}' [y/N]: ").strip().lower()
        new_room = None
        
        if change_room in ['y', 'yes']:
            new_room = input("Enter new room name: ").strip().lower().replace(" ", "_")
            if not new_room:
                new_room = None
    
    except KeyboardInterrupt:
        print("\nCancelled")
        return False
    
    # Load current overrides
    overrides = load_overrides()
    
    # Create/update override entry
    mac = device['mac']
    if mac not in overrides:
        overrides[mac] = {}
    
    overrides[mac]['name'] = new_name
    if new_room:
        overrides[mac]['room'] = new_room
    
    # Optionally store SKU for offline mode
    if device['sku'] != 'unknown':
        overrides[mac]['sku'] = device['sku']
    
    # Save
    if save_overrides(overrides):
        print(f"\n✓ Override saved: {device['name']} → {new_name}")
        if new_room:
            print(f"✓ Room updated: {device['room']} → {new_room}")
        return True
    else:
        print("\n❌ Failed to save override")
        return False


def interactive_set_room(device: Dict) -> bool:
    """Interactive room change for a device."""
    print(f"\nChanging room for device:")
    print(f"  MAC: {device['mac']}")
    print(f"  Name: {device['name']}")
    print(f"  Current room: {device['room']}")
    print()
    
    try:
        new_room = input("Enter new room name (or 'cancel' to abort): ").strip()
        
        if new_room.lower() in ['cancel', 'q', 'quit', '']:
            print("Cancelled")
            return False
        
        # Normalize room name
        new_room = new_room.lower().replace(" ", "_")
        
        # Load current overrides
        overrides = load_overrides()
        
        # Create/update override entry
        mac = device['mac']
        if mac not in overrides:
            overrides[mac] = {}
        
        overrides[mac]['room'] = new_room
        
        # Preserve name override if exists
        if device['has_override'] and 'name' not in overrides[mac]:
            overrides[mac]['name'] = device['name']
        
        # Save
        if save_overrides(overrides):
            print(f"\n✓ Room updated: {device['room']} → {new_room}")
            return True
        else:
            print("\n❌ Failed to save override")
            return False
    
    except KeyboardInterrupt:
        print("\nCancelled")
        return False


def interactive_clear_override(device: Dict) -> bool:
    """Interactive override removal for a device."""
    if not device['has_override']:
        print(f"\nDevice '{device['name']}' has no override to clear.")
        return False
    
    print(f"\nClearing override for device:")
    print(f"  MAC: {device['mac']}")
    print(f"  Current name: {device['name']}")
    print(f"  Current room: {device['room']}")
    print()
    
    try:
        confirm = input("Are you sure? This will revert to API name/room [y/N]: ").strip().lower()
        
        if confirm not in ['y', 'yes']:
            print("Cancelled")
            return False
        
        # Load current overrides
        overrides = load_overrides()
        
        # Remove override
        mac = device['mac']
        if mac in overrides:
            del overrides[mac]
        
        # Save
        if save_overrides(overrides):
            print(f"\n✓ Override cleared for {device['name']}")
            return True
        else:
            print("\n❌ Failed to save changes")
            return False
    
    except KeyboardInterrupt:
        print("\nCancelled")
        return False


# ============================================================================
# CLI Commands
# ============================================================================

def cmd_list(args):
    """List all devices with override indicators."""
    api_data = load_api_devices()
    overrides = load_overrides()
    devices = merge_devices(api_data, overrides)
    
    if not api_data:
        print("⚠ API offline - showing override-only devices", file=sys.stderr)
    
    show_device_list(devices, verbose=True)
    
    # Summary
    override_count = sum(1 for d in devices if d['has_override'])
    print(f"Total devices: {len(devices)}")
    print(f"Overrides: {override_count}")


def cmd_rename(args):
    """Interactive device rename."""
    api_data = load_api_devices()
    overrides = load_overrides()
    devices = merge_devices(api_data, overrides)
    
    if not devices:
        print("No devices found. Is govee2mqtt running?")
        return 1
    
    if not api_data:
        print("⚠ API offline - can only rename existing overrides\n", file=sys.stderr)
    
    device = interactive_select_device(devices)
    if not device:
        return 0
    
    success = interactive_rename(device, devices)
    return 0 if success else 1


def cmd_set_room(args):
    """Interactive room change."""
    api_data = load_api_devices()
    overrides = load_overrides()
    devices = merge_devices(api_data, overrides)
    
    if not devices:
        print("No devices found. Is govee2mqtt running?")
        return 1
    
    device = interactive_select_device(devices)
    if not device:
        return 0
    
    success = interactive_set_room(device)
    return 0 if success else 1


def cmd_clear_override(args):
    """Interactive override removal."""
    api_data = load_api_devices()
    overrides = load_overrides()
    devices = merge_devices(api_data, overrides)
    
    # Filter to only devices with overrides
    override_devices = [d for d in devices if d['has_override']]
    
    if not override_devices:
        print("No devices with overrides found.")
        return 0
    
    print("Devices with overrides:")
    device = interactive_select_device(override_devices)
    if not device:
        return 0
    
    success = interactive_clear_override(device)
    return 0 if success else 1


def cmd_check_bad(args):
    """Detect and list devices with bad names."""
    api_data = load_api_devices()
    overrides = load_overrides()
    devices = merge_devices(api_data, overrides)
    
    bad_devices = detect_bad_names(devices)
    
    if not bad_devices:
        print("No devices with questionable names detected.", file=sys.stderr)
        return 0
    
    print(f"Found {len(bad_devices)} device(s) with questionable names:", file=sys.stderr)
    for device in bad_devices:
        print(json.dumps(device))
    
    return 0


def cmd_merge(args):
    """Merge API data with overrides and output JSON (for update-device-map.sh)."""
    api_data = load_api_devices()
    overrides = load_overrides()
    devices = merge_devices(api_data, overrides)
    
    if not devices:
        print("[]")
        return 1
    
    # Convert back to API format for compatibility with update-device-map.sh
    output = []
    for device in devices:
        # Format MAC with colons for output compatibility
        mac_with_colons = ":".join([device["mac"][i:i+2] for i in range(0, len(device["mac"]), 2)])
        
        output.append({
            "id": mac_with_colons,
            "name": device["name"],
            "room": device["room"],
            "sku": device["sku"]
        })
    
    # Output JSON to stdout (for shell consumption)
    print(json.dumps(output))
    
    # Progress to stderr
    override_count = sum(1 for d in devices if d['has_override'])
    if override_count > 0:
        print(f"Applied {override_count} override(s)", file=sys.stderr)
    
    return 0


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: manage-devices.py <command>")
        print("\nCommands:")
        print("  list              - List all devices with override indicators")
        print("  rename            - Interactive device rename")
        print("  set-room          - Interactive room change")
        print("  clear-override    - Remove local override for a device")
        print("  check-bad         - Detect devices with questionable names")
        print("  merge             - Merge API data with overrides (JSON output)")
        return 1
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    commands = {
        'list': cmd_list,
        'rename': cmd_rename,
        'set-room': cmd_set_room,
        'clear-override': cmd_clear_override,
        'check-bad': cmd_check_bad,
        'merge': cmd_merge,
    }
    
    if command not in commands:
        print(f"Unknown command: {command}")
        return 1
    
    try:
        return commands[command](args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
