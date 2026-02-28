#!/bin/bash
# ================================================================================
# M4300 Network Connectivity Setup
# ================================================================================
# Temporary network fix for M4300 OOB (out-of-band) port access
# Adds secondary IP on 192.168.0.x network to reach switch management interfaces
#
# NOTE: This is a TEMPORARY solution until proper management VLAN is deployed
#
# Usage:
#   sudo ./scripts/setup-m4300-network.sh [interface]
#   Default interface: eth0
#
# To make persistent across reboots, add to systemd service or /etc/rc.local
# ================================================================================

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Interface (default: eth0, can pass as first argument)
INTERFACE="${1:-eth0}"

# Secondary IP for M4300 network (192.168.0.x subnet)
SECONDARY_IP="192.168.0.1/24"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}ERROR${NC}: This script must be run as root (use sudo)" 
   exit 1
fi

echo "======================================================================"
echo "M4300 Network Connectivity Setup (TEMPORARY)"
echo "======================================================================"
echo ""

# Check if interface exists
if ! ip link show "$INTERFACE" > /dev/null 2>&1; then
    echo -e "${RED}ERROR${NC}: Network interface $INTERFACE does not exist"
    echo "Available interfaces:"
    ip link show | grep '^[0-9]' | awk '{print $2}' | tr -d ':'
    exit 1
fi

# Check if secondary IP already configured
if ip addr show "$INTERFACE" | grep -q "192.168.0.1"; then
    echo -e "${YELLOW}INFO${NC}: Secondary IP already configured on $INTERFACE"
    ip addr show "$INTERFACE" | grep "192.168.0"
    echo ""
    echo "Nothing to do."
    exit 0
fi

# Add secondary IP
echo -n "Adding secondary IP $SECONDARY_IP to $INTERFACE... "
ip addr add "$SECONDARY_IP" dev "$INTERFACE"

if ip addr show "$INTERFACE" | grep -q "192.168.0.1"; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
    exit 1
fi

# Verify connectivity
echo ""
echo "Verifying configuration:"
ip addr show "$INTERFACE" | grep "inet " | grep -v "127.0.0.1"

echo ""
echo -e "${GREEN}✓${NC} M4300 network accessible on 192.168.0.x subnet"
echo ""
echo -e "${YELLOW}NOTE${NC}: This configuration is TEMPORARY"
echo "  - Will be lost on reboot unless made persistent"
echo "  - To persist: Add to systemd or network config"
echo "  - Proper solution: Deploy management VLAN"
echo ""
echo "Test connectivity:"
echo "  ping 192.168.0.238  # M4300-FOH switch"
echo "  ping 192.168.0.239  # M4300-SR switch"
echo ""
