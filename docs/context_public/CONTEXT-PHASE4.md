# dpx-showsite-ops - Phase 4 BLE Integration Context
# Last updated: 2026-02-06
# Upload this file to continue Phase 4 BLE gateway work

---

## CURRENT STATUS - PHASE 4

**Phase 3: COMPLETE ✅**
- Cloud monitoring stack fully operational
- Repository structured and documented
- Grafana dashboards showing cloud data

**Phase 4: IN PROGRESS 🔄**
- ✅ ESP32 gateway deployed (192.168.1.213) - OpenMQTTGateway v1.8.1
- ✅ Theengs Gateway deployed (Windows NUC, 192.168.1.68) - Backup option
- ✅ H5051 sensors analyzed (manufacturer data decoding required)
- ✅ H5074 sensor evaluated (UNRELIABLE - retire or replace)
- ✅ Cloud data flowing to InfluxDB (2 sensors with full tags)
- ⏳ **PENDING: Deploy ble_decoder.py systemd service**
- ⏳ **PENDING: Update Telegraf config for dual-source (cloud + BLE)**
- ⏳ **PENDING: Update Grafana dashboards with source filter**

---

## ENVIRONMENT

- **VM**: Ubuntu Server 24.04 on Hyper-V
- **Hostname**: dpx-showsite-ops
- **IP**: 192.168.1.100 (static)
- **User**: dubpixel
- **Stack dir**: ~/dpx_govee_stack/
- **GitHub**: https://github.com/dubpixel/dpx_showsite_ops

---

## NETWORK MAP (192.168.1.x)

- **.1**: Router
- **.16**: Philips Hue bridge
- **.28**: Govee H6076 Floor Lamp
- **.68**: Windows NUC (Hyper-V host, Theengs Gateway)
- **.100**: dpx-showsite-ops VM (main stack)
- **.213**: ESP32 BLE Gateway (OMG_ESP32_FTH_BLE)
- **.220**: User's Mac

---

## BLE GATEWAYS

### ESP32 Gateway (Primary)
- **IP**: 192.168.1.213
- **Hostname**: OMG_ESP32_FTH_BLE
- **Firmware**: OpenMQTTGateway v1.8.1 (esp32feather-ble)
- **MQTT Topics**: 
  - Publishes: `dpx-gateway1/dpx_showsite_gateway1/BTtoMQTT/#`
  - Config: `dpx-gateway1/dpx_showsite_gateway1/commands/MQTTtoBT/config`
- **Status**: ✅ Live and publishing

**CRITICAL CONFIG**: `pubadvdata` setting resets on ESP32 reboot!
```bash
# Must re-enable after each gateway restart
mosquitto_pub -h localhost \
  -t "dpx-gateway1/dpx_showsite_gateway1/commands/MQTTtoBT/config" \
  -m '{"pubadvdata":true}'

# Verify data flowing
iot mqtt "dpx-gateway1/dpx_showsite_gateway1/BTtoMQTT" 5
```

### Theengs Gateway (Fallback)
- **Host**: Windows NUC (192.168.1.68)
- **MQTT Topics**: `home/TheengsGateway/BTtoMQTT/#`
- **Status**: ✅ Running
- **Limitation**: Does not decode H5051 (not in library)
- **Use Case**: Backup gateway, supports H5074/H5075 decoding

---

## GOVEE SENSORS

### H5051 Sensors (BLE-only, RECOMMENDED)

**Sensor 1 - Studio 5051 Down**
- **Cloud ID**: 33FA4381ECA1010A
- **BLE MAC**: 4381ECA1010A
- **Room**: studown (Studio Downstairs)
- **Name**: "Studio 5051 Down"
- **Cloud Status**: ✅ Full tags in InfluxDB (device_name, room)
- **BLE Broadcast**: Every ~1min with manufacturer data (88ec00...)
- **Theengs Support**: ❌ Not in decoder library
- **Solution**: Custom decoder required (simple)

**Sensor 2 - New H5051**
- **Cloud ID**: 19544381ECB1405D
- **BLE MAC**: 4381ECB1405D
- **Room**: Unassigned (needs Govee app configuration)
- **Cloud Status**: ⚠️ Partial tags (missing room assignment)
- **BLE Broadcast**: Every ~1min with manufacturer data

