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

## ✅ Phase 2.8: Device Name Override System (Completed)

**Goal**: Provide persistent local device renaming independent of Govee Cloud API

**What we built:**
- Local JSON override file (`device-overrides.json`) with MAC → name/room mappings
- Python helper script (`manage-devices.py`) for override management
- Interactive rename commands (`iot rename-device`, `iot set-room`, `iot clear-override`)
- Auto-detection of bad names with heuristic pattern matching
- BLE decoder and Telegraf both load overrides on startup
- Graceful degradation when govee2mqtt API is offline
- Override file excluded from git tracking (local-only configuration)

**Benefits:**
- Replace auto-generated garbage names (e.g., `h5075_5a9`) with meaningful labels
- Overrides survive `iot update` commands and service restarts
- Works offline if Govee Cloud API is unavailable
- Interactive menu-driven UI (no typing MAC addresses)
- Automatic service restart prompts after rename

**Status**: ✅ Complete - override system operational

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

### Phase 4.5: Geist Watchdog SNMP Integration ✅

**Infrastructure monitoring add-on** deployed alongside BLE gateways for enterprise environmental monitoring.

**What was deployed:**
- ✅ SNMP input configured in `telegraf/conf.d/geist-watchdog.conf` (197 lines)
- ✅ Geist Watchdog 100 device @ dpx-geist.local (192.168.1.214)
- ✅ Internal sensors: Temperature, humidity, dewpoint
- ✅ Remote sensors: 3x temperature probes, 2x airflow sensors
- ✅ 30-second polling interval via SNMP v2c
- ✅ Data flowing to InfluxDB measurements: `geist_internal`, `geist_temp_remote`, `geist_airflow_remote`
- ✅ `iot nuke-geist` cleanup command for schema issues
- ✅ Grafana dashboards operational

**Use case:** Server room and infrastructure climate monitoring with wired reliability.

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

## � Phase 5: Network Device Backups (In Progress)

**Goal**: Automated backups of network infrastructure configs with monitoring

**What we're building:**

### Phase 5.1: TFTP Server Deployment
- Deploy TFTP service (Docker container or host-based service)
- Base configuration for secure access (read/write paths, access controls)
- Storage volume for switch configs with rotation policy
- Integration with dpx-showsite-ops stack networking
- **Source**: Work from https://github.com/dubpixel/dpx-netgear-backup (mostly complete)

### Phase 5.2: dpx-netgear-backup Integration
- **Repo**: https://github.com/dubpixel/dpx-netgear-backup (private)
- **Current State**: Backup script complete, needs cleanup and documentation
- **Integration Plan**:
  - Clean up repo (add README, document workflow)
  - Add as git submodule to `services/netgear-backup/` or `scripts/netgear-backup/`
  - Add to workspace for easy submodule updates
  - Wire into `iot` management commands (e.g., `iot m4300-backup`)
  - Configure cron for automated daily backups
  - Git-commit configs for version history
  - Alert on backup failures (InfluxDB metrics + Grafana)

### Phase 5.3: M4300 Network Connectivity
- **Current Challenge**: M4300 8x8 switch with OOB port at studio
  - Switch likely at default IP: 192.168.0.238 or .239
  - VM on different subnet: 192.168.1.100
  - Windows host on DHCP (may not have static route)
- **Solution Options**:
  - Add secondary IP to VM network interface (192.168.0.x)
  - Configure static route on VM for 192.168.0.0/24 subnet
  - Bridge VM to physical network with access to both subnets
  - Or: Configure M4300 OOB port to 192.168.1.x subnet (if accessible)
- **Testing**: Verify connectivity from VM to M4300 OOB interface
- **Documentation**: Document final IP schema and connectivity method

### Phase 5.4: M4300 SNMP Monitoring
- SNMP poller configuration in Telegraf
- Metric collection:
  - Port status (up/down, speed, duplex)
  - VLAN information
  - Uptime and system info
  - Interface errors/drops
  - Temperature (if available)
- InfluxDB integration for historical data
- Grafana dashboard for switch health monitoring
- Alert thresholds for port state changes

### Phase 5.5: Monitoring Integration
- Track backup job success/failure in InfluxDB
- Grafana dashboard for backup status
- Slack/email alerts on failures (optional)
- Config diff visualization over time

**Status**: 🚧 In Progress - TFTP and connectivity work underway

---

## 🚧 Phase 6: Set Schedule Integration (Art-Net Testing Incomplete)

