# dpx-showsite-ops - System Reference
# Last updated: 2026-03-06
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
- **.214**: Geist Watchdog 100 (dpx-geist.local) — Environmental monitoring
- **.220**: User's Mac

### Installed Services

| Service | Status | Purpose |
|---------|--------|---------|
| SSH | enabled | Remote access |
| avahi-daemon | enabled | mDNS (*.local hostnames) |
| cloudflared | installed | Cloudflare tunnels (manual start, auto-installed by setup.sh) |
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

### M4300 Network Switches

**Phase 5 - Network Device Backups** (Core Complete)

#### Overview

- **Purpose**: Automated configuration backups for Netgear M4300 managed switches
- **Method**: TFTP-based backup via SSH-triggered commands
- **Integration**: Git submodule at `services/netgear-backup`
- **Status**: ✅ Backup automation working, Grafana dashboards pending

#### Switch Configuration Requirements

**CRITICAL**: Both RSA AND DSA SSH host keys must be generated and activated on each switch:

```
(M4300) # configure
(M4300) (config)# crypto key generate rsa
(M4300) (config)# crypto key activate rsa
(M4300) (config)# crypto key generate dsa
(M4300) (config)# crypto key activate dsa
(M4300) (config)# exit
(M4300) # write memory
```

**Verify keys exist:**
```
(M4300) # show crypto key mypubkey rsa
(M4300) # show crypto key mypubkey dsa
```

#### Known Issues & Gotchas

- **Password compatibility**: Some switches reject newer passwords — multiple password environment variables available (`M4300_PASSWORD_M4300`, `M4300_PASSWORD_OTHER`) to accommodate different switch behaviors
- **TFTP server config**: Took significant troubleshooting to get working correctly (see TFTP Server section below)
- **No TFTP logs**: TFTP server runs as user `nobody` with minimal logging — troubleshooting is difficult
- **Secure vs unsecure mode**: TFTP configuration requires specific flags for file uploads to work

#### Management

**Configuration:**
- Switch inventory: `config/switches.conf` (IP, hostname, model)
- Credentials: `.env` file (`M4300_USERNAME`, passwords)
- Backup storage: Docker volume `netgear-backups`

**Commands:**
```bash
iot m4300-backup          # Run backup for all switches
iot m4300-backup-mock     # Test mode (no real switches)
iot m4300-logs [n]        # View backup logs
iot m4300-list [n]        # List recent backups
iot m4300-list-switches   # Show switch inventory
iot m4300-clean           # Remove empty backup folders
```

**See also**: [services/netgear-backup/README.md](../../services/netgear-backup/README.md) for detailed switch configuration steps.

### Geist Watchdog Environmental Monitoring

**Phase 4.5 - Infrastructure Monitoring** (✅ Complete)

#### Overview

- **Device**: Geist Watchdog 100 @ dpx-geist.local (192.168.1.214)
- **Purpose**: Server room and infrastructure climate monitoring with wired SNMP reliability
- **Integration**: Telegraf SNMP input polling every 30 seconds
- **Status**: ✅ Deployed and operational, data flowing to InfluxDB

#### Monitored Sensors

**Internal Sensors:**
- Temperature
- Humidity  
- Dewpoint

**Remote Sensors:**
- 3x temperature probes (external wired sensors)
- 2x airflow sensors

#### Configuration

- **Config file**: `telegraf/conf.d/geist-watchdog.conf` (197 lines)
- **Protocol**: SNMP v2c
- **Polling interval**: 30 seconds
- **InfluxDB measurements**: 
  - `geist_internal` — Internal temp/humidity/dewpoint
  - `geist_temp_remote` — External temperature probes
  - `geist_airflow_remote` — Airflow sensors

#### Hostname Resolution

The Geist device uses hostname `dpx-geist.local` via mDNS. Docker containers need explicit hostname mapping in `docker-compose.yml`:

