#!/usr/bin/env python3
"""
NTP Server Test Script
Tests NTP server connectivity and time synchronization.
"""

import ntplib
import socket
import sys
from datetime import datetime
from time import ctime


def test_ntp_server(server, timeout=5):
    """
    Test NTP server and display time synchronization info.
    
    Args:
        server: NTP server hostname or IP address
        timeout: Query timeout in seconds
    
    Returns:
        bool: True if test successful, False otherwise
    """
    client = ntplib.NTPClient()
    
    print(f"\n{'='*60}")
    print(f"Testing NTP Server: {server}")
    print(f"{'='*60}")
    
    try:
        # Attempt to resolve hostname
        try:
            ip = socket.gethostbyname(server)
            print(f"✓ Resolved {server} → {ip}")
        except socket.gaierror:
            print(f"✗ Failed to resolve hostname: {server}")
            return False
        
        # Query NTP server
        print(f"⌛ Querying NTP server (timeout: {timeout}s)...")
        response = client.request(server, version=3, timeout=timeout)
        
        # Display results
        print(f"✓ NTP query successful!\n")
        
        print(f"Server Time:         {ctime(response.tx_time)}")
        print(f"Local Time:          {ctime()}")
        print(f"Offset:              {response.offset:.6f} seconds")
        print(f"Round-trip Delay:    {response.delay:.6f} seconds")
        print(f"Stratum:             {response.stratum}")
        print(f"Precision:           2^{response.precision} seconds")
        print(f"Root Delay:          {response.root_delay:.6f} seconds")
        print(f"Root Dispersion:     {response.root_dispersion:.6f} seconds")
        
        # Offset interpretation
        offset_ms = response.offset * 1000
        print(f"\nTime Offset:         {offset_ms:.2f} ms")
        
        if abs(offset_ms) < 10:
            status = "✓ EXCELLENT"
        elif abs(offset_ms) < 50:
            status = "✓ GOOD"
        elif abs(offset_ms) < 100:
            status = "⚠ ACCEPTABLE"
        else:
            status = "✗ POOR"
        
        print(f"Sync Status:         {status}")
        
        if response.offset > 0:
            print(f"→ Local clock is {offset_ms:.2f} ms AHEAD of {server}")
        else:
            print(f"→ Local clock is {abs(offset_ms):.2f} ms BEHIND {server}")
        
        return True
        
    except ntplib.NTPException as e:
        print(f"✗ NTP query failed: {e}")
        return False
    except socket.timeout:
        print(f"✗ Connection timed out after {timeout}s")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False


def main():
    """Main test function."""
    print("\n🕐 NTP Server Test Utility")
    print("=" * 60)
    
    # Check for custom server argument
    if len(sys.argv) > 1:
        custom_server = sys.argv[1]
        test_servers = [(custom_server, "Custom Server")]
        print(f"Testing custom server: {custom_server}\n")
    else:
        # Interactive mode - prompt for local NTP server IP
        print("\nUsage: python3 test_ntp.py <server> to test a specific server")
        print("Or run interactively to test upstream + your local NTP server\n")
        
        local_ntp_ip = input("Enter your local NTP server IP address (or press Enter to skip): ").strip()
        
        if local_ntp_ip:
            # Test NIST upstream and user's local server
            test_servers = [
                ("time.nist.gov", "NIST Internet Time Service (upstream)"),
                (local_ntp_ip, "Local NTP Server"),
            ]
            print(f"\nTesting NIST upstream + local server ({local_ntp_ip})\n")
        else:
            # Just test NIST
            test_servers = [
                ("time.nist.gov", "NIST Internet Time Service"),
            ]
            print("\nTesting NIST server only\n")
    
    results = []
    
    for server, description in test_servers:
        result = test_ntp_server(server)
        results.append((server, description, result))
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    for server, description, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status:8} {server:25} ({description})")
    
    print(f"{'='*60}\n")
    
    # Exit code based on results
    if any(not success for _, _, success in results):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
