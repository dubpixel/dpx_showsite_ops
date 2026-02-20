#!/usr/bin/env python3
"""
Device Override Management Tool
Manages local device name/room overrides for govee2mqtt devices.
"""

import csv
import json
import os
import re
import subprocess
import sys
import urllib.request
import tempfile
from typing import Dict, List, Optional, Tuple


# Version
VERSION = "1.1.0"  # Added delete-device-data command

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
OVERRIDE_FILE = os.path.join(REPO_ROOT, "telegraf", "conf.d", "device-overrides.json")
API_URL = "http://localhost:8056/api/devices"
API_TIMEOUT = 5


# ============================================================================
# Core Functions
# ============================================================================

def get_env_value(key: str, default: Optional[str] = None) -> str:
    """Read value from .env file with fallback to default."""
    env_file = os.path.join(REPO_ROOT, ".env")
    
    if not os.path.exists(env_file):
        return default
    
    try:
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('#') or '=' not in line:
                    continue
                
                if line.startswith(f"{key}="):
                    value = line.split('=', 1)[1]
                    # Strip quotes if present
                    value = value.strip('"\'')
                    return value
    except Exception as e:
        print(f"Warning: Error reading .env file: {e}", file=sys.stderr)
    
    return default


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
        
        # Set readable permissions for Docker container
        os.chmod(override_path, 0o644)
        
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
            mac = get_mac_suffix(d["id"], 12)  # Use last 12 chars to match ble_decoder
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


def query_device_name_history(mac_suffix: str) -> List[Dict]:
    """
    Query InfluxDB for all historical device_name values for a given MAC.
    Returns list of dicts with device_name, source, count, first_seen, last_seen.
    """
    token = get_env_value("INFLUX_TOKEN", "my-super-secret-token")
    org = get_env_value("INFLUX_ORG", "home")
    bucket = get_env_value("INFLUX_BUCKET", "sensors")
    
    debug = os.getenv("DEBUG_DEVICE_DELETE", "").lower() in ["1", "true", "yes"]
    
    results = []
    
    # Query both sources together to get all device_name values
    flux_query = f'''
from(bucket: "{bucket}")
  |> range(start: 1970-01-01T00:00:00Z)
  |> filter(fn: (r) => r["_measurement"] == "mqtt_consumer")
  |> filter(fn: (r) => r["z_device_id"] =~ /{mac_suffix}$/)
  |> filter(fn: (r) => exists r.device_name)
  |> keep(columns: ["_time", "device_name", "room", "source", "z_device_id"])
'''
    
    try:
        cmd = [
            "docker", "exec", "influxdb", "influx", "query",
            "--org", org,
            "--token", token,
            "--raw", flux_query
        ]
        
        if debug:
            print(f"\nDEBUG: Running query for MAC suffix: {mac_suffix}", file=sys.stderr)
            print(f"DEBUG: Full MAC regex pattern: /{mac_suffix}$/", file=sys.stderr)
            print(f"DEBUG: Query:\n{flux_query}", file=sys.stderr)
            print(f"DEBUG: Command: {' '.join(cmd[:7])} ...", file=sys.stderr)
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f"Error: Query failed: {result.stderr}", file=sys.stderr)
            if debug:
                print(f"DEBUG: stdout: {result.stdout}", file=sys.stderr)
            return []
        
        if debug:
            print(f"DEBUG: Query returned {len(result.stdout)} bytes", file=sys.stderr)
            print(f"DEBUG: First 1000 chars of output:", file=sys.stderr)
            print(result.stdout[:1000], file=sys.stderr)
            print(f"DEBUG: Output line count: {len(result.stdout.splitlines())}", file=sys.stderr)
        
        # Parse CSV output
        lines = result.stdout.strip().split('\n')
        if len(lines) < 2:
            if debug:
                print(f"DEBUG: No data rows found (only {len(lines)} lines)", file=sys.stderr)
            return []
        
        # Group by device_name and source
        device_data = {}
        
        # Skip empty lines and InfluxDB comment lines (starting with #)
        csv_lines = [line for line in lines if line.strip() and not line.startswith('#')]
        if not csv_lines:
            if debug:
                print(f"DEBUG: No CSV data lines after filtering (all comments/empty)", file=sys.stderr)
            return []
        
        if debug:
            print(f"DEBUG: CSV data lines after filtering: {len(csv_lines)}", file=sys.stderr)
            print(f"DEBUG: First CSV line: {csv_lines[0][:200]}", file=sys.stderr)
        
        reader = csv.DictReader(csv_lines)
        
        for row in reader:
            if not row:
                continue
            
            device_name = row.get('device_name', '').strip()
            room = row.get('room', '').strip()
            source = row.get('source', '').strip()
            timestamp = row.get('_time', '').strip()
            
            if not device_name or not source:
                continue
            
            key = (device_name, room, source)
            
            if key not in device_data:
                device_data[key] = {
                    'timestamps': []
                }
            
            if timestamp:
                device_data[key]['timestamps'].append(timestamp)
        
        if debug:
            print(f"DEBUG: Found {len(device_data)} unique (device_name, room, source) combinations", file=sys.stderr)
        
        # Convert to result format
        for (device_name, room, source), data in device_data.items():
            timestamps = sorted(data['timestamps']) if data['timestamps'] else []
            results.append({
                'device_name': device_name,
                'room': room,
                'source': source,
                'count': len(timestamps),
                'first_seen': timestamps[0] if timestamps else 'unknown',
                'last_seen': timestamps[-1] if timestamps else 'unknown'
            })
    
    except subprocess.TimeoutExpired:
        print(f"Error: Query timeout", file=sys.stderr)
    except Exception as e:
        print(f"Error: Query failed: {e}", file=sys.stderr)
        if debug:
            import traceback
            traceback.print_exc(file=sys.stderr)
    
    return results


