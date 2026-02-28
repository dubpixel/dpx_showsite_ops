# dpx-showsite-ops - System Reference
# Last updated: 2026-02-16
# Upload this file for system context (network, sensors, configs, stack operations)
# **For tasks/roadmap**: See [ROADMAP.md](../ROADMAP.md)
# **For set-schedule app development**: See [set-schedule-development.md](set-schedule-development.md)
---

## SYSTEM OVERVIEW

### Environment

- **VM**: Ubuntu Server 24.04 on Hyper-V (NUC Windows host)
- **Hostname**: dpx-showsite-ops
- **mDNS**: dpx-showsite-ops.local
- **LOCAL IP**: 192.168.1.100 (static)
- **User**: dubpixel
- **Stack dir**: ~/dpx_govee_stack/ (local folder name, GitHub repo is dpx_showsite_ops)
- **GitHub**: https://github.com/dubpixel/dpx_showsite_ops
- **Backups**: ~/backups/

### Network Map (192.168.1.x)

- **.1**: Router
- **.16**: Philips Hue bridge
- **.28**: Govee H6076 Floor Lamp
- **.68**: Windows NUC (Hyper-V host, Theengs Gateway)
- **.100**: dpx-showsite-ops VM (main stack)
- **.213**: ESP32 BLE Gateway (OMG_ESP32_FTH_BLE)
- **.220**: User's Mac

### Installed Services

| Service | Status | Purpose |
|---------|--------|---------|
| SSH | enabled | Remote access |
| avahi-daemon | enabled | mDNS (*.local hostnames) |
| cloudflared | installed | Cloudflare tunnels (manual start) |
| tailscale | enabled | Mesh VPN |
| Docker | enabled | Container runtime |

---

## ACCESS & CREDENTIALS

### Service URLs & Credentials

- **Grafana**: (see .env) @ http://<server-ip>:3000
- **InfluxDB**: (see .env) @ http://<server-ip>:8086
- **MQTT**: anonymous @ <server-ip>:1883
- **Govee**: (see .env — do NOT commit)
- **govee2mqtt web API**: http://localhost:8056/api/devices

### Remote Access

- **SSH**: dubpixel@dpx-showsite-ops (192.168.1.100)
- **Tailscale**: Installed on VM + user's Mac, mesh VPN for SSH from anywhere
- **Cloudflare Tunnel**: `iot tunnel` for temporary public dashboard sharing
- **Public dashboard**: Requires Cloudflare Tunnel or port forwarding to work

### Git Credentials

- **Git User**: i@dubpixel.tv / dubpixel
- **GitHub**: https://github.com/dubpixel/dpx_showsite_ops

**IMPORTANT**: All service passwords are in .env file (not tracked in git)

---

## HARDWARE

### BLE Gateways

#### ESP32 Gateway (Primary)
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

#### Theengs Gateway (Fallback)
- **Host**: Windows NUC (192.168.1.68)
- **MQTT Topics**: `home/TheengsGateway/BTtoMQTT/#`
- **Status**: ✅ Running
- **Limitation**: Does not decode H5051 (not in library)
- **Use Case**: Backup gateway, supports H5074/H5075 decoding

**Monitor Gateways:**
```bash
iot mqtt "dpx-gateway1/dpx_showsite_gateway1/BTtoMQTT" 5  # ESP32
iot mqtt "home/TheengsGateway/BTtoMQTT" 5                 # Theengs
```

### Govee Sensors

#### Current Device Naming & Mappings

Updated device names in Govee app/API. Current mappings from update-device-map.sh:
- **33FA4381ECA1010A**: 5051_studio_down (studiodown)
- **19544381ECB1405D**: 5051_studio_up (studioup)
- **17A8D003C1061976**: floor_lamp_upper (studiodown)
- **D278A4C138504E6F**: h5074_4e6f (studiodown)

Device map updates logged to: `~/dpx_govee_stack/scripts/update-device-map.log`

