#!/usr/bin/env python3
"""
Govee Device Control Script

Controls Govee smart lights and plugs via govee2mqtt HTTP API.
Supports power control, brightness, color, and color temperature.

Requirements:
    - requests library
    - govee2mqtt service running on port 8056

Device Naming:
    - Loads device names from govee2mqtt API
    - Applies local overrides from telegraf/conf.d/device-overrides.json
    - Supports fuzzy matching and aliases (see DEVICE_ALIASES)

Usage:
    python3 govee_control.py --list
    python3 govee_control.py --device "stick light" --on
    python3 govee_control.py --device "floor_lamp_upper" --on --brightness 75
    python3 govee_control.py --device "H6159" --on --brightness 75
    python3 govee_control.py --device "plug" --off
    python3 govee_control.py --device "strip" --on --color red
    python3 govee_control.py --device "strip" --on --color "#FF8800"

API Reference:
    GET  /api/devices - list all devices
    POST /api/devices/{device_id}/state - control device

Return Codes:
    0 - Success
    1 - API connection failed
    2 - Device not found
    3 - Invalid arguments
"""

import argparse
import sys
import json
import os
from typing import Optional, Dict, Any, List

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)


# Device name aliases for convenience
DEVICE_ALIASES = {
    "stick": "Govee H6159",
    "plug": "Govee Smart Plug",
    # Add more aliases as needed
}

# Color presets (RGB values)
COLOR_PRESETS = {
    "red": {"r": 255, "g": 0, "b": 0},
    "green": {"r": 0, "g": 255, "b": 0},
    "blue": {"r": 0, "g": 0, "b": 255},
    "white": {"r": 255, "g": 255, "b": 255},
    "yellow": {"r": 255, "g": 255, "b": 0},
    "cyan": {"r": 0, "g": 255, "b": 255},
    "magenta": {"r": 255, "g": 0, "b": 255},
    "orange": {"r": 255, "g": 165, "b": 0},
    "purple": {"r": 128, "g": 0, "b": 128},
    "pink": {"r": 255, "g": 192, "b": 203},
}


def get_api_url(endpoint: str, api_base: str = "http://localhost:8056") -> str:
    """Construct full API URL."""
    return f"{api_base}/api{endpoint}"


def list_devices(api_base: str = "http://localhost:8056", verbose: bool = False) -> Optional[List[Dict[str, Any]]]:
    """
    Get list of all Govee devices from API with local overrides applied.
    
    Args:
        api_base: Base URL for govee2mqtt API
        verbose: Print detailed info
        
    Returns:
        List of device dicts with overrides applied, or None on error
    """
    url = get_api_url("/devices", api_base)
    
    if verbose:
        print(f"Fetching devices from {url}...")
    
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        devices = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching devices: {e}", file=sys.stderr)
        return None
    
    # Apply local overrides from device-overrides.json
    override_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "telegraf", "conf.d", "device-overrides.json")
    
    if verbose:
        print(f"Checking for overrides at: {override_file}")
    
    if os.path.exists(override_file):
        try:
            with open(override_file) as f:
                overrides = json.load(f)
            
            override_count = 0
            for device in devices:
                # Get MAC address (with or without colons)
                mac = device.get("id") or device.get("address", "")
                mac_normalized = mac.replace(":", "").upper()
                
                # Check if this device has an override
                if mac_normalized in overrides:
                    override_data = overrides[mac_normalized]
                    
                    # Skip JSON comment entries
                    if mac_normalized.startswith("_"):
                        continue
                    
                    # Apply name override
                    if "name" in override_data:
                        if verbose:
                            print(f"  Override: {device.get('name')} → {override_data['name']}")
                        device["name"] = override_data["name"]
                    
                    # Apply room override
                    if "room" in override_data:
                        device["room"] = override_data["room"]
                    
                    device["has_override"] = True
                    override_count += 1
                else:
                    device["has_override"] = False
            
            if override_count > 0 and verbose:
                print(f"Applied {override_count} device override(s)")
        
        except Exception as e:
            if verbose:
                print(f"Warning: Failed to load overrides: {e}")
    
    return devices


