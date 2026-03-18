# Physical Control Service

Alert-driven automation service that receives Grafana webhooks and triggers physical device control actions.

## Overview

This service acts as a bridge between your monitoring/alerting system (Grafana) and physical devices:

```
Grafana Alert → Webhook → physical-control → Control Scripts → Physical Devices
                                              ├─ geist_control.py → Geist relay
                                              ├─ x410_control.py → X410 relays  
                                              └─ govee_control.py → Govee lights
```

## Configuration

### alert_actions.yaml

Defines routing rules that map alerts to device actions:

```yaml
alerts:
  - name: "High Temperature Alert"
    match:
      alert_name: "Temperature Above Threshold"
    actions:
      alerting:
        - device: govee
          command: "python3 /app/scripts/govee_control.py --device 'floor_lamp' --color red"
          description: "Flash red light for high temp"
      resolved:
        - device: govee
          command: "python3 /app/scripts/govee_control.py --device 'floor_lamp' --color green"
          description: "Return to green"
```

### Environment Variables

Set in `.env` file:

- `PHYSICAL_CONTROL_PORT` - Webhook receiver port (default: 5000)
- `WEBHOOK_AUTH_TOKEN` - Optional authentication token
- `GEIST_IP`, `GEIST_SNMP_RW_COMMUNITY` - Geist Watchdog config
- `X410_IP`, `X410_SNMP_COMMUNITY` - X410 relay controller config

## Endpoints

### POST /webhook

Receive Grafana alert webhooks. Expected payload:

```json
{
  "ruleName": "Temperature Above Threshold",
  "state": "alerting",
  "message": "Temperature is 95°F",
  "labels": {"room": "server_room"},
  "value": 95,
  "threshold": 85
}
```

### GET /health

Health check endpoint for monitoring.

### GET /

Service info and statistics.

## Grafana Configuration

Configure a webhook contact point in Grafana:

1. **Alerting → Contact points → Add contact point**
2. **Name**: Physical Control
3. **Integration**: Webhook
4. **URL**: `http://physical-control:5000/webhook`
5. **HTTP Method**: POST
6. **Authorization**: Bearer `<your-token>` (if using WEBHOOK_AUTH_TOKEN)

Then create alert rules that use this contact point.

## Logs

Action logs are stored in `/var/log/physical-control/actions.log` (Docker volume).

View logs:
```bash
docker logs physical-control
# or
docker exec physical-control tail -f /var/log/physical-control/actions.log
```

## Testing

Test webhook receiver manually:

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "ruleName": "Test Alert",
    "state": "alerting",
    "message": "Test message"
  }'
```

Test with authentication:

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token-here" \
  -d '{"ruleName": "Test", "state": "alerting"}'
```

## Development

Edit `alert_actions.yaml` and restart:

```bash
docker compose restart physical-control
```

No rebuild needed for config changes - only Python code changes require rebuild.
