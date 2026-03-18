#!/usr/bin/env python3
"""
ControlByWeb X-410 Relay Controller Script

Controls relays on ControlByWeb X-410 device via SNMP.
Supports 4 independent relays with on/off/toggle/pulse operations.
Supports multiple devices via config/relays.conf or direct IP access.

Requirements:
    - pysnmp library (~5.0.0)
    - X-410 device configured with SNMP v2c enabled

Usage:
    # List configured devices
    python3 x410_control.py --list-devices
    
    # Control via device name (from config/relays.conf)
    python3 x410_control.py --device x410-tent --relay 1 --state on
    python3 x410_control.py --device x410-truck --relay 2 --state toggle
    python3 x410_control.py --device x410-tent --relay 1,2,3 --state off
    
    # Control via direct IP (backward compatible)
    python3 x410_control.py --relay 1 --state on --ip 192.168.1.100
    python3 x410_control.py --relay 2 --state toggle --ip dpx-x410.local
    python3 x410_control.py --relay 3 --pulse 5 --ip 192.168.1.100

OID Reference (per X-410 MIB):
    Base: 1.3.6.1.4.1.30586.46.0
    Relay 1: .5
    Relay 2: .6
    Relay 3: .7
    Relay 4: .8
    Values: "0" = off, "1" = on (DisplayString type, not INTEGER)

Configuration:
    Device inventory: config/relays.conf (INI format)
    SNMP community: .env (X410_SNMP_COMMUNITY)

Return Codes:
    0 - Success
    1 - Connection failed / SNMP error
    2 - Invalid relay number (must be 1-4)
    3 - Invalid arguments
"""

import argparse
import sys
import json
import time
import os
from configparser import ConfigParser
from pathlib import Path
from typing import List, Literal, Optional, Dict

try:
    from pysnmp.hlapi import (
        getCmd, setCmd, SnmpEngine, CommunityData, UdpTransportTarget,
        ContextData, ObjectType, ObjectIdentity, OctetString
    )
except ImportError:
    print("Error: pysnmp library not found. Install with: pip install pysnmp", file=sys.stderr)
    sys.exit(1)


# X-410 OID base for relays
RELAY_OID_BASE = "1.3.6.1.4.1.30586.46.0"

# Relay OID mappings (1-4)
RELAY_OIDS = {
    1: f"{RELAY_OID_BASE}.5",
    2: f"{RELAY_OID_BASE}.6",
    3: f"{RELAY_OID_BASE}.7",
    4: f"{RELAY_OID_BASE}.8",
}

# Relay state values (STRING type per MIB)
RELAY_OFF = "0"
RELAY_ON = "1"


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
    Load X-410 devices from config/relays.conf
    
    Returns:
        Dict of device_name -> {ip, location, relay_count, input_count, enabled, snmp_community}
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
        if config.get(section, 'type', fallback='') == 'x410':
            devices[section] = {
                'ip': config.get(section, 'ip'),
                'location': config.get(section, 'location', fallback=''),
                'relay_count': config.getint(section, 'relay_count', fallback=4),
                'input_count': config.getint(section, 'input_count', fallback=4),
                'enabled': config.getboolean(section, 'enabled', fallback=True),
                'snmp_community': config.get(section, 'snmp_community', fallback=None)
            }
    
    return devices


def list_devices(devices: Dict[str, dict]) -> None:
    """Print formatted list of configured X-410 devices."""
    if not devices:
        print("No X-410 devices found in config/relays.conf")
        print("See config/relays.conf.example for configuration format")
        return
    
    print(f"{'Device Name':<20} {'IP Address':<16} {'Location':<30} {'Status'}")
    print("-" * 75)
    
    for name, info in devices.items():
        status = "✓ enabled" if info['enabled'] else "✗ disabled"
        location = info['location'] or '-'
        print(f"{name:<20} {info['ip']:<16} {location:<30} {status}")


def snmp_get_relay_state(ip: str, community: str, relay_num: int, timeout: int = 5) -> Optional[str]:
    """
    Read current relay state via SNMP GET.
    
    Args:
        ip: Device IP address or hostname
        community: SNMP community string
        relay_num: Relay number (1-4)
        timeout: SNMP timeout in seconds
        
    Returns:
        "0" for OFF, "1" for ON, None on error
    """
    if relay_num not in RELAY_OIDS:
        print(f"Invalid relay number: {relay_num} (must be 1-4)", file=sys.stderr)
        return None
    
    oid = RELAY_OIDS[relay_num]
    
    try:
        iterator = getCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((ip, 161), timeout=timeout),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
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
                state = str(varBind[1])
                return state
                
    except Exception as e:
        print(f"Error reading relay {relay_num} state: {e}", file=sys.stderr)
        return None


