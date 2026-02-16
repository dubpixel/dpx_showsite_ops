# Changelog

All notable changes to dpx-showsite-ops.

---

## [Unreleased]

### Phase 4 - BLE Gateway (Planned)
- BLE decoder service for real-time sensor data
- ESP32 or Windows Theengs Gateway integration
- Unified Telegraf config with source tagging

### Phase 5 - Network Backups (Planned)  
- TFTP server deployment
- M4300 automated backup scripts
- Monitoring integration

---

## [1.1.0] - 2026-02-16

### Added
- **setup.sh**: Automated first-time deployment script
  - Checks Docker and Docker Compose prerequisites
  - Creates .env from .env.example template
  - Prompts to edit .env with user's preferred editor (nano/vi)
  - Initializes git submodule for services/set-schedule
  - Installs iot wrapper with auto-detected installation path (fixes dir name mismatch)
  - Optional cron job installation for hourly device-map updates
  - Shows next steps with actual IP address
- **VERSION file**: Centralized version number (1.1.0)
- **AGENTS.md**: GitHub agent workflow guidelines in .github/ directory

### Changed
- **CONTEXT.md**: Updated iot wrapper installation instructions to reference setup.sh
  - Added collapsible manual installation section for reference
  - Note about auto-detected path
- **APPLICATION_SETUP_GUIDE_COMPLETE.md**: Added Part 11 ESP32 BLE Gateway Setup section

---

## [1.0.1] - 2025-02-05

### Phase 3 - Final Touches
- Added docs/GRAFANA_SETUP.md with complete datasource and dashboard setup guide
- Reorganized repository structure: moved scripts to scripts/ directory
- Fixed all path references in manage.sh, update-device-map.sh, and iot wrapper
- Updated .gitignore to exclude backup and temporary files
- Tested all iot commands working correctly after reorganization

---

## [1.0.0] - 2025-02-05
---

## [Unreleased]

### Phase 3 - Deployment & Documentation (In Progress)
- Added README.md with quick start guide
- Added ROADMAP.md with phase tracking
- Added ARCHITECTURE.md with data flow diagrams
- Added .gitignore for secrets and logs
- Added .env.example template
- Created setup.sh for automated deployment
- Enhanced manage.sh with better error handling
- Fixed iot command to use wrapper script instead of symlink
- Organized scripts into scripts/ directory
- Project renamed from dpx-coachella-ops to dpx-showsite-ops

---

## [1.0.0] - 2025-02-05

### Phase 2.7 - Hostname Cleanup
- Changed hostname from dpx-coachella-ops to dpx-showsite-ops
- Updated /etc/hosts and restarted avahi-daemon
- Verified mDNS and Tailscale auto-updated

### Phase 2.6 - IPv6 Network Fix
- Identified IPv6 causing govee2mqtt AWS IoT timeouts
- Disabled IPv6 on eth0 at kernel level
- Made permanent via /etc/sysctl.conf
- govee2mqtt now connects reliably

### Phase 2.5 - Friendly Name Tags
- Added Telegraf regex processors to extract device_id from MQTT topics
- Added Telegraf enum processors to map device_id → device_name and room
- Created update-device-map.sh script to fetch device info from govee2mqtt API
- Implemented hourly cron job for auto-updating device mappings
- Tags confirmed working in InfluxDB and Grafana queries

### Phase 2 - External Access & Network
- Configured static IP (<server-ip>)
- Set up mDNS via avahi-daemon (dpx-showsite-ops.local)
- Installed and configured Tailscale for remote SSH access
- Set up Cloudflare Tunnel for temporary public dashboard sharing
- Created Grafana public dashboard links

### Phase 1 - Core Data Pipeline
- Created Docker Compose stack with 5 services
- Deployed govee2mqtt to poll Govee Cloud API
- Set up Mosquitto MQTT broker
- Configured Telegraf for MQTT→InfluxDB routing
- Deployed InfluxDB 2.x for time-series storage
- Set up Grafana for visualization
- Data flowing end-to-end from sensors to dashboards

---

## Version History

- **1.0.0** (2025-02-05): Initial stable release with cloud monitoring
- **Future**: Phase 4 (BLE gateway), Phase 5 (network backups)
