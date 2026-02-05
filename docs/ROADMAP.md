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

**Status**: ✅ Complete - all deliverables shipped

---

## 📋 Phase 4: BLE Gateway Integration (Planned)

**Goal**: Read sensors locally via BLE instead of waiting for cloud sync

**What we'll build:**

### Phase 4.1: BLE Gateway (Parallel Paths)
- **Windows NUC Path**: Use existing Theengs Gateway on Windows NUC (ready now)
- **ESP32 Path**: Optional WT32-ETH01 or similar with Theengs firmware (future)
- Both paths publish to standardized MQTT topics
- Either can work independently; both together = redundancy

**Hardware Options** (ESP32 path, optional):
- WT32-ETH01 (ethernet + BLE built-in) - easiest
- Olimex ESP32-POE (PoE power + ethernet + BLE)
- ESP32 DevKit + W5500 module (most flexible, needs wiring)

### Phase 4.2: BLE Decoder Service
- Deploy `ble_decoder.py` as systemd service
- Subscribes to Theengs raw MQTT topics
- Decodes H5051/H507x manufacturerdata
- Publishes to standardized topics (govee/ble/{room}/{metric})
- Auto-loads device mappings from govee2mqtt API

### Phase 4.3: Unified Telegraf Config
- Single telegraf.conf with two MQTT inputs:
  - Cloud source: gv2mqtt/# topics (10min intervals)
  - BLE source: govee/ble/# topics (real-time, from Theengs)
- Add `source` tag to differentiate data origin
- Keep device_name, room, sensor_type tags on both

### Phase 4.4: Grafana Dashboard Update
- Update queries to handle both sources
- Add source selector/filter
- Show data latency by source
- Compare cloud vs BLE accuracy

**Benefits:**
- Sub-second latency instead of 10-20 minutes
- No dependency on Govee cloud uptime
- More frequent readings (every BLE broadcast)
- Better debugging (see exactly what sensor transmits)

**Status**: 📋 Ready - use Windows NUC Theengs Gateway; ESP32 optional later

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

## 🔮 Future Phases (Ideas)

### Phase 7: Additional Sensor Types
- Motion sensors (PIR)
- Light sensors
- Door/window sensors
- Energy monitoring (smart plugs)

### Phase 8: Automation & Control
- Home Assistant integration
- Scene triggers based on sensor data
- HVAC control based on temperature readings
- Lighting automation

### Phase 9: Alert System
- Slack/Discord/email notifications
- Temperature threshold alerts
- Device offline detection
- API health monitoring

### Phase 10: Multi-Site Support
- Replicate stack to additional show sites
- Centralized monitoring dashboard
- Site comparison views
- Federated data queries

---

## Success Metrics

**Phase 3 (Complete):**
- [x] Someone can deploy from scratch in under 15 minutes
- [x] Zero manual config file editing after setup.sh
- [x] All secrets in .env, nothing hardcoded
- [x] Documentation covers 90%+ of common issues

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

---

## Timeline

**Phase 3**: ✅ Complete (2026-02-05)  
**Phase 4**: Ready to start (2026-02-05) - use Theengs Gateway on Windows NUC  
**Phase 5**: After Phase 4 completes - hardware available at studio  
**Phase 6**: Can start anytime (independent of 4/5) - Sean's repo ready  

**Custom ESP32 hardware**: Optional future enhancement, not blocking current phases

---

## Notes

- Each phase builds on previous phases without breaking existing functionality
- Phases can be skipped or reordered based on priority
- Phase 4 will use existing Windows NUC with Theengs Gateway (already tested)
- Custom ESP32 BLE gateway is a nice-to-have for later, not required
- Phase 5 depends on stabilizing M4300 scripts in separate repo
- Phase 6 is independent and can run in parallel with 4/5
- Naming convention (dpx-showsite-ops) enables multi-site deployments