#### H5051 Sensors (BLE-only, RECOMMENDED)

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

#### H5074 Sensor (PROBLEMATIC - RETIRE)
- **BLE MAC**: A4C138504E6F
- **Issue**: Mostly broadcasts iBeacon ads (length 56) with no data
- **Data Packets**: Rarely sends actual sensor data (length 40)
- **Frequency**: Minutes between useful broadcasts
- **Recommendation**: Replace with H5075 or keep using H5051

#### H6076 Floor Lamp (BLE + LAN)
- **Cloud ID**: 17A8D003C1061976
- **BLE MAC**: D003C1061976
- **LAN IP**: 192.168.1.28
- **Type**: WiFi connected, supports LAN API
- **BLE Broadcast**: Manufacturer data format: 4388ec...

### Sensor Comparison

| Model | BLE Reliability | Theengs Support | Recommendation |
|-------|----------------|-----------------|----------------|
| **H5051** | ✅ Excellent (1min) | ❌ No | Use with custom decoder |
| **H5074** | ❌ Poor (iBeacon spam) | ✅ Yes | **NOT RECOMMENDED** |
| **H5075** | ✅ Excellent | ✅ Yes | **Best for future purchases** |
| H5101/H5102 | ✅ Good | ✅ Yes | Good alternative |

---

## DOCKER STACK

### File Structure

```
~/dpx_govee_stack/              (local directory)
├── README.md                   ← Quick start guide
├── CHANGELOG.md                ← Version history
├── VERSION                     ← Current version number
├── docker-compose.yml          ← Main stack definition
├── Dockerfile.ble-decoder      ← BLE decoder container build
├── requirements-ble-decoder.txt ← Python dependencies for BLE decoder
├── .env                        ← Secrets (gitignored)
├── .env.example                ← Template for users
├── .gitignore                  ← Excludes secrets, logs, backups
├── setup.sh                    ← Initial deployment script
├── mosquitto/
│   └── config/
│       └── mosquitto.conf
├── telegraf/
│   ├── telegraf.conf           ← Auto-generated by update-device-map.sh
│   └── backups/                ← Last 10 config backups
├── scripts/
│   ├── manage.sh               ← Main management CLI
│   ├── ble_decoder.py          ← BLE decoder Python script
│   ├── update-device-map.sh    ← Hourly device mapping updates
│   └── update-device-map.log   ← Update script log
└── docs/
    ├── ARCHITECTURE.md         ← Technical deep dive
    ├── ROADMAP.md              ← Phase plans and timeline
    ├── GRAFANA_SETUP.md        ← Manual Grafana configuration guide
    └── SETUP_GUIDE_COMPLETE.md ← Complete idiot-proof guide from zero
└── images/
    ├── architecture.png        ← Architecture diagram
    ├── grafana-dashboard.png   ← Screenshot
    ├── logo.png                ← Project logo
    └── dubpixel_identicon.png  ← Identity icon
```

**Phase 6 Integration (🚧 In Progress)**:
```
└── services/
    └── set-schedule/           ← Sean's repo as git submodule
        ├── (festival schedule app)
        └── Dockerfile          ← Integrated in docker-compose stack
```

**Not tracked in git** (gitignored):
- .env (actual credentials)
- .env_bu (backup)
- *.log files
- backups/
- hostname
- *.backup files

### Volume Naming & Operations

#### Volume Naming

Docker volumes are prefixed with directory name:
- `dpx_govee_stack_grafana-data`
- `dpx_govee_stack_influxdb-data`
- `dpx_govee_stack_govee2mqtt-data`

**CRITICAL**: Renaming directory creates NEW volumes = data loss. Use `iot backup` first.

#### Docker Operations

- `/etc/docker/daemon.json`: `{"ipv6": false, "fixed-cidr-v6": ""}`
- Docker bridge sometimes goes DOWN after network changes, fix: `sudo systemctl restart docker`
- Full recreate needed for .env changes: `docker compose down && docker compose up -d`
- Restart sufficient for telegraf.conf changes: `docker compose restart telegraf`
- **Logs are lost on container recreate** (down/up cycle) - use `iot restart` when possible

