# Changelog

All notable changes to dpx-showsite-ops.

---

## [Unreleased]

### Phase 5 - Network Backups (Planned)  
- TFTP server deployment
- M4300 automated backup scripts
- Monitoring integration

### Future Phases
- See ROADMAP.md for Phases 7-14 (device control, consumables tracking, etc.)

---

## [1.4.2] - 2026-02-27

### Documentation
- **ROADMAP Updates**:
  - Added Phase 4.5: Geist Watchdog SNMP Integration (✅ Complete) - documents existing SNMP monitoring deployed alongside BLE infrastructure
  - Updated Phase 9: Changed from "Planned" to "Feasibility Check" - quick 30-minute validation test for temperature probes
  - Elevated Phase 10: LTC Monitoring from "Future Ideas" to "Production Priority" with expanded implementation plan (awaiting rs-ltc-qc repo access)
  - Phase 6: Updated Art-Net testing approach - using USB NIC workaround (KISS) instead of waiting for Phase 11 VLAN work. Phase 11 provides production-ready VLAN isolation later.
  - Phase 8: Updated to reflect H5194 meat probe proof-of-concept work in progress
  - Phase 11: Removed "blocks Phase 6" language - now provides production-ready Art-Net isolation while Phase 6 proceeds with USB NIC approach
- **CONTEXT.md Updates**:
  - Changed "Planned Phase 6 addition" to "Phase 6 Integration (🚧 In Progress)" - service deployed but not fully tested/complete
- **File Management**:
  - Renamed `docs/context_public/ Plan-Integrate Set-Schedule Service i.md` to `Plan-Integrate-Set-Schedule-Service.md` (removed leading space, added hyphens)
  - Archived old session notes to `docs/context_private/archive/`: phase6-set-schedule-context.md, session-2026-02-12-documentation-consolidation.md, govee-iot-context*.md, phase4_session_context.md, CONTEXT_old.md, GIT_QUICK_REFERENCE_old.md
- **git-workflow-cheatsheet.md**:
  - Added comprehensive "Releases & Tags" section with git tag, GitHub CLI, and release workflow examples

---

## [1.412] - 2026-02-25

### Added
- **Dashboard Restore Utility**:
  - New `restore-dashboard.py` script for restoring backups as fully editable dashboards via Grafana API
  - Interactive picker UI matching provision-dashboard workflow
  - Generates unique UIDs (timestamp-based) to prevent conflicts with existing dashboards
  - New `iot restore-dashboard [file]` command with .env environment variable support
  - Complements existing provisioning workflow for complete backup/restore/provision lifecycle

### Changed
- **Dashboard Provisioning Enhancements**:
  - `provision-dashboard.py` now adds `[P]` prefix to dashboard titles for visual identification
  - Appends `-p` suffix to UIDs to prevent provisioned dashboards from overwriting live copies
  - Updated help text in manage.sh to clarify provisioning creates read-only dashboards
  - Prevents accidental deletion of working dashboards when provisioning from similar backups

---

## [1.4.0] - 2026-02-24

### Added
- **BLE Decoder Service Containerization** (Phase 4j):
  - Created `Dockerfile.ble-decoder` for production deployment (Python 3.11-slim with curl, ping debugging tools)
  - Added `ble-decoder` service to docker-compose.yml with mosquitto integration
  - Process guard for `iot ble-decode` command prevents duplicate instances (pgrep/pkill logic)
  - Environment variable configuration via Dockerfile (BROKER, GOVEE_API_URL, SHOWSITE_NAME)
  - Docker service runs with `host.docker.internal` networking for govee2mqtt API access
  - Volume mount for device-overrides.json (read-only)
  - New management commands: `ble-up`, `ble-down`, `ble-restart`, `ble-rebuild`, `ble-status`, `ble-logs`, `ble-follow`
  - Log shortcut: `lb [n]` for ble-decoder logs
  - Added to `iot la` (all logs) command