```yaml
telefraf:
  extra_hosts:
    - "dpx-geist.local:192.168.1.214"
```

If device IP changes, update both `docker-compose.yml` and `telegraf/conf.d/geist-watchdog.conf`.

#### Management

**Data verification:**
```bash
iot query "1h" 10 | grep geist
```

**Schema cleanup** (if needed after sensor changes):
```bash
iot nuke-geist  # Deletes all Geist measurements from InfluxDB
```

**Grafana**: Data is available in InfluxDB. Dashboards pending design.

### Set-Schedule Festival App

**Phase 6 - Real-Time Schedule Tracking** (✅ Deployed, Art-Net Testing Pending)

#### Overview

- **Purpose**: Real-time festival schedule tracking with slip monitoring and downstream impact projections
- **Repository**: https://github.com/macswg/coachella_set_schedule (Sean's repo)
- **Integration**: Git submodule at `services/set-schedule`
- **Ports**: 8000 (production), 8001 (development)
- **Status**: ✅ Deployed and operational, Art-Net hardware testing blocked by Phase 11 VLAN config

#### Key Features

- **Real-time WebSocket sync**: All connected clients see updates instantly
- **Operator mode** (`/edit`): Record actual start/end times for each act
- **View-only mode** (`/`): Dashboard display for stage crew
- **Slip tracking**: Calculates accumulated lateness vs published schedule
- **Downstream projections**: Shows impact of current slip on future acts
- **Break time calculations**: Early finishes extend breaks, late finishes compress them
- **Google Sheets integration**: Optional schedule data persistence
- **Art-Net DMX support**: React to lighting console brightness changes (hardware testing pending)

#### Docker Services

**Production** (port 8000):
- Container: `set-schedule`
- Auto-starts with stack
- Management: `iot schedule-up/down/restart/rebuild/status/logs/follow/shell`

**Development** (port 8001):
- Builds from `../COACHELLA_SET_SCHEDULE` directory
- For testing and contributing PRs  
- Management: `iot schedule-dev-build/up/down/restart/rebuild/logs/follow/shell`

#### Configuration

**Environment variables** (in `.env`):
- `SCHEDULE_PORT`: Port for production service (default 8000)
- `STAGE_NAME`: Display name (e.g., "Main Stage")
- `TIMEZONE`: Local timezone (e.g., "America/Los_Angeles")
- `USE_GOOGLE_SHEETS`: Enable Google Sheets integration (true/false)
- `GOOGLE_SHEETS_ID`: Spreadsheet ID
- `GOOGLE_SHEET_TAB`: Tab name (default "Schedule")
- `GOOGLE_SERVICE_ACCOUNT_FILE`: Path to credentials file in `secret/` directory
- `ARTNET_*` variables: Art-Net DMX configuration (listener IP, port, universe, channels)

#### Access URLs

- **Production view-only**: http://192.168.1.100:8000
- **Production operator**: http://192.168.1.100:8000/edit
- **Development**: http://192.168.1.100:8001 (when dev service running)

#### Management Commands

**Production:**
```bash
iot schedule-up           # Start production service
iot schedule-down         # Stop production service
iot schedule-restart      # Restart production service
iot schedule-rebuild      # Rebuild and redeploy
iot schedule-status       # Show container status
iot schedule-logs [n]     # View logs (last n lines)
iot schedule-follow       # Stream logs in real-time
iot schedule-shell        # Open shell in container
```

**Development:**
```bash
iot schedule-dev-build    # Build dev image from ../COACHELLA_SET_SCHEDULE
iot schedule-dev-up       # Start dev service
iot schedule-dev-restart  # Restart dev service
iot schedule-dev-rebuild  # Build and start dev service
iot schedule-dev-logs [n] # View dev logs
```

**See also**: [set-schedule-development.md](set-schedule-development.md) for detailed development workflow.

### WLED Bridge