**Goal**: Integrate real-time show schedule tracking for festival operations

**Sean's Repo**: https://github.com/macswg/coachella_set_schedule

**What we built:**

### Phase 6.1: Git Submodule Setup ✅
- Added Sean's repo as `services/set-schedule/` submodule
- Easy updates without code duplication
- Tracks commits independently

### Phase 6.2: Docker Service ✅
- Integrated existing Dockerfile from upstream repo
- Added `set-schedule` service to docker-compose.yml
- Runs on port 8000 alongside other services (dev instance on 8001)
- Restart policy and volume mounts configured for Google Sheets auth

### Phase 6.3: CLI Integration ✅
- Added 16 management commands for production and development instances
- Added `iot web` URL for schedule access
- Updated `manage.sh` with set-schedule lifecycle management

### Phase 6.4: Update Scripts ✅
- Updated `setup.sh` for automatic submodule initialization
- Updated `manage.sh` with comprehensive command set and help text

### Phase 6.5: Art-Net DMX Integration (Incomplete)
- **Implementation Status**: ✅ Complete (app/artnet.py, test_artnet.py)
  - UDP listener on port 6454
  - 16-bit DMX value parsing (channels 1-512)
  - Converts to nits (0-11,000)
  - WebSocket broadcast on value change
  - Disabled by default (ARTNET_ENABLED=false)
- **Outstanding Items**:
  - [ ] Art-Net testing with actual DMX controller hardware
  - [ ] Usage documentation (enable/configure/troubleshoot)
  - [ ] Network configuration for Art-Net traffic (blocked by Phase 11)
  - [ ] Production deployment validation

**What It Is:**
- FastAPI web app for real-time schedule tracking
- WebSocket sync across all connected clients
- Google Sheets integration for schedule data persistence
- Operator mode (edit times) + view-only mode
- Tracks "slip" (lateness vs scheduled times) and projects downstream impacts
- Art-Net DMX integration for lighting control (implemented, not tested)

**Benefits:**
- Central operations dashboard for set times
- Real-time visibility across mobile + desktop clients
- Historical tracking for post-event analysis
- Optional: Future InfluxDB integration for slip metrics in Grafana dashboards
- DMX lighting control via Art-Net (pending testing)

**Status**: 🚧 In Progress - core features complete, Art-Net testing depends on Phase 11

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

## � Phase 8: Consumables Tracking (In Progress - H5194 Proof of Concept)

**Goal**: Monitor and track consumable item usage by person, type, and over time

**Current Status**: Detoured to proof-of-concept for Govee H5194 meat probe integration

**What we're building:**

### Phase 8.0: Govee H5194 Meat Probe Integration (Active Development)
- **Status**: 🔬 Proof-of-concept phase
- **Current Work**:
  - BLE packet reverse engineering complete
  - Scripts: `scripts/scan_h5194.py` (advanced), `scan_h5194_simple.py` (basic)
  - Multiple scanning modes: 60s watch, 20s fast, deep scan, live monitoring
  - Multi-probe support (up to 4 probes per H5194 base unit)
- **Next Steps**:
  - Merge H5194 decoder logic into `ble_decoder.py` container
  - MQTT payload standardization with existing sensor topics
  - Test with ESP32 gateways (currently script uses direct BLE on Mac)
  - InfluxDB integration for temperature history
  - Grafana dashboards for multi-probe monitoring
- **Use Case**: Temperature monitoring for food prep/service at show sites

### Phase 8.1: HID Input Integration
- USB barcode scanner / HID keyboard support
- Alphanumeric ID entry interface
- Quantity input forms
- Person/item/timestamp association
- Integration with H5194 temperature data

### Phase 8.2: Consumables Database
- InfluxDB schema for consumption events
- Person ID tracking (badge scan, manual entry)
- Item type taxonomy (food, beverage, supplies, etc.)
- Quantity and timestamp logging
- Temperature history from H5194 probes

### Phase 8.3: Reporting & Analytics
- Grafana dashboards for consumption trends
- Per-person usage tracking
- Item type breakdowns over time
- Inventory depletion projections
- Peak consumption period analysis
- Temperature compliance reporting

### Phase 8.4: Input Interfaces
- Web form for manual entry
- Dedicated HID keyboard station for fast entry
- Mobile-friendly interface for field use
- Batch entry support for bulk logging

