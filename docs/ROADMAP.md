# Project Roadmap

This document tracks the evolution of dpx-showsite-ops from initial Govee monitoring to a full operations platform for show sites.

---

## ✅ Phase 1: Core Data Pipeline (Completed)

**Goal**: Get Govee sensor data into a time-series database with visualization

**What we built:**
- Docker Compose stack with 5 services
- govee2mqtt polling Govee Cloud API every 10 minutes
- MQTT broker for pub/sub messaging
- Telegraf for MQTT→InfluxDB routing
- InfluxDB 2.x for time-series storage
- Grafana for dashboards

**Status**: ✅ Complete - data flowing end-to-end

---

## ✅ Phase 2: External Access & Network (Completed)

**Goal**: Make the stack accessible remotely and fix network issues

**What we built:**
- Static IP configuration (<server-ip>)
- mDNS support via avahi-daemon (dpx-showsite-ops.local)
- Tailscale mesh VPN for secure remote SSH
- Cloudflare Tunnel for temporary public dashboard sharing
- Grafana public dashboard links

**Status**: ✅ Complete - accessible from anywhere

---

## ✅ Phase 2.5: Friendly Name Tags (Completed)

**Goal**: Replace MAC addresses with human-readable device names in data

**What we built:**
- Telegraf regex processors to extract device_id from MQTT topics
- Telegraf enum processors to map device_id → device_name and room
- `update-device-map.sh` script to fetch device info from govee2mqtt API
- Hourly cron job to auto-update mappings when devices change

**Status**: ✅ Complete - tags confirmed working in InfluxDB and Grafana

---

## ✅ Phase 2.6: IPv6 Network Fix (Completed)

**Goal**: Fix govee2mqtt AWS IoT connection timeouts

**What we fixed:**
- Identified IPv6 causing timeouts to AWS IoT endpoint
- Disabled IPv6 on eth0 at kernel level
- Made permanent via /etc/sysctl.conf
- Documented in troubleshooting guide

**Status**: ✅ Complete - govee2mqtt connects reliably

---

## ✅ Phase 2.7: Hostname Cleanup (Completed)

**Goal**: Use RFC-compliant hostname and rebrand for reusability

**What we did:**
- Renamed server from `dpx-coachella-ops` to `dpx-showsite-ops`
- Updated /etc/hosts and avahi-daemon
- Verified mDNS and Tailscale auto-updated
- Established naming convention for multi-site deployments

**Status**: ✅ Complete - hostname clean and discoverable

---

## 🚧 Phase 3: Deployment & Documentation (In Progress)

**Goal**: Make the stack reproducible and shareable

**What we're building:**

### Phase 3.1: Deployment Automation
- [x] Create `setup.sh` for initial deployment
- [x] Create `.env.example` template with comments
- [x] Enhance `manage.sh` with better help and error handling
- [x] Fix `iot` wrapper script (not symlink) to handle paths correctly
- [x] Create `backup-restore.sh` script for volume backups
- [x] Test full deployment from scratch

### Phase 3.2: Documentation
- [x] Write README.md with quick start guide
- [x] Write ROADMAP.md (this file)
- [x] Write ARCHITECTURE.md with technical deep dive
- [x] Create CHANGELOG.md for version history
- [x] Document all known issues and fixes
- [x] Create service-specific docs (Govee quirks, etc.)

### Phase 3.3: Version Control
- [x] Create .gitignore
- [x] Initialize Git repository
- [x] Tag v1.0 release
- [x] Push to GitHub as `dpx-showsite-ops`
- [x] Set up comprehensive documentation links

### Phase 3.4: Dashboard Backup & Provisioning Utility
- [x] `backup-grafana-dashboards.py` - Fetch all dashboards via Grafana API
- [x] `provision-dashboard.py` - Convert exported dashboards to provisioning format
- [x] Format auto-detection (v2beta1 vs legacy JSON)
- [x] Metadata cleanup (removes instance-specific version, id, timestamps)
- [x] Preserves essential fields (uid, panel IDs, datasource refs)
- [x] CLI integration via manage.sh (`iot backup-dashboards`, `iot provision-dashboard`)
- [x] Optional cron setup for daily automated backups

**Purpose**: Streamlines dashboard version control and deployment by automating the export → clean → provision workflow. Dashboards backed up daily to `manual_dashboard_backup/`, manually promoted to `provisioning/dashboards/` when ready for deployment.

**Benefits**:
- Automated nightly backups prevent dashboard loss
- One-command conversion eliminates manual JSON editing
- Git-trackable provisioned dashboards for version control
- Consistent deployment across stack instances

**Status**: ✅ Complete - all deliverables shipped

---

## � Phase 4: BLE Gateway Integration (In Progress)

**Goal**: Read sensors locally via BLE instead of waiting for cloud sync

