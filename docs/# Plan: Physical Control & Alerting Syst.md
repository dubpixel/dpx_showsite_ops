# Plan: Physical Control & Alerting System (Merged Phase 7+8)

**Goal**: Enable metric-driven physical device control at show sites - SNMP relays (Geist, X410), Govee lights/plugs triggered by Grafana alert thresholds or manual CLI/web commands.

**Architecture**:
- **Control Layer**: Standalone Python CLIs for each device class (SNMP, HTTP API)
- **Automation Layer**: Flask webhook receiver parses Grafana alerts → calls control scripts
- **Interface Layer**: CLI wrappers (`iot` commands) + future web dashboard (Phase 7)
- **Monitoring Loop**: Telegraf polls device states → InfluxDB → Grafana dashboards → alerts → webhooks → device actions

**Implementation Priority**: Geist relay (simplest) → X410 (monitoring + control) → Govee (HTTP wrapper) → Webhook receiver → Alert rules → Web GUI (future)

---

## Steps

### Phase 1: Geist Relay Control (Foundation)

**Prerequisites**: 
- User must configure Geist Watchdog with read-write SNMP community string (via web UI)
- Recommended: Create separate "control" community (e.g., "private") for write operations, keep "public" for Telegraf read-only monitoring

**Implementation Steps**:

1. **Update Geist SNMP credentials**
   - Access Geist web interface at http://192.168.1.214 (dpx-geist.local)
   - Navigate to SNMP settings
   - Add read-write community string: "private" (or user's choice)
   - Keep "public" read-only for Telegraf monitoring

2. **Create `scripts/geist_control.py`** - Standalone SNMP control CLI
   ```python
   # Dependencies: pysnmp (~1.0.0)
   # OID: 1.3.6.1.4.1.21239.5.1.2.1.12 (relay_state)
   # Values: 0=off, 1=on
   ```
   - CLI args: `--ip`, `--community`, `--relay on|off|toggle`, `--verbose`
   - Read relay state before SNMP SET for confirmation
   - Verify state change after SET operation (read-back)
   - Return codes: 0=success, 1=connection failed, 2=SNMP error, 3=state verification failed
   - Timeout: 5 seconds
   - Output format: JSON (for scripting) or human-readable (default)

3. **Update `.env` file**
   ```bash
   # Add new variables
   GEIST_IP=192.168.1.214
   GEIST_SNMP_RW_COMMUNITY=private
   ```

4. **Add CLI wrapper to `scripts/manage.sh`**
   ```bash
   geist-relay)
       python3 scripts/geist_control.py \
           --ip ${GEIST_IP:-dpx-geist.local} \
           --community ${GEIST_SNMP_RW_COMMUNITY:-private} \
           --relay "$2"
   ```
   - Reads credentials from .env
   - Usage: `iot geist-relay on|off|toggle`

5. **Testing checklist**:
   - [ ] Standalone script: `python scripts/geist_control.py --relay on --ip dpx-geist.local --community private`
   - [ ] Verify relay audible click
   - [ ] Check InfluxDB: `SELECT relay_state FROM geist_internal ORDER BY time DESC LIMIT 1`
   - [ ] CLI wrapper: `iot geist-relay toggle`
   - [ ] Error handling: test with wrong community string, unreachable IP, invalid state

### Phase 2: X410 Integration - Monitoring + Control

**Prerequisites**:
- User provides X410 IP address (awaiting from user)
- X410 SNMP v2c enabled with community string (typically "public" for both read/write)

**Implementation Steps**:

1. **Create `telegraf/conf.d/x410.conf`** - SNMP monitoring
   ```toml
   [[inputs.snmp]]
     agents = ["${X410_IP}:161"]
     version = 2
     community = "${X410_SNMP_COMMUNITY}"
     interval = "30s"
     timeout = "5s"
     retries = 3
     
     # Digital Inputs (read-only)
     [[inputs.snmp.field]]
       name = "digital_input_1"
       oid = "1.3.6.1.4.1.30586.46.0.1"
     # ... inputs 2-4 (OIDs .0.2, .0.3, .0.4)
     
     # Relay Outputs (read/write via SNMP SET)
     [[inputs.snmp.field]]
       name = "relay_1"
       oid = "1.3.6.1.4.1.30586.46.0.5"
     # ... relays 2-4 (OIDs .0.6, .0.7, .0.8)
     
     # Vin (power supply voltage)
     [[inputs.snmp.field]]
       name = "vin"
       oid = "1.3.6.1.4.1.30586.46.0.9"
   ```
   - InfluxDB measurement: `x410_io`
   - Tags: source (device IP), host
   - Fields: digital_input_1-4, relay_1-4, vin

2. **Update `.env` and docker-compose.yml**
   ```bash
   # .env
   X410_IP=<user-provided-ip>
   X410_SNMP_COMMUNITY=public
   ```
   ```yaml
   # docker-compose.yml - telegraf service
   extra_hosts:
     - "dpx-x410.local:${X410_IP}"
   ```

3. **Create `scripts/x410_control.py`** - Standalone control CLI
   ```python
   # OIDs: relay1=.46.0.5, relay2=.46.0.6, relay3=.46.0.7, relay4=.46.0.8
   # Values: "0"=off, "1"=on (STRING type, not INTEGER)
   # Note: X410 returns DisplayString per MIB definition
   ```
   - CLI args: `--ip`, `--community`, `--relay 1-4`, `--state on|off|toggle`, `--pulse <seconds>`
   - Pulse mode: turn on, wait N seconds, turn off (for momentary activation)
   - Batch mode: `--relay 1,3,4 --state on` (control multiple relays)
   - Read-back verification after each SET operation
   - Return codes: 0=success, 1=connection failed, 2=invalid relay (must be 1-4)

4. **Add CLI wrapper to `scripts/manage.sh`**
   ```bash
   x410-relay)
       python3 scripts/x410_control.py \
           --ip ${X410_IP} \
           --community ${X410_SNMP_COMMUNITY:-public} \
           --relay "$2" \
           --state "$3"
   ```
   - Usage: `iot x410-relay 1 on`, `iot x410-relay 2 toggle`

5. **Restart Telegraf and verify**:
   ```bash
   iot restart-telegraf
   # Wait 30 seconds for first poll
   # Query InfluxDB
   influx query 'SELECT * FROM x410_io WHERE time > now() - 5m'
   ```

6. **Testing checklist**:
   - [ ] Telegraf polling: verify x410_io measurement appears in InfluxDB
   - [ ] Digital inputs: trigger input 1-4, verify state changes in InfluxDB
   - [ ] Relay control (standalone): `python scripts/x410_control.py --relay 1 --state on --ip <x410-ip>`
   - [ ] Relay control (wrapper): `iot x410-relay 2 toggle`
   - [ ] Pulse mode: `python scripts/x410_control.py --relay 3 --pulse 5` (5 second pulse)
   - [ ] Batch control: `python scripts/x410_control.py --relay 1,2,3 --state off`
   - [ ] Verify state changes visible in Grafana dashboard within 30 seconds

### Phase 3: Govee Control Wrapper

**Prerequisites**:
- govee2mqtt service already running (confirmed in docker-compose.yml)
- HTTP API enabled on port 8056

**Implementation Steps**:

1. **Discover Govee API capabilities**
   ```bash
   # Test API access
   curl http://localhost:8056/api/devices | jq
   # Expected: JSON array of devices with names, models, capabilities
   ```

2. **Create `scripts/govee_control.py`** - HTTP API wrapper CLI
   ```python
   # API Base: http://govee2mqtt:8056/api
   # Endpoints:
   #   GET  /devices - list all devices
   #   POST /devices/{device_id}/state - control device
   # Payload example:
   #   {"on": true, "brightness": 100, "color": {"r": 255, "g": 0, "b": 0}}
   ```
   - CLI args: 
     - `--list` - show all controllable devices (name, model, state)
     - `--device <name|mac|model>` - target device (fuzzy match by name)
     - `--on | --off` - power state
     - `--brightness <0-100>` - optional, only for lights
     - `--color <red|blue|green|white|#RRGGBB>` - optional, only for RGB lights
     - `--temperature <2000-9000>` - color temperature in Kelvin (optional)
   - Device matching: try exact name → partial name → MAC address
   - Return device state after command (confirmation)
   - Dependencies: `requests` library

3. **Add device name aliases (optional)**
   ```python
   # In govee_control.py
   DEVICE_ALIASES = {
       "stick": "Govee H6159",
       "studio_light": "Studio RGB Strip",
       # ... user can customize
   }
   ```

4. **Add CLI wrapper to `scripts/manage.sh`**
   ```bash
   govee-control)
       python3 scripts/govee_control.py "$@"
   list-govee | list-devices)
       python3 scripts/govee_control.py --list
   ```
   - Usage: `iot govee-control --device "stick light" --on --brightness 75`
   - Usage: `iot list-devices` (show all Govee devices)

5. **Testing checklist**:
   - [ ] List devices: `iot list-devices` → shows Govee stick light, other devices
   - [ ] Power control: `iot govee-control --device "stick" --on`
   - [ ] Brightness: `iot govee-control --device "stick" --brightness 50`
   - [ ] Color (RGB): `iot govee-control --device "stick" --color red`
   - [ ] Color (hex): `iot govee-control --device "stick" --color #FF8800`
   - [ ] Smart plug control: `iot govee-control --device "plug 1" --off`
   - [ ] Verify state changes visible immediately (API is synchronous)
   - [ ] Error handling: invalid device name, API unreachable

### Phase 4: Grafana Webhook Receiver (Automation Layer)

**Goal**: Receive Grafana alert webhooks and route to device control actions

**Implementation Steps**:

1. **Create `services/webhook-receiver/Dockerfile`**
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY app.py .
   COPY config/ ./config/
   EXPOSE 5001
   CMD ["python", "app.py"]
   ```

2. **Create `services/webhook-receiver/requirements.txt`**
   ```
   Flask==3.0.0
   PyYAML==6.0.1
   pysnmp==5.0.0
   requests==2.31.0
   influxdb-client==1.38.0
   ```

3. **Create `services/webhook-receiver/app.py`** - Flask webhook endpoint
   ```python
   # Main components:
   # - POST /webhook/grafana - receives alert JSON
   # - POST /webhook/test - test endpoint with sample alert
   # - GET /health - health check
   # - GET /devices - list controllable devices
   
   # Alert JSON structure (Grafana v9+):
   # {
   #   "title": "Temperature High Studio",
   #   "state": "alerting|ok",
   #   "message": "Temperature is 87.5F",
   #   "labels": {"alert": "temp_high_studio", "severity": "warning"}
   # }
   
   # Flow:
   # 1. Parse alert JSON
   # 2. Match alert name to config/alert_actions.yaml
   # 3. Execute actions sequentially
   # 4. Log to InfluxDB (control_actions measurement)
   # 5. Return 200 OK with executed actions
   ```

4. **Create `services/webhook-receiver/config/alert_actions.yaml`**
   ```yaml
   # Alert routing configuration
   settings:
     max_actions_per_hour: 60  # rate limiting
     dry_run: false  # set true for testing without actual control
     log_to_influxdb: true
   
   alerts:
     temp_high_studio:
       description: "Studio temperature exceeds threshold"
       actions:
         - device: geist_relay
           action: on
           params: {}
         - device: govee_stick_light
           action: set_color
           params:
             color: red
             brightness: 100
       
     temp_normal_studio:
       description: "Studio temperature returns to normal"
       actions:
         - device: geist_relay
           action: off
         - device: govee_stick_light
           action: off
     
     schedule_slip_warning:
       description: "Show schedule running 10+ minutes late"
       actions:
         - device: x410_relay_1
           action: pulse
           params:
             duration: 3  # seconds
     
     schedule_slip_critical:
       description: "Show schedule running 15+ minutes late"
       actions:
         - device: x410_relay_1
           action: on
         - device: x410_relay_2
           action: on
         - device: govee_stick_light
           action: set_color
           params:
             color: "#FF0000"
             brightness: 100
   ```

5. **Add webhook-receiver to `docker-compose.yml`**
   ```yaml
   webhook-receiver:
     build: ./services/webhook-receiver
     container_name: webhook-receiver
     restart: unless-stopped
     ports:
       - "5001:5001"  # internal only, not exposed to LAN
     volumes:
       - ./services/webhook-receiver/config:/app/config
       - ./scripts:/app/scripts:ro  # mount control scripts
     environment:
       - GEIST_IP=${GEIST_IP}
       - GEIST_SNMP_RW_COMMUNITY=${GEIST_SNMP_RW_COMMUNITY}
       - X410_IP=${X410_IP}
       - X410_SNMP_COMMUNITY=${X410_SNMP_COMMUNITY}
       - INFLUXDB_URL=http://influxdb:8086
       - INFLUXDB_TOKEN=${DOCKER_INFLUXDB_INIT_ADMIN_TOKEN}
       - INFLUXDB_ORG=home
       - INFLUXDB_BUCKET=sensors
       - GOVEE_API_URL=http://govee2mqtt:8056
     depends_on:
       - influxdb
       - telegraf
       - govee2mqtt
     networks:
       - iot
   ```

6. **Configure Grafana contact point**
   - Navigate to Alerting → Contact points → New contact point
   - Name: "Physical Control Webhook"
   - Type: Webhook
   - URL: `http://webhook-receiver:5001/webhook/grafana`
   - HTTP Method: POST
   - Optional: Add custom header `X-Webhook-Token: <secret>` for auth

7. **Testing checklist**:
   - [ ] Build and start: `docker-compose up -d webhook-receiver`
   - [ ] Health check: `curl http://localhost:5001/health` → 200 OK
   - [ ] Test endpoint: `curl -X POST http://localhost:5001/webhook/test` → executes sample alert
   - [ ] Manual webhook: `curl -X POST http://localhost:5001/webhook/grafana -d @test_alert.json`
   - [ ] Verify device responds (Geist relay, Govee light, or X410)
   - [ ] Check logs: `iot webhook-logs` → see parsed alert and actions executed
   - [ ] Verify InfluxDB logging: `SELECT * FROM control_actions WHERE time > now() - 1h`

### Phase 5: Grafana Alert Rules (Metric-Driven Automation)

**Goal**: Define threshold-based alerts that trigger physical device responses

**Implementation Steps**:

1. **Create alert rule: Temperature High**
   - Grafana → Alerting → Alert rules → New alert rule
   - Name: "Studio Temperature High"
   - Query: 
     ```
     FROM geist_internal
     WHERE sensor_name = 'Internal'
     SELECT temperature / 10  # Scale from 0.1 degrees
     ```
   - Condition: `WHEN last() > 85`  # 85°F threshold
   - Evaluation interval: Every 1m for 2m (reduce flapping)
   - Labels: `alert=temp_high_studio`, `severity=warning`, `room=studio`
   - Notification: "Physical Control Webhook" contact point

2. **Create alert rule: Temperature Normal (recovery)**
   - Name: "Studio Temperature Normal"
   - Same query as above
   - Condition: `WHEN last() < 80`  # 5° hysteresis below threshold
   - Labels: `alert=temp_normal_studio`
   - Notification: "Physical Control Webhook"

3. **Create alert rule: Schedule Slip Warning** *(if set-schedule integrated)*
   - Query: 
     ```
     # Custom metric from set-schedule app
     FROM schedule_metrics
     WHERE stage = 'main'
     SELECT slip_seconds
     ```
   - Condition: `WHEN last() > 600`  # 10 minutes
   - Labels: `alert=schedule_slip_warning`, `severity=info`
   - Notification: "Physical Control Webhook"

4. **Create alert rule: Schedule Slip Critical**
   - Same query
   - Condition: `WHEN last() > 900`  # 15 minutes
   - Labels: `alert=schedule_slip_critical`, `severity=critical`
   - Notification: "Physical Control Webhook"

5. **Create alert rule: Sensor Offline** *(early warning)*
   - Query:
     ```
     FROM govee_sensor
     SELECT last(battery)
     ```
   - Condition: `WHEN last() < 10`  # 10% battery
   - Labels: `alert=sensor_battery_low`
   - Notification: Slack/Email (not physical control)

6. **Configure evaluation settings**
   - Navigate to Alerting → Evaluation groups
   - Create group: "Physical Control" 
   - Evaluation interval: 1 minute
   - Pending period: 2 minutes (avoid flapping)

7. **Testing checklist**:
   - [ ] Manual trigger: Use Grafana "Test alert" button → verify webhook fires
   - [ ] Real trigger: Adjust temperature threshold to current value → wait for alert
   - [ ] Verify: Device responds (relay clicks, light changes)
   - [ ] Check: Grafana alert history shows "Alerting" state
   - [ ] Check: InfluxDB control_actions has logged entry
   - [ ] Recovery: Threshold returns to normal → verify "OK" alert fires, device resets
   - [ ] Silence test: Silence alert in Grafana → verify no webhook fires
   - [ ] Rate limiting: Trigger same alert 3x in 1 minute → verify max_actions_per_hour enforced

### Phase 6: CLI Integration & Documentation

**Goal**: Unified CLI commands for all device control + comprehensive help

**Implementation Steps**:

1. **Update `scripts/manage.sh`** - Add device control commands
   ```bash
   # Geist relay control
   geist-relay)
       check_env_var GEIST_IP GEIST_SNMP_RW_COMMUNITY
       python3 scripts/geist_control.py \
           --ip "$GEIST_IP" \
           --community "$GEIST_SNMP_RW_COMMUNITY" \
           --relay "$2"
       ;;
   
   # X410 relay control
   x410-relay)
       check_env_var X410_IP X410_SNMP_COMMUNITY
       if [ -z "$2" ] || [ -z "$3" ]; then
           echo "Usage: iot x410-relay <1-4> <on|off|toggle|pulse>"
           exit 1
       fi
       python3 scripts/x410_control.py \
           --ip "$X410_IP" \
           --community "$X410_SNMP_COMMUNITY" \
           --relay "$2" \
           --state "$3"
       ;;
   
   # Govee device control
   govee-control)
       shift  # remove 'govee-control' from args
       python3 scripts/govee_control.py "$@"
       ;;
   
   # List all controllable devices
   list-devices)
       echo "=== Geist Watchdog ==="
       echo "  Relay: $GEIST_IP (SNMP)"
       echo ""
       echo "=== X410 Relay Controller ==="
       echo "  Relay 1-4: $X410_IP (SNMP)"
       echo ""
       echo "=== Govee Devices ==="
       python3 scripts/govee_control.py --list
       ;;
   
   # Webhook receiver lifecycle
   webhook-up)
       docker-compose up -d webhook-receiver
       ;;
   webhook-down)
       docker-compose stop webhook-receiver
       ;;
   webhook-restart)
       docker-compose restart webhook-receiver
       ;;
   webhook-logs)
       docker-compose logs -f webhook-receiver
       ;;
   ```

2. **Add comprehensive help text**
   ```bash
   # In manage.sh help function
   echo "Device Control Commands:"
   echo "  iot geist-relay <on|off|toggle>         Control Geist Watchdog relay"
   echo "  iot x410-relay <1-4> <on|off|toggle>    Control X410 relay (specify relay number)"
   echo "  iot govee-control --device <name> [opts] Control Govee lights/plugs"
   echo "  iot list-devices                         Show all controllable devices"
   echo ""
   echo "Webhook Receiver:"
   echo "  iot webhook-up                           Start webhook receiver"
   echo "  iot webhook-down                         Stop webhook receiver"
   echo "  iot webhook-restart                      Restart webhook receiver"
   echo "  iot webhook-logs                         View webhook receiver logs"
   echo ""
   echo "Examples:"
   echo "  iot geist-relay on                       Turn on Geist relay"
   echo "  iot x410-relay 1 toggle                  Toggle X410 relay 1"
   echo "  iot govee-control --device stick --on --brightness 75"
   echo "  iot list-devices                         Show all devices with status"
   ```

3. **Update `.env.example`** - Document new variables
   ```bash
   # Physical Device Control (Phase 7+8)
   # Geist Watchdog - Relay Control
   GEIST_IP=192.168.1.214
   GEIST_SNMP_RW_COMMUNITY=private  # Must be read-write, not "public"
   
   # ControlByWeb X-410 - 4 Relays + 4 Digital Inputs
   X410_IP=192.168.1.XXX  # Provide your X410 IP address
   X410_SNMP_COMMUNITY=public  # Default is usually "public" for R/W
   
   # Webhook Receiver Rate Limiting
   WEBHOOK_MAX_ACTIONS_PER_HOUR=60
   ```

4. **Update ROADMAP.md** (docs/ROADMAP.md)
   - Merge Phase 7 & 8 sections into single "Physical Control & Alerting" section
   - Mark completed subsections with ✅ checkboxes
   - Update with X410, Govee, webhook receiver implementation details
   - Add "Known Issues" subsection if any discovered during implementation

5. **Create quick reference card** - `docs/DEVICE_CONTROL_QUICK_REF.md`
   ```markdown
   # Device Control Quick Reference
   
   ## Geist Watchdog Relay
   - IP: 192.168.1.214
   - Control: `iot geist-relay on|off|toggle`
   - Direct: `python scripts/geist_control.py --relay on --ip dpx-geist.local`
   
   ## X410 Relay Controller
   - IP: [Your IP]
   - 4 Relays: `iot x410-relay <1-4> on|off|toggle`
   - Pulse: `python scripts/x410_control.py --relay 1 --pulse 5`
   
   ## Govee Devices
   - List: `iot list-devices`
   - Control: `iot govee-control --device "stick" --on --brightness 100`
   - Colors: red, blue, green, white, or #RRGGBB hex
   
   ## Grafana Alerts → Physical Actions
   - Configure: `services/webhook-receiver/config/alert_actions.yaml`
   - Test: `curl -X POST http://localhost:5001/webhook/test`
   - Logs: `iot webhook-logs`
   ```

6. **Testing checklist**:
   - [ ] Help text: `iot` (no args) → shows device control commands
   - [ ] All commands executable: `iot geist-relay on`, `iot x410-relay 1 off`, `iot govee-control --list`
   - [ ] Error handling: `iot x410-relay` (missing args) → shows usage
   - [ ] Missing .env: `unset GEIST_IP; iot geist-relay on` → error message with guidance
   - [ ] Documentation accuracy: verify all commands in quick ref work as documented

### Phase 7: Web GUI Dashboard (Future Enhancement)

**Goal**: Browser-based control panel for all devices - visual status + click-to-control

**Scope**: Separate phase after CLI tools proven. Web GUI imports/calls same control scripts (no code duplication).

**Implementation Steps**:

1. **Create `services/control-dashboard/Dockerfile`**
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   EXPOSE 5002
   CMD ["python", "app.py"]
   ```

2. **Create `services/control-dashboard/requirements.txt`**
   ```
   Flask==3.0.0
   Flask-SocketIO==5.3.5
   influxdb-client==1.38.0
   pysnmp==5.0.0
   requests==2.31.0
   ```

3. **Create `services/control-dashboard/app.py`** - Flask web app
   ```python
   # Routes:
   # GET  / - main dashboard HTML
   # GET  /api/devices - JSON list of all devices with current states
   # POST /api/geist/relay - control Geist relay
   # POST /api/x410/relay/<id> - control X410 relay 1-4
   # POST /api/govee/device/<name> - control Govee device
   # WS   /socket.io - WebSocket for real-time state updates
   
   # State polling:
   # - Query InfluxDB every 5 seconds for latest device states
   # - Push updates to all connected WebSocket clients
   # - Clients update UI without page refresh
   
   # Control flow:
   # Frontend → POST /api/x410/relay/1 → import x410_control.py → call set_relay()
   # → Return new state → WebSocket broadcast → All clients update
   ```

4. **Create `services/control-dashboard/templates/index.html`** - Frontend UI
   ```html
   <!-- Bootstrap 5 grid layout -->
   <!-- Device cards:
        - Geist Watchdog: 1 relay toggle button
        - X410: 4 relay toggle buttons (grid 2x2)
        - Govee: Device list with power/brightness/color controls
   -->
   
   <!-- Real-time updates via Socket.IO -->
   <script src="https://cdn.socket.io/4.6.0/socket.io.min.js"></script>
   <script>
     const socket = io();
     socket.on('device_update', function(data) {
       updateDeviceUI(data.device, data.state);
     });
   </script>
   
   <!-- Color coded states:
        - Relay ON: green background
        - Relay OFF: gray background
        - Unreachable: red background + "Offline" badge
   -->
   ```

5. **Create `services/control-dashboard/static/styles.css`** - Dark theme
   ```css
   /* Inspiration: Grafana dark theme */
   /* Device card: border, rounded corners, shadow */
   /* Button states: Bootstrap .btn-success (ON), .btn-secondary (OFF) */
   /* Responsive: mobile-friendly stacked layout */
   ```

6. **Add control-dashboard to `docker-compose.yml`**
   ```yaml
   control-dashboard:
     build: ./services/control-dashboard
     container_name: control-dashboard
     restart: unless-stopped
     ports:
       - "5002:5002"  # Exposed to LAN for browser access
     volumes:
       - ./scripts:/app/scripts:ro
       - ./services/control-dashboard/templates:/app/templates
       - ./services/control-dashboard/static:/app/static
     environment:
       - GEIST_IP=${GEIST_IP}
       - GEIST_SNMP_RW_COMMUNITY=${GEIST_SNMP_RW_COMMUNITY}
       - X410_IP=${X410_IP}
       - X410_SNMP_COMMUNITY=${X410_SNMP_COMMUNITY}
       - INFLUXDB_URL=http://influxdb:8086
       - INFLUXDB_TOKEN=${DOCKER_INFLUXDB_INIT_ADMIN_TOKEN}
       - INFLUXDB_ORG=home
       - INFLUXDB_BUCKET=sensors
       - GOVEE_API_URL=http://govee2mqtt:8056
     depends_on:
       - influxdb
       - telegraf
       - govee2mqtt
     networks:
       - iot
   ```

7. **Add dashboard CLI commands to `scripts/manage.sh`**
   ```bash
   dashboard-up)
       docker-compose up -d control-dashboard
       echo "Dashboard available at:"
       echo "  http://localhost:5002"
       echo "  http://dpx-showsite-ops.local:5002"
       ;;
   dashboard-down)
       docker-compose stop control-dashboard
       ;;
   dashboard-restart)
       docker-compose restart control-dashboard
       ;;
   dashboard-logs)
       docker-compose logs -f control-dashboard
       ;;
   ```

8. **Optional: Add authentication**
   - Flask-Login for session management
   - Single user: admin password in .env
   - Or: HTTP Basic Auth via nginx reverse proxy
   - Or: Skip auth if LAN-only deployment trusted

9. **UI Features** (prioritized):
   - **Must have**:
     - Device grid with current states
     - Toggle buttons for all relays
     - Power on/off for Govee devices
     - Responsive mobile layout
   - **Should have**:
     - Brightness slider for Govee lights (0-100)
     - Color picker for RGB devices
     - Last update timestamp per device
     - Connection status indicators
   - **Nice to have**:
     - Dark/light theme toggle
     - Device grouping (by room/function)
     - Action history log (last 10 actions)
     - Alert status badges (show active Grafana alerts)

10. **Testing checklist**:
    - [ ] Build: `docker-compose build control-dashboard`
    - [ ] Start: `iot dashboard-up`
    - [ ] Access: Open `http://dpx-showsite-ops.local:5002` in browser
    - [ ] Device display: Verify all devices show with correct current states
    - [ ] Geist control: Click relay button → verify relay responds, UI updates
    - [ ] X410 control: Click relay 1-4 → verify relays respond, UI updates
    - [ ] Govee control: Toggle power, adjust brightness → verify light responds
    - [ ] Real-time updates: Change device state via CLI → verify UI updates without refresh
    - [ ] Multi-client: Open dashboard in 2 browsers → change in one reflects in other
    - [ ] Mobile: Test on phone → verify responsive layout, touch-friendly buttons
    - [ ] Error handling: Disconnect device → verify "Offline" indicator appears

---

## Relevant Files

### Existing Files (to modify)
- `telegraf/conf.d/geist-watchdog.conf` - update SNMP community string to RW
- `docker-compose.yml` - add webhook-receiver service, X410 extra_hosts entry
- `scripts/manage.sh` - add control CLI commands
- `.env.example` - add X410_IP, X410_SNMP_COMMUNITY, GEIST_SNMP_RW_COMMUNITY
- `docs/ROADMAP.md` - merge sections, mark Phase 7+8 as "Physical Control & Alerting"

### New Files (to create)
- `scripts/geist_control.py` - Geist relay SNMP control (standalone CLI)
- `scripts/x410_control.py` - X410 relay SNMP control (standalone CLI)
- `scripts/govee_control.py` - Govee device HTTP API wrapper (standalone CLI)
- `telegraf/conf.d/x410.conf` - X410 SNMP polling config (based on geist pattern)
- `services/webhook-receiver/Dockerfile` - Flask webhook receiver
- `services/webhook-receiver/app.py` - webhook endpoint and routing logic
- `services/webhook-receiver/config/alert_actions.yaml` - alert → action mappings
- `services/webhook-receiver/requirements.txt` - Flask, PyYAML dependencies
- `services/control-dashboard/` - Web GUI Flask app, Dockerfile, HTML/JS frontend (Phase 7)

### Reference Files (existing, for patterns)
- `docs/mibs_archive/x410-swg_v2d2-device.mib` - X410 OID reference
- `telegraf/conf.d/geist-watchdog.conf` - SNMP config pattern to replicate
- `scripts/ble_decoder.py` - Python service pattern for webhook receiver

---

## Verification

1. **Geist Relay (Standalone)**: `python scripts/geist_control.py --relay on --ip dpx-geist.local`, verify relay clicks and returns current state
2. **Geist Relay (Wrapper)**: `iot geist-relay on`, verify relay clicks and state updates in Grafana
3. **X410 Monitoring**: Query InfluxDB - `SELECT * FROM x410_io WHERE time > now() - 5m`, verify relay states and input values
4. **X410 Control (Standalone)**: `python scripts/x410_control.py --relay 1 --state on --ip <x410-ip>`, verify relay state change
5. **X410 Control (Wrapper)**: `iot x410-relay 1 on`, verify relay state change in InfluxDB
6. **Govee List Devices**: `python scripts/govee_control.py --list`, verify shows Govee stick light and other devices
7. **Govee Control**: `iot govee-control "stick light" on --brightness 50`, verify light responds
8. **Webhook Receiver**: `curl -X POST http://localhost:5001/webhook/grafana -d @test_alert.json`, verify device action triggered
9. **End-to-End Alert**: Manually raise temperature above threshold, verify webhook fires and Geist relay activates
10. **Grafana Dashboard**: Create monitoring panel showing relay states, alert status, last action timestamp
11. **Web GUI (Phase 7)**: Open `http://dpx-showsite-ops.local:5002`, verify device status display, click control buttons, verify device responses

---

## Decisions

- **Merged Phase 7 & 8**: User confirmed they're the same work (physical control + alerting thresholds)
- **Priority Order**: 1) Geist relay, 2) X410 (monitor + control), 3) Govee, 4) Grafana webhooks
- **X410 Credentials**: User has IP/creds for online unit (will provide)
- **Grafana Integration**: Option 1 (webhook from alert rules → Python script) - easiest native integration
- **Webhook Receiver**: Separate Flask service (not part of Telegraf) for clean separation of concerns
- **Alert Actions Config**: YAML file for flexibility without code changes
- **CLI Integration**: Control scripts are standalone CLIs (can call directly) AND wrapped via `iot` commands for consistency
- **Standalone Scripts First**: CLI tools ship first for immediate testing, Web GUI built after control proven (Phase 7)
- **Web GUI Design**: Separate Flask service on port 5002, calls same Python control scripts (avoid code duplication)

---

## Further Considerations

1. **Second X410 Unit**: Plan mentions one offline unit - defer integration until second unit is online?
   - Recommendation: Build with single X410 first, add second unit as additional `agents` entry in telegraf config later
2. **Geist RW Community String**: User needs to provide new credentials or update device config
   - Recommendation: If device web interface allows, create separate "control" community string (keep "public" read-only for Telegraf monitoring)
3. **Alert Action Logging**: Should webhook actions be logged to InfluxDB for audit trail?
   - Recommendation: Yes - create `control_actions` measurement with fields: device, action, timestamp, triggered_by_alert
4. **Manual Override Safety**: Should webhook actions be rate-limited or require confirmation for destructive operations?
   - Recommendation: Add `max_actions_per_hour` config and dry-run mode for testing
5. **Govee Device Discovery**: How to handle dynamic device list from govee2mqtt API?
   - Recommendation: Cache device list on webhook receiver startup, refresh every 5 minutes