### Phase 8.5: Hotdog Consumption Tracking
- **Temperature Monitoring**: Govee H5194 meat probes for food safety
- **Consumption Tracking UI**:
  - Push button interface for general consumption counter
  - Numeric keyboard with 3-letter ID entry (localized, secure)
  - Alternative: Typing observed but acceptable for event environment
- **Leaderboard/Stats Board**:
  - Real-time consumption stats per person
  - Total consumption counters
  - InfluxDB storage for historical analysis
- **Optional**: SMS short code integration to link 3-letter ID to phone number
- **Grafana Integration**: Live leaderboard dashboard with competitor rankings

**Use Cases:**
- Track catering consumption per person per meal
- Monitor supplies depletion rates
- Food temperature compliance monitoring
- Hotdog eating contest scoring and leaderboards
- Identify high-use items for restocking
- Generate per-event expense reports
- Analyze consumption patterns across multiple events

**Status**: 🚧 In Progress - H5194 BLE decoder proof-of-concept underway, full phase follows

---

## 🌡️ Phase 9: Wireless Temperature Probes (Feasibility Check)

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

**Status**: 🧪 Feasibility Test - Quick 30-minute validation test with probes on hand. Just need to verify BLE broadcast format compatibility with existing decoder infrastructure.

---

## 🔮 Future Phases (Additional Ideas)

### Phase 10: LTC Monitoring Real-Time Dashboard (Production Priority)

**Goal**: Real-time Linear Timecode monitoring for A/V sync validation in live show environments

**What we'll build:**

### Phase 10.1: rs-ltc-qc Integration
- Integrate rs-ltc-qc (private repo - awaiting access for detailed planning)
- Parse timecode quality analysis output
- Extract sync health metrics, drift detection, signal loss events
- Determine data format (JSON, text logs, metrics endpoint?)
- Define deployment architecture (same host, separate machine?)

### Phase 10.2: Data Pipeline
- Stream rs-ltc-qc output to InfluxDB
- Schema design: timecode values, drift measurements, quality scores
- Sub-100ms latency from signal capture to database write
- Timestamp synchronization strategy

### Phase 10.3: Real-Time Dashboard
- Grafana panel showing live timecode display
- Visual alerts for drift >2 frames
- Signal loss/recovery indicators
- Historical drift trend visualization
- Multi-source timecode comparison (if applicable)

### Phase 10.4: Alert System
- Trigger conditions: drift threshold, signal loss, quality degradation
- Alert delivery mechanism (Grafana alerts, external notification?)
- Configurable thresholds per show environment

**Use Cases:**
- Live show A/V sync monitoring
- Recording studio timecode validation  
- Multi-camera sync health tracking
- Post-event analysis of sync issues

**Outstanding Items:**
- [ ] rs-ltc-qc repo access for output format analysis
- [ ] Timecode generation setup adjacent to NIC
- [ ] Hardware selection/procurement for LTC input
- [ ] Testing with rs-ltc-qc decoder
- [ ] Network latency profiling for sub-100ms target
- [ ] Deployment target specification
- [ ] Alert delivery requirements

**Status**: 📋 Production Requirement - awaiting rs-ltc-qc repo access to begin implementation

---

## 📋 Phase 11: External Network VLAN Integration (Planned)

**Goal**: Design and implement VLAN segmentation for show site operations with new IP addressing schema

**Status**: 📋 Planned - blocks Phase 6 Art-Net testing completion

**What we'll build:**

### Phase 11.1: Traffic Analysis & Requirements
- **Document traffic types and VLAN assignments**:
  - **VLAN 20**: Art-Net (DMX/lighting control)
  - **VLAN 110**: IoT devices (sensors, Govee, Geist)
  - **VLAN 90**: Internet gateway
  - **VLAN 50**: System/management network
- Bandwidth requirements per VLAN
- Inter-VLAN routing rules and policies
- Security considerations (ACLs, isolation)

### Phase 11.2: IP Schema Redesign
- **CIDR ranges**: User has VLAN CIDR ranges ready/in progress
- New subnet allocation per VLAN
- Static IP assignments for critical devices (dpx-showsite-ops VM, switches, gateways)
- DHCP ranges and reservations per VLAN
- DNS/mDNS considerations across VLANs
- Migration plan from current flat 192.168.1.0/24 network

### Phase 11.3: Documentation & Planning
- **Coachella Spreadsheet**: Document network architecture for event ("killing 2 stoners with 1 bong")
- Network diagrams (logical topology, physical layout)
- IP allocation tables per VLAN
- Device inventory with VLAN assignments
- Cabling plan and port assignments