---

## SERVICES CONFIGURATION

### Telegraf

#### Configuration Structure

Split into modular structure:
- `telegraf.conf`: Static base config (agent, outputs, inputs, BLE processors)
- `conf.d/device-mappings.conf`: Dynamic enum mappings (regenerated by update-device-map.sh)

Docker container loads both files via --config-directory flag.

#### Key Configuration Details

- Fixed enum processor deprecation: changed `tag` to `tags` array
- TZ environment variable loaded from .env
- BLE regex processor added for demo_showsite topics (extracts source_node, room, device_name, sensor_type)

**View config:**
```bash
iot conf  # Show telegraf configuration
```

### Mosquitto

**Configuration file**: `mosquitto/config/mosquitto.conf`

**Permissions fix** (if Mosquitto fails to start):
```bash
sudo chown -R 1883:1883 ~/dpx_govee_stack/mosquitto/data/
sudo chmod -R 755 ~/dpx_govee_stack/mosquitto/data/
iot restart mosquitto
```

**Key notes:**
- Allows anonymous connections on port 1883
- MQTT wildcard `+` catches non-numeric topics causing parse errors (harmless)

### govee2mqtt

**Configuration:**
- Uses `network_mode: host` (inherits host networking)
- Publishes to `gv2mqtt/#` topics (NOT `govee2mqtt/#`)
- Web API available at `http://localhost:8056/api/devices`

**Environment variables:**
- `RUST_LOG`: Changes need full `down/up` cycle, not just restart
- Credentials loaded from .env (do NOT commit)

**Key notes:**
- Govee API requires devices assigned to rooms to return data
- Update frequency: polls cloud API every ~10 minutes

### InfluxDB

**Access:**
- URL: `http://influxdb:8086` (internal) or `http://<server-ip>:8086` (external)
- Organization: `home`
- Token: `my-super-secret-token` (from .env)
- Default Bucket: `sensors`

**Key notes:**
- Timestamps are UTC — adjust for local timezone in queries
- Volume: `dpx_govee_stack_influxdb-data`

**Emergency data wipe:**
```bash
iot nuke  # DELETE all data in sensors bucket
```

### Grafana

#### Access & Credentials

- URL: `http://<server-ip>:3000`
- Credentials: See .env file
- Version: OSS 12.3.2 (no Enterprise features)

#### InfluxDB Datasource Setup

1. Configuration → Data sources → Add data source → InfluxDB
2. Configure:
   - Query Language: **Flux**
   - URL: **http://influxdb:8086**
   - Organization: **home**
   - Token: **my-super-secret-token**
   - Default Bucket: **sensors**
3. Save & Test

#### Dashboard Configuration

See [GRAFANA_SETUP.md](../GRAFANA_SETUP.md) for detailed dashboard configuration.

**Dashboard features:**
- Time series panels, gauges, stat panels
- Flux queries with custom display names via map()

**Branding note:**
- OSS version does not support custom logos/branding
- Enterprise license required (~$299/mo) for branding features

---

## DATA ARCHITECTURE

### Current Data Flow

#### Cloud Path (Working ✅)

```
Govee Sensors
  ↓ BLE broadcast (~1min)
Govee Phone/Gateway
  ↓ Upload to cloud (~10min)
Govee Cloud API
  ↓ govee2mqtt polls (~10min)
MQTT (gv2mqtt/sensor/+/state)
  ↓ Telegraf subscribes
InfluxDB (bucket: sensors, source=gv_cloud)
  ↓ Grafana queries
Dashboard
```

**Latency**: 10-20 minutes
**Sensors Working**: 2/4 (1 with full tags, 1 missing room)

#### BLE Path (Hardware Ready, Software Deployed)

