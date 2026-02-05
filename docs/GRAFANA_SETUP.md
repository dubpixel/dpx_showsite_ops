# Grafana Setup Guide

Manual configuration steps after running `iot up`.

---

## Connect InfluxDB Datasource

1. Open Grafana: http://<server-ip>:3000 (admin/grafanapass123)
2. Go to: Configuration (⚙️) → Data sources → Add data source
3. Select: **InfluxDB**
4. Configure:
   - **Name**: InfluxDB
   - **Query Language**: Flux
   - **URL**: http://influxdb:8086
   - **Auth**: Toggle OFF all options
   - **Organization**: home
   - **Token**: my-super-secret-token
   - **Default Bucket**: govee
5. Click: **Save & Test** (should show green checkmark)

---

## Create Your First Dashboard

### Find Your Room Names First

Query to see available rooms:
```flux
from(bucket: "govee")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "mqtt_consumer")
  |> keep(columns: ["room"])
  |> distinct(column: "room")
```

Or from CLI: `iot query 1h 100 | grep room`

### Create Dashboard

1. Go to: Dashboards → New → New Dashboard → Add visualization
2. Select datasource: **InfluxDB**
3. **Temperature query**:
```flux
   from(bucket: "govee")
     |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
     |> filter(fn: (r) => r.sensor_type == "temperature")
     |> filter(fn: (r) => r.room == "your_room_name")
```
4. Add another panel for **Humidity**:
```flux
   from(bucket: "govee")
     |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
     |> filter(fn: (r) => r.sensor_type == "humidity")
     |> filter(fn: (r) => r.room == "your_room_name")
```
5. Save dashboard

---

## Enable Public Dashboards

**Requires**: Cloudflare Tunnel (`iot tunnel`) or port forwarding

1. Open your dashboard
2. Click: Share icon (top right)
3. Tab: Public dashboard
4. Toggle: Enable public dashboard
5. Click: Save sharing configuration
6. Copy: The public URL

---

## Backup Dashboards
```bash
# Backup entire Grafana volume
iot backup

# Export dashboard as JSON (manual)
# Dashboard → ⚙️ → JSON Model → Copy JSON
# Save to: dashboards/my-dashboard.json
# Commit to git for version control
```

---

## Troubleshooting

**"Error reading InfluxDB"**
- Verify token: `iot env | grep TOKEN`
- Check InfluxDB running: `iot status`
- Test query: `iot query 1h 5`

**"No data points"**
- Check MQTT: `iot mqtt "gv2mqtt/#" 10`
- Devices must be assigned to rooms in Govee app
- Refresh mappings: `iot update`

**Dashboard won't save**
- Check disk space: `df -h`
- Verify volume: `docker volume ls | grep grafana`