**What we've built:**

### Phase 4.1: BLE Gateway (Parallel Paths) ✅
- ✅ ESP32 gateway deployed (192.168.1.213, OpenMQTTGateway v1.8.1)
- ✅ Theengs Gateway deployed (Windows NUC, 192.168.1.68)
- ✅ Both publish to standardized MQTT topics
- Both gateways operational with redundancy

### Phase 4.2: BLE Decoder Service ✅
- ✅ ble_decoder.py script created and functional
- ✅ Subscribes to both ESP32 and Theengs MQTT topics
- ✅ Decodes H5051/H507x manufacturerdata
- ✅ Publishes to demo_showsite topics with source tagging
- ✅ Loads device mappings from govee2mqtt API
- ✅ Dockerized as ble-decoder service in docker-compose.yml
- ✅ Full management via iot commands (ble-up/down/restart/logs)

### Phase 4.3: Unified Telegraf Config ✅
- ✅ Modular telegraf.conf structure (base config + device-mappings.conf)
- ✅ Two MQTT inputs configured:
  - Cloud source: gv2mqtt/# topics (10min intervals)
  - BLE source: demo_showsite/# topics (real-time)
- ✅ Source tagging implemented (gv_cloud, dpx_ops_decoder)
- ✅ BLE regex processor extracts source_node, room, device_name, sensor_type
- ✅ Dynamic enum mappings regenerated by update-device-map.sh

### Phase 4.4: Grafana Dashboard Update ✅
- ✅ Dashboards created with time series, gauges, stat panels
- ✅ Queries handle multiple sources (gv_cloud, dpx_ops_decoder)
- ✅ Custom display names via map() showing source, node, room, device
- ✅ Real-time data flowing from both cloud and BLE sources

**Benefits:**
- Sub-second latency instead of 10-20 minutes
- No dependency on Govee cloud uptime
- More frequent readings (every BLE broadcast)
- Better debugging (see exactly what sensor transmits)

### Outstanding Items

#### Critical
1. **MQTT Retained Message Ghost Data** - ble_decoder.py publishes with `retain=True` to topics containing device names. When devices are renamed (e.g., `studio_5051_down` → `5051_studio_down`), old retained messages persist on old topic paths. Every Telegraf restart (hourly cron) causes resubscription, replaying both old and new retained messages, creating duplicate time series in InfluxDB with frozen ghost data.
   - **Trigger**: update-device-map.sh unconditionally restarts Telegraf hourly (no diff check)
   - **Impact**: Stale data appears in Grafana dashboards alongside current data
   - **Workaround**: Manually clear old retained messages with `mosquitto_pub -r -n`
   - **Fix plan**: See [plan-mqtt-cleanup.md](context_public/plan-mqtt-cleanup.md)

2. **update-device-map.sh Lacks Diff Check** - Script unconditionally restarts Telegraf every hour even when device mappings haven't changed, causing unnecessary service interruptions and replaying retained messages.
   - **Current**: Always runs `docker compose restart telegraf`
   - **Needed**: Compare new config to existing, only restart if different
   - **Benefit**: Reduces hourly disruptions, minimizes ghost data exposure

3. **BLE Decoder restart on name changes** - Decoder loads device map once at startup; needs API polling or cron restart

#### High Priority
4. **ESP32 pubadvdata persistence** - Setting resets on reboot; need auto-enable script or systemd timer

#### Medium Priority
5. **Telegraf "Available" error suppression** - govee2mqtt status messages trigger parse errors (low impact)
6. **MAC-based device filtering** - Use z_device_id instead of device_name for stability across renames
7. **Theengs Gateway auto-start** - Windows scheduled task or NSSM service needed

**Status**: ✅ Complete - BLE decoder dockerized and operational, cleanup tasks remain

---

## 📋 Phase 5: Network Device Backups (Planned)

**Goal**: Automated backups of network infrastructure configs

**What we'll build:**

### Phase 5.1: TFTP Server
- Add TFTP service to docker-compose.yml
- Configure storage volume for switch configs
- Set up access controls (read/write paths)

### Phase 5.2: M4300 Backup Scripts
- Pull/integrate existing m4300-scripts repository
- Automate config downloads via TFTP
- Schedule daily backups via cron
- Git-commit configs for version history
- Alert on backup failures

### Phase 5.3: Monitoring Integration
- Track backup job success/failure in InfluxDB
- Grafana dashboard for backup status
- Slack/email alerts on failures (optional)

**Status**: 📋 Planned - existing scripts need integration

---

## � Phase 6: Set Schedule Integration (Planned)

**Goal**: Integrate real-time show schedule tracking for festival operations

**Sean's Repo**: https://github.com/macswg/coachella_set_schedule

**What we'll build:**