### Phase 11.4: M4300 VLAN Configuration
- Port VLAN assignments (access vs trunk)
- Inter-VLAN routing setup (L3 switch or external router)
- ACLs for traffic isolation
- QoS policies for Art-Net priority (VLAN 20)
- VLAN tagging and untagged port configuration

### Phase 11.5: Testing & Validation
- Connectivity testing per VLAN
- Art-Net traffic validation on VLAN 20 (unblocks Phase 6)
- IoT sensor communication on VLAN 110
- Inter-VLAN routing verification
- Performance benchmarking (latency, throughput)
- Failover scenarios and recovery testing

**Dependencies**: 
- Phase 5.3-5.4 (M4300 connectivity and monitoring) should be complete for visibility
- M4300 switch at studio (currently at 192.168.0.238/239, needs connectivity from VM)

**Blocks**: 
- Phase 6.5 Art-Net testing cannot complete without VLAN 20 configured

**Status**: 📋 Planned - CIDR design in progress, spreadsheet documentation pending

---

## 📋 Phase 12: VLAN Meistro Configuration Tool (Exploratory)

**Goal**: Web-based VLAN configuration generator that outputs deployment scripts

**Status**: 📋 Planned - exploratory concept for multi-site deployment efficiency

**What we'll explore:**

### Phase 12.1: Requirements & Design
- **User Input**:
  - Device types and quantities
  - Network topology (switch count, uplink configuration)
  - Site-specific requirements (VLANs needed, bandwidth)
- **Output**: Shell script for M4300 switch configuration
- **Template System**: Common show site layouts (single-stage, multi-stage, festival)
- **Validation**: IP schema conflicts, VLAN ID availability, port capacity

### Phase 12.2: Web Interface (If Pursuing)
- FastAPI or Flask web application
- Form-based configuration wizard
- Real-time IP allocation preview
- VLAN assignment visualization
- Download generated configuration script
- Optional: Direct API integration to push configs to switches

### Phase 12.3: Script Generation
- **M4300 CLI command templates**:
  - VLAN creation and naming
  - Port VLAN assignment (access/trunk)
  - Inter-VLAN routing configuration
  - ACL generation for traffic isolation
- Static IP allocation script for dpx-showsite-ops stack
- DHCP server configuration (if managed by M4300)
- Documentation generation:
  - Network diagram (Graphviz or similar)
  - IP allocation table (CSV/Markdown)
  - Port assignment map

**Note**: This is an exploratory concept to streamline multi-site deployments. May be deferred indefinitely if manual VLAN configuration proves sufficient or if tool development effort exceeds value.

**Status**: 📋 Planned - low priority, exploratory

---

### Phase 13: Device Override Backup & Sync
- Backup device-overrides.json to cloud storage or scruot
- Sync overrides across multiple showsite deployments
- Version control integration for team collaboration
- Optional removal of .gitignore for committed overrides
- Merge conflict resolution for multi-operator scenarios

**Success Metrics**:
- [ ] Automated backup of device-overrides.json to external storage
- [ ] Cross-site synchronization of device naming conventions
- [ ] Conflict resolution strategy for simultaneous edits
- [ ] Recovery time <1 minute for override restore

### Phase 14: Alert System
- Slack/Discord/email notifications
- Temperature threshold alerts
- Device offline detection
- API health monitoring
- Schedule slip notifications
- LTC sync loss alerts

### Phase 15: Multi-Site Support
- Replicate stack to additional show sites
- Centralized monitoring dashboard
- Site comparison views
- Federated data queries

### Phase 16: Additional Sensor Types
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
- [x] BLE latency under 5 seconds
- [x] Zero data loss during cloud outages
- [x] Both sources visible in Grafana with source tag
- [x] Windows NUC Theengs Gateway configured and tested

**Phase 5:**
- [ ] TFTP server deployed and operational
- [ ] dpx-netgear-backup repo integrated as submodule
- [ ] M4300 connectivity established from VM (192.168.0.x subnet access)
- [ ] M4300 SNMP monitoring live in Grafana
- [ ] Network configs backed up daily
- [ ] 30-day retention of config history
- [ ] Recovery time < 5 minutes for switch restore

**Phase 6:**
- [x] Set-schedule service running in Docker
- [x] Real-time schedule updates via WebSocket
- [x] Manual set time tracking working end-to-end
- [ ] Art-Net implementation tested with DMX hardware
- [ ] Art-Net usage documentation complete
- [ ] Optional: Slip data flowing to InfluxDB