def interactive_delete_device_data(device: Dict, all_devices: List[Dict]) -> bool:
    """
    Interactive deletion of historical device data from InfluxDB.
    Used to clean up old device_name values after renaming.
    """
    mac_suffix = get_mac_suffix(device['mac'], 12)
    
    print(f"\nQuerying historical data for device:")
    print(f"  MAC: {device['mac']}")
    print(f"  Current name: {device['name']}")
    print(f"  Current room: {device['room']}")
    print()
    
    # Query historical device_name values
    history = query_device_name_history(mac_suffix)
    
    if not history:
        print("No historical data found in InfluxDB for this device.")
        print("\nTip: Enable debug mode to see query details:")
        print("  DEBUG_DEVICE_DELETE=1 iot delete-device-data")
        return False
    
    # Separate current vs old names
    current_entries = [h for h in history if h['device_name'] == device['name']]
    old_entries = [h for h in history if h['device_name'] != device['name']]
    
    if not old_entries:
        print(f"No old data to delete. Only current device_name '{device['name']}' found.")
        print("\nThis means:")
        print(f"  - Device has NOT been renamed (or data was already cleaned up)")
        print(f"  - All {sum(h['count'] for h in current_entries)} rows use current name '{device['name']}'")
        return False
    
    # Display table of historical data with clear OLD/CURRENT markers
    print(f"Found historical data for MAC {mac_suffix}:\n")
    
    if current_entries:
        print("CURRENT NAME (keep this):")
        print(f"{'  device_name':<27} {'room':<20} {'source':<17} {'count':<10} {'first_seen':<25} {'last_seen':<25}")
        print("  " + "─" * 125)
        for h in current_entries:
            print(f"  {h['device_name']:<25} {h['room']:<20} {h['source']:<17} {h['count']:<10} {h['first_seen']:<25} {h['last_seen']:<25}")
        print()
    
    if old_entries:
        print("OLD NAME(S) (delete these to fix Grafana duplicates):")
        print(f"{'  device_name':<27} {'room':<20} {'source':<17} {'count':<10} {'first_seen':<25} {'last_seen':<25}")
        print("  " + "─" * 125)
        for h in old_entries:
            print(f"  {h['device_name']:<25} {h['room']:<20} {h['source']:<17} {h['count']:<10} {h['first_seen']:<25} {h['last_seen']:<25}")
        print()
    
    # If only one old name, suggest it
    unique_old_names = list(set(h['device_name'] for h in old_entries))
    
    if len(unique_old_names) == 1:
        suggested_name = unique_old_names[0]
        print(f"💡 Suggestion: Delete '{suggested_name}' to remove ghost data")
        print()
    
    # Prompt for device_name to delete
    while True:
        if len(unique_old_names) == 1:
            prompt = f"Enter device_name to delete [default: {suggested_name}] (or 'cancel'): "
            old_name = input(prompt).strip()
            if old_name == '':
                old_name = suggested_name
        else:
            old_name = input("Enter device_name to delete (or 'cancel'): ").strip()
        
        if old_name.lower() in ['cancel', 'c']:
            print("Cancelled")
            return False
        
        if old_name == device['name']:
            print(f"❌ Cannot delete CURRENT device_name '{device['name']}'. Choose an OLD name from the list above.")
            continue
        
        # Check if this device_name exists in history
        if not any(h['device_name'] == old_name for h in history):
            print(f"❌ device_name '{old_name}' not found in history. Try again.")
            continue
        
        break
    
    # Optional room filter for stuck/glitched devices
    old_room = None
    rooms_for_old_name = list(set(h['room'] for h in history if h['device_name'] == old_name))
    
    if len(rooms_for_old_name) > 1:
        print(f"\n💡 This device_name appears in multiple rooms: {', '.join(rooms_for_old_name)}")
        print("   You can optionally filter by room to target stuck/glitched data.")
        room_input = input("\nFilter by room? [leave blank for all rooms]: ").strip()
        
        if room_input:
            old_room = room_input.lower().replace(" ", "_")
            if old_room not in rooms_for_old_name:
                print(f"⚠ Warning: room '{old_room}' not found in history, will still use it as filter")
    
    # Get sources that have this device_name (and optionally room)
    if old_room:
        sources_to_delete = [h for h in history if h['device_name'] == old_name and h['room'] == old_room]
        print(f"\n✓ Filtering deletion to device_name='{old_name}' AND room='{old_room}'")
    else:
        sources_to_delete = [h for h in history if h['device_name'] == old_name]
    
    total_count = sum(h['count'] for h in sources_to_delete)
    
    # Display dry-run information
    print(f"\n{'='*80}")
    print("DRY RUN - Will delete:")
    print(f"{'='*80}\n")
    
    token = get_env_value("INFLUX_TOKEN", "my-super-secret-token")
    org = get_env_value("INFLUX_ORG", "home")
    bucket = get_env_value("INFLUX_BUCKET", "sensors")
    showsite = get_env_value("SHOWSITE_NAME", "demo_showsite")
    debug = os.getenv("DEBUG_DEVICE_DELETE", "").lower() in ["1", "true", "yes"]
    
    for h in sources_to_delete:
        # Build predicate with MAC filter (critical!) and optional room filter
        predicate = f'device_name="{old_name}" AND z_device_id=~/{mac_suffix}$/'
        if old_room:
            predicate = f'device_name="{old_name}" AND room="{old_room}" AND z_device_id=~/{mac_suffix}$/'
        
        print(f"Source: {h['source']}")
        if old_room:
            print(f"Room: {h['room']}")
        print(f"Predicate: {predicate}")
        print(f"Estimated rows: {h['count']}")
        print()
    
    print(f"MQTT cleanup: {showsite}/dpx_ops_decoder/*/*/{old_name}/#")
    print(f"\nTotal estimated rows: {total_count} across {len(sources_to_delete)} source(s)")
    print(f"{'='*80}\n")
    
    # Confirmation
    try:
        confirm = input("Proceed with deletion? [y/N]: ").strip().lower()
        
        if confirm not in ['y', 'yes']:
            print("Cancelled")
            return False
        
        print("\nDeleting data...\n")
        
        # Execute deletions
        deleted_count = 0
        for h in sources_to_delete:
            # Build predicate with MAC filter (CRITICAL!) and optional room filter
            predicate = f'device_name="{old_name}" AND z_device_id=~/{mac_suffix}$/'
            if old_room:
                predicate = f'device_name="{old_name}" AND room="{old_room}" AND z_device_id=~/{mac_suffix}$/'
            
            cmd = [
                "docker", "exec", "influxdb", "influx", "delete",
                "--org", org,
                "--token", token,
                "--bucket", bucket,
                "--start", "1970-01-01T00:00:00Z",
                "--stop", "2030-01-01T00:00:00Z",
                "--predicate", predicate
            ]
            
            if debug:
                print(f"\nDEBUG: Deleting from source '{h['source']}'", file=sys.stderr)
                print(f"DEBUG: Predicate: {predicate}", file=sys.stderr)
                print(f"DEBUG: Command: {' '.join(cmd)}", file=sys.stderr)
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if debug:
                    print(f"DEBUG: returncode={result.returncode}", file=sys.stderr)
                    print(f"DEBUG: stdout={result.stdout}", file=sys.stderr)
                    print(f"DEBUG: stderr={result.stderr}", file=sys.stderr)
                
                if result.returncode == 0:
                    print(f"  ✓ Deleted from source: {h['source']}")
                    deleted_count += 1
                else:
                    print(f"  ❌ Failed to delete from {h['source']}: {result.stderr}")
            
            except subprocess.TimeoutExpired:
                print(f"  ❌ Timeout deleting from {h['source']}")
            except Exception as e:
                print(f"  ❌ Error deleting from {h['source']}: {e}")
        
        # Clear MQTT retained messages
        print(f"\nClearing MQTT retained messages for '{old_name}'...")
        mqtt_pattern = f"{showsite}/dpx_ops_decoder/*/*/{old_name}/#"
        
        try:
            mqtt_cmd = ["iot", "clear-retained", mqtt_pattern]
            mqtt_result = subprocess.run(mqtt_cmd, capture_output=True, text=True, timeout=30)
            
            if mqtt_result.returncode == 0:
                print(f"  ✓ MQTT retained messages cleared")
            else:
                print(f"  ⚠ MQTT cleanup had issues (may be okay if no retained messages exist)")
        
        except Exception as e:
            print(f"  ⚠ MQTT cleanup error: {e}")
        
        print()
        print(f"✓ Deleted data for device_name='{old_name}' ({total_count} rows across {deleted_count} source(s))")
        print(f"✓ MQTT retained messages cleared")
        
        # Verify deletion by re-querying
        print("\n🔍 Verifying deletion...")
        verification_history = query_device_name_history(mac_suffix)
        still_exists = [h for h in verification_history if h['device_name'] == old_name]
        
        if old_room:
            still_exists = [h for h in still_exists if h['room'] == old_room]
        
        if still_exists:
            remaining_count = sum(h['count'] for h in still_exists)
            print(f"\n⚠ WARNING: Found {remaining_count} rows still in InfluxDB after deletion!")
            print("\nPossible causes:")
            print("  1. Telegraf replayed retained MQTT messages")
            print("  2. Device is still broadcasting with old name")
            print("  3. InfluxDB deletion is still processing (wait a few seconds)")
            print("\nRecommended actions:")
            print("  1. Verify MQTT retained messages were cleared")
            print("  2. Restart Telegraf: iot restart telegraf")
            print("  3. Wait 30 seconds and run delete-device-data again")
        else:
            print("✓ Verification passed - no data remains for deleted device_name")
        
        print()
        print("Recommendation: Restart Telegraf to verify ghost data doesn't reappear:")
        print("  iot restart telegraf")
        
        return True
    
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


