# DPX Guest Alert Button Controller

Always-running service that monitors button inputs on one X410 device and controls blinking lamp relays on another X410 device.

## Overview

This service connects colored buttons to colored lamps for a visual alert/status indication system:

```
Button Panel (192.168.105.112)     Lamp Controller (192.168.105.111)
┌─────────────────────────┐       ┌─────────────────────────┐
│ Input 1: RED button     │──────>│ Relay 1: RED lamp       │
│ Input 2: YELLOW button  │──────>│ Relay 2: YELLOW lamp    │
│ Input 3: GREEN button   │──────>│ Relay 3: GREEN lamp     │
│ Input 4: BLUE button    │──────>│ Relay 4: BLUE lamp      │
└─────────────────────────┘       │ Input 1: BIG RED clear  │
                                  └─────────────────────────┘
```

## Behavior

- **Press colored button** → Corresponding lamp blinks at 2 Hz (default)
- **Hold colored button >10 seconds** → That specific lamp turns OFF
- **Press big red button** (on lamp controller) → All lamps turn OFF
- **Multiple lamps** can blink simultaneously at the same rate

## Architecture

**Main Controller Loop** (`button_controller.py`):
- Polls button states via SNMP every 150ms
- Detects rising edges (button presses) and hold timers
- Maintains lamp state dictionary (`{1: 'blink', 2: 'off', ...}`)
- Runs blink timer that toggles relay physical states

**Health Server** (Flask on port 8080):
- `GET /health` - Status, lamp states, statistics
- `GET /metrics` - Prometheus-compatible metrics
- `POST /clear` - Manually clear all lamps
- `POST /reset/<color>` - Reset specific lamp

## Configuration

### config.yaml

Defines device IPs, SNMP settings, and blink behavior:

```yaml
devices:
  lamp_controller:
    ip: 192.168.105.111
  button_panel:
    ip: 192.168.105.112

snmp:
  community: "public"
  poll_interval_ms: 150

blink:
  frequency_hz: 2.0  # 2 Hz = blink twice per second
  
button_hold:
  reset_threshold_seconds: 10.0
```

### Environment Variables

Set in `.env` or docker-compose.yml:

- `X410_SNMP_COMMUNITY` - SNMP community string (default: `public`)
- `BUTTON_BLINK_HZ` - Blink frequency override (default: `2.0`)
- `LOG_LEVEL` - Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`)

## Deployment

### Build and Run

```bash
# Build container
docker compose build dpx-guest-alert-button

# Start service
docker compose up -d dpx-guest-alert-button

# View logs
docker logs -f dpx-guest-alert-button
```

### Check Status

```bash
# Health check
curl http://localhost:8080/health

# Metrics
curl http://localhost:8080/metrics

# Manually clear all lamps
curl -X POST http://localhost:8080/clear

# Reset specific lamp
curl -X POST http://localhost:8080/reset/red
curl -X POST http://localhost:8080/reset/yellow
```

## Testing

### Manual Testing Procedure

1. **Test colored button → lamp blink**:
   - Press RED button on 192.168.105.112
   - Verify RED lamp on 192.168.105.111 blinks at ~2 Hz
   - Press YELLOW button
   - Verify YELLOW lamp blinks (RED continues)

2. **Test hold-to-reset**:
   - Hold GREEN button for >10 seconds
   - Verify GREEN lamp turns OFF
   - Other lamps should continue blinking

3. **Test big red button clear**:
   - Press big red button (input 1 on lamp controller)
   - Verify all lamps turn OFF

4. **Test health endpoint**:
   ```bash
   curl http://localhost:8080/health | jq
   ```
   Should show current lamp states and button press counts

5. **Test SNMP communication**:
   ```bash
   # Read button state (should be "0" or "1")
   snmpget -v2c -c public 192.168.105.112 1.3.6.1.4.1.30586.46.0.1
   
   # Read relay state
   snmpget -v2c -c public 192.168.105.111 1.3.6.1.4.1.30586.46.0.5
   ```

### Automated Testing

```bash
# Test button presses via API (simulates button behavior)
curl -X POST http://localhost:8080/clear  # Reset state

