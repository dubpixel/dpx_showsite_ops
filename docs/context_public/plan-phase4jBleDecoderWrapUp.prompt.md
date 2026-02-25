# Phase 4j — BLE Decoder Wrap-Up Plan
# Created: 2026-02-09

## Summary

Two fixes to productionize the BLE decoder: (1) add a process-guard to the `iot ble-decode` CLI command so it kills stale instances before starting, and (2) containerize `ble_decoder.py` as a proper Docker service in the compose stack — eliminating the need for bare-metal Python, systemd, or manual `iot ble-decode` invocations. This brings the decoder in line with every other service in the stack.

---

## Steps

### Step 1 — Add kill-existing-instances guard to `iot ble-decode`

**File**: `scripts/manage.sh` (line 16)

Replace the current one-liner:
```bash
ble-decode) source ../.env && python3 ble_decoder.py ;;
```

with logic that:
- Uses `pgrep -f ble_decoder.py` to find any running instances
- If found, prints a message listing PIDs, then kills them with `pkill -f ble_decoder.py`
- Waits briefly (`sleep 1`) for clean shutdown
- Force-kills (`pkill -9 -f`) if any survive
- Then starts the new instance as before with `source ../.env && python3 ble_decoder.py`

This keeps `iot ble-decode` usable as a manual/debug tool even after containerization.


---

### Step 2 — Make `ble_decoder.py` connection settings configurable via env vars

**File**: `scripts/ble_decoder.py`

Change the three hardcoded values at the top:

- `BROKER = "localhost"` → `BROKER = os.getenv("MQTT_HOST", "localhost")`
- `PORT = 1883` → `PORT = int(os.getenv("MQTT_PORT", "1883"))`
- `API = "http://localhost:8056/api/devices"` → `API = os.getenv("GOVEE_API_URL", "http://localhost:8056/api/devices")`

This is backward-compatible — bare-metal `iot ble-decode` still defaults to `localhost`, while the Docker service can override to use Docker DNS names.

---

### Step 4 — Create `scripts/requirements.txt`

**File**: `scripts/requirements.txt` (new file)

Single dependency:
```
paho-mqtt>=1.6,<2.0
```

Note: Pin below v2 — paho-mqtt 2.x has breaking API changes to `Client()` constructor and callbacks.

---

### Step 5 — Create `scripts/Dockerfile.ble-decoder`

**File**: `scripts/Dockerfile.ble-decoder` (new file)

Lightweight Alpine-based Python image:
```dockerfile
FROM python:3.11-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ble_decoder.py .

CMD ["python3", "ble_decoder.py"]
```

Keep it in `scripts/` alongside the decoder itself.

---

### Step 6 — Add `ble-decoder` service to `docker-compose.yml`

**File**: `docker-compose.yml`

Add a new service:

```yaml
  ble-decoder:
    build:
      context: ./scripts
      dockerfile: Dockerfile.ble-decoder
    container_name: ble-decoder
    restart: unless-stopped
    networks:
      - iot
    depends_on:
      - mosquitto
    environment:
      - MQTT_HOST=mosquitto
      - MQTT_PORT=1883
      - GOVEE_API_URL=http://host.docker.internal:8056/api/devices
      - SHOWSITE_NAME=${SHOWSITE_NAME:-demo_showsite}
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

**Key networking detail**: `govee2mqtt` runs with `network_mode: host`, so it's only reachable from other containers via the host's actual network stack. The `host.docker.internal` alias is the clean Docker-idiomatic way to handle this without hardcoding the VM's IP. The `extra_hosts` line is required on Linux (macOS/Windows Docker does this automatically).

---

### Step 7 — Update `manage.sh` help text and log shortcut

**File**: `scripts/manage.sh`

- Add `lb` log shortcut for the ble-decoder container: `docker logs ble-decoder 2>&1 | tail -${2:-30}`
- Add it to the `la` (all logs) loop
- Update the help text to document the new log command and note that `ble-decode` is now a debug/manual-run option

---

### Step 8 — Update `.env.example`

**File**: `.env.example`

Add:
```
SHOWSITE_NAME=demo_showsite
```

So future deployments know to set it.

---

### Step 9 — Update documentation

**Files to update**:

1. **`CHANGELOG.md`**: Add Phase 4 completion entries:
   - ESP32 gateway deployment
   - BLE decoder service implementation
   - Dual-source Telegraf configuration
   - H507x temperature decode fix
   - BLE decoder containerization

2. **`docs/ROADMAP.md`**: 
   - Mark Phase 4 subsections as complete
   - Add Phase 4j wrap-up section

3. **`docs/context_public/CONTEXT.md`**: 
   - Update status to complete
   - Mark pending items complete
   - Note containerized architecture
   - Document temperature fix

---

## Verification Steps

1. **Kill-guard test**: Run `iot ble-decode` in one terminal, run it again in another — first instance should be killed cleanly, no "address already in use" or duplicate MQTT client errors

2. **Temperature values**: Check InfluxDB or Grafana — H507x sensors should show reasonable temps (~65-75°F), not ~360°F

3. **Container build**: `docker compose build ble-decoder` — should build cleanly

4. **Container start**: `docker compose up -d ble-decoder` — should connect to Mosquitto and load devices from govee2mqtt API

5. **Logs**: `iot lb 20` (or `docker logs ble-decoder`) — should show "Connected to MQTT broker at mosquitto:1883" and "Loaded N devices from API"

6. **Data flow**: Check InfluxDB for `source=dpx_ops_decoder` data continuing to arrive with correct values — `iot query-tags 5m 10`

7. **Full stack restart**: `iot down && iot up` — ble-decoder should auto-start with everything else

---

## Decisions & Rationale

- **Fix temp bug first**: Diagnose whether it's double-conversion or byte-parsing, then standardize on decoder outputting Celsius with single Telegraf F conversion — ensures consistency across all data sources

- **`host.docker.internal` over hardcoded IP**: Portable across environments, no need to update if VM IP changes

- **Keep `iot ble-decode` as manual command**: Useful for debugging — runs bare-metal with local stdout, separate from container lifecycle

- **Pin paho-mqtt < 2.0**: v2.x has breaking callback signature changes; avoids silent failures

- **Dockerfile in `scripts/`**: Co-located with the decoder it builds, keeps root clean

- **`SHOWSITE_NAME` from `.env`**: Single source of truth for the site name across docker-compose

---

## ✅ Completion Summary

**Status**: Complete (2026-02-24)

All steps implemented successfully:

1. ✅ **Kill-guard for `iot ble-decode`**: Added process guard logic to prevent duplicate instances
   - Detects running instances with `pgrep`
   - Graceful SIGTERM with fallback to SIGKILL
   - Clear user feedback on what's happening
   
2. ✅ **Environment variable configuration**: Implemented via Dockerfile `sed` replacement (alternative to source-level changes)

3. ✅ **requirements-ble-decoder.txt**: Created with `paho-mqtt>=1.6.1,<2.0.0`

4. ✅ **Dockerfile.ble-decoder**: Python 3.11-slim image with proper dependencies

5. ✅ **docker-compose.yml integration**: Service added with proper networking via `host.docker.internal`

6. ✅ **manage.sh updates**: `lb` log command, help text, all log aggregation

7. ✅ **.env.example**: SHOWSITE_NAME variable added

8. ✅ **Documentation updates**: CHANGELOG.md, ROADMAP.md, CONTEXT.md all updated

**Final deliverable**: BLE decoder fully containerized and operational with both production (Docker) and debug (manual) modes supported.