**Phase 7:**
- [ ] Control at least 2 device types (Govee + Hue or similar)
- [ ] ControlByWeb relay control operational
- [ ] Digital Loggers power switch integration working
- [ ] Rule engine responds to threshold triggers within 5 seconds
- [ ] Manual override capability working
- [ ] Dashboard shows device states and automation status

**Phase 8:**
- [ ] H5194 BLE decoder integrated into ble_decoder.py
- [ ] H5194 temperature data flowing to InfluxDB
- [ ] HID keyboard input working for ID + quantity entry
- [ ] Data flowing to InfluxDB with person/item/timestamp
- [ ] Grafana dashboards show consumption trends per person and item type
- [ ] Hotdog leaderboard dashboard operational
- [ ] Sub-30 second entry time for typical transaction

**Phase 9:**
- [ ] Feasibility assessment complete (range, battery, cost)
- [ ] At least 1 Govee temperature probe model decoded
- [ ] Multi-probe tracking working simultaneously
- [ ] Specialized dashboard showing temperature gradients

**Phase 10:**
- [ ] LTC hardware interface selected and procured
- [ ] Timecode generation setup adjacent to NIC
- [ ] rs-ltc-qc integration complete
- [ ] Sub-100ms latency achieved
- [ ] Grafana dashboard showing real-time sync status

**Phase 11:**
- [ ] VLAN traffic requirements documented
- [ ] IP schema redesigned and documented (CIDR ranges)
- [ ] Coachella spreadsheet network documentation complete
- [ ] M4300 VLANs configured and tested
- [ ] Art-Net traffic isolated on VLAN 20 (unblocks Phase 6)
- [ ] Inter-VLAN routing validated

**Phase 12:**
- [ ] Requirements defined and approved
- [ ] Web interface deployed (if pursuing)
- [ ] Script generation tested on M4300
- [ ] Multi-site deployment validated

---

## Timeline

**Phase 3**: ✅ Complete (2026-02-05)  
**Phase 4**: ✅ Complete (2026-02-24) - BLE decoder dockerized and operational  
**Phase 5**: 🚧 In Progress (2026-02-27) - TFTP server and M4300 connectivity work underway  
**Phase 6**: 🚧 In Progress - Core complete, Art-Net testing blocked by Phase 11  
**Phase 7**: 📋 Planned - After Phase 4 + Phase 6, requires BLE data and schedule integration  
**Phase 8**: 🚧 In Progress (2026-02-27) - H5194 proof-of-concept, detoured from Phase 5  
**Phase 9**: 📋 Planned - After Phase 4, extends BLE infrastructure  
**Phase 10**: 🚧 Proof of Concept (2026-02-27) - LTC monitoring exploration, parallel with Phase 8  
**Phase 11**: 📋 Planned - CIDR ranges in progress, blocks Phase 6 completion  
**Phase 12**: 📋 Exploratory - Low priority, multi-site deployment tool  

**Current Focus** (2026-02-27): 
- **Primary**: Phase 5 (M4300 setup) - should be working on this
- **Detour**: Phase 8 (H5194 meat probes) - proof-of-concept exploration
- **Parallel**: Phase 10 (timecode monitoring) - proof-of-concept exploration
- **Blocked**: Phase 6 Art-Net testing - requires Phase 11 VLAN configuration

---

## Notes

- Each phase builds on previous phases without breaking existing functionality
- Phases can be skipped or reordered based on priority
- **Phase 5**: TFTP work comes FIRST (dpx-netgear-backup repo), then M4300 connectivity, then SNMP monitoring
- **Phase 6**: Art-Net code complete but untested - requires Phase 11 VLAN configuration
- **Phase 8**: Currently exploring H5194 meat probe integration as proof-of-concept (detour from Phase 5)
- **Phase 10**: Timecode monitoring in proof-of-concept phase (parallel with Phase 8)
- **Phase 11**: VLAN work blocks Phase 6 Art-Net testing - CIDR ranges ready/in-progress
- **Phase 12**: Exploratory concept, may be deferred indefinitely
- Custom ESP32 BLE gateways: Deployed and operational (Phase 4 complete)
- M4300 8x8 switch available at studio (192.168.0.238 or .239, needs connectivity from VM at 192.168.1.100)
- dpx-netgear-backup repo (private): Backup script mostly complete, needs integration
- Naming convention (dpx-showsite-ops) enables multi-site deployments
