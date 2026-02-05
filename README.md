# dpx-showsite-ops

Operations stack for DPX show sites. A unified platform for IoT monitoring, environmental sensors, and network infrastructure management.

**Current Deployment:** Govee IoT monitoring via cloud API + planned BLE gateway integration  
**Future:** Network device backups, additional sensor types, automation workflows

---

## What's Running Now

- **Govee IoT Stack**: Temperature/humidity monitoring via Govee H5051 sensors
- **MQTT Broker**: Eclipse Mosquitto for sensor data pub/sub
- **Time Series DB**: InfluxDB 2.x for storing sensor readings
- **Visualization**: Grafana dashboards with public sharing
- **Data Pipeline**: Telegraf for MQTT→InfluxDB routing with tag enrichment
- **LIVE DEMO**: [HERE](https://calling-penalties-slides-timothy.trycloudflare.com/public-dashboards/21f922f1bbcb4bba81b1a7fed502d1c3)

---

## Prerequisites

- **OS**: Ubuntu 22.04+ (tested on Ubuntu Server 24.04)
- **Docker**: Docker Engine 20.10+ with Compose plugin
- **Network**: Static IP recommended (current deployment: `192.168.1.100`)
- **Optional**: Tailscale for remote access, Cloudflare Tunnel for public dashboards

---

## Post-Deployment Setup

After running `iot up`, see [Grafana Setup Guide](docs/GRAFANA_SETUP.md) for connecting InfluxDB and creating dashboards.

---

## Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/youruser/dpx-showsite-ops.git
cd dpx-showsite-ops
```

### 2. Run setup
```bash
./setup.sh
```

This will:
- Check for Docker/Compose
- Create directory structure
- Copy `.env.example` to `.env` and prompt you to edit it
- Set up the `iot` management command

### 3. Configure credentials
```bash
nano .env
```

Fill in your:
- Govee account credentials (email/password)
- Govee API key (from https://developer.govee.com)
- Timezone (e.g., `America/New_York`)

### 4. Start the stack
```bash
iot up
```

### 5. Access services
- **Grafana**: http://192.168.1.100:3000 (admin/grafanapass123)
- **InfluxDB**: http://192.168.1.100:8086 (admin/influxpass123)
- **MQTT**: 192.168.1.100:1883 (anonymous)

---

## Management Commands

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
iot la [n]          # all logs

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

---

## Architecture
```
Govee Devices (H5051, H6076)
    ↓
Govee Cloud API (polls every 10min)
    ↓
govee2mqtt (AWS IoT MQTT bridge)
    ↓
Mosquitto MQTT Broker (gv2mqtt/# topics)
    ↓
Telegraf (tag enrichment: device_name, room, sensor_type)
    ↓
InfluxDB (govee bucket)
    ↓
Grafana (dashboards + public links)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed data flow, MQTT topics, and configuration notes.

---

## Adding Devices

The stack automatically discovers Govee devices from your account:

1. Add device in Govee app and assign to a room
2. Wait for hourly cron job, OR run: `iot update`
3. Device mappings update in `telegraf.conf`
4. Telegraf auto-restarts if config changed
5. Data appears in Grafana (may need to refresh queries)

**Note**: Devices MUST be assigned to a room in the Govee app, or the API won't return data.

---

## Troubleshooting

### govee2mqtt won't connect to AWS IoT (timeout errors)
**Symptom**: Logs show "timeout connecting to aqm3wd1qlc3dy-ats.iot.us-east-1.amazonaws.com:8883"

**Cause**: IPv6 is enabled but can't route to internet (common on Hyper-V VMs)

**Fix**:
```bash
sudo sysctl -w net.ipv6.conf.eth0.disable_ipv6=1
echo "net.ipv6.conf.eth0.disable_ipv6=1" | sudo tee -a /etc/sysctl.conf
iot restart govee2mqtt
```

### Telegraf shows "parsing 'Available': invalid syntax"
**Cause**: govee2mqtt publishes status messages on sensor topics

**Impact**: Harmless noise in logs, data still flows correctly

**Fix**: Planned for Phase 4 (separate topic filtering)

### No data showing up in Grafana
1. Check devices are assigned to rooms in Govee app
2. Verify govee2mqtt is running: `iot lg`
3. Check MQTT messages: `iot mqtt "gv2mqtt/#" 10`
4. Query InfluxDB directly: `iot query 1h 10`
5. Make sure Grafana queries use correct tags (device_name, room, sensor_type)

### Docker containers won't start
```bash
# Check Docker is running
sudo systemctl status docker

# Check for port conflicts
sudo netstat -tlnp | grep -E ':(3000|8086|1883)'

# View detailed container errors
docker compose logs [service-name]
```

### iot command not working after symlink
The `iot` command uses a wrapper script, not a direct symlink. If `iot status` fails:
```bash
sudo rm /usr/local/bin/iot
sudo tee /usr/local/bin/iot > /dev/null << 'WRAPPER'
#!/bin/bash
cd /home/dubpixel/dpx_govee_stack
exec /home/dubpixel/dpx_govee_stack/manage.sh "$@"
WRAPPER
sudo chmod +x /usr/local/bin/iot
```

### Logs disappeared after restart
Docker logs are lost when containers are recreated (`docker compose down && up`). Use `iot backup` regularly to preserve Grafana dashboards and InfluxDB data.

---

## Remote Access

### Tailscale (Recommended)
Secure mesh VPN for SSH and service access from anywhere:
```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Connect from remote machine
ssh dubpixel@dpx-showsite-ops
```

### Cloudflare Tunnel (For sharing dashboards)
Temporary public URL for Grafana:
```bash
iot tunnel
# Copy the generated URL and share
```

For persistent public access, use Grafana's built-in public dashboard feature.

---

## Project Roadmap

See [ROADMAP.md](ROADMAP.md) for detailed phase plans.

**Completed:**
- ✅ Phase 1-2: Core data pipeline, external access
- ✅ Phase 2.5-2.7: Tag enrichment, IPv6 fix, hostname cleanup

**In Progress:**
- 🚧 Phase 3: Deployment automation, documentation, Git setup

**Planned:**
- 📋 Phase 4: BLE gateway (ESP32 + Theengs) for local sensor reads
- 📋 Phase 5: TFTP server + automated network device backups

---

## Contributing

This is a personal ops stack, but feel free to fork and adapt for your own use. If you find bugs or have suggestions, open an issue.

---

## License

MIT License - see LICENSE file for details

---

## Credits

Built with:
- [govee2mqtt](https://github.com/wez/govee2mqtt) by Wez Furlong
- [Eclipse Mosquitto](https://mosquitto.org/)
- [InfluxDB](https://www.influxdata.com/)
- [Telegraf](https://www.influxdata.com/time-series-platform/telegraf/)
- [Grafana](https://grafana.com/)
- [Theengs Gateway](https://github.com/theengs/gateway) (planned for Phase 4)