**H5051 Advantages**:
- Reliable BLE broadcasts every ~1 minute
- Simple manufacturer data format
- Stable packet structure
- Good for real-time monitoring

### H5074 Sensor (PROBLEMATIC - RETIRE)
- **BLE MAC**: A4C138504E6F
- **Issue**: Mostly broadcasts iBeacon ads (length 56) with no data
- **Data Packets**: Rarely sends actual sensor data (length 40)
- **Frequency**: Minutes between useful broadcasts
- **Recommendation**: Replace with H5075 or keep using H5051

### H6076 Floor Lamp (BLE + LAN)
- **Cloud ID**: 17A8D003C1061976
- **BLE MAC**: D003C1061976
- **LAN IP**: 192.168.1.28
- **Type**: WiFi connected, supports LAN API
- **BLE Broadcast**: Manufacturer data format: 4388ec...

---

## SENSOR COMPARISON

| Model | BLE Reliability | Theengs Support | Recommendation |
|-------|----------------|-----------------|----------------|
| **H5051** | ✅ Excellent (1min) | ❌ No | Use with custom decoder |
| **H5074** | ❌ Poor (iBeacon spam) | ✅ Yes | **NOT RECOMMENDED** |
| **H5075** | ✅ Excellent | ✅ Yes | **Best for future purchases** |
| H5101/H5102 | ✅ Good | ✅ Yes | Good alternative |

---

## H5051 MANUFACTURER DATA DECODING

### Packet Format
**Example**: `88ec00TTTTHHBB`

| Bytes | Field | Format | Example | Decoded |
|-------|-------|--------|---------|---------|
| 0-1 | Header | - | 88ec | Govee identifier |
| 2 | Packet Type | - | 00 | Standard data |
| 3-4 | Temperature | int16 LE ÷ 100 | 0fa4 | 0x0fa4 = 4004 = 40.04°C |
| 5-6 | Humidity | int16 LE ÷ 100 | 1388 | 0x1388 = 5000 = 50.00% |
| 7 | Battery | uint8 | 64 | 100% |

### Python Decoder Template
```python
def decode_h5051_manufacturer_data(hex_string):
    """
    Decode H5051 manufacturer data from hex string
    Returns: dict with temp_c, humidity, battery
    """
    # Convert hex string to bytes
    data = bytes.fromhex(hex_string)
    
    # Validate header
    if len(data) < 8 or data[0:2] != b'\x88\xec':
        return None
    
    # Extract fields (little-endian)
    temp_raw = int.from_bytes(data[3:5], 'little', signed=True)
    humidity_raw = int.from_bytes(data[5:7], 'little')
    battery = data[7]
    
    return {
        'temperature': temp_raw / 100.0,  # °C
        'humidity': humidity_raw / 100.0,  # %
        'battery': battery  # %
    }
```

---

## CURRENT DATA FLOW

### Cloud Path (Working ✅)
```
Govee Sensors
  ↓ BLE broadcast (~1min)
Govee Phone/Gateway
  ↓ Upload to cloud (~10min)
Govee Cloud API
  ↓ govee2mqtt polls (~10min)
MQTT (gv2mqtt/sensor/+/state)
  ↓ Telegraf subscribes
InfluxDB (bucket: govee, source=cloud)
  ↓ Grafana queries
Dashboard
```

**Latency**: 10-20 minutes
**Sensors Working**: 2/4 (1 with full tags, 1 missing room)

### BLE Path (Hardware Ready, Software Pending)
```
Govee Sensors
  ↓ BLE broadcast (~1min)
ESP32/Theengs Gateway
  ↓ Publish raw manufacturer data
MQTT (dpx-gateway1/.../BTtoMQTT/# or home/TheengsGateway/...)
  ↓ ble_decoder.py subscribes (NOT YET DEPLOYED)
  ↓ Decode manufacturer data
  ↓ Map BLE MAC to room
MQTT (govee/ble/{room}/{metric})
  ↓ Telegraf subscribes (NOT YET CONFIGURED)
InfluxDB (bucket: govee, source=ble)
  ↓ Grafana queries
Dashboard
```