```
Govee Sensors
  ↓ BLE broadcast (~1min)
ESP32/Theengs Gateway
  ↓ Publish raw manufacturer data
MQTT (dpx-gateway1/.../BTtoMQTT/# or home/TheengsGateway/...)
  ↓ ble_decoder.py subscribes
  ↓ Decode manufacturer data
  ↓ Map BLE MAC to room
MQTT (demo_showsite/dpx_ops_decoder/{source_node}/{room}/{device_name}/{metric})
  ↓ Telegraf subscribes
InfluxDB (bucket: sensors, source=dpx_ops_decoder)
  ↓ Grafana queries
Dashboard
```

**Target Latency**: <5 seconds
**Status**: ✅ Dockerized and running as `ble-decoder` service
**Decoder details:**
- Container: ble-decoder (auto-starts with stack)
- Management: `iot ble-up/down/restart/rebuild/logs` or `iot lb`
- Manual debug mode: `iot ble-decode` (requires python3-paho-mqtt on host)
- Subscribes to both ESP32 (`+/BTtoMQTT/#`) and Theengs (`home/TheengsGateway/BTtoMQTT/#`) gateway patterns
- Both dpx_ops_1 (ESP32) and TheengsGateway sources operational
- Uses `retain=True` on published topics
- **Critical**: ESP32 gateway `pubadvdata` setting resets on reboot - must re-enable or manufacturerdata stops flowing

### MQTT Topics

#### Cloud Topics (Current - Working)

```
gv2mqtt/sensor/sensor-33FA4381ECA1010A-sensortemperature/state  → float
gv2mqtt/sensor/sensor-33FA4381ECA1010A-sensorhumidity/state     → float
```

#### BLE Topics (Raw from Gateways)

```
# ESP32 Gateway
dpx-gateway1/dpx_showsite_gateway1/BTtoMQTT/4381ECA1010A
  → JSON: {"id":"43:81:EC:A1:01:0A","manufacturerdata":"88ec00..."}

# Theengs Gateway (Fallback)
home/TheengsGateway/BTtoMQTT/4381ECA1010A
  → JSON: {"id":"43:81:EC:A1:01:0A","manufacturerdata":"88ec00..."}
```

#### BLE Topics (Decoded - Current Output)

```
demo_showsite/dpx_ops_decoder/{source_node}/{room}/{device_name}/temperature  → 25.48
demo_showsite/dpx_ops_decoder/{source_node}/{room}/{device_name}/humidity     → 51.19
demo_showsite/dpx_ops_decoder/{source_node}/{room}/{device_name}/battery      → 100
```

**Topic path breakdown:**
- **Inbound** (gateway → decoder): `{base}/{gateway_name}/BTtoMQTT/{MAC}`
- **Outbound** (decoder → Telegraf): `{site}/dpx_ops_decoder/{source_node}/{room}/{device_name}/{MAC}/{metric}`
- Room and device_name come from Govee API, source_node extracted from inbound topic

---

## MANAGEMENT

### Management CLI (iot command)

Symlinked: /usr/local/bin/iot → wrapper script → ~/dpx_govee_stack/scripts/manage.sh

**Installation**: Automatically installed by [setup.sh](../../setup.sh) with auto-detected path.

<details>
<summary>Manual installation (if needed)</summary>

Wrapper script required, NOT direct symlink:
```bash
sudo tee /usr/local/bin/iot > /dev/null << 'WRAPPER'
#!/bin/bash
cd /home/dubpixel/dpx_govee_stack
exec /home/dubpixel/dpx_govee_stack/scripts/manage.sh "$@"
WRAPPER
sudo chmod +x /usr/local/bin/iot
```

**Note**: Replace `/home/dubpixel/dpx_govee_stack` with your actual installation directory path.
</details>

