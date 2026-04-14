#!/bin/bash

# === NTP Server Test Script ===
# Tests the NTP server running in Docker container

set -e

echo "🕐 NTP Server Test Utility"
echo "=========================================="
echo ""

# Check if container is running
echo "Checking if ntp-server container is running..."
if docker compose ps ntp-server | grep -q "Up"; then
    echo "✓ ntp-server container is running"
else
    echo "✗ ntp-server container is NOT running"
    echo "  Start it with: docker compose up -d ntp-server"
    exit 1
fi

echo ""
echo "Container logs (last 10 lines):"
echo "----------------------------------------"
docker compose logs --tail=10 ntp-server
echo "----------------------------------------"
echo ""

# Check if chrony is listening inside the container
echo "Checking if chrony is listening on port 123..."
if docker compose exec ntp-server ss -ulnp 2>/dev/null | grep -q 123; then
    echo "✓ Chrony is listening on port 123"
else
    echo "⚠ Cannot verify if chrony is listening (ss command may not be available)"
fi

echo ""

# Test chrony tracking inside container
echo "Checking chrony sync status inside container..."
echo "----------------------------------------"
docker compose exec ntp-server chronyc tracking || echo "⚠ chronyc tracking failed"
echo "----------------------------------------"
echo ""

# Check chrony sources
echo "Checking chrony time sources..."
echo "----------------------------------------"
docker compose exec ntp-server chronyc sources || echo "⚠ chronyc sources failed"
echo "----------------------------------------"
echo ""

# Prompt for IP to test
echo "Enter the IP address to test NTP from (or press Enter to skip external test):"
read -r TEST_IP

if [ -n "$TEST_IP" ]; then
    echo ""
    echo "Testing NTP query to $TEST_IP..."
    echo "----------------------------------------"
    
    # Try sntp first
    if command -v sntp &> /dev/null; then
        sntp -d "$TEST_IP" 2>&1 || echo "⚠ sntp test failed - this might be normal if testing from localhost"
    elif command -v ntpdate &> /dev/null; then
        ntpdate -q "$TEST_IP" 2>&1 || echo "⚠ ntpdate test failed"
    else
        echo "⚠ Neither sntp nor ntpdate found on host system"
        echo "  Install with: brew install sntp (macOS) or apt-get install sntp (Linux)"
    fi
    echo "----------------------------------------"
fi

echo ""
echo "✅ Test complete!"
echo ""
echo "Troubleshooting tips:"
echo "  - Container logs: docker compose logs ntp-server -f"
echo "  - Restart server: docker compose restart ntp-server"
echo "  - Check config: cat config/ntp.conf"
echo ""
