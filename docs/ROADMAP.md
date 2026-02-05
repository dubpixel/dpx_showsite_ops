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
- [ ] Create `backup-restore.sh` script for volume backups
- [ ] Test full deployment from scratch

### Phase 3.2: Documentation
- [x] Write README.md with quick start guide
- [x] Write ROADMAP.md (this file)
- [ ] Write ARCHITECTURE.md with technical deep dive
- [ ] Create CHANGELOG.md for version history
- [ ] Document all known issues and fixes
- [ ] Create service-specific docs (Govee quirks, etc.)

### Phase 3.3: Version Control
- [x] Create .gitignore
- [ ] Initialize Git repository
- [ ] Tag v1.0 release
- [ ] Push to GitHub as `dpx-showsite-ops`
- [ ] Set up GitHub Actions for validation (optional)

**Status**: 🚧 In Progress - core docs done, testing pending

---

## 📋 Phase 4: BLE Gateway Integration (Planned)

**Goal**: Read sensors locally via BLE instead of waiting for cloud sync

**What we'll build:**

### Phase 4.1: ESP32 BLE Gateway
- ESP32 + W5500 ethernet module (or WT32-ETH01)
- Flash with Theengs firmware
- Publishes raw BLE advertisements to MQTT
- Hardwired to network for reliability
- Alternative: Continue using Theengs Gateway on Windows NUC

**Hardware Options:**
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
  - BLE source: govee/ble/# topics (real-time)
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

**Status**: 📋 Planned - hardware ordered, design documented

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

## 🔮 Future Phases (Ideas)

### Phase 6: Additional Sensor Types
- Motion sensors (PIR)
- Light sensors
- Door/window sensors
- Energy monitoring (smart plugs)

### Phase 7: Automation & Control
- Home Assistant integration
- Scene triggers based on sensor data
- HVAC control based on temperature readings
- Lighting automation

### Phase 8: Alert System
- Slack/Discord/email notifications
- Temperature threshold alerts
- Device offline detection
- API health monitoring

### Phase 9: Multi-Site Support
- Replicate stack to additional show sites
- Centralized monitoring dashboard
- Site comparison views
- Federated data queries

---

## Success Metrics

**Phase 3 (Current):**
- [ ] Someone can deploy from scratch in under 15 minutes
- [ ] Zero manual config file editing after setup.sh
- [ ] All secrets in .env, nothing hardcoded
- [ ] Documentation covers 90%+ of common issues

**Phase 4:**
- [ ] BLE latency under 5 seconds
- [ ] Zero data loss during cloud outages
- [ ] Both sources visible in Grafana with source tag

**Phase 5:**
- [ ] Network configs backed up daily
- [ ] 30-day retention of config history
- [ ] Recovery time < 5 minutes for switch restore

---

## Timeline
## Notes

- Each phase builds on previous phases without breaking existing functionality
- Phases can be skipped or reordered based on priority
- Hardware delays may shift Phase 4 timeline
- Phase 5 depends on stabilizing M4300 scripts in separate repo
- Naming convention (dpx-showsite-ops) enables multi-site deployments

## Timeline

**Phase 3**: Target completion 2025-02-05 (today)  
**Phase 4**: Starting today (2025-02-05) - using Theengs Gateway on Windows NUC  
**Phase 5**: Immediately after Phase 4 - hardware available at studio  

**Custom ESP32 hardware**: Optional future enhancement, not blocking current phases

---

## Notes

- Each phase builds on previous phases without breaking existing functionality
- Phases can be skipped or reordered based on priority
- Phase 4 will use existing Windows NUC with Theengs Gateway (already tested)
- Custom ESP32 BLE gateway is a nice-to-have for later, not required
- Phase 5 depends on stabilizing M4300 scripts in separate repo
- Naming convention (dpx-showsite-ops) enables multi-site deployments
