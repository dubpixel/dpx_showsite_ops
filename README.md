<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
<!--
*** I'm using markdown "reference style" links for readability.
*** Reference links are enclosed in brackets [ ] instead of parentheses ( ).
*** See the bottom of this document for the declaration of the reference variables
*** for contributors-url, forks-url, etc. This is an optional, concise syntax you may use.
*** https://www.markdownguide.org/basic-syntax/#reference-style-links
***
-->
<div align="center">

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![GPL-3.0 License][license-shield]][license-url]
[![LinkedIn][linkedin-shield]][linkedin-url]
</div>

<!-- PROJECT LOGO -->
<div align="center">
  <a href="https://github.com/dubpixel/dpx_showsite_ops">
    <img src="images/logo.png" alt="Logo" height="120">
  </a>
<h1 align="center">dpx-showsite-ops</h1>
<h3 align="center"><i>Operations stack for DPX show sites</i></h3>
  <p align="center">
    A unified platform for IoT monitoring, environmental sensors, and network infrastructure management
    <br />
     »  
     <a href="https://github.com/dubpixel/dpx_showsite_ops"><strong>Project Here!</strong></a>
     »  
     <br />
    <a href="https://github.com/dubpixel/dpx_showsite_ops/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    ·
    <a href="https://github.com/dubpixel/dpx_showsite_ops/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
    </p>
</div>

<br />

<!-- TABLE OF CONTENTS -->
<!-- ABOUT THE PROJECT -->

## About The Project

Operations stack for DPX show sites. Unified platform for IoT monitoring, environmental sensors, network infrastructure management, and live event operations. Get sensor data flowing into InfluxDB with Grafana dashboards in minutes. Includes MQTT pub/sub messaging, time-series storage, real-time schedule tracking, and remote access via Tailscale or Cloudflare Tunnel.

**Current Deployment:** IoT monitoring via cloud API + ESP32 BLE gateways, SNMP monitoring (Geist Watchdog, ControlByWeb, d3 SMC), network device backups (Netgear M4300), and live festival schedule tracking
**Future:** Additional sensor types, metrics-driven automation workflows, consumables tracking, LTC monitoring — see roadmap for details