**Phase 7 (Partial) - MQTT Sensor → WLED Ropelight** (✅ Deployed)

#### Overview

- **Purpose**: Maps MQTT sensor data to pixel zones on a WLED ropelight using WLED's native MQTT API
- **Service**: `wled-bridge` (`services/wled-bridge/`)
- **Initial feature**: Tent temperature sensor drives pixels 75–99 (last 25px of a 100px ropelight)
- **Zone system**: Full 100px ropelight divided into 4 named zones for future status mapping

#### Pixel Zone Map

```
px  0– 24  →  Zone A  (spare — future use)
px 25– 49  →  Zone B  (spare — future use)
px 50– 74  →  Zone C  (spare — future use)
px 75– 99  →  Zone D  = Tent Temperature  (active)
```

#### Data Flow

```
Tent sensor BLE → ESP32 → MQTT raw → ble-decoder
  → {SHOWSITE}/dpx_ops_decoder/{gw}/{room}/{device}/{mac}/temperature
  → wled-bridge (subscribes, filters by room, interpolates color)
  → wled/{WLED_DEVICE_NAME}/api  (WLED native MQTT segment API)
  → WLED ropelight pixels 75–99
```

#### Temperature Color Gradient (Zone D)

| °F   | Color  | RGB           |
|------|--------|---------------|
| ≤60  | Blue   | [0, 50, 255]  |
| 65   | Cyan   | [0, 200, 200] |
| 72   | Green  | [0, 200, 0]   |
| 78   | Yellow | [220, 220, 0] |
| 85   | Orange | [255, 100, 0] |
| ≥92  | Red    | [255, 0, 0]   |

#### Configuration

- **Zone config**: `services/wled-bridge/config.yaml` — zones, pixel ranges, gradient stops
- **Env vars** (in `.env`):
  - `WLED_DEVICE_TOPIC` — full MQTT base topic as set in WLED Config → Sync Interfaces → MQTT → Device topic (e.g. `coachella_26/wled-rambo`). Code appends `/api` for JSON commands.
  - `TENT_SENSOR_ROOM` — room name assigned to the tent sensor in Govee app / device-overrides.json

#### WLED Setup (one-time)

WLED firmware must have MQTT enabled:
- WLED web UI → Config → Sync Interfaces → MQTT
- Server IP: `192.168.109.69` (stack VM, VLAN 109), Port: `1883`
- Device topic: `coachella_26/wled-rambo`
- Group topic: `coachella_26/all`

#### Adding a Zone

1. Add a zone block to `services/wled-bridge/config.yaml` (use commented examples as templates)
2. Set `pixels.start`/`stop`, `source.room`, and `gradient` stops
3. `iot wled-rebuild` to pick up the new config

#### Management

```bash
iot wled-up                 # Start service
iot wled-restart            # Restart (picks up .env changes)
iot wled-rebuild            # Rebuild image and restart (code changes)
iot wled-logs [n]           # View logs
iot wled-follow             # Stream logs in real-time
```

---

### Matrix Blast

**Web UI for blasting scrolling text to WLED LED matrices** (✅ Deployed)

#### Overview

- **Purpose**: Browser form that lets operators type messages and send them to one or more WLED matrix signs via MQTT
- **Service**: `matrix-blast` (`services/matrix-blast/`)
- **Port**: `8090` (`MATRIX_BLAST_PORT` env var)
- **Config**: `services/matrix-blast/config.yaml` — define signs (MQTT topic, WLED host, text_preset, led_count)

#### Endpoints

| URL | Purpose |
|-----|---------|
| `http://<server>:8090/` | Blast form |
| `http://<server>:8090/messages` | Recent blast history (auto-refreshes every 5s) |
| `http://<server>:8090/status` | JSON — active message + queue per sign |
| `http://<server>:8090/health` | Health check |

Note: no `.html` extension on any URL.

#### Features

