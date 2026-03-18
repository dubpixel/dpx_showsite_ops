#!/usr/bin/env python3
"""
Geist Watchdog Relay Control Script

Controls the on-board relay on Geist Watchdog environmental monitor via SNMP.
Supports on/off/toggle operations with state verification.
Supports multiple devices via config/relays.conf or direct IP access.

Requirements:
    - pysnmp library (~1.0.0)
    - Geist device configured with read-write SNMP community string

Usage:
    # List configured devices
    python3 geist_control.py --list-devices
    
    # Control via device name (from config/relays.conf)
    python3 geist_control.py --device geist-rack-a --relay on
    python3 geist_control.py --device geist-rack-a --relay toggle
    
    # Control via direct IP (backward compatible)
    python3 geist_control.py --relay on --ip dpx-geist.local --community private
    python3 geist_control.py --relay off --ip 192.168.1.214 --community private
    python3 geist_control.py --relay toggle --ip dpx-geist.local --community private

OID Reference:
    Relay State: 1.3.6.1.4.1.21239.5.1.2.1.12
    Values: 0 = off, 1 = on

Configuration:
    Device inventory: config/relays.conf (INI format)
    SNMP community: .env (GEIST_SNMP_RW_COMMUNITY)

Return Codes:
    0 - Success
    1 - Connection failed / SNMP error
    2 - State verification failed
    3 - Invalid arguments
"""

import argparse
import sys
import json
import os
from configparser import ConfigParser
from pathlib import Path
from typing import Optional, Literal, Dict

try:
    from pysnmp.hlapi import (
        getCmd, setCmd, SnmpEngine, CommunityData, UdpTransportTarget,
        ContextData, ObjectType, ObjectIdentity, Integer
    )
except ImportError:
    print("Error: pysnmp library not found. Install with: pip install pysnmp", file=sys.stderr)
    sys.exit(1)


# Geist Watchdog OID for relay state
RELAY_STATE_OID = "1.3.6.1.4.1.21239.5.1.2.1.12"

# Relay state values
RELAY_OFF = 0
RELAY_ON = 1


def find_config_file() -> Optional[Path]:
    """Find config/relays.conf in current dir or parent dirs."""
    current = Path.cwd()
    for _ in range(5):  # Check up to 5 levels up
        config_path = current / "config" / "relays.conf"
        if config_path.exists():
            return config_path
        current = current.parent
    return None


def load_devices_from_config(config_path: Optional[Path] = None) -> Dict[str, dict]:
    """
    Load Geist devices from config/relays.conf
    
    Returns:
        Dict of device_name -> {ip, location, enabled, snmp_community}
    """
    if config_path is None:
        config_path = find_config_file()
    
    if config_path is None or not config_path.exists():
        return {}
    
    config = ConfigParser()
    try:
        config.read(config_path)
    except Exception as e:
        print(f"Error reading config file: {e}", file=sys.stderr)
        return {}
    
    devices = {}
    for section in config.sections():
        if config.get(section, 'type', fallback='') == 'geist':
            devices[section] = {
                'ip': config.get(section, 'ip'),
                'location': config.get(section, 'location', fallback=''),
                'enabled': config.getboolean(section, 'enabled', fallback=True),
                'snmp_community': config.get(section, 'snmp_community', fallback=None)
            }
    
    return devices


def list_devices(devices: Dict[str, dict]) -> None:
    """Print formatted list of configured Geist devices."""
    if not devices:
        print("No Geist devices found in config/relays.conf")
        print("See config/relays.conf.example for configuration format")
        return
    
    print(f"{'Device Name':<20} {'IP Address':<16} {'Location':<30} {'Status'}")
    print("-" * 75)
    
    for name, info in devices.items():
        status = "✓ enabled" if info['enabled'] else "✗ disabled"
        location = info['location'] or '-'
        print(f"{name:<20} {info['ip']:<16} {location:<30} {status}")


def snmp_get_relay_state(ip: str, community: str, timeout: int = 5) -> Optional[int]:
    """
    Read current relay state via SNMP GET.
    
    Args:
        ip: Device IP address or hostname
        community: SNMP community string
        timeout: SNMP timeout in seconds
        
    Returns:
        0 for OFF, 1 for ON, None on error
    """
    try:
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((ip, 161), timeout=timeout),
            ContextData(),
            ObjectType(ObjectIdentity(RELAY_STATE_OID))
        )
        
        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        
        if errorIndication:
            print(f"SNMP Error: {errorIndication}", file=sys.stderr)
            return None
        elif errorStatus:
            print(f"SNMP Error: {errorStatus.prettyPrint()} at {errorIndex}", file=sys.stderr)
            return None
        else:
            # Extract relay state from response
            for varBind in varBinds:
                state = int(varBind[1])
                return state
                
    except Exception as e:
        print(f"Error reading relay state: {e}", file=sys.stderr)
        return None


def snmp_set_relay_state(ip: str, community: str, state: int, timeout: int = 5) -> bool:
    """
    Set relay state via SNMP SET.
    
    Args:
        ip: Device IP address or hostname
        community: SNMP community string (must have write access)
        state: 0 for OFF, 1 for ON
        timeout: SNMP timeout in seconds
        
    Returns:
        True on success, False on error
    """
    try:
        iterator = setCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((ip, 161), timeout=timeout),
            ContextData(),
            ObjectType(ObjectIdentity(RELAY_STATE_OID), Integer(state))
        )
        
        errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
        
        if errorIndication:
            print(f"SNMP Error: {errorIndication}", file=sys.stderr)
            return False
        elif errorStatus:
            print(f"SNMP Error: {errorStatus.prettyPrint()} at {errorIndex}", file=sys.stderr)
            return False
        else:
            return True
            
    except Exception as e:
        print(f"Error setting relay state: {e}", file=sys.stderr)
        return False