**Target Latency**: <5 seconds
**Status**: Hardware deployed, software pending

---

## MQTT TOPICS

### Cloud Topics (Current - Working)
```
gv2mqtt/sensor/sensor-33FA4381ECA1010A-sensortemperature/state  → float
gv2mqtt/sensor/sensor-33FA4381ECA1010A-sensorhumidity/state     → float
```

### BLE Topics (Raw from Gateways)
```
# ESP32 Gateway
dpx-gateway1/dpx_showsite_gateway1/BTtoMQTT/4381ECA1010A
  → JSON: {"id":"43:81:EC:A1:01:0A","manufacturerdata":"88ec00..."}

# Theengs Gateway (Fallback)
home/TheengsGateway/BTtoMQTT/4381ECA1010A
  → JSON: {"id":"43:81:EC:A1:01:0A","manufacturerdata":"88ec00..."}
```

### BLE Topics (Decoded - Target Output)
```
govee/ble/studown/temperature  → 25.48
govee/ble/studown/humidity     → 51.19
govee/ble/studown/battery      → 100
```

---

## PHASE 4 REMAINING TASKS

### 1. Create ble_decoder.py Service

**Requirements**:
- Subscribe to both ESP32 and Theengs MQTT topics
- Decode H5051 manufacturer data (88ec00... format)
- Map BLE MACs to rooms using device_map.json
- Publish decoded values to govee/ble/{room}/{metric}
- Run as systemd service with auto-restart

**Files Needed**:
```
~/dpx_govee_stack/
├── ble_decoder.py                    # Main decoder script
├── ble_decoder.service               # systemd unit file
└── device_map.json                   # BLE MAC to room mapping
```

**BLE MAC Mapping** (device_map.json):
```json
{
  "4381ECA1010A": {"room": "studown", "name": "Studio 5051 Down"},
  "4381ECB1405D": {"room": "unassigned", "name": "New H5051"},
  "D003C1061976": {"room": "unassigned", "name": "H6076 Floor Lamp"}
}
```

### 2. Update Telegraf Configuration

**Modify**: `scripts/update-device-map.sh`

Add BLE input section:
```toml
# BLE source input
[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  topics = [
    "govee/ble/+/temperature",
    "govee/ble/+/humidity",
    "govee/ble/+/battery"
  ]
  data_format = "value"
  data_type = "float"
  topic_tag = "topic"
  
  # Tag as BLE source
  [inputs.mqtt_consumer.tags]
    source = "ble"

# Extract room and metric from topic
[[processors.regex]]
  [[processors.regex.tags]]
    key = "topic"
    pattern = "govee/ble/([^/]+)/([^/]+)"
    replacement = "${1}"
    result_key = "room"
  
  [[processors.regex.tags]]
    key = "topic"
    pattern = "govee/ble/([^/]+)/([^/]+)"
    replacement = "${2}"
    result_key = "sensor_type"
```

**Tag cloud input with source=cloud**:
```toml
# Cloud source input (existing)
[[inputs.mqtt_consumer]]
  # ... existing config ...
  [inputs.mqtt_consumer.tags]
    source = "cloud"
```

### 3. Update Grafana Dashboards

**Add Source Filter**:
- Create variable: `source` (cloud, ble, both)
- Update queries to filter by source tag
- Add data availability badges (cloud: 10-20min, ble: <5sec)
- Show which source is active per sensor

**Query Example**:
```flux
from(bucket: "govee")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor")
  |> filter(fn: (r) => r["source"] == v.source or v.source == "both")
  |> filter(fn: (r) => r["room"] == "studown")
```

### 4. Testing & Validation

- [ ] Verify BLE data flowing to InfluxDB
- [ ] Compare cloud vs BLE values for accuracy
- [ ] Monitor BLE latency (<5 sec target)
- [ ] Test failover (ESP32 down → Theengs backup)
- [ ] Verify source tagging in InfluxDB
- [ ] Check Grafana dashboard filtering

### 5. Documentation

- [ ] Update CHANGELOG.md with Phase 4 completion
- [ ] Document pubadvdata reset issue in README
- [ ] Add ble_decoder.py usage guide
- [ ] Document BLE troubleshooting steps