- **Palette selector** — Solid (uses RGB picker), Rainbow (11), Party (6), Fire (35), Lava (8), Ocean (9), Aurora (49). Palette number maps directly to WLED's built-in palette index; when non-zero, WLED colors the text using the palette instead of the solid RGB value.
- **RGB color picker** — shown only when Solid palette is selected
- **Speed** (0–255) — scroll speed
- **TTL** — auto-clear after N seconds; first 50% of TTL is "locked" (new blasts queue)
- **Message queue** — blasts arriving during lock window are queued and dispatched in order
- **History page** (`/messages`) — last 100 blasts with color swatch, palette badge, age ("2m ago"); HTMX polls `/messages/feed` every 5s

#### MQTT Payload

```json
{
  "text": "DOORS OPEN",
  "color": [255, 220, 0],
  "speed": 255,
  "ttl": 30,
  "rotate": 14,
  "pal": 0
}
```

`pal: 0` = solid color; non-zero = WLED palette index. `rotate` maps to WLED `m12` (2D transform for the scrolling text effect).

#### Management

```bash
iot matrix-blast-rebuild    # Rebuild image + restart (required after code changes)
iot matrix-blast-restart    # Restart only (for .env / config changes, no rebuild)
iot matrix-blast-logs [n]   # View logs
iot matrix-blast-follow     # Stream logs in real-time
iot matrix-blast-status     # Show active message + queue (alias: mb-status)
iot tunnel-matrix           # Start Cloudflare tunnel to port 8090
```

---

## DOCKER STACK

### File Structure

```
~/dpx_govee_stack/              (local directory)
├── README.md                   ← Quick start guide
├── CHANGELOG.md                ← Version history
├── VERSION                     ← Current version number (2.2.0)
├── docker-compose.yml          ← Main stack definition
├── Dockerfile.ble-decoder      ← BLE decoder container build
├── requirements-ble-decoder.txt ← Python dependencies for BLE decoder
├── .env                        ← Secrets (gitignored)
├── .env.example                ← Template for users
├── .gitignore                  ← Excludes secrets, logs, backups
├── install.sh                  ← One-liner installer (clones repo + runs wizard)
├── setup.sh                    ← Interactive setup wizard (v2.1.0: no vim/vi required!)
├── config/
│   └── switches.conf.example   ← M4300 switch inventory template
├── mosquitto/
│   └── config/
│       └── mosquitto.conf
├── telegraf/
│   ├── telegraf.conf           ← Static base config
│   ├── conf.d/
│   │   ├── device-mappings.conf    ← Dynamic device mappings (auto-generated)
│   │   ├── geist-watchdog.conf     ← Geist SNMP monitoring (197 lines)
│   │   └── device-overrides.json.example ← Device rename template
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

**Phase 5 Integration (✅ Core Complete)**:
```
└── services/
    └── netgear-backup/         ← Netgear M4300 backup automation (git submodule)
        ├── netgear_system_backup_TFTP-v0d1.py
        ├── switches.conf       ← Switch inventory (symlinked to ../../config/)
        └── Dockerfile          ← Integrated in docker-compose stack
```

**Phase 6 Integration (✅ Deployed)**:
```
└── services/
    └── set-schedule/           ← Sean's repo as git submodule
        ├── main.py             ← FastAPI application
        ├── app/                ← Server-side modules (models, sheets, artnet)
        ├── templates/          ← Jinja2 templates + Alpine.js
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
- **VERSION file**: Tracks current release (2.1.0 as of 2026-03-06)

---

## SERVICES CONFIGURATION

### Telegraf

#### Configuration Structure

Split into modular structure:
- `telegraf.conf`: Static base config (agent, outputs, inputs, BLE processors)
- `conf.d/device-mappings.conf`: Dynamic enum mappings (regenerated by update-device-map.sh)
- `conf.d/geist-watchdog.conf`: Geist Watchdog SNMP monitoring (197 lines)
- `conf.d/device-overrides.json`: Local device name overrides (optional, gitignored)