def control_relay(
    ip: str,
    community: str,
    action: Literal["on", "off", "toggle"],
    verbose: bool = False,
    json_output: bool = False
) -> int:
    """
    Control Geist relay with the specified action.
    
    Args:
        ip: Device IP address or hostname
        community: SNMP community string (must have write access)
        action: "on", "off", or "toggle"
        verbose: Print detailed operation info
        json_output: Output result as JSON
        
    Returns:
        Exit code (0=success, 1=connection failed, 2=verification failed)
    """
    # Read current state
    if verbose:
        print(f"Connecting to {ip}...")
    
    current_state = snmp_get_relay_state(ip, community)
    
    if current_state is None:
        if json_output:
            result = {"success": False, "error": "Failed to read relay state"}
            print(json.dumps(result))
        else:
            print(f"✗ Failed to connect to {ip} or read relay state", file=sys.stderr)
        return 1
    
    current_state_str = "ON" if current_state == RELAY_ON else "OFF"
    if verbose:
        print(f"Current relay state: {current_state_str}")
    
    # Determine target state
    if action == "toggle":
        target_state = RELAY_OFF if current_state == RELAY_ON else RELAY_ON
    elif action == "on":
        target_state = RELAY_ON
    else:  # off
        target_state = RELAY_OFF
    
    target_state_str = "ON" if target_state == RELAY_ON else "OFF"
    
    # Check if state change is needed
    if current_state == target_state:
        if json_output:
            result = {
                "success": True,
                "action": "no_change",
                "state": target_state_str,
                "message": f"Relay already {target_state_str}"
            }
            print(json.dumps(result))
        else:
            print(f"Relay already {target_state_str}")
        return 0
    
    # Set new state
    if verbose:
        print(f"Setting relay to {target_state_str}...")
    
    if not snmp_set_relay_state(ip, community, target_state):
        if json_output:
            result = {"success": False, "error": "Failed to set relay state"}
            print(json.dumps(result))
        else:
            print(f"✗ Failed to set relay state", file=sys.stderr)
        return 1
    
    # Verify state change
    import time
    time.sleep(0.5)  # Brief delay for device to process
    
    new_state = snmp_get_relay_state(ip, community)
    
    if new_state != target_state:
        if json_output:
            result = {
                "success": False,
                "error": "State verification failed",
                "expected": target_state_str,
                "actual": "ON" if new_state == RELAY_ON else "OFF"
            }
            print(json.dumps(result))
        else:
            print(f"✗ Verification failed: expected {target_state_str}, got {new_state}", file=sys.stderr)
        return 2
    
    # Success
    if json_output:
        result = {
            "success": True,
            "action": action,
            "previous_state": current_state_str,
            "new_state": target_state_str
        }
        print(json.dumps(result))
    else:
        print(f"✓ Relay switched from {current_state_str} to {target_state_str}")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Control Geist Watchdog relay via SNMP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List configured devices
  %(prog)s --list-devices
  
  # Control via device name (from config/relays.conf)
  %(prog)s --device geist-rack-a --relay on
  %(prog)s --device geist-rack-a --relay toggle --verbose
  
  # Control via direct IP (backward compatible)
  %(prog)s --relay on --ip dpx-geist.local --community private
  %(prog)s --relay off --ip 192.168.1.214 --community private
  %(prog)s --relay toggle --ip dpx-geist.local --community private --json
"""
    )
    
    # Device selection (mutually exclusive)
    device_group = parser.add_mutually_exclusive_group()
    device_group.add_argument(
        "--device",
        help="Device name from config/relays.conf"
    )
    device_group.add_argument(
        "--ip",
        help="Device IP address or hostname (for direct access)"
    )
    
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List configured Geist devices and exit"
    )
    
    parser.add_argument(
        "--community",
        help="SNMP community string (required with --ip, optional with --device)"
    )
    
    parser.add_argument(
        "--relay",
        choices=["on", "off", "toggle"],
        help="Relay action: on, off, or toggle"
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
    
    # Load devices from config
    devices = load_devices_from_config()
    
    # Handle --list-devices
    if args.list_devices:
        list_devices(devices)
        sys.exit(0)
    
    # Validate arguments for relay control
    if not args.relay:
        parser.error("--relay is required (unless using --list-devices)")
    
    # Determine IP and community based on device selection
    if args.device:
        # Using device name from config
        if args.device not in devices:
            print(f"Error: Device '{args.device}' not found in config/relays.conf", file=sys.stderr)
            print(f"\nAvailable devices:", file=sys.stderr)
            list_devices(devices)
            sys.exit(3)
        
        device_info = devices[args.device]
        
        if not device_info['enabled']:
            print(f"Warning: Device '{args.device}' is disabled in config", file=sys.stderr)
        
        ip = device_info['ip']
        
        # Community: use device override, CLI arg, or env default
        community = (
            args.community or 
            device_info['snmp_community'] or 
            os.getenv('GEIST_SNMP_RW_COMMUNITY', 'private')
        )
        
        if args.verbose:
            print(f"Using device: {args.device}")
            print(f"  IP: {ip}")
            print(f"  Location: {device_info['location']}")
            print(f"  Community: {community}")
        
    elif args.ip:
        # Direct IP access (backward compatible)
        if not args.community:
            parser.error("--community is required when using --ip")
        
        ip = args.ip
        community = args.community
        
    else:
        parser.error("Either --device or --ip must be specified")
    
    # Execute control command
    exit_code = control_relay(
        ip=ip,
        community=community,
        action=args.relay,
        verbose=args.verbose,
        json_output=args.json
    )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