def find_device(
    device_query: str,
    api_base: str = "http://localhost:8056",
    verbose: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Find device by name, model, or MAC address.
    Supports fuzzy matching and aliases.
    
    Args:
        device_query: Device name, model, MAC, or alias
        api_base: Base URL for govee2mqtt API
        verbose: Print detailed info
        
    Returns:
        Device dict, or None if not found
    """
    # Check if query is an alias
    if device_query.lower() in DEVICE_ALIASES:
        device_query = DEVICE_ALIASES[device_query.lower()]
        if verbose:
            print(f"Using alias: {device_query}")
    
    devices = list_devices(api_base, verbose)
    
    if devices is None:
        return None
    
    # Try exact name match first
    for device in devices:
        name = device.get("name", "")
        if name.lower() == device_query.lower():
            return device
    
    # Try partial name match
    for device in devices:
        name = device.get("name", "")
        if device_query.lower() in name.lower():
            return device
    
    # Try model match
    for device in devices:
        model = device.get("model", "")
        if device_query.lower() in model.lower():
            return device
    
    # Try MAC address match
    for device in devices:
        mac = device.get("address", "")
        if device_query.lower() in mac.lower():
            return device
    
    return None


def parse_color(color_str: str) -> Optional[Dict[str, int]]:
    """
    Parse color string to RGB dict.
    Supports color names and hex codes.
    
    Args:
        color_str: Color name ("red") or hex code ("#FF0000")
        
    Returns:
        Dict with r, g, b keys, or None if invalid
    """
    # Check if it's a preset name
    if color_str.lower() in COLOR_PRESETS:
        return COLOR_PRESETS[color_str.lower()]
    
    # Check if it's a hex color code
    if color_str.startswith("#"):
        hex_code = color_str[1:]
        if len(hex_code) == 6:
            try:
                r = int(hex_code[0:2], 16)
                g = int(hex_code[2:4], 16)
                b = int(hex_code[4:6], 16)
                return {"r": r, "g": g, "b": b}
            except ValueError:
                return None
    
    return None


def control_device(
    device_id: str,
    power: Optional[bool] = None,
    brightness: Optional[int] = None,
    color: Optional[Dict[str, int]] = None,
    temperature: Optional[int] = None,
    api_base: str = "http://localhost:8056",
    verbose: bool = False
) -> bool:
    """
    Send control command to device.
    
    Args:
        device_id: Device ID or address
        power: True for on, False for off, None to leave unchanged
        brightness: 0-100, None to leave unchanged
        color: RGB dict {"r": 0-255, "g": 0-255, "b": 0-255}, None to leave unchanged
        temperature: Color temperature in Kelvin (2000-9000), None to leave unchanged
        api_base: Base URL for govee2mqtt API
        verbose: Print detailed info
        
    Returns:
        True on success, False on error
    """
    url = get_api_url(f"/devices/{device_id}/state", api_base)
    
    payload = {}
    
    if power is not None:
        payload["on"] = power
    
    if brightness is not None:
        if not 0 <= brightness <= 100:
            print(f"Invalid brightness: {brightness} (must be 0-100)", file=sys.stderr)
            return False
        payload["brightness"] = brightness
    
    if color is not None:
        payload["color"] = color
    
    if temperature is not None:
        if not 2000 <= temperature <= 9000:
            print(f"Invalid temperature: {temperature} (must be 2000-9000 Kelvin)", file=sys.stderr)
            return False
        payload["colorTemperature"] = temperature
    
    if verbose:
        print(f"Sending to {url}:")
        print(f"  Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        
        if verbose:
            print(f"Response: {response.status_code}")
            print(f"  {response.text}")
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error controlling device: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Control Govee devices via govee2mqtt API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list
  %(prog)s --device "stick light" --on
  %(prog)s --device "H6159" --on --brightness 75
  %(prog)s --device "plug" --off
  %(prog)s --device "strip" --on --color red
  %(prog)s --device "strip" --on --color "#FF8800"
  %(prog)s --device "bulb" --on --temperature 4000

Device Aliases:
  stick  → Govee H6159
  plug   → Govee Smart Plug
"""
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available devices"
    )
    
    parser.add_argument(
        "--device",
        help="Device name, model, MAC address, or alias"
    )
    
    parser.add_argument(
        "--on",
        action="store_true",
        help="Turn device on"
    )
    
    parser.add_argument(
        "--off",
        action="store_true",
        help="Turn device off"
    )
    
    parser.add_argument(
        "--brightness",
        type=int,
        metavar="0-100",
        help="Set brightness (0-100, only for lights)"
    )
    
    parser.add_argument(
        "--color",
        help="Set color: red, blue, green, white, yellow, cyan, magenta, orange, purple, pink, or #RRGGBB hex"
    )
    
    parser.add_argument(
        "--temperature",
        type=int,
        metavar="KELVIN",
        help="Set color temperature in Kelvin (2000-9000, only for lights)"
    )
    
    parser.add_argument(
        "--api-url",
        default="http://localhost:8056",
        help="govee2mqtt API base URL (default: http://localhost:8056)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed operation info"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON"
    )
    
    args = parser.parse_args()
    
    # List mode
    if args.list:
        devices = list_devices(args.api_url, args.verbose)
        
        if devices is None:
            print("✗ Failed to list devices", file=sys.stderr)
            sys.exit(1)
        
        if args.json:
            print(json.dumps(devices, indent=2))
        else:
            print(f"Found {len(devices)} device(s):\n")
            for device in devices:
                name = device.get("name", "Unknown")
                model = device.get("model", "Unknown")
                address = device.get("address", "Unknown")
                state = device.get("state", {})
                power = "ON" if state.get("on") else "OFF"
                brightness = state.get("brightness", "N/A")
                has_override = device.get("has_override", False)
                override_marker = " [override]" if has_override else ""
                
                print(f"  • {name}{override_marker}")
                print(f"    Model: {model}")
                print(f"    Address: {address}")
                print(f"    State: {power}, Brightness: {brightness}")
                print()
        
        sys.exit(0)
    
    # Control mode - require device
    if not args.device:
        parser.error("--device is required (or use --list to show devices)")
    
    # Validate arguments
    if args.on and args.off:
        parser.error("Cannot specify both --on and --off")
    
    if not (args.on or args.off or args.brightness is not None or args.color or args.temperature is not None):
        parser.error("Must specify at least one control action: --on, --off, --brightness, --color, or --temperature")
    
    # Find device
    device = find_device(args.device, args.api_url, args.verbose)
    
    if device is None:
        if args.json:
            result = {"success": False, "error": f"Device not found: {args.device}"}
            print(json.dumps(result))
        else:
            print(f"✗ Device not found: {args.device}", file=sys.stderr)
            print("\nUse --list to see available devices", file=sys.stderr)
        sys.exit(2)
    
    device_id = device.get("id") or device.get("address")
    device_name = device.get("name", "Unknown")
    
    if args.verbose:
        print(f"Found device: {device_name} (ID: {device_id})")
    
    # Determine power state
    power = None
    if args.on:
        power = True
    elif args.off:
        power = False
    
    # Parse color if provided
    color_rgb = None
    if args.color:
        color_rgb = parse_color(args.color)
        if color_rgb is None:
            if args.json:
                result = {"success": False, "error": f"Invalid color: {args.color}"}
                print(json.dumps(result))
            else:
                print(f"✗ Invalid color: {args.color}", file=sys.stderr)
                print("Valid colors: red, blue, green, white, yellow, cyan, magenta, orange, purple, pink, #RRGGBB", file=sys.stderr)
            sys.exit(3)
    
    # Execute control command
    success = control_device(
        device_id=device_id,
        power=power,
        brightness=args.brightness,
        color=color_rgb,
        temperature=args.temperature,
        api_base=args.api_url,
        verbose=args.verbose
    )
    
    if success:
        if args.json:
            result = {
                "success": True,
                "device": device_name,
                "device_id": device_id
            }
            if power is not None:
                result["power"] = "on" if power else "off"
            if args.brightness is not None:
                result["brightness"] = args.brightness
            if color_rgb:
                result["color"] = color_rgb
            if args.temperature is not None:
                result["temperature"] = args.temperature
            print(json.dumps(result))
        else:
            actions = []
            if power is not None:
                actions.append("ON" if power else "OFF")
            if args.brightness is not None:
                actions.append(f"Brightness: {args.brightness}%")
            if color_rgb:
                actions.append(f"Color: {args.color}")
            if args.temperature is not None:
                actions.append(f"Temperature: {args.temperature}K")
            
            print(f"✓ {device_name}: {', '.join(actions)}")
        sys.exit(0)
    else:
        if args.json:
            result = {"success": False, "error": "Failed to control device"}
            print(json.dumps(result))
        else:
            print(f"✗ Failed to control device: {device_name}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