Docker container loads all conf.d files via --config-directory flag.

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

### TFTP Server

**Purpose**: Receives configuration files from M4300 switches during automated backups.

**Image**: `pghalliday/tftp:latest`

**Critical Configuration**:
```yaml
command: ["-L", "-s", "-c", "/var/tftpboot"]
```

**Flags explained**:
- `-L`: Enable logging
- `-s`: Secure mode (chroot to directory)
- `-c`: **CRITICAL** — Allow file creation (required for switch uploads)

**Gotchas**:
- **Took significant troubleshooting** to get working — issue was secure vs unsecure mode
- `-c` flag is non-obvious but essential for receiving config files from switches
- Runs as user `nobody` — minimal permissions
- **No useful logs** — makes troubleshooting difficult
- Requires `network_mode: host` for TFTP's dynamic port allocation

**Network**: Host mode (port 69/UDP)

**Volume**: `tftp-data` (persistent storage for uploaded configs)

**Access**: Switch-triggered only, no manual interaction needed

### netgear-backup

**Purpose**: Automated M4300 switch configuration backups via TFTP.

**Integration**: Git submodule at `services/netgear-backup/`

**Restart policy**: `"no"` — Manual or cron-triggered, not always-on

**Configuration**:
- **Switch inventory**: `config/switches.conf` (IP, hostname, model)
- **Credentials**: Environment variables from `.env`:
  - `M4300_USERNAME` — Switch SSH username
  - `M4300_PASSWORD_M4300` — Password for M4300 models
  - `M4300_PASSWORD_OTHER` — Password for other models (some switches reject newer passwords)
  - `M4300_TFTP_SERVER` — TFTP server hostname (default: tftp-server)

**Process**:
1. SSH to each switch (requires RSA + DSA host keys activated)
2. Execute `copy nvram:startup-config tftp://...` command
3. Switch uploads config to TFTP server
4. netgear-backup validates file size and content
5. Publishes backup metrics to InfluxDB

**Storage**:
- **Backups**: Docker volume `netgear-backups:/backups`
- **TFTP files**: Read-only access to `tftp-data` volume for retrieval

**InfluxDB Integration**: Publishes backup success/failure metrics with switch name, IP, duration, result.

**Management**: See M4300 Network Switches section above for commands.

### set-schedule

**Purpose**: Festival schedule tracking application with real-time slip monitoring.

**Integration**: Git submodule at `services/set-schedule/`

**Ports**:
- Production: 8000 (`SCHEDULE_PORT` env var)
- Development: 8001 (when dev service running)

**Configuration**: See Set-Schedule Festival App section above for full details.

**Environment** (from `.env`):
- Stage name, timezone
- Google Sheets integration (optional)
- Art-Net DMX listener config
- Service account credentials (in `secret/` directory)

**Volume**: `./secret:/app/secret:ro` — Read-only mount for Google service account credentials

**Network**: Bridge (iot network)

**Management**: 16 commands — see Set-Schedule Festival App section above.

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

#### Flux Query Patterns - Filtering Stray BLE Pickups

BLE gateways occasionally pick up signals from devices in other rooms. To eliminate stray pickups and ensure each gateway only reports its designated location, add source/location filtering to Flux queries:

```flux
from(bucket: "sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r.source == "dpx_ops_decoder" or r.source == "SNMP")
  |> filter(fn: (r) => 
      (r.source == "dpx_ops_decoder" and r.sensor_type == "temperature") or 
      (r.source == "SNMP" and r._field == "temperature")
  )
  // Filter stray pickups: each gateway reports only its designated location
  |> filter(fn: (r) => 
      r.source != "dpx_ops_decoder" or
      (r.source_node == "dpx_ops_1" and r.room == "tent") or
      (r.source_node == "TheengsGateway" and r.room == "truck")
  )
  |> map(fn: (r) => ({r with _field: "|"+ r.device_name + "|"}))
```

