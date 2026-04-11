#!/bin/bash

# Simple NTP test - just query the server

echo "Enter NTP server IP to test:"
read -r SERVER_IP

if [ -z "$SERVER_IP" ]; then
    echo "No IP provided. Exiting."
    exit 1
fi

echo ""
echo "Testing NTP server at $SERVER_IP..."
echo "=========================================="

# Try sntp
if command -v sntp &> /dev/null; then
    sntp -d "$SERVER_IP"
elif command -v ntpdate &> /dev/null; then
    ntpdate -q "$SERVER_IP"
else
    echo "Error: sntp or ntpdate not found."
    echo "Install with: brew install sntp"
    exit 1
fi
