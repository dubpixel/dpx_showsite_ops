# Architecture Documentation

Technical reference for dpx-showsite-ops implementation details.

---

## Complete Data Flow (Current + Phase 4)
```
┌─────────────────────────────────────────────────────────────────┐
│                     Govee Sensors                                │
│  - Broadcast BLE every ~1min (sensor readings)                  │
│  - Upload to cloud every ~10min (via gateway/phone or WiFi)     │
└──────────────────┬─────────────────────┬─────────────────────────┘
                   │                     │
                   │                     │
    ┌──────────────▼─────────┐    ┌─────▼──────────────────────┐
    │  Govee Gateway/Phone   │    │  Theengs Gateway           │
    │  OR WiFi (H6076)       │    │  (BLE receiver)            │
    │  (uploads to cloud     │    │  - Windows NUC (current)   │
    │   every ~10min)        │    │  - ESP32 (Phase 4 option)  │
    └──────────────┬─────────┘    │  Receives BLE broadcasts   │
                   │               │  every ~1min               │
                   │               └─────┬──────────────────────┘
    ┌──────────────▼─────────┐           │
    │    Govee Cloud API     │           │
    │   (AWS IoT backend)    │           │
    └──────────────┬─────────┘           │
                   │                     │
    ┌──────────────▼─────────┐    ┌─────▼──────────────────────┐
    │   govee2mqtt container │    │  ble_decoder.py            │
    │   polls API ~10min     │    │  (systemd service)         │
    │   publishes to:        │    │  decodes manufacturerdata  │
    │   gv2mqtt/sensor/...   │    │  publishes to:             │
    │                        │    │  govee/ble/{room}/{metric} │
    └──────────────┬─────────┘    └─────┬──────────────────────┘
                   │                     │
                   └──────────┬──────────┘
                              │
                   ┌──────────▼─────────┐
                   │  Mosquitto MQTT    │
                   │  localhost:1883    │
                   └──────────┬─────────┘
                              │
                   ┌──────────▼─────────┐
                   │     Telegraf       │
                   │  - subscribes to   │
                   │    both topics     │
                   │  - enriches tags   │
                   │  - adds "source"   │
                   │    (cloud/ble)     │
                   └──────────┬─────────┘
                              │
                   ┌──────────▼─────────┐
                   │     InfluxDB       │
                   │   bucket: govee    │
                   └──────────┬─────────┘
                              │
                   ┌──────────▼─────────┐
                   │      Grafana       │
                   │  - queries both    │
                   │    sources         │
                   │  - filters by      │
                   │    source tag      │
                   └────────────────────┘
```

**Cloud Path Latency**: 10-20 minutes (sensor → cloud → API → our stack)  
**BLE Path Latency**: <5 seconds (sensor → Theengs → decoder → stack)

---

## Govee Sensor Types

**BLE-only (e.g., H5051)**
- Broadcasts BLE every ~1min, uploads to cloud every ~10min via phone/gateway
- No direct LAN or cloud API access

**BLE + LAN (e.g., H6076)**
- Broadcasts BLE every ~1min, uploads to cloud every ~10min via WiFi
- Has LAN API, can be controlled directly over local network

---

## MQTT Topics

### Cloud (current - working)
```
gv2mqtt/sensor/sensor-{MAC}-sensortemperature/state  → float
gv2mqtt/sensor/sensor-{MAC}-sensorhumidity/state     → float
```

### BLE (Phase 4 - planned)
```
home/TheengsGateway/BTtoMQTT/{MAC}      → JSON with manufacturerdata
govee/ble/{room}/temperature             → float (°C)
govee/ble/{room}/humidity                → float (%)
govee/ble/{room}/battery                 → int (%)
```

---

## H5051 BLE Decode

Theengs publishes raw hex in `manufacturerdata`. ble_decoder.py parses:

| Bytes | Field | Calculation |
|-------|-------|-------------|
| 3-4 | Temperature | `(byte[3] \| byte[4] << 8) / 100.0` = °C |
| 5 | Humidity | `byte[5] / 10.0` = % |
| 7 | Battery | `byte[7]` = % |

Example: `88ec004e06f00864e00101`
- Temp: `0x064E` = 1614 → 16.14°C
- Humidity: `0xF0` = 240 → 24.0%
- Battery: `0x64` = 100%

---

## Telegraf Tag Enrichment

**For both cloud and BLE paths:**

1. **Regex processor** extracts `device_id` and `sensor_type` from topic
2. **Enum processor** maps `device_id` → `device_name` and `room`
3. **Source tag** differentiates cloud vs BLE data
4. Device mappings auto-updated hourly via `scripts/update-device-map.sh`

**Result in InfluxDB**: 
- Tags: `device_name`, `room`, `sensor_type`, `source`
- Field: `value` (the actual reading)

---

## Docker Volumes

Volumes prefixed with directory name: `dpx_govee_stack_grafana-data`

**⚠️ Critical**: Renaming directory = new volumes = data loss. Use `iot backup` first.

---

## Known Issues

### govee2mqtt AWS IoT timeouts
**Cause**: IPv6 enabled but can't route to internet  
**Fix**:
```bash
sudo sysctl -w net.ipv6.conf.eth0.disable_ipv6=1
echo "net.ipv6.conf.eth0.disable_ipv6=1" | sudo tee -a /etc/sysctl.conf
```

### iot command fails
**Cause**: Symlink doesn't preserve path  
**Fix**: Use wrapper script (see setup.sh or README troubleshooting)

### Telegraf parse errors
Harmless - govee2mqtt publishes status messages on sensor topics

### Hourly restarts
Not a crash - `update-device-map.sh` cron restarts Telegraf when config changes

---

## Key Facts

- **Sensor broadcast**: BLE every ~1 minute
- **Cloud upload**: Every ~10 minutes
- govee2mqtt uses `network_mode: host` (required for AWS IoT)
- Devices MUST be assigned rooms in Govee app
- InfluxDB stores timestamps in UTC
- Docker logs lost on `compose down/up` (use `restart` instead)
- govee2mqtt API: `localhost:8056/api/devices` returns device JSON
- Phase 4 works with Theengs on Windows OR ESP32

---

See ROADMAP.md for phase details and timeline.