**Key points:**
- `source_node` identifies which gateway received the signal
- `room` identifies the device's assigned location
- Filter logic: keep non-BLE sources OR keep BLE only when source_node matches expected room
- Adjust gateway/room mappings to match your deployment

---

## MANAGEMENT

### Management CLI (iot command)

Symlinked: /usr/local/bin/iot → wrapper script → ~/dpx_govee_stack/scripts/manage.sh

**Installation**: Automatically installed by [setup.sh](../../setup.sh) interactive wizard with auto-detected path.

**Quick Deploy**: Use the one-liner installer:
```bash
curl -fsSL https://raw.githubusercontent.com/dubpixel/dpx_showsite_ops/master/install.sh | bash
```

The wizard (v2.1.0+) handles everything interactively:
- Docker auto-install if missing
- Email/password/API key prompts with validation
- Timezone auto-detection
- System optimizations (IPv6, avahi, Tailscale, cloudflared)
- No vim/vi required!

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

# Data & Monitoring
iot query [range] [rows]        # Query InfluxDB (default: 30m, 5 rows)
iot query-tags [range] [rows]   # Query InfluxDB with device metadata columns
iot mqtt [topic] [count]        # Subscribe to MQTT topics
iot watch-gv2                   # Subscribe to Govee cloud sensor topics

# M4300 Network Backup Management
iot m4300-backup                # Run config backup for all switches
iot m4300-backup-mock           # Run in mock mode (testing, no real switches)
iot m4300-logs [n]              # View backup logs (last n entries)
iot m4300-log-view <file>       # Display specific log file
iot m4300-list [n]              # List recent backups (last n)
iot m4300-list-all              # List all backup files
iot m4300-clean                 # Remove empty backup folders
iot m4300-list-switches         # Show parsed switch inventory
iot m4300-rebuild               # Rebuild netgear-backup container
iot tftp-rebuild                # Recreate TFTP server container

# Set-Schedule Management (Production - port 8000)
iot schedule-up                 # Start production service
iot schedule-down               # Stop production service
iot schedule-restart            # Restart production service
iot schedule-rebuild            # Rebuild and redeploy production
iot schedule-status             # Show container status
iot schedule-logs [n]           # View logs (last n lines)
iot schedule-follow             # Stream logs in real-time
iot schedule-shell              # Open shell in container

# Set-Schedule Development (port 8001)
iot schedule-dev-build          # Build dev image from ../COACHELLA_SET_SCHEDULE
iot schedule-dev-up             # Start dev service
iot schedule-dev-down           # Stop dev service
iot schedule-dev-restart        # Restart dev service
iot schedule-dev-rebuild        # Build and start dev service
iot schedule-dev-logs [n]       # View dev logs
iot schedule-dev-follow         # Stream dev logs in real-time
iot schedule-dev-shell          # Open shell in dev container

# Config & Device Management
iot env                         # Show .env file
iot conf                        # Show telegraf config
iot edit [file]                 # Edit a file (default: .env)
iot update                      # Refresh device name mappings
iot list-devices                # Show all devices with metadata
iot rename-device               # Interactive device renaming
iot set-room                    # Set room for a device
iot clear-override              # Remove device override
iot cron-on                     # Enable hourly device map updates
iot cron-off                    # Disable cron job

# Network & Tunnels
iot ip                          # Show VM IP address
iot web                         # Show all service URLs
iot tunnel                      # Start Cloudflare tunnel (general)
iot tunnel-grafana              # Tunnel specifically to Grafana
iot tunnel-influxdb             # Tunnel specifically to InfluxDB
iot tunnel-schedule             # Tunnel specifically to set-schedule

# ESP32 BLE Gateway Configuration
iot esp32-enable                # Enable ESP32 BLE gateway external decoder mode
iot esp32-verbose               # Configure ESP32 for maximum scan frequency