def cmd_delete_device_data(args):
    """Interactive deletion of historical device data from InfluxDB."""
    print(f"Device Data Deletion Tool v{VERSION}\n")
    
    api_data = load_api_devices()
    overrides = load_overrides()
    devices = merge_devices(api_data, overrides)
    
    if not devices:
        print("No devices found")
        return 1
    
    if not api_data:
        print("Warning: API not available, showing override-only devices", file=sys.stderr)
    
    device = interactive_select_device(devices)
    if not device:
        return 0
    
    success = interactive_delete_device_data(device, devices)
    return 0 if success else 1


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: manage-devices.py <command>")
        print("\nCommands:")
        print("  list                - List all devices with override indicators")
        print("  rename              - Interactive device rename")
        print("  set-room            - Interactive room change")
        print("  clear-override      - Remove local override for a device")
        print("  check-bad           - Detect devices with questionable names")
        print("  delete-device-data  - Delete InfluxDB data for renamed devices (interactive)")
        print("  merge               - Merge API data with overrides (JSON output)")
        return 1
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    commands = {
        'list': cmd_list,
        'rename': cmd_rename,
        'set-room': cmd_set_room,
        'clear-override': cmd_clear_override,
        'check-bad': cmd_check_bad,
        'delete-device-data': cmd_delete_device_data,
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
