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
[![MIT License][license-shield]][license-url]
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

Operations stack for DPX show sites. Get Govee sensor data flowing into InfluxDB with Grafana dashboards in minutes. Includes MQTT pub/sub messaging, time-series storage, and remote access via Tailscale or Cloudflare Tunnel.

**Current Deployment:** Govee IoT monitoring via cloud API + ESP32 BLE gateways (OpenMQTTGateway)
**Future:** Network device backups, additional sensor types, automation workflows

**Key features:**
- **Govee IoT Stack**: Temperature/humidity monitoring via Govee H5051 sensors
- **ESP32 BLE Gateways**: Real-time BLE data collection (<5 sec latency)
- **MQTT Broker**: Eclipse Mosquitto for sensor data pub/sub
- **Time Series DB**: InfluxDB 2.x for storing sensor readings
- **Visualization**: Grafana dashboards with public sharing
- **Data Pipeline**: Telegraf for MQTT→InfluxDB routing with tag enrichment
- **Live Demo**: [HERE](https://calling-penalties-slides-timothy.trycloudflare.com/public-dashboards/21f922f1bbcb4bba81b1a7fed502d1c3)

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
* **Hardware Gateways**: ESP32 with OpenMQTTGateway firmware
* **Infrastructure**: Docker, systemd, cron
* **Remote Access**: Tailscale, Cloudflare Tunnel (optional)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->

## Getting Started

> **🆕 First time?** See the [Complete Setup Guide](https://github.com/dubpixel/dpx_showsite_ops/blob/master/docs/SETUP_GUIDE_COMPLETE.md) — covers everything from creating the VM to Cloudflare tunnels, step by step.

### Prerequisites

- **OS**: Ubuntu 22.04+ (tested on Ubuntu Server 24.04)
- **Docker**: Docker Engine 20.10+ with Compose plugin
- **Network**: Static IP recommended (set your `<server-ip>`)
- **Optional**: Tailscale for remote access, Cloudflare Tunnel for public dashboards

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/dubpixel/dpx_showsite_ops.git
   cd dpx_showsite_ops
   ```

2. **Run setup**
   ```bash
   ./setup.sh
   ```
   This will:
   - Check for Docker/Compose
   - Create directory structure
   - Copy `.env.example` to `.env` and prompt you to edit it
   - Set up the `iot` management command

3. **Configure credentials**
   ```bash
   vim .env
   ```
   Fill in your:
   - Govee account credentials (email/password)
   - Govee API key (from https://developer.govee.com)
   - Timezone (e.g., `America/New_York`)

4. **Start the stack**
   ```bash
   iot up
   ```

5. **Access services**
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
iot ble-status      # Show status
iot ble-logs [n]    # View logs (alias: iot lb)

# Data & Monitoring
iot query [range] [rows]  # Query InfluxDB directly
iot mqtt [topic] [count]  # Subscribe to MQTT topics

# Maintenance
iot backup          # Backup Grafana + InfluxDB volumes
iot update          # Refresh device name mappings from Govee API
iot cron-on         # Enable hourly device map updates
iot cron-off        # Disable cron job

# Utilities
iot ip              # Show VM IP addresses
iot web             # Show all service URLs
iot tunnel          # Start Cloudflare tunnel (requires cloudflared)
iot env             # Show current .env config
iot conf            # Show telegraf config
iot help            # Show all commands
```

### Adding Devices

The stack automatically discovers Govee devices from your account:

1. Add device in Govee app and assign to a room
2. Wait for hourly cron job, OR run: `iot update`
3. Device mappings update in `telegraf.conf`
4. Telegraf auto-restarts if config changed
5. Data appears in Grafana (may need to refresh queries)

**Note**: Devices MUST be assigned to a room in the Govee app, or the API won't return data.

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

### ✅ Phase 4: BLE Gateway (Completed)
- ble-decoder service dockerized and operational
- ESP32 gateways deployed (OpenMQTTGateway firmware)
- Theengs Gateway available as fallback
- Real-time BLE data (<5 sec latency) alongside cloud data
- Unified Telegraf config with source tagging (gv_cloud, dpx_ops_decoder)
- Grafana dashboards showing both data sources

### 📋 Phase 5: Network Backups (Planned)
- TFTP server deployment
- M4300 automated backup scripts
- Monitoring integration

### 📋 Phase 6: Set Schedule Integration (Planned)
- Integration of Sean's coachella_set_schedule app
- Git submodule + Docker service deployment
- Real-time show schedule tracking and WebSocket updates
- Optional InfluxDB integration for slip tracking

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
This work is licensed under CC BY-SA 4.0 with the following additional restriction: __commercial sale of unmodified reproductions is prohibited.__ Modified versions that constitute a substantial remix may be sold under the same terms.

__In plain terms:__

* Use it, learn from it, build on it — go buck wild!!
* Give credit back to this project
* _Don't_ just clone this and sell it— __that's not allowed__
* Remixes, improvements, and real derivatives? Sell them, just keep the attribution and share-alike
* Share your modifications under these same terms

_Questions about commercial use? Open an issue or reach out._

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
[license-url]: https://github.com/dubpixel/dpx_showsite_ops/blob/main/LICENSE.txt
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