- **Set-Schedule Service Integration** (Phase 6):
  - Git submodule integration at `services/set-schedule` (https://github.com/macswg/coachella_set_schedule)
  - Docker service for festival schedule tracking app on port 8000
  - Development instance support on port 8001
  - 16 new management commands:
    - Production: `schedule-up`, `schedule-down`, `schedule-restart`, `schedule-status`, `schedule-logs`, `schedule-follow`, `schedule-rebuild`, `schedule-shell`
    - Development: `schedule-dev-build`, `schedule-dev-up`, `schedule-dev-down`, `schedule-dev-restart`, `schedule-dev-logs`, `schedule-dev-follow`, `schedule-dev-rebuild`, `schedule-dev-shell`
  - Configuration via .env (STAGE_NAME, TIMEZONE, Google Sheets integration, Art-Net DMX support)
  - WebSocket-based real-time schedule sync across all clients
  - Operator mode (edit times) and view-only mode
  - Tracks "slip" (lateness vs scheduled times) and projects downstream impacts
  - Optional Google Sheets integration for schedule data persistence
  - Documentation: `docs/Plan-Integrate Set-Schedule Service i.md` (integration guide)
- **MQTT Maintenance Tools**:
  - `iot clear-retained [topic]` command for cleaning stale MQTT retained messages
  - Interactive cleanup with confirmation and progress reporting
  - Default clears all topics (`#`), accepts specific topic patterns
  - Resolves ghost data issues from device renames

### Changed
- Updated `setup.sh` to initialize set-schedule git submodule automatically
- Enhanced `scripts/manage.sh` help text with BLE Decoder and Set-Schedule sections
- Updated `.env.example` with:
  - `SHOWSITE_NAME` for site identification
  - Comprehensive set-schedule configuration variables (SCHEDULE_PORT, STAGE_NAME, TIMEZONE, USE_GOOGLE_SHEETS, GOOGLE_SHEETS_ID, GOOGLE_SHEET_TAB, GOOGLE_SERVICE_ACCOUNT_FILE, ARTNET_* variables)
- Updated `iot web` command to include set-schedule URL (port 8000)
- Updated `iot la` (all logs) command to include ble-decoder service

### Documentation
- Created `docs/Plan-Integrate Set-Schedule Service i.md` - Comprehensive integration guide (477 lines)
- Created `docs/context_public/set-schedule-development.md` - Development workflow documentation
- Updated `docs/ROADMAP.md` marking Phase 4 complete (2026-02-24), Phase 6 complete (2026-02-24)
- Updated `docs/context_public/CONTEXT.md` with Phase 6 section

---

## [1.3.0] - 2026-02-18

### Added
- **Device Name Override System**: Persistent device renaming for BLE sensors
  - Created `scripts/manage-devices.py` - Interactive CLI tool for device management
  - New `iot` commands: `list-devices`, `rename-device`, `set-room`, `clear-override`
  - Override storage in `telegraf/conf.d/device-overrides.json` (local-only, .gitignored)
  - Interactive device selection with numbered menu
  - Auto-detection of bad/auto-generated device names
  - Override file format with device name, room, and SKU overrides
  - Template file: `device-overrides.json.example`
- **BLE Decoder Enhancements**: 
  - Override support in `scripts/ble_decoder.py` 
  - `load_devices()` applies overrides after API load
  - Logs show "Applied X override(s)" and [OVERRIDE] markers
  - MAC address normalization (12-char suffix matching)
- **Update Command Integration**:
  - Modified `scripts/update-device-map.sh` to merge API + overrides via manage-devices.py
  - Renamed log message to "Device mappings updated (with overrides)"
- **Validation & Safety**:
  - Device name validation (lowercase_underscore, 3-50 chars, no duplicates)
  - Auto-restart prompts after rename operations
  - Atomic JSON file writes with temp file pattern

### Changed
- Updated `.gitignore` to exclude `device-overrides.json`
- Enhanced ROADMAP.md with Phase 2.8 (completed) and Phase 11 (future backup/sync)
- Updated README.md with device renaming documentation and examples

---

## [1.2.0] - 2026-02-16

### Added
- **BLE Decoder Service**: Dockerized Python BLE decoder for Govee sensors
  - Created Dockerfile.ble-decoder with Python 3.11 slim image
  - Added requirements-ble-decoder.txt (paho-mqtt dependency)
  - Integrated ble-decoder service into docker-compose.yml
  - Auto-connects to mosquitto and govee2mqtt API
  - Decodes H5051, H5074, H5075 manufacturer data to standardized MQTT topics
- **Management Commands**: New iot commands for BLE decoder
  - `iot ble-up/down/restart/rebuild` - Service control
  - `iot ble-status` - Container status
  - `iot ble-logs [n]` / `iot lb [n]` - View logs (default 30 lines)
  - `iot ble-follow` - Real-time log streaming
  - `iot ble-decode` - Manual foreground mode (for debugging)
- **Configuration**: Added SHOWSITE_NAME to .env.example for site identification
- **setup.sh**: Added Python3/pip3 checks and paho-mqtt installation
  - Checks for Python3 and pip3 availability
  - Automatically installs paho-mqtt for manual decoder mode
  - Gracefully handles missing dependencies (Docker mode unaffected)

### Changed
- Updated manage.sh to include ble-decoder in `iot la` (all logs)
- Updated help text with BLE Decoder service section

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