### Phase 6.1: Git Submodule Setup
- Add Sean's repo as `services/set-schedule/` submodule
- Enables easy updates without code duplication
- Tracks his commits independently

### Phase 6.2: Docker Service
- Create `Dockerfile.showsite` for containerization
- Add `set-schedule` service to docker-compose.yml
- Runs on port 8000 alongside other services
- Restart policy and volume mounts configured

### Phase 6.3: CLI Integration
- Add `iot ls` command for set-schedule logs
- Add `iot web` URL for schedule access
- Update `manage.sh` to handle set-schedule lifecycle

### Phase 6.4: Update Scripts
- Update `setup.sh` for submodule initialization
- Update `manage.sh` for logs and web commands

**What It Is:**
- FastAPI web app for real-time schedule tracking
- WebSocket sync across clients
- Google Sheets integration
- Operator mode (edit times) + view-only mode
- Tracks "slip" (lateness vs scheduled times)

**Benefits:**
- Central operations dashboard for set times
- Real-time visibility across mobile + desktop clients
- Historical tracking for post-event analysis
- Optional: Log slip data to InfluxDB for Grafana dashboards

**Status**: 📋 Planned - can be done anytime (independent of 4/5)

---

## � Phase 7: Metrics-Driven Device Control (Planned)

**Goal**: Control lighting and other devices based on sensor metrics and conditions

**What we'll build:**

### Phase 7.1: Control API Integration
- Govee API integration for controllable lights (H6159, smart plugs)
- Philips Hue bridge integration
- MQTT command topics for ESP32-controlled devices
- Unified control interface abstraction

### Phase 7.2: Rule Engine
- Define threshold-based triggers (temp > X → lights on)
- Schedule-based automation (set-schedule integration)
- Multi-condition rules (temp + time + occupancy)
- Override capabilities for manual control

### Phase 7.3: Control Dashboard
- Grafana panel for manual device control
- Visual feedback of device states
- Automation rule status display
- Quick disable/enable for automation rules

**Use Cases:**
- Turn on Govee/Hue lights when temperature drops below threshold
- Activate warning lights when show schedule slips beyond tolerance
- Control venue lighting based on set schedule state (pre-show, live, break)
- Automated climate control based on sensor readings

**Status**: 📋 Planned - depends on Phase 4 BLE data and Phase 6 schedule integration

---

## 📦 Phase 8: Consumables Tracking (Planned)

**Goal**: Monitor and track consumable item usage by person, type, and over time

**What we'll build:**

### Phase 8.1: HID Input Integration
- USB barcode scanner / HID keyboard support
- Alphanumeric ID entry interface
- Quantity input forms
- Person/item/timestamp association

### Phase 8.2: Consumables Database
- InfluxDB schema for consumption events
- Person ID tracking (badge scan, manual entry)
- Item type taxonomy (food, beverage, supplies, etc.)
- Quantity and timestamp logging

### Phase 8.3: Reporting & Analytics
- Grafana dashboards for consumption trends
- Per-person usage tracking
- Item type breakdowns over time
- Inventory depletion projections
- Peak consumption period analysis

### Phase 8.4: Input Interfaces
- Web form for manual entry
- Dedicated HID keyboard station for fast entry
- Mobile-friendly interface for field use
- Batch entry support for bulk logging

**Use Cases:**
- Track catering consumption per person per meal
- Monitor supplies depletion rates
- Identify high-use items for restocking
- Generate per-event expense reports
- Analyze consumption patterns across multiple events

**Status**: 📋 Planned - independent of other phases, can start anytime

---

## 🌡️ Phase 9: Wireless Temperature Probes (Planned)

**Goal**: Integrate Govee wireless temperature/humidity probes into monitoring stack

**What we'll explore:**

### Phase 9.1: Device Compatibility Research
- Identify compatible Govee temperature probe models (H5179, H5075, etc.)
- Protocol analysis (BLE advertisement format)
- Range and battery life testing
- Multi-probe deployment feasibility

### Phase 9.2: BLE Integration
- Extend ble_decoder.py with temperature probe support
- Add probe-specific MQTT topics and parsing
- Handle multiple probes simultaneously
- Source tagging and device mapping

### Phase 9.3: Specialized Monitoring
- Probe-specific Grafana dashboards
- Temperature gradient visualization (multiple locations)
- Alert thresholds for critical temperatures
- Historical trend analysis for venue climate patterns

### Phase 9.4: Use Case Applications
- Food storage temperature compliance
- Equipment room thermal monitoring
- Outdoor vs indoor temperature differentials
- HVAC performance validation
- Cold chain monitoring for perishables

**Feasibility Questions:**
- Can existing ESP32/Theengs gateways decode probe formats?
- What's the practical range with existing BLE infrastructure?
- Battery life under continuous monitoring?
- Cost-effectiveness vs wired sensors?