**Key features:**
- **Govee IoT Stack**: Temperature/humidity monitoring via Govee sensors (cloud API + BLE)
- **ESP32 BLE Gateways**: Real-time BLE data collection (<5 sec latency)
- **SNMP Monitoring**: Environmental and system monitoring (Geist Watchdog, ControlByWeb X-410, D3 SMC)
- **Network Backups**: Automated Netgear M4300 switch configuration backups via TFTP
- **Set Schedule**: Real-time festival schedule tracking with slip calculations and WebSocket sync (by Sean Green)
- **MQTT Broker**: Eclipse Mosquitto for sensor data pub/sub
- **Time Series DB**: InfluxDB 2.x for storing sensor readings
- **Visualization**: Grafana dashboards with public sharing
- **Data Pipeline**: Telegraf for MQTT→InfluxDB routing with tag enrichment
- **Grafana Live Demo**: [HERE](https://symantec-granny-attorneys-brokers.trycloudflare.com)
- **Set Schedule Live Demo**; [HERE]( https://trades-pools-handled-adaptive.trycloudflare.com)

### Hardware: ESP32 BLE Gateways

For real-time BLE data collection (<5 sec latency), deploy ESP32 hardware gateways running OpenMQTTGateway:

- **Board**: Custom ESP32-based hardware (WiFi enabled)
- **Firmware**: OpenMQTTGateway **esp32feather-ble** build
- **Flash Tool**: Browser-based [web installer](https://docs.openmqttgateway.com/upload/web-install.html) (no code required)
- **Setup Time**: 5-10 minutes per gateway
- **Multi-Site**: Deploy multiple gateways for coverage

**Quick Deploy**: Open the [web installer](https://docs.openmqttgateway.com/upload/web-install.html), select **esp32feather-ble**, flash, and configure WiFi + MQTT broker.

**Fallback**: Theengs Gateway on Windows available for testing/development.

<details>
<summary>Images</summary>

### ARCHITECTURE
![ARCHITECTURE][product-architecture]

### GRAFANA DASHBOARD
![GRAFANA][product-grafana]

</details>

### Built With

* **Container Orchestration**: Docker Engine 20.10+ with Docker Compose
* **Time Series Database**: InfluxDB 2.x
* **Visualization**: Grafana
* **Message Broker**: Eclipse Mosquitto
* **Data Pipeline**: Telegraf
* **Data Sources**: 
  * govee2mqtt (AWS IoT bridge for cloud data)
  * ble-decoder (Python service for real-time BLE data)
  * SNMP devices (Geist Watchdog, ControlByWeb X-410, D3 SMC)
  * Netgear M4300 switches (configuration backups)
* **Applications**:
  * Set Schedule (festival schedule tracker by Sean Green)
* **Hardware Gateways**: ESP32 with OpenMQTTGateway firmware
* **Infrastructure**: Docker, systemd, cron
* **Remote Access**: Tailscale, Cloudflare Tunnel (optional)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->

## Getting Started

> **🆕 First time?** See the [Complete Setup Guide](https://github.com/dubpixel/dpx_showsite_ops/blob/master/docs/SETUP_GUIDE_COMPLETE.md) — covers everything from creating the VM to Cloudflare tunnels, step by step.

### Quick Install (Recommended)

Deploy the entire stack in minutes with our interactive wizard. Perfect for fresh Ubuntu/Debian systems:

```bash
curl -fsSL https://raw.githubusercontent.com/dubpixel/dpx_showsite_ops/master/install.sh | bash
```

**What the wizard does:**
- ✅ Installs Docker automatically (if needed)
- ✅ Guides you through Govee credentials setup (no vim/vi required!)
- ✅ Validates email and API key format
- ✅ Auto-detects timezone and system settings
- ✅ Optional system optimizations (IPv6 disable, avahi, Tailscale)
- ✅ Deploys all services via Docker Compose
- ✅ Installs `iot` management command system-wide
- ✅ Shows you exactly how to access Grafana

**Time to deploy:** 5-10 minutes on a fresh VM

**Tested on:**  _wizard not currently tested_. - dev system runs on ubuntu 24.04 LTS

---

### Manual Installation

For advanced users or custom setups:

### Prerequisites

- **OS**: Ubuntu 22.04+ (tested on Ubuntu Server 24.04)
- **Docker**: Docker Engine 20.10+ with Compose plugin
- **Network**: Static IP recommended (set your `<server-ip>`)
- **Optional**: Tailscale for remote access, Cloudflare Tunnel for public dashboards

### Manual Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/dubpixel/dpx_showsite_ops.git
   cd dpx_showsite_ops
   ```

2. **Run interactive setup wizard**
   ```bash
   ./setup.sh
   ```
   The wizard will:
   - Check for Docker/Compose (installs if needed)
   - Guide you through credential entry (email, password, API key)
   - Validate inputs before proceeding
   - Configure timezone and display preferences
   - Offer system optimizations (IPv6, avahi, Tailscale)
   - Set up the `iot` management command
   - Optionally deploy the stack immediately

3. **Access services**
   - **Grafana**: http://<server-ip>:3000 (admin/grafanapass123)
   - **InfluxDB**: http://<server-ip>:8086 (admin/influxpass123)
   - **MQTT**: <server-ip>:1883 (anonymous)

<!-- USAGE EXAMPLES -->
## Usage

### Management Commands

The `iot` command is your main interface:
```bash
iot up              # Start all services
iot down            # Stop all services
iot restart [svc]   # Restart service(s)
iot status          # Show container status

# Logs
iot lg [n]          # govee2mqtt logs (last n lines)
iot lt [n]          # telegraf logs
iot lm [n]          # mosquitto logs
iot li [n]          # influxdb logs
iot lf [n]          # grafana logs
iot lb [n]          # ble-decoder logs
iot la [n]          # all logs

# BLE Decoder Service
iot ble-up          # Start BLE decoder
iot ble-down        # Stop BLE decoder
iot ble-restart     # Restart BLE decoder
iot ble-rebuild     # Rebuild container image
iot ble-status      # Show status
iot ble-logs [n]    # View logs (alias: iot lb)
iot ble-follow      # Stream logs in real-time
iot ble-decode      # Run manually in foreground (debugging)

# Data & Monitoring
iot query [range] [rows]      # Query InfluxDB directly
iot query-tags [range] [rows] # Query with device metadata columns
iot mqtt [topic] [count]      # Subscribe to MQTT topics
iot watch-gv2                 # Subscribe to Govee sensor topics

# Maintenance
iot backup          # Backup Grafana + InfluxDB volumes
iot update          # Refresh device name mappings from Govee API
iot cron-on         # Enable hourly device map updates
iot cron-off        # Disable cron job

# Utilities
iot ip              # Show VM IP addresses
iot web             # Show all service URLs
iot env             # Show current .env config
iot conf            # Show telegraf config
iot help            # Show all commands

# Remote Access & Tunneling
# Cloudflare tunnels run in background, provide public HTTPS URLs
# Tunnel state tracked in ~/logs/tunnel/ (PID, URL, logs)
iot tunnel                # Start Grafana tunnel (default)
iot tunnel-grafana        # Start Grafana tunnel (port 3000)
iot tunnel-influxdb       # Start InfluxDB tunnel (port 8086)
iot tunnel-schedule       # Start set-schedule tunnel (port 8000)
iot tunnel-stop           # Stop all running tunnels
iot tunnel-stop-grafana   # Stop Grafana tunnel only
iot tunnel-stop-influxdb  # Stop InfluxDB tunnel only
iot tunnel-stop-schedule  # Stop schedule tunnel only
iot tunnel-status         # Show status of all tunnels (PID, URL)
iot tunnel-logs [name] [n]  # View tunnel logs (name: grafana/influxdb/schedule)
```

**Tunnel usage example:**
```bash
# Start a tunnel to share Grafana dashboard publicly
iot tunnel-grafana
# ✓ grafana tunnel ready: https://abc-xyz-123.trycloudflare.com

# Check all tunnels
iot tunnel-status
# NAME            STATUS     PID      URL
# grafana         running    12345    https://abc-xyz-123.trycloudflare.com

# Stop when done
iot tunnel-stop-grafana
# ✓ Grafana tunnel stopped
```

### Adding Devices

The stack automatically discovers Govee devices from your account:

1. Add device in Govee app and assign to a room
2. Wait for hourly cron job, OR run: `iot update`
3. Device mappings update in `telegraf.conf`
4. Telegraf auto-restarts if config changed
5. Data appears in Grafana (may need to refresh queries)

**Note**: Devices MUST be assigned to a room in the Govee app, or the API won't return data.

### Device Renaming

The Govee API sometimes returns auto-generated garbage names like `h5075_5a9` (model + MAC suffix). You can override these locally with meaningful names:

```bash
# View all devices with current names
iot list-devices

# Interactive rename (prompts for device selection and new name)
iot rename-device

# Change room assignment
iot set-room

# Remove local override (revert to API name)
iot clear-override
```

**How it works:**
- Overrides stored in `telegraf/conf.d/device-overrides.json` (local-only, .gitignored)
- Applied automatically during `iot update` and BLE decoder startup
- Survives API changes and service restarts
- Works offline if govee2mqtt API is unavailable

**Naming rules:**
- Lowercase letters, numbers, and underscores only
- 3-50 characters
- No leading/trailing underscores

**Example:**
```bash
$ iot rename-device
Devices:
================================================================================
[1] MAC: 33FA4381ECA1... | Name: h5075_5a9 | Room: unassigned | SKU: H5075
[2] MAC: 19544381ECB1... | Name: studio_main | Room: studio_down | SKU: H5051
[0] Cancel

Select device number: 1
Enter new name (or 'cancel' to abort): green_room_sensor
Also change room? Current: 'unassigned' [y/N]: y
Enter new room name: green_room

✓ Override saved: h5075_5a9 → green_room_sensor
✓ Room updated: unassigned → green_room

Restart services to apply changes? [Y/n] y
✓ Services restarted
```

### Set-Schedule Management

Manage the festival schedule tracking application (Phase 6):

**Production commands (port 8000):**
```bash
iot schedule-up         # Start production service
iot schedule-down       # Stop production service
iot schedule-restart    # Restart production service
iot schedule-rebuild    # Rebuild and redeploy production
iot schedule-status     # Show container status
iot schedule-logs [n]   # View logs (last n lines)
iot schedule-follow     # Stream logs in real-time
iot schedule-shell      # Open shell in container
```

**Development commands (port 8001):**
```bash
iot schedule-dev-build   # Build dev image from ../COACHELLA_SET_SCHEDULE
iot schedule-dev-up      # Start dev service
iot schedule-dev-down    # Stop dev service
iot schedule-dev-restart # Restart dev service
iot schedule-dev-rebuild # Build and start dev service
iot schedule-dev-logs [n]   # View dev logs
iot schedule-dev-follow  # Stream dev logs in real-time
iot schedule-dev-shell   # Open shell in dev container
```

**Access:**
- Production: http://<server-ip>:8000
- Development: http://<server-ip>:8001
- View-only mode: append `/` to URL
- Operator mode: append `/edit` to URL

### M4300 Network Backup Management

Automate Netgear M4300 switch configuration backups via TFTP (Phase 5):

```bash
# Backup Operations
iot m4300-backup        # Run config backup for all switches
iot m4300-backup-mock   # Run in mock mode (testing, no real switches)

# View Logs & Results
iot m4300-logs [n]      # View backup logs (last n entries)
iot m4300-log-view <file>  # Display specific log file
iot m4300-list [n]      # List recent backups (last n)
iot m4300-list-all      # List all backup files

# Maintenance
iot m4300-clean         # Remove empty backup folders
iot m4300-list-switches # Show parsed switch inventory
iot m4300-rebuild       # Rebuild netgear-backup container
iot tftp-rebuild        # Recreate TFTP server container
```

**Configuration:**
- Edit `config/switches.conf` to define switch inventory
- Set credentials in `.env`: `M4300_USERNAME`, `M4300_PASSWORD_M4300`, `M4300_PASSWORD_OTHER`
- TFTP server runs on port 69 (UDP)
- Backups stored in Docker volume: `netgear-backups:/backups`

### Dashboard Backup & Provisioning

Automate Grafana dashboard backups and convert them to provisioning format for version control:

**First-time setup (on server):**
```bash
sudo pip3 install requests
# or: sudo apt install python3-requests
```

**Backup dashboards:**
```bash
iot backup-dashboards     # Fetches all dashboards via API
                          # Saves to ~/backups/grafana/dashboards/YYYY-MM-DD-HHMMSS/
```

**Convert to provisioning format:**
```bash
# Interactive picker - shows backups grouped by session
iot provision-dashboard

# Or specify file directly
iot provision-dashboard ~/backups/grafana/dashboards/2026-02-18-120000/dashboard-abc123.json

# Auto-detects format (v2beta1 or legacy JSON)
# Removes instance-specific metadata (version, id, timestamps)
# Saves to grafana/provisioning/dashboards/
# Grafana auto-loads within 10 seconds
```

**Remove from provisioning:**
```bash
# Interactive picker - shows all provisioned dashboards
iot deprovision-dashboard

# Or specify file directly
iot deprovision-dashboard grafana/provisioning/dashboards/dashboard-xyz.json

# Grafana auto-removes dashboard within 10 seconds
```

**Optional daily backups:**
```bash
iot setup-dashboard-cron    # Install 2am daily backup job
iot remove-dashboard-cron   # Remove cron job
```

**Restore dashboard from backup:**
```bash
iot restore-dashboard [file]  # Restore dashboard via Grafana API
```

**Workflow:**
1. Make dashboard changes in Grafana UI
2. Run `iot backup-dashboards` to export
3. Run `iot provision-dashboard` to convert (interactive picker)
4. Git commit the provisioned file for version control
5. Run `iot deprovision-dashboard` to remove old versions (optional)

### Advanced Usage

Power-user commands for advanced data management and system control.

#### ESP32 BLE Gateway Configuration

Configure ESP32 hardware gateways for optimal BLE scanning:

```bash
iot esp32-enable    # Enable ESP32 BLE gateway decoder mode
iot esp32-verbose   # Configure for maximum scan frequency
```

These commands adjust BLE decoder settings to work with ESP32 OpenMQTTGateway hardware.

#### MQTT Utilities

```bash
iot clear-retained [topic]  # Clear retained MQTT messages
                            # Useful for removing stale sensor data
```

#### Data Deletion (⚠️ DANGEROUS)

**WARNING:** These commands permanently delete data. Use with extreme caution.

```bash
iot delete-device-data   # Interactive deletion wizard
                         # Options: old data, current device, or all data

iot nuke                 # Delete ALL data in sensors bucket
                         # Cannot be undone

iot nuke-geist           # Delete all Geist measurements
                         # Useful for schema changes
```

**Safe workflow for schema changes:**
1. Backup data first: `iot backup`
2. Run `iot nuke-geist` to clear old measurements
3. Restart Telegraf: `iot restart telegraf`
4. Verify new data flows correctly

### Troubleshooting

**govee2mqtt won't connect to AWS IoT (timeout errors)**
- Symptom: Logs show "timeout connecting to aqm3wd1qlc3dy-ats.iot.us-east-1.amazonaws.com:8883"
- Cause: IPv6 is enabled but can't route to internet (common on Hyper-V VMs)
- Fix:
  ```bash
  sudo sysctl -w net.ipv6.conf.eth0.disable_ipv6=1
  echo "net.ipv6.conf.eth0.disable_ipv6=1" | sudo tee -a /etc/sysctl.conf
  iot restart govee2mqtt
  ```

**Telegraf shows "parsing 'Available': invalid syntax"**
- Cause: govee2mqtt publishes status messages on sensor topics
- Impact: Harmless noise in logs, data still flows correctly
- Fix: Planned for Phase 4 (separate topic filtering)

**No data showing up in Grafana**
1. Check devices are assigned to rooms in Govee app
2. Verify govee2mqtt is running: `iot lg`
3. Check MQTT messages: `iot mqtt "gv2mqtt/#" 10`
4. Query InfluxDB directly: `iot query 1h 10`
5. Make sure Grafana queries use correct tags (device_name, room, sensor_type)

**Docker containers won't start**
```bash
# Check Docker is running
sudo systemctl status docker

# Check for port conflicts
sudo netstat -tlnp | grep -E ':(3000|8086|1883)'

# View detailed container errors
docker compose logs [service-name]
```

<!-- ROADMAP -->
## Roadmap

### ✅ Phase 1: Core Data Pipeline (Completed)
- Docker Compose stack with 6 services
- govee2mqtt polling Govee Cloud API every 10 minutes
- MQTT broker for pub/sub messaging
- Telegraf for MQTT→InfluxDB routing
- InfluxDB 2.x for time-series storage
- Grafana for dashboards
- ble-decoder for real-time BLE data processing

### ✅ Phase 2: External Access & Network (Completed)
- Static IP configuration (<server-ip>)
- mDNS support via avahi-daemon (dpx-showsite-ops.local)
- Tailscale mesh VPN for secure remote SSH
- Cloudflare Tunnel for temporary public dashboard sharing
- Grafana public dashboard links

### ✅ Phase 2.5: Friendly Name Tags (Completed)
- Telegraf regex processors to extract device_id from MQTT topics
- Telegraf enum processors to map device_id → device_name and room
- `update-device-map.sh` script to fetch device info from govee2mqtt API
- Hourly cron job to auto-update mappings when devices change

### ✅ Phase 3: Deployment & Documentation (Completed)
- Setup automation (setup.sh)
- Documentation (README, ARCHITECTURE, GRAFANA_SETUP)
- Volume backup/restore scripts
- Full deployment testing

### ✅ Phase 4: BLE Gateway + Decoder Containerization (Completed)
- **ble-decoder service** dockerized and operational (Dockerfile.ble-decoder, docker-compose integration)
- **ESP32 gateways** deployed with OpenMQTTGateway firmware
- **Theengs Gateway** available as fallback
- **Real-time BLE data** (<5 sec latency) alongside cloud data
- **Unified Telegraf config** with source tagging (gv_cloud, dpx_ops_decoder)
- **Process guards** prevent duplicate decoder instances
- **Management commands**: ble-up/down/restart/rebuild/status/logs/follow
- **Grafana dashboards** showing both data sources

### ✅🚧 Phase 5: Network Device Backups (Core Complete, SNMP Monitoring Pending)
- ✅ **TFTP server deployed** in docker-compose with persistent storage
- ✅ **dpx-netgear-backup integrated** as submodule with 11 CLI commands
- ✅ **M4300 backup automation** via TFTP protocol
- ✅ **Switch inventory management** via config/switches.conf
- 🚧 **M4300 SNMP monitoring** (port status, VLANs, errors, uptime) — pending implementation
- 🚧 **Grafana dashboards** for backup status — pending implementation

### ✅🚧 Phase 6: Set Schedule Integration (Software Complete, Hardware Testing Blocked)
- ✅ **Git submodule integrated** (services/set-schedule)
- ✅ **Docker services deployed** on port 8000 (production) + 8001 (dev)
- ✅ **16 management commands** implemented (8 production + 8 dev)
- ✅ **Real-time WebSocket sync** across all connected clients
- ✅ **Operator + view-only modes** for schedule tracking
- ✅ **Google Sheets integration** for schedule data persistence
- ✅ **Art-Net DMX implementation** complete (app/artnet.py, test_artnet.py)
- ✅ **Slip tracking** and downstream impact projections
- 🚧 **Art-Net hardware testing** blocked by Phase 11 VLAN configuration

### 📋 Phase 7: Metrics-Driven Device Control (Planned)
- **Govee + Hue API** integration for lighting control
- **ControlByWeb** relay devices (HTTP/SNMP API)
- **Digital Loggers** Web Power Switch integration
- **Rule engine** for threshold-based automation
- **Grafana control panels** for manual device control

### 🚧 Phase 8: Consumables Tracking (In Progress - H5194 Proof of Concept)
- **Govee H5194 meat probe** BLE decoder (proof-of-concept underway)
- **Scripts**: scan_h5194.py/scan_h5194_simple.py for packet reverse engineering
- **Integration plan**: Merge H5194 logic into ble_decoder.py container
- **HID keyboard + push button** input interfaces
- **Hotdog consumption tracking** with leaderboard/stats dashboards
- **Temperature monitoring** for food safety compliance
- **InfluxDB + Grafana** for consumption analytics

### 📋 Phase 9: Wireless Temperature Probes (Planned)
- Compatibility research (H5179, H5075 models)
- BLE integration for multi-probe deployment
- Specialized monitoring dashboards
- Use cases: food storage, equipment rooms, HVAC validation

### 🚧 Phase 10: LTC Monitoring (Proof of Concept)
- Real-time Linear Timecode signal monitoring
- rs-ltc-qc integration for quality analysis
- Sub-100ms latency target
- Grafana dashboards for A/V sync health
- **Outstanding**: Hardware setup adjacent to NIC

### 📋 Phase 11: External Network VLAN Integration (Planned)
- **VLAN segmentation** for show site operations
- **Traffic analysis**: Art-Net (VLAN 20), IoT (110), Internet (90), System (50)
- **IP schema redesign** with CIDR ranges (ready/in-progress)
- **M4300 VLAN configuration** with inter-VLAN routing
- **Coachella spreadsheet** network documentation
- **Blocks**: Phase 6 Art-Net testing (requires VLAN 20)

### 📋 Phase 12: VLAN Meistro Configuration Tool (Exploratory)
- Web-based VLAN config generator
- Outputs deployment scripts for M4300
- Streamlines multi-site deployments
- **Status**: Low priority, may be deferred indefinitely

See the [open issues](https://github.com/dubpixel/dpx_showsite_ops/issues) for a full list of proposed features (and known issues).

<!-- CONTRIBUTING -->
## Contributing

_Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**._

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Top contributors:
<a href="https://github.com/dubpixel/dpx_showsite_ops/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=dubpixel/dpx_showsite_ops" alt="contrib.rocks image" />
</a>

<!-- LICENSE -->
## License

This software is licensed under the **GNU General Public License v3.0 (GPL-3.0)** — the Free Software Foundation's strong copyleft license for software.

__In plain terms:__

* **Use it, learn from it, build on it** — go buck wild!!
* **Modify and distribute** — you can change it and share your changes
* **Share your source code** — if you distribute modified versions, you must share the source under GPL-3.0
* **Give credit** — preserve copyright notices and attributions
* **Commercial use is allowed** — sell it, deploy it commercially, just keep it open source
* **No warranty** — software is provided as-is

The GPL-3.0 ensures this remains free and open source software forever. See the [LICENSE](LICENSE) file for the full legal text.

_Questions about the license? Open an issue or reach out._

### License History

This project has evolved through different licenses:

| Version | License | Period | Git Reference |
|---------|---------|--------|---------------|
| v1.0 | MIT License | Feb 5, 2026 | [f9a0428](https://github.com/dubpixel/dpx_showsite_ops/commit/f9a0428) |
| v1.0.1 - v1.4.2 | CC BY-SA 4.0 | Feb 5 - Mar 5, 2026 | [1a415f0](https://github.com/dubpixel/dpx_showsite_ops/commit/1a415f0) onwards |
| v2.0.0+ | **GPL-3.0** | March 5, 2026+ | Current |

**Why the changes?**
- **MIT → CC BY-SA 4.0**: Initial attempt to prevent unmodified commercial resale
- **CC BY-SA 4.0 → GPL-3.0**: CC BY-SA is designed for creative works (documentation, art), not software. GPL-3.0 is the proper strong copyleft license for software projects.

As the sole copyright holder, the author has relicensed the codebase. Previous versions obtained during earlier license periods remain available under those original licenses.

<!-- CONTACT -->
## Contact

### Joshua Fleitell - i@dubpixel.tv

Project Link: [https://github.com/dubpixel/dpx_showsite_ops](https://github.com/dubpixel/dpx_showsite_ops)

<!-- ACKNOWLEDGMENTS -->
## Acknowledgments

- **Tim Nauss** – for giving me the Govee sensors last year and being an ever-present source of truth and strength.
- **Sean Green** – for validating my exploration into self-built showsite tools and pushing me to go further.
- Govee for the cloud API and sensor platform
- Eclipse Mosquitto for reliable MQTT brokering
- Influx Data for InfluxDB time-series database
- Grafana Labs for visualization platform
- Telegraf contributors for data pipeline

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/dubpixel/dpx_showsite_ops.svg?style=flat-square
[contributors-url]: https://github.com/dubpixel/dpx_showsite_ops/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/dubpixel/dpx_showsite_ops.svg?style=flat-square
[forks-url]: https://github.com/dubpixel/dpx_showsite_ops/network/members
[stars-shield]: https://img.shields.io/github/stars/dubpixel/dpx_showsite_ops.svg?style=flat-square
[stars-url]: https://github.com/dubpixel/dpx_showsite_ops/stargazers
[issues-shield]: https://img.shields.io/github/issues/dubpixel/dpx_showsite_ops.svg?style=flat-square
[issues-url]: https://github.com/dubpixel/dpx_showsite_ops/issues
[license-shield]: https://img.shields.io/github/license/dubpixel/dpx_showsite_ops.svg?style=flat-square
[license-url]: https://github.com/dubpixel/dpx_showsite_ops/blob/main/LICENSE
[linkedin-shield]: https://img.shields.io/badge/-LinkedIn-black.svg?style=flat-square&logo=linkedin&colorB=555
[linkedin-url]: https://linkedin.com/in/jfleitell
[product-architecture]: images/architecture.png
[product-grafana]: images/grafana-dashboard.png
[linkedin-url]: https://linkedin.com/in/jfleitell
[product-front]: images/front.png
[product-rear]: images/rear.png
[product-front-rendering]: images/front_render.png
[product-rear-rendering]: images/rear_render.png
[product-pcbFront]: images/pcb_front.png
[product-pcbRear]: images/pcb_rear.png
[Next.js]: https://img.shields.io/badge/next.js-000000?style=for-the-badge&logo=nextdotjs&logoColor=white
[Next-url]: https://nextjs.org/
[React.js]: https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB
[React-url]: https://reactjs.org/
[Vue.js]: https://img.shields.io/badge/Vue.js-35495E?style=for-the-badge&logo=vuedotjs&logoColor=4FC08D
[Vue-url]: https://vuejs.org/
[Angular.io]: https://img.shields.io/badge/Angular-DD0031?style=for-the-badge&logo=angular&logoColor=white
[Angular-url]: https://angular.io/
[Svelte.dev]: https://img.shields.io/badge/Svelte-4A4A55?style=for-the-badge&logo=svelte&logoColor=FF3E00
[Svelte-url]: https://svelte.dev/
[Laravel.com]: https://img.shields.io/badge/Laravel-FF2D20?style=for-the-badge&logo=laravel&logoColor=white
[Laravel-url]: https://laravel.com
[Bootstrap.com]: https://img.shields.io/badge/Bootstrap-563D7C?style=for-the-badge&logo=bootstrap&logoColor=white
[Bootstrap-url]: https://getbootstrap.com
[JQuery.com]: https://img.shields.io/badge/jQuery-0769AD?style=for-the-badge&logo=jquery&logoColor=white
[JQuery-url]: https://jquery.com 
[KiCad.org]: https://img.shields.io/badge/KiCad-v8.0.6-blue
[KiCad-url]: https://kicad.org 
[Fusion-360]: https://img.shields.io/badge/Fusion360-v4.2.0-green
[Autodesk-url]: https://autodesk.com 
[FastLed.io]: https://img.shields.io/badge/FastLED-v3.9.9-red
[FastLed-url]: https://fastled.io 