**Commands:**
```bash
# Stack control
iot up                          # Start all containers
iot down                        # Stop all containers
iot restart [service]           # Restart service(s)
iot status                      # Show container status
iot validate                    # Check stack configuration

# Logs (n = line count, default 30)
iot lg [n]                      # govee2mqtt logs
iot lt [n]                      # telegraf logs
iot lm [n]                      # mosquitto logs
iot li [n]                      # influxdb logs
iot lf [n]                      # grafana logs
iot lb [n]                      # ble-decoder logs
iot ls [n]                      # set-schedule logs (Phase 6)
iot la [n]                      # all logs (default 10 each)

# BLE Decoder (Python BLE-to-MQTT decoder service)
iot ble-up                      # Start BLE decoder service
iot ble-down                    # Stop BLE decoder service
iot ble-restart                 # Restart BLE decoder
iot ble-rebuild                 # Rebuild and restart
iot ble-status                  # Show container status
iot ble-logs [n]                # View logs (same as iot lb)
iot ble-follow                  # Follow logs in real-time
iot ble-decode                  # Run manually (debug mode, requires python3-paho-mqtt)

# Data
iot query [range] [rows]        # Query InfluxDB (default: 30m, 5 rows)
iot mqtt [topic] [count]        # Subscribe to MQTT topics
iot nuke                        # DELETE all data in sensors bucket

# Config
iot env                         # Show .env file
iot conf                        # Show telegraf config
iot edit [file]                 # Edit a file (default: .env)
iot update                      # Refresh device name mappings
iot cron-on                     # Enable hourly device map updates
iot cron-off                    # Disable cron job

# Network
iot ip                          # Show VM IP address
iot web                         # Show all service URLs
iot tunnel                      # Start Cloudflare tunnel

# Maintenance
iot backup                      # Backup Grafana + InfluxDB volumes to ~/backups/

# Help
iot help                        # Show all commands
```

### Cron Jobs

Device map update runs hourly:
```bash
0 * * * * /home/dubpixel/dpx_govee_stack/scripts/update-device-map.sh
```

Enable/disable:
```bash
iot cron-on   # Enable hourly updates
iot cron-off  # Disable cron job
```

**Note**: Hourly cron restarts Telegraf if config changed. Check log:
```bash
cat ~/dpx_govee_stack/scripts/update-device-map.log | tail -5
```

### Backup Procedures

**Manual backup:**
```bash
iot backup  # Backup Grafana + InfluxDB volumes to ~/backups/
```

**Remember**: This VM is production infrastructure for DPX shows. Test changes thoroughly before deploying. Keep backups current!

---

## INTEGRATIONS

### Phase 6 - Set Schedule Integration

**Sean's Repo**: https://github.com/macswg/coachella_set_schedule

### What It Is
- FastAPI/Uvicorn web app for real-time show schedule tracking
- Records actual vs scheduled set times for festival stages
- Tracks "slip" (accumulated lateness throughout show)
- WebSocket sync across multiple clients
- View-only and operator modes
- Google Sheets integration for schedule data

### Integration Method
- Added as **git submodule** at `services/set-schedule/`
- Keeps Sean's repo separate (easy to pull updates)
- Runs as Docker service in compose stack
- Managed with `iot` commands like other services

### Docker Service Config
Added to `docker-compose.yml`:
```yaml
set-schedule:
  build:
    context: ./services/set-schedule
    dockerfile: Dockerfile.showsite
  container_name: set-schedule
  restart: unless-stopped
  ports:
    - "8000:8000"
  environment:
    # Add any required env vars
  volumes:
    - ./services/set-schedule/data:/app/data
```

### Usage
- **Clone with submodules**: `git clone --recurse-submodules <repo-url>`
- **View-only mode**: http://<server-ip>:8000
- **Operator mode**: http://<server-ip>:8000/edit
- **Update Sean's code**: `git submodule update --remote services/set-schedule`
- **Logs**: `iot ls` (set-schedule logs)
- **Restart**: `iot restart set-schedule`

### Development Workflow
**For local development, contributing PRs to Sean's repo, and testing**:  
See [set-schedule-development.md](set-schedule-development.md)

