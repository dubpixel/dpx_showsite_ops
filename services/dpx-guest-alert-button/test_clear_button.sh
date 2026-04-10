#!/bin/bash
# Quick test script to diagnose clear button (Input 1 on lamp controller)

echo "=== Testing Clear Button (Lamp Controller Input 1) ==="
echo ""

LAMP_IP="192.168.105.111"
BUTTON_IP="192.168.105.112"
COMMUNITY="public"
OID_INPUT_1="1.3.6.1.4.1.30586.46.0.1"

echo "1. Testing SNMP read from BUTTON PANEL (should work):"
echo "   snmpget -v2c -c $COMMUNITY $BUTTON_IP $OID_INPUT_1"
time snmpget -v2c -c $COMMUNITY $BUTTON_IP $OID_INPUT_1
echo ""

echo "2. Testing SNMP read from LAMP CONTROLLER (clear button):"
echo "   snmpget -v2c -c $COMMUNITY $LAMP_IP $OID_INPUT_1"
time snmpget -v2c -c $COMMUNITY $LAMP_IP $OID_INPUT_1
echo ""

echo "3. Checking current metrics from service:"
echo "   curl -s http://localhost:8080/metrics | grep -E '(clear_button|snmp_errors)'"
curl -s http://localhost:8080/metrics 2>/dev/null | grep -E "(clear_button|snmp_errors)" || echo "   Service not reachable"
echo ""

echo "=== Analysis ==="
echo "- If LAMP CONTROLLER times out: Input 1 not enabled or SNMP misconfigured"
echo "- If response is slow (>0.5s): Reduce timeout further or check network"
echo "- If snmp_errors_total is high: Lamp controller SNMP has issues"
echo ""
echo "Next steps:"
echo "1. Check lamp controller web UI → Digital Inputs → Enable Input 1"
echo "2. Verify SNMP Agent Read Community = 'public'"
echo "3. Check SNMP Manager 1 IP allows Docker host"