# Data Deletion (⚠️ DANGEROUS)
iot clear-retained [topic]      # Clear retained MQTT messages (fixes ghost data)
iot delete-device-data          # Interactive deletion wizard (old/current/all modes)
iot nuke                        # DELETE all data in sensors bucket
iot nuke-geist                  # Delete all Geist measurements

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

### Phase 6 - Set Schedule Integration (✅ Deployed)

**Sean's Repo**: https://github.com/macswg/coachella_set_schedule

**Status**: Phase 6 deployment complete. Software fully operational. Art-Net hardware testing blocked by Phase 11 VLAN configuration.

### What It Is
- FastAPI/Uvicorn web app for real-time show schedule tracking
- Records actual vs scheduled set times for festival stages
- Tracks "slip" (accumulated lateness throughout show)
- Projects downstream impacts of current slip
- WebSocket sync across multiple clients
- View-only and operator modes
- Google Sheets integration for schedule data persistence
- Art-Net DMX listener (reacts to lighting console brightness changes)

### Integration Method
- Added as **git submodule** at `services/set-schedule/`
- Keeps Sean's repo separate (easy to pull updates)
- Runs as Docker service in compose stack
- Managed with `iot` commands like other services
- 16 management commands (8 production + 8 development)

### Docker Services

**Production** (port 8000):
```yaml
set-schedule:
  build:
    context: ./services/set-schedule
    dockerfile: Dockerfile
  container_name: set-schedule
  restart: unless-stopped
  ports:
    - "${SCHEDULE_PORT:-8000}:8000"
  environment:
    - STAGE_NAME=${STAGE_NAME:-Main Stage}
    - TIMEZONE=${TIMEZONE:-America/Los_Angeles}
    - USE_GOOGLE_SHEETS=${USE_GOOGLE_SHEETS:-false}
    # ... additional env vars ...
  volumes:
    - ./secret:/app/secret:ro
```

**Development** (port 8001): Builds from `../COACHELLA_SET_SCHEDULE` for local testing.

### Usage
- **Clone with submodules**: `git clone --recurse-submodules <repo-url>`
- **View-only mode**: http://192.168.1.100:8000
- **Operator mode**: http://192.168.1.100:8000/edit
- **Update Sean's code**: `git submodule update --remote services/set-schedule`
- **Commands**: `iot schedule-up/down/restart/logs/shell` + 11 more (see Management section)

### Development Workflow
**For local development, contributing PRs to Sean's repo, and testing**:  
See [set-schedule-development.md](set-schedule-development.md)

### Future Enhancement
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

### Known Issues

#### MQTT Retained Message Ghost Data (ACTIVE ISSUE)

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

**Immediate workaround**: Use `iot clear-retained` command:
```bash
iot clear-retained "demo_showsite/dpx_ops_decoder/dpx_ops_1/studiodown/studio_5051_down/#"
```

Or manually:
```bash
mosquitto_pub -h localhost -t "demo_showsite/dpx_ops_decoder/dpx_ops_1/studiodown/studio_5051_down/4381ECA1010A/temperature" -r -n
mosquitto_pub -h localhost -t "demo_showsite/dpx_ops_decoder/dpx_ops_1/studiodown/studio_5051_down/4381ECA1010A/humidity" -r -n
mosquitto_pub -h localhost -t "demo_showsite/dpx_ops_decoder/dpx_ops_1/studiodown/studio_5051_down/4381ECA1010A/battery" -r -n
```

**Long-term fixes needed**:
1. Add diff check to update-device-map.sh (only restart if config actually changed)
2. Create automated cleanup script to detect and clear stale retained messages
3. Consider using MAC-based topics instead of device_name to avoid renames creating new topics
4. Auto-cleanup on device rename operations

See [ROADMAP.md](../ROADMAP.md) Phase 4 Outstanding Items for fix details.

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