### Optional Enhancement
Could log actual vs scheduled times to InfluxDB for historical slip analysis and Grafana dashboards showing per-stage timeliness trends.

---

## DEVELOPMENT REFERENCE

### H5051 Manufacturer Data Decoding

#### Packet Format

**Example**: `88ec00TTTTHHBB`

| Bytes | Field | Format | Example | Decoded |
|-------|-------|--------|---------|---------|
| 0-1 | Header | - | 88ec | Govee identifier |
| 2 | Packet Type | - | 00 | Standard data |
| 3-4 | Temperature | int16 LE ÷ 100 | 0fa4 | 0x0fa4 = 4004 = 40.04°C |
| 5-6 | Humidity | int16 LE ÷ 100 | 1388 | 0x1388 = 5000 = 50.00% |
| 7 | Battery | uint8 | 64 | 100% |

#### Python Decoder Template

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

### InfluxDB Query Examples

**View cloud data:**
```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor")
  |> filter(fn: (r) => r["source"] == "gv_cloud")
  |> filter(fn: (r) => r["room"] == "studown")
```

**Compare sources (cloud vs BLE):**
```flux
from(bucket: "sensors")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "sensor")
  |> filter(fn: (r) => r["room"] == "studown")
  |> filter(fn: (r) => r["sensor_type"] == "temperature")
  |> pivot(rowKey: ["_time"], columnKey: ["source"], valueColumn: "_value")
```

**Multi-source with custom display names:**
```flux
from(bucket: "sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.source == "gv_cloud" or r.source == "dpx_ops_decoder")
  |> filter(fn: (r) => r.sensor_type == "temperature")
  |> filter(fn: (r) => r.device_name != "studio_5051_down")
  |> map(fn: (r) => ({r with _field: 
      r.source + 
      (if exists r.source_node then " -- |" + r.source_node + "| - " else " - ") + 
      r.room + " - " + r.device_name
  }))
```

---

## TROUBLESHOOTING

### IPv6 Causing govee2mqtt AWS IoT Timeouts (SOLVED)

govee2mqtt kept timing out connecting to AWS IoT (port 8883). Error:
"timeout connecting to IoT aqm3wd1qlc3dy-ats.iot.us-east-1.amazonaws.com:8883"

**Root cause:** AWS IoT endpoint resolves to both IPv4 and IPv6. System prefers IPv6 but Hyper-V network can't route IPv6 to internet. govee2mqtt uses host networking so it inherits the host's IPv6 preference and hangs.

**Fix:** Disable IPv6 on eth0 at kernel level:
```bash
sudo sysctl -w net.ipv6.conf.eth0.disable_ipv6=1
echo "net.ipv6.conf.eth0.disable_ipv6=1" | sudo tee -a /etc/sysctl.conf
```

**Previous red herrings that didn't fully fix it:**
- IPv6 disabled in /etc/docker/daemon.json — doesn't help because govee2mqtt uses network_mode: host
- `sudo tailscale down && iot restart govee2mqtt` — sometimes worked, inconsistent
- Waiting 10-15 min — intermittent success

### Mosquitto Permissions Issues

If Mosquitto fails to start:
```bash
sudo chown -R 1883:1883 ~/dpx_govee_stack/mosquitto/data/
sudo chmod -R 755 ~/dpx_govee_stack/mosquitto/data/
iot restart mosquitto
```

### Telegraf "Available" Parse Errors (HARMLESS)

Telegraf logs spam: `strconv.ParseFloat: parsing "Available": invalid syntax`

This is govee2mqtt publishing status messages on same topics. Data still flows. Fix later with topic filtering.

### Telegraf Restarting Hourly (NOT A CRASH)

The update-device-map.sh cron job runs hourly and restarts telegraf if config changed. Check log:
```bash
cat ~/dpx_govee_stack/scripts/update-device-map.log | tail -5
```

### Docker Logs Lost on Recreate

`docker compose down && up` wipes logs (new container ID). No fix currently — just be aware. Use `iot restart` instead when possible.