def snmp_set_relay_state(ip: str, community: str, relay_num: int, state: str, timeout: int = 5) -> bool:
    """
    Set relay state via SNMP SET.
    
    Args:
        ip: Device IP address or hostname
        community: SNMP community string
        relay_num: Relay number (1-4)
        state: "0" for OFF, "1" for ON
        timeout: SNMP timeout in seconds
        
    Returns:
        True on success, False on error
    """
    if relay_num not in RELAY_OIDS:
        print(f"Invalid relay number: {relay_num} (must be 1-4)", file=sys.stderr)
        return False
    
    oid = RELAY_OIDS[relay_num]
    
    try:
        iterator = setCmd(
            SnmpEngine(),
            CommunityData(community),
            UdpTransportTarget((ip, 161), timeout=timeout),
            ContextData(),
            ObjectType(ObjectIdentity(oid), OctetString(state))
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
        print(f"Error setting relay {relay_num} state: {e}", file=sys.stderr)
        return False


def control_relay(
    ip: str,
    community: str,
    relay_nums: List[int],
    action: Literal["on", "off", "toggle"],
    verbose: bool = False,
    json_output: bool = False
) -> int:
    """
    Control X-410 relay(s) with the specified action.
    
    Args:
        ip: Device IP address or hostname
        community: SNMP community string
        relay_nums: List of relay numbers (1-4)
        action: "on", "off", or "toggle"
        verbose: Print detailed operation info
        json_output: Output result as JSON
        
    Returns:
        Exit code (0=success, 1=connection failed, 2=invalid relay)
    """
    results = []
    overall_success = True
    
    for relay_num in relay_nums:
        if relay_num not in RELAY_OIDS:
            if json_output:
                results.append({
                    "relay": relay_num,
                    "success": False,
                    "error": f"Invalid relay number (must be 1-4)"
                })
            else:
                print(f"✗ Relay {relay_num}: Invalid relay number (must be 1-4)", file=sys.stderr)
            overall_success = False
            continue
        
        # Read current state
        if verbose:
            print(f"Connecting to {ip} for relay {relay_num}...")
        
        current_state = snmp_get_relay_state(ip, community, relay_num)
        
        if current_state is None:
            if json_output:
                results.append({
                    "relay": relay_num,
                    "success": False,
                    "error": "Failed to read relay state"
                })
            else:
                print(f"✗ Relay {relay_num}: Failed to connect or read state", file=sys.stderr)
            overall_success = False
            continue
        
        current_state_str = "ON" if current_state == RELAY_ON else "OFF"
        if verbose:
            print(f"Relay {relay_num} current state: {current_state_str}")
        
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
                results.append({
                    "relay": relay_num,
                    "success": True,
                    "action": "no_change",
                    "state": target_state_str
                })
            else:
                print(f"Relay {relay_num} already {target_state_str}")
            continue
        
        # Set new state
        if verbose:
            print(f"Setting relay {relay_num} to {target_state_str}...")
        
        if not snmp_set_relay_state(ip, community, relay_num, target_state):
            if json_output:
                results.append({
                    "relay": relay_num,
                    "success": False,
                    "error": "Failed to set relay state"
                })
            else:
                print(f"✗ Relay {relay_num}: Failed to set state", file=sys.stderr)
            overall_success = False
            continue
        
        # Verify state change
        time.sleep(0.5)  # Brief delay for device to process
        
        new_state = snmp_get_relay_state(ip, community, relay_num)
        
        if new_state != target_state:
            if json_output:
                results.append({
                    "relay": relay_num,
                    "success": False,
                    "error": "State verification failed",
                    "expected": target_state_str,
                    "actual": "ON" if new_state == RELAY_ON else "OFF"
                })
            else:
                print(f"✗ Relay {relay_num}: Verification failed (expected {target_state_str}, got {new_state})", file=sys.stderr)
            overall_success = False
            continue
        
        # Success
        if json_output:
            results.append({
                "relay": relay_num,
                "success": True,
                "action": action,
                "previous_state": current_state_str,
                "new_state": target_state_str
            })
        else:
            print(f"✓ Relay {relay_num}: {current_state_str} → {target_state_str}")
    
    if json_output:
        print(json.dumps({"results": results, "overall_success": overall_success}))
    
    return 0 if overall_success else 1


def pulse_relay(
    ip: str,
    community: str,
    relay_num: int,
    duration: float,
    verbose: bool = False,
    json_output: bool = False
) -> int:
    """
    Pulse a relay: turn on, wait, turn off.
    
    Args:
        ip: Device IP address or hostname
        community: SNMP community string
        relay_num: Relay number (1-4)
        duration: Pulse duration in seconds
        verbose: Print detailed operation info
        json_output: Output result as JSON
        
    Returns:
        Exit code (0=success, 1=error)
    """
    if relay_num not in RELAY_OIDS:
        if json_output:
            result = {"success": False, "error": f"Invalid relay number (must be 1-4)"}
            print(json.dumps(result))
        else:
            print(f"✗ Invalid relay number: {relay_num} (must be 1-4)", file=sys.stderr)
        return 2
    
    if verbose:
        print(f"Pulsing relay {relay_num} for {duration} seconds...")
    
    # Turn relay ON
    if not snmp_set_relay_state(ip, community, relay_num, RELAY_ON):
        if json_output:
            result = {"success": False, "error": "Failed to turn relay on"}
            print(json.dumps(result))
        else:
            print(f"✗ Relay {relay_num}: Failed to turn on", file=sys.stderr)
        return 1
    
    if verbose:
        print(f"Relay {relay_num} ON, waiting {duration}s...")
    
    # Wait for pulse duration
    time.sleep(duration)
    
    # Turn relay OFF
    if not snmp_set_relay_state(ip, community, relay_num, RELAY_OFF):
        if json_output:
            result = {"success": False, "error": "Failed to turn relay off"}
            print(json.dumps(result))
        else:
            print(f"✗ Relay {relay_num}: Failed to turn off", file=sys.stderr)
        return 1
    
    # Success
    if json_output:
        result = {
            "success": True,
            "action": "pulse",
            "relay": relay_num,
            "duration": duration
        }
        print(json.dumps(result))
    else:
        print(f"✓ Relay {relay_num}: Pulsed for {duration}s")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Control ControlByWeb X-410 relays via SNMP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List configured devices
  %(prog)s --list-devices
  
  # Control via device name (from config/relays.conf)
  %(prog)s --device x410-tent --relay 1 --state on
  %(prog)s --device x410-truck --relay 2 --state toggle
  %(prog)s --device x410-tent --relay 1,2,3 --state off
  %(prog)s --device x410-tent --relay 4 --pulse 5
  
  # Control via direct IP (backward compatible)
  %(prog)s --relay 1 --state on --ip dpx-x410.local
  %(prog)s --relay 2 --state toggle --ip 192.168.1.100
  %(prog)s --relay 3 --pulse 5 --ip 192.168.1.100
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
        help="List configured X-410 devices and exit"
    )
    
    parser.add_argument(
        "--community",
        help="SNMP community string (required with --ip, optional with --device)"
    )
    
    parser.add_argument(
        "--relay",
        help="Relay number (1-4) or comma-separated list (e.g., 1,2,3)"
    )
    
    parser.add_argument(
        "--state",
        choices=["on", "off", "toggle"],
        help="Relay action: on, off, or toggle"
    )
    
    parser.add_argument(
        "--pulse",
        type=float,
        metavar="SECONDS",
        help="Pulse relay for N seconds (turn on, wait, turn off)"
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
    
    if not args.state and not args.pulse:
        parser.error("Either --state or --pulse must be specified")
    
    if args.state and args.pulse:
        parser.error("Cannot specify both --state and --pulse")
    
    # Parse relay numbers
    try:
        relay_nums = [int(r.strip()) for r in args.relay.split(",")]
    except ValueError:
        parser.error(f"Invalid relay number: {args.relay}")
        return 3
    
    # Pulse mode only supports single relay
    if args.pulse and len(relay_nums) > 1:
        parser.error("Pulse mode only supports a single relay")
        return 3
    
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
            os.getenv('X410_SNMP_COMMUNITY', 'public')
        )
        
        if args.verbose:
            print(f"Using device: {args.device}")
            print(f"  IP: {ip}")
            print(f"  Location: {device_info['location']}")
            print(f"  Relays: {device_info['relay_count']}")
            print(f"  Community: {community}")
        
    elif args.ip:
        # Direct IP access (backward compatible)
        if not args.community:
            # Default to public if not specified
            community = "public"
        else:
            community = args.community
        
        ip = args.ip
        
    else:
        parser.error("Either --device or --ip must be specified")
    
    # Execute command
    if args.pulse:
        exit_code = pulse_relay(
            ip=ip,
            community=community,
            relay_num=relay_nums[0],
            duration=args.pulse,
            verbose=args.verbose,
            json_output=args.json
        )
    else:
        exit_code = control_relay(
            ip=ip,
            community=community,
            relay_nums=relay_nums,
            action=args.state,
            verbose=args.verbose,
            json_output=args.json
        )
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