# Check metrics for button press counts
curl http://localhost:8080/metrics | grep button_presses_total
```

## Troubleshooting

### Lamps not responding to buttons

1. **Check SNMP connectivity**:
   ```bash
   docker exec dpx-guest-alert-button python3 -c "
   from pysnmp.hlapi import *
   result = next(getCmd(SnmpEngine(), CommunityData('public'),
                        UdpTransportTarget(('192.168.105.112', 161)),
                        ContextData(), ObjectType(ObjectIdentity('1.3.6.1.4.1.30586.46.0.1'))))
   print(result)
   "
   ```

2. **Check logs for SNMP errors**:
   ```bash
   docker logs dpx-guest-alert-button | grep -i error
   ```

3. **Verify device IPs are reachable**:
   ```bash
   ping 192.168.105.111
   ping 192.168.105.112
   ```

### Blink rate too fast/slow

Adjust via environment variable:

```bash
# In .env or docker-compose.yml
BUTTON_BLINK_HZ=1.0  # Slower (1 Hz = 1 blink per second)
BUTTON_BLINK_HZ=4.0  # Faster (4 Hz = 4 blinks per second)
```

Then restart:
```bash
docker compose restart dpx-guest-alert-button
```

### Lamp stuck in ON or OFF state

1. **Check lamp state via health endpoint**:
   ```bash
   curl http://localhost:8080/health | jq '.lamp_states'
   ```

2. **Manually reset**:
   ```bash
   # Reset specific lamp
   curl -X POST http://localhost:8080/reset/red
   
   # Or clear all
   curl -X POST http://localhost:8080/clear
   ```

3. **Restart service** (clears all state):
   ```bash
   docker compose restart dpx-guest-alert-button
   ```

### High SNMP error count

Check metrics:
```bash
curl http://localhost:8080/metrics | grep snmp_errors_total
```

If high:
- Verify X410 devices have SNMP enabled (web UI → SNMP settings)
- Check SNMP community string matches (`X410_SNMP_COMMUNITY` env var)
- Ensure network connectivity between container and devices
- Check X410 device logs for rate limiting or blocked requests

## Monitoring

### Grafana Dashboard (Future Enhancement)

Add Telegraf scraper for `/metrics` endpoint:

```toml
# telegraf/conf.d/button-controller.conf
[[inputs.prometheus]]
  urls = ["http://dpx-guest-alert-button:8080/metrics"]
  name_prefix = "button_"
```

Then create Grafana dashboard with:
- Lamp state indicators (gauges)
- Button press counts over time (counters)
- SNMP error rate (rate of errors per minute)
- System uptime

## Architecture Notes

### Why Polling Instead of SNMP Traps?

X410 devices don't support SNMP traps for input state changes, so we poll every 150ms. This is fast enough to catch momentary button presses without excessive network traffic (~7 SNMP requests/second per device).

### Why Software Blink Timer?

X410 has a built-in pulse feature, but software timing provides:
- Configurable blink rates (via env var)
- Synchronized blinking across multiple lamps
- Ability to change blink pattern without device reconfiguration

### State Persistence

Lamp states are NOT persisted across container restarts. After restart, all lamps default to OFF. This is intentional - press big red button or restart service to clear stuck states.

## Development

### Local Testing (Without Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export X410_SNMP_COMMUNITY=public

# Run controller
python3 button_controller.py
```

### Enable Debug Logging

```bash
# In docker-compose.yml or .env
LOG_LEVEL=DEBUG

docker compose restart dpx-guest-alert-button
docker logs -f dpx-guest-alert-button
```

Debug mode logs every poll cycle and SNMP transaction.

## License

See LICENSE file in repository root.