---

## TROUBLESHOOTING

### ESP32 Gateway Issues

**pubadvdata resets on reboot**:
```bash
# Symptom: No manufacturer data in MQTT messages
# Fix: Re-enable after each ESP32 restart
mosquitto_pub -h localhost \
  -t "dpx-gateway1/dpx_showsite_gateway1/commands/MQTTtoBT/config" \
  -m '{"pubadvdata":true}'
```

**Verify BLE data flowing**:
```bash
iot mqtt "dpx-gateway1/dpx_showsite_gateway1/BTtoMQTT" 5
# Should see JSON with manufacturerdata field
```

### Telegraf Parse Errors

**Error**: `strconv.ParseFloat: parsing 'Available': invalid syntax`
**Cause**: govee2mqtt status messages on sensor topics
**Impact**: Harmless, data still flows
**Fix**: Will be filtered in Phase 4 Telegraf update with topic filtering

### Mosquitto Permissions

If Mosquitto fails to start:
```bash
sudo chown -R 1883:1883 ~/dpx_govee_stack/mosquitto/data/
sudo chmod -R 755 ~/dpx_govee_stack/mosquitto/data/
iot restart mosquitto
```

---

## CLI SHORTCUTS

```bash
# Service management
iot up                    # Start all services
iot down                  # Stop all services
iot restart <service>     # Restart a service
iot ps                    # Show service status
iot logs <service>        # Show logs

# BLE Gateway management
iot mqtt "dpx-gateway1/dpx_showsite_gateway1/BTtoMQTT" 5  # Monitor ESP32
iot mqtt "home/TheengsGateway/BTtoMQTT" 5                 # Monitor Theengs
mosquitto_pub -h localhost -t "dpx-gateway1/dpx_showsite_gateway1/commands/MQTTtoBT/config" -m '{"pubadvdata":true}'  # Enable pubadvdata

# Device management
iot devices               # List devices from govee2mqtt
iot update                # Regenerate Telegraf config from device_map.json
iot backup                # Backup config + data to ~/backups/

# Monitoring
iot query                 # Query InfluxDB data
iot web                   # Show all service URLs
```

---

## INFLUXDB QUERIES

**View cloud data**:
```flux
from(bucket: "govee")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor")
  |> filter(fn: (r) => r["source"] == "cloud")
  |> filter(fn: (r) => r["room"] == "studown")
```

**View BLE data** (after Phase 4):
```flux
from(bucket: "govee")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor")
  |> filter(fn: (r) => r["source"] == "ble")
  |> filter(fn: (r) => r["room"] == "studown")
```

**Compare sources**:
```flux
from(bucket: "govee")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor")
  |> filter(fn: (r) => r["room"] == "studown")
  |> filter(fn: (r) => r["sensor_type"] == "temperature")
  |> pivot(rowKey: ["_time"], columnKey: ["source"], valueColumn: "_value")
```

---

## NEXT SESSION PRIORITIES

1. **Create ble_decoder.py**
   - Write decoder script with H5051 support
   - Create systemd service file
   - Test locally before deploying

2. **Deploy and Test**
   - Install as systemd service
   - Monitor MQTT for decoded topics
   - Verify data accuracy vs cloud

3. **Update Telegraf**
   - Modify update-device-map.sh
   - Add BLE input section
   - Tag both sources appropriately
   - Restart Telegraf, verify dual input

4. **Update Grafana**
   - Add source filter variable
   - Modify dashboard queries
   - Test filtering (cloud, ble, both)

5. **Sensor Management**
   - Assign new H5051 sensor to room in Govee app
   - Run `iot update` to regenerate config
   - Consider retiring H5074 or relocating

---

## REFERENCE LINKS

- **Main repo**: https://github.com/dubpixel/dpx_showsite_ops
- **OpenMQTTGateway**: https://docs.openmqttgateway.com
- **Theengs Decoder**: https://github.com/theengs/decoder
- **H5051 Protocol**: Community reverse engineering (not officially documented)

---

**REMEMBER**: This VM is production infrastructure for DPX shows. Test changes thoroughly before deploying. Keep backups current with `iot backup`!