**Status**: 📋 Planned - feasibility exploration before full implementation

---

## 🔮 Future Phases (Additional Ideas)

### Phase 10: LTC Monitoring Real-Time Dashboard
- Real-time LTC (Linear Timecode) signal monitoring
- rs-ltc-qc integration for timecode quality analysis
- Visual alerts for timecode drift or signal loss
- Grafana dashboards showing timecode sync health
- Historical timecode data storage in InfluxDB
- Integration with show infrastructure for A/V sync monitoring
- Sub-100ms latency timecode display

**Success Metrics**:
- [ ] LTC signal monitoring with <100ms latency
- [ ] Visual alerts trigger on timecode drift (>2 frames)
- [ ] Historical timecode data flowing to InfluxDB
- [ ] Grafana dashboard showing real-time sync status
- [ ] rs-ltc-qc reports integrated into monitoring stack

### Phase 11: Alert System
- Slack/Discord/email notifications
- Temperature threshold alerts
- Device offline detection
- API health monitoring
- Schedule slip notifications
- LTC sync loss alerts

### Phase 12: Multi-Site Support
- Replicate stack to additional show sites
- Centralized monitoring dashboard
- Site comparison views
- Federated data queries

### Phase 13: Additional Sensor Types
- Motion sensors (PIR)
- Light sensors
- Door/window sensors
- Energy monitoring (smart plugs)

---

## Success Metrics

**Phase 3 (Complete):**
- [x] Someone can deploy from scratch in under 15 minutes
- [x] Zero manual config file editing after setup.sh
- [x] All secrets in .env, nothing hardcoded
- [x] Documentation covers 90%+ of common issues
- [x] Dashboard backup utility automates export and provisioning workflow
- [x] One-command dashboard conversion eliminates manual JSON editing

**Phase 4:**
- [ ] BLE latency under 5 seconds
- [ ] Zero data loss during cloud outages
- [ ] Both sources visible in Grafana with source tag
- [ ] Windows NUC Theengs Gateway configured and tested

**Phase 5:**
- [ ] Network configs backed up daily
- [ ] 30-day retention of config history
- [ ] Recovery time < 5 minutes for switch restore

**Phase 6:**
- [ ] Set-schedule service running in Docker
- [ ] Real-time schedule updates via WebSocket
- [ ] Manual set time tracking working end-to-end
- [ ] Optional: Slip data flowing to InfluxDB

**Phase 7:**
- [ ] Control at least 2 device types (Govee + Hue or similar)
- [ ] Rule engine responds to threshold triggers within 5 seconds
- [ ] Manual override capability working
- [ ] Dashboard shows device states and automation status

**Phase 8:**
- [ ] HID keyboard input working for ID + quantity entry
- [ ] NFC card checkout system operational for resource deployment logging
- [ ] Data flowing to InfluxDB with person/item/timestamp
- [ ] Grafana dashboards show consumption trends per person and item type
- [ ] Sub-30 second entry time for typical transaction
- [ ] Both HID keyboard and NFC card input methods supported

**Phase 9:**
- [ ] Feasibility assessment complete (range, battery, cost)
- [ ] At least 1 Govee temperature probe model decoded
- [ ] Multi-probe tracking working simultaneously
- [ ] Specialized dashboard showing temperature gradients

---

## Timeline

**Phase 3**: ✅ Complete (2026-02-05)  
**Phase 4**: ✅ Complete (2026-02-16) - BLE decoder dockerized and operational  
**Phase 5**: After Phase 4 completes - hardware available at studio  
**Phase 6**: 🔄 In Progress - set-schedule integration underway  
**Phase 7**: After Phase 4 + Phase 6 - requires BLE data and schedule integration  
**Phase 8**: Independent - can start anytime, NFC + HID keyboard tracking  
**Phase 9**: After Phase 4 - requires BLE infrastructure and decoder framework  
**Phase 10**: Planning - LTC monitoring integration with rs-ltc-qc  

**Custom ESP32 hardware**: Optional future enhancement, not blocking current phases

---

## Notes

- Each phase builds on previous phases without breaking existing functionality
- Phases can be skipped or reordered based on priority
- Phase 4 will use existing Windows NUC with Theengs Gateway (already tested)
- Custom ESP32 BLE gateway is a nice-to-have for later, not required
- Phase 5 depends on stabilizing M4300 scripts in separate repo
- Phase 6 is independent and can run in parallel with 4/5
- Phase 7 depends on Phase 4 (BLE metrics) and Phase 6 (schedule integration) for full functionality
- Phase 8 (consumables tracking) is completely independent and can start anytime
- Phase 9 (temperature probes) extends Phase 4's BLE infrastructure with additional device types
- Naming convention (dpx-showsite-ops) enables multi-site deployments