### Docker Bridge Goes Down After Network Changes

Fix: `sudo systemctl restart docker`

### MQTT Retained Message Ghost Data (ACTIVE ISSUE)

**Problem**: After renaming a device (e.g., `studio_5051_down` → `5051_studio_down`), old data continues to appear in InfluxDB/Grafana.

**Root cause**: ble_decoder.py publishes with `retain=True` to topics containing device names:
```
demo_showsite/dpx_ops_decoder/{source_node}/{room}/{device_name}/{mac}/{metric}
```

When a device is renamed, the decoder creates NEW retained messages on new topics, but old retained messages persist on old topics. Every time Telegraf restarts (hourly cron), it resubscribes and receives BOTH sets of retained messages:
- Old ghost: `demo_showsite/dpx_ops_decoder/dpx_ops_1/studiodown/studio_5051_down/4381ECA1010A/temperature`
- New current: `demo_showsite/dpx_ops_decoder/dpx_ops_1/studiodown/5051_studio_down/4381ECA1010A/temperature`

Telegraf regex processors extract `device_name` from topic path, creating two separate time series in InfluxDB—one frozen at old values, one updating.

**Why hourly**: `update-device-map.sh` cron job **unconditionally** restarts Telegraf every hour (no diff check), forcing resubscription and replay of all retained messages.

**Immediate workaround**: Manually clear old retained messages:
```bash
mosquitto_pub -h localhost -t "demo_showsite/dpx_ops_decoder/dpx_ops_1/studiodown/studio_5051_down/4381ECA1010A/temperature" -r -n
mosquitto_pub -h localhost -t "demo_showsite/dpx_ops_decoder/dpx_ops_1/studiodown/studio_5051_down/4381ECA1010A/humidity" -r -n
mosquitto_pub -h localhost -t "demo_showsite/dpx_ops_decoder/dpx_ops_1/studiodown/studio_5051_down/4381ECA1010A/battery" -r -n
```

**Long-term fixes needed**:
1. Add diff check to update-device-map.sh (only restart if config actually changed)
2. Create cleanup script to detect and clear stale retained messages
3. Consider using MAC-based topics instead of device_name to avoid renames creating new topics
4. Add `iot mqtt-cleanup` command to manage.sh

See [ROADMAP.md](../ROADMAP.md) Phase 4 Outstanding Items and [plan-mqtt-cleanup.md](plan-mqtt-cleanup.md) for fix details.

### Key Learnings & Gotchas

- govee2mqtt publishes to `gv2mqtt/#` NOT `govee2mqtt/#`
- Govee API requires devices assigned to rooms to return data
- `RUST_LOG` env changes need full `down/up` cycle, not just restart
- **IPv6 on host causes govee2mqtt timeouts** — disable with sysctl
- Docker daemon.json IPv6 disable doesn't help govee2mqtt (uses `network_mode: host`)
- MQTT wildcard `+` catches non-numeric topics causing parse errors (harmless)
- govee2mqtt web API at port 8056 returns device JSON
- H5051 is BLE only, no LAN/IoT API
- **InfluxDB timestamps are UTC** — adjust for local timezone
- **Docker logs lost on recreate** — use `iot restart` not `down/up`
- **update-device-map.sh cron unconditionally restarts Telegraf hourly** — lacks diff check
- **MQTT retained messages persist across device renames** — creates ghost data
- **iot command needs wrapper script** not direct symlink
- **Underscores in hostnames are invalid** (RFC) — use dashes
- **Directory rename breaks Docker volumes** — backup first
- Sensor broadcast: BLE every ~1min, cloud upload every ~10min
- GitHub repo naming: use underscores to match existing projects

---

**For tasks and roadmap, see**: [docs/ROADMAP.md](../ROADMAP.md)

**REMEMBER**: This VM is production infrastructure for DPX shows. Test changes thoroughly before deploying. Keep backups current with `iot backup`!

