# MQTT Retained Message Ghost Data - Fix Plan

**Issue**: Device renames create persistent ghost data in MQTT/InfluxDB/Grafana
**Date**: 2026-02-09
**Status**: Active issue, workaround available

---

## Problem Summary

### What's Happening

When a device is renamed in the Govee app/API (e.g., `studio_5051_down` → `5051_studio_down`):

1. **ble_decoder.py** loads new device name from API
2. Publishes to **NEW** topic: `demo_showsite/dpx_ops_decoder/.../5051_studio_down/4381ECA1010A/temperature`
3. **OLD** retained message persists: `demo_showsite/dpx_ops_decoder/.../studio_5051_down/4381ECA1010A/temperature`
4. Every Telegraf restart (hourly cron) re-subscribes to `demo_showsite/dpx_ops_decoder/#`
5. Receives **BOTH** retained messages (old + new)
6. Creates **TWO** time series in InfluxDB:
   - `device_name="studio_5051_down"` ← frozen ghost data
   - `device_name="5051_studio_down"` ← live updating data

### Root Causes

1. **ble_decoder.py uses `retain=True`** (line 179):
   ```python
   client.publish(f"{base_topic}/temperature", decoded["temp_f"], retain=True)
   ```

2. **Topics contain device names** (line 176):
   ```python
   base_topic = f"{SHOWSITE}/{DECODER_NODE}/{source_node}/{room}/{device_name}/{mac}"
   ```

3. **update-device-map.sh unconditionally restarts Telegraf** (line 47):
   ```bash
   docker compose restart telegraf  # Always runs, no diff check
   ```

4. **No cleanup mechanism** for stale retained messages

---

## Immediate Workaround - Step-by-Step Diagnosis & Manual Fix

### Step 1: Confirm Retained Messages Exist

Subscribe and capture ALL retained messages (they arrive immediately on subscribe):

```bash
# Capture to file for analysis
timeout 3 mosquitto_sub -h localhost -t "demo_showsite/dpx_ops_decoder/#" -v | tee /tmp/retained_messages.txt
```

**Note**: Retained messages appear instantly when you subscribe. Regular messages arrive as sensors broadcast.

### Step 2: Identify Ghost Topics

Look for duplicate MACs with different device names:

```bash
# Example: Find all topics for sensor 4381ECA1010A
grep "4381ECA1010A" /tmp/retained_messages.txt

# Extract just topics with old device name
grep "studio_5051_down" /tmp/retained_messages.txt | cut -d' ' -f1
```

Expected output showing ghost:
```
demo_showsite/dpx_ops_decoder/dpx_ops_1/studiodown/studio_5051_down/4381ECA1010A/temperature 67.5
demo_showsite/dpx_ops_decoder/dpx_ops_1/studiodown/5051_studio_down/4381ECA1010A/temperature 68.2
```

### Step 3: Test Clearing a Single Topic

Pick ONE ghost topic and clear it:

```bash
mosquitto_pub -h localhost \
  -t "demo_showsite/dpx_ops_decoder/dpx_ops_1/studiodown/studio_5051_down/4381ECA1010A/temperature" \
  -r -n
```

**Immediately verify** it's gone:

```bash
timeout 2 mosquitto_sub -h localhost \
  -t "demo_showsite/dpx_ops_decoder/dpx_ops_1/studiodown/studio_5051_down/4381ECA1010A/temperature" -v
```

Should timeout with no message. If you still see a value, the clear didn't work (see Troubleshooting below).

### Step 4: Batch Clear All Ghost Topics

Once single-topic clear is confirmed working:

```bash
#!/bin/bash
# Save as /tmp/clear_ghosts.sh

GHOST_TOPICS=$(timeout 3 mosquitto_sub -h localhost -t "demo_showsite/dpx_ops_decoder/#" -v 2>/dev/null | \
  grep "studio_5051_down" | cut -d' ' -f1)

echo "Topics to clear:"
echo "$GHOST_TOPICS"
echo ""

if [ -z "$GHOST_TOPICS" ]; then
  echo "No ghost topics found!"
  exit 0
fi

read -p "Clear these topics? (y/N): " -n 1 -r
echo ""
[[ ! $REPLY =~ ^[Yy]$ ]] && exit 0

while IFS= read -r topic; do
  [ -z "$topic" ] && continue
  echo "Clearing: $topic"
  mosquitto_pub -h localhost -t "$topic" -r -n
done <<< "$GHOST_TOPICS"

echo ""
echo "Done. Verifying..."
sleep 2

# Check if any still exist
REMAINING=$(timeout 3 mosquitto_sub -h localhost -t "demo_showsite/dpx_ops_decoder/#" -v 2>/dev/null | \
  grep "studio_5051_down" | wc -l)

if [ "$REMAINING" -eq 0 ]; then
  echo "✓ All ghost messages cleared!"
else
  echo "⚠ $REMAINING ghost messages still remain"
fi
```

Run it:
```bash
chmod +x /tmp/clear_ghosts.sh
/tmp/clear_ghosts.sh
```

### Step 5: Trigger Telegraf Restart & Verify

After clearing retained messages, force Telegraf to resubscribe:

```bash
docker compose -f ~/dpx_govee_stack/docker-compose.yml restart telegraf
```

Wait 10 seconds, then check if ghost data appears in InfluxDB:

```flux
from(bucket: "sensors")
  |> range(start: -5m)
  |> filter(fn: (r) => r.device_name == "studio_5051_down")
  |> filter(fn: (r) => r.source == "dpx_ops_decoder")
```

Should return **no results** (or only old data with timestamps before the restart).

### Step 6: Monitor Next Hourly Cron

Wait for the hourly update-device-map.sh cron to run (top of the hour), then immediately check:

```bash
# Right after the hour (e.g., 14:01)
timeout 3 mosquitto_sub -h localhost -t "demo_showsite/dpx_ops_decoder/#" -v | grep "studio_5051_down"
```

Should return nothing. If ghost topics reappear, the BLE decoder may be recreating them (see Troubleshooting below).

### Troubleshooting

**If `mosquitto_pub -r -n` doesn't clear:**

1. Check Mosquitto config allows clearing retained messages:
```bash
grep -i "retain" ~/dpx_govee_stack/mosquitto/config/mosquitto.conf
```
Ensure no `retain_available false` setting.

2. Check Mosquitto logs for errors:
```bash
docker logs dpx_govee_stack-mosquitto-1 --tail 50
```

3. Try explicit empty string instead of null:
```bash
mosquitto_pub -h localhost -t "demo_showsite/dpx_ops_decoder/..." -r -m ""
```

4. Verify you're connecting to the right broker (check if authentication required):
```bash
# If mosquitto requires credentials (unlikely for localhost)
mosquitto_pub -h localhost -u username -P password -t "..." -r -n
```

**If ghost messages reappear after clearing:**

The BLE decoder may still have old device names in memory. It only loads device mappings at startup via `load_devices()`. 

If you renamed a device in Govee app but haven't restarted the decoder:
- Decoder still publishes to old topic names
- Creates new retained messages with old names

**Solution**: Restart BLE decoder after any device rename:
```bash
# Kill manual decoder process
pkill -f ble_decoder.py

# Restart (however you normally start it)
# Example: if using iot command
cd ~/dpx_govee_stack && python3 scripts/ble_decoder.py
```

**Check which device names the decoder currently has:**
```bash
# Look at decoder startup output for "Loaded X devices from API:"
# Shows current device name mappings in memory
```

---

## Fix 1: Add Diff Check to update-device-map.sh (HIGH PRIORITY)

**Impact**: Reduces Telegraf restarts from hourly to only when config changes
**Benefit**: Minimizes ghost data exposure, reduces service disruption

### Implementation

```bash
#!/bin/bash
API="http://localhost:8056/api/devices"
CONF="$HOME/dpx_govee_stack/telegraf/conf.d/device-mappings.conf"
CONF_TMP="${CONF}.tmp"
LOG="$HOME/dpx_govee_stack/scripts/update-device-map.log"

mkdir -p "$(dirname "$CONF")"

DEVICES=$(curl -s --max-time 10 "$API")
if [ -z "$DEVICES" ] || [ "$DEVICES" = "[]" ]; then
  echo "$(date) - Failed to fetch devices. Skipping." >> "$LOG"
  exit 1
fi

NAME_MAPPINGS=$(echo "$DEVICES" | python3 -c "
import json, sys
for d in json.load(sys.stdin):
    did = d['id'].replace(':','')
    name = d['name'].lower().replace(' ','_')
    print(f'      \"{did}\" = \"{name}\"')
")

ROOM_MAPPINGS=$(echo "$DEVICES" | python3 -c "
import json, sys
for d in json.load(sys.stdin):
    did = d['id'].replace(':','')
    room = (d.get('room') or 'unassigned').lower().replace(' ','_')
    print(f'      \"{did}\" = \"{room}\"')
")

# Generate new config in temp file
cat > "$CONF_TMP" << EOF
[[processors.enum]]
  [[processors.enum.mapping]]
    tags = ["z_device_id"]
    dest = "device_name"
    [processors.enum.mapping.value_mappings]
${NAME_MAPPINGS}

  [[processors.enum.mapping]]
    tags = ["z_device_id"]
    dest = "room"
    [processors.enum.mapping.value_mappings]
${ROOM_MAPPINGS}
EOF

# Only restart if config actually changed
if ! diff -q "$CONF_TMP" "$CONF" > /dev/null 2>&1; then
  mv "$CONF_TMP" "$CONF"
  docker compose -f "$HOME/dpx_govee_stack/docker-compose.yml" restart telegraf
  echo "$(date) - Config changed, Telegraf restarted" >> "$LOG"
  echo "$DEVICES" | python3 -c "
import json, sys
for d in json.load(sys.stdin):
    did = d['id'].replace(':','')
    name = d['name'].lower().replace(' ','_')
    room = (d.get('room') or 'unassigned').lower().replace(' ','_')
    print(f'  {did}: {name} in {room}')
" >> "$LOG"
else
  rm "$CONF_TMP"
  echo "$(date) - No changes detected, skipped restart" >> "$LOG"
fi

echo "" >> "$LOG"
```

**Testing**:
1. Run script manually: `~/dpx_govee_stack/scripts/update-device-map.sh`
2. Check log: `tail -20 ~/dpx_govee_stack/scripts/update-device-map.log`
3. Verify "No changes detected" on subsequent runs
4. Rename a device in Govee app, verify script detects change

---

## Fix 2: MQTT Retained Message Cleanup Script (HIGH PRIORITY)

**Impact**: Provides automated detection and cleanup of ghost messages
**Benefit**: Safe, auditable cleanup without manual topic specification

### Implementation: `scripts/mqtt-cleanup.sh`

```bash
#!/bin/bash
# mqtt-cleanup.sh - Detect and clear stale retained messages

BROKER="localhost"
API="http://localhost:8056/api/devices"
SHOWSITE="demo_showsite"
NODE="dpx_ops_decoder"

echo "======================================"
echo "MQTT Retained Message Cleanup"
echo "======================================"
echo ""

# Get current device list from API
echo "Fetching current device list from API..."
DEVICES=$(curl -s --max-time 10 "$API")
if [ -z "$DEVICES" ] || [ "$DEVICES" = "[]" ]; then
  echo "ERROR: Failed to fetch devices from API"
  exit 1
fi

# Build list of current device names (lowercase, underscores)
CURRENT_NAMES=$(echo "$DEVICES" | python3 -c "
import json, sys
for d in json.load(sys.stdin):
    name = d['name'].lower().replace(' ','_')
    print(name)
")

echo "Current devices:"
echo "$CURRENT_NAMES"
echo ""

# Subscribe to all decoder topics for 5 seconds, capture retained messages
echo "Scanning MQTT for retained messages..."
RETAINED=$(timeout 5 mosquitto_sub -h "$BROKER" -t "${SHOWSITE}/${NODE}/#" -v 2>/dev/null)

# Extract unique device names from topics
MQTT_NAMES=$(echo "$RETAINED" | grep -oP "${SHOWSITE}/${NODE}/[^/]+/[^/]+/\K[^/]+" | sort -u)

echo "Devices found in MQTT:"
echo "$MQTT_NAMES"
echo ""

# Find stale device names (in MQTT but not in API)
STALE=""
while IFS= read -r mqtt_name; do
  if ! echo "$CURRENT_NAMES" | grep -qx "$mqtt_name"; then
    STALE="$STALE$mqtt_name"$'\n'
  fi
done <<< "$MQTT_NAMES"

if [ -z "$STALE" ]; then
  echo "✓ No stale retained messages found"
  exit 0
fi

echo "⚠ Stale device names found in MQTT:"
echo "$STALE"
echo ""

# List all topics for each stale device
echo "Stale topics to be cleared:"
while IFS= read -r stale_name; do
  [ -z "$stale_name" ] && continue
  echo "$RETAINED" | grep "/${stale_name}/" | cut -d' ' -f1
done <<< "$STALE"
echo ""

read -p "Clear these retained messages? (y/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted"
  exit 0
fi

# Clear each stale topic
CLEARED=0
while IFS= read -r stale_name; do
  [ -z "$stale_name" ] && continue
  while IFS= read -r topic; do
    mosquitto_pub -h "$BROKER" -t "$topic" -r -n
    echo "Cleared: $topic"
    ((CLEARED++))
  done <<< "$(echo "$RETAINED" | grep "/${stale_name}/" | cut -d' ' -f1)"
done <<< "$STALE"

echo ""
echo "✓ Cleared $CLEARED retained messages"
```

**Usage**:
```bash
# Make executable
chmod +x ~/dpx_govee_stack/scripts/mqtt-cleanup.sh

# Run cleanup
~/dpx_govee_stack/scripts/mqtt-cleanup.sh
```

**Add to manage.sh**:
```bash
mqtt-cleanup)
  $SCRIPT_DIR/mqtt-cleanup.sh
  ;;
```

Then use: `iot mqtt-cleanup`

---

## Fix 3: Use MAC-Based Topics (MEDIUM PRIORITY - BREAKING CHANGE)

**Impact**: Prevents topic changes when devices are renamed
**Benefit**: Device renames don't create new topics, no ghost data possible
**Tradeoff**: Less human-readable topics

### Proposed Topic Structure

**Current**:
```
demo_showsite/dpx_ops_decoder/{source_node}/{room}/{device_name}/{mac}/{metric}
                                                       ^^^^^^^^^^^^
                                                       Changes on rename
```

**Proposed**:
```
demo_showsite/dpx_ops_decoder/{source_node}/{mac}/{metric}
                                             ^^^
                                             Stable ID
```

Use Telegraf enum processors to add `device_name` and `room` as **tags** (not topic parts):
- MAC never changes → topic never changes
- Telegraf maps MAC → device_name/room from device-mappings.conf
- Rename updates mappings.conf, Telegraf applies new tags to existing topic

### Implementation

**ble_decoder.py changes**:
```python
# Line 176 - remove room/device_name from topic
base_topic = f"{SHOWSITE}/{DECODER_NODE}/{source_node}/{mac}"

# Still publish same metrics
client.publish(f"{base_topic}/temperature", decoded["temp_f"], retain=True)
client.publish(f"{base_topic}/humidity", decoded["humidity"], retain=True)
client.publish(f"{base_topic}/battery", decoded["battery"], retain=True)
```

**telegraf.conf changes**:
```toml
# New regex to extract MAC from simpler topic structure
[[processors.regex]]
  [[processors.regex.tags]]
    key = "topic"
    pattern = "demo_showsite/dpx_ops_decoder/([^/]+)/([^/]+)/([^/]+)"
    replacement = "${1}"
    result_key = "source_node"

  [[processors.regex.tags]]
    key = "topic"
    pattern = "demo_showsite/dpx_ops_decoder/([^/]+)/([^/]+)/([^/]+)"
    replacement = "${2}"
    result_key = "z_device_id"

  [[processors.regex.tags]]
    key = "topic"
    pattern = "demo_showsite/dpx_ops_decoder/([^/]+)/([^/]+)/([^/]+)"
    replacement = "${3}"
    result_key = "sensor_type"

# Enum processors still map z_device_id → device_name/room from device-mappings.conf
```

**Migration**:
1. Clear all existing retained messages under old topic structure
2. Deploy updated ble_decoder.py
3. Deploy updated telegraf.conf
4. Restart both services
5. New data flows with stable topics

---

## Fix 4: Reduce/Remove Retain Flag (LOW PRIORITY)

**Impact**: Eliminates retained messages entirely
**Benefit**: No ghost data possible
**Tradeoff**: Telegraf restart causes data gap until next BLE broadcast

### Analysis

**Pros**:
- No retained message management needed
- Clean restarts, no ghost data
- Simpler MQTT broker state

**Cons**:
- Telegraf misses data if restarted between BLE broadcasts (~1min window)
- No "last known value" available on subscription
- Historical context lost for debugging

**Recommendation**: Keep retain=True for operational visibility, implement Fixes 1 & 2 instead

---

## Implementation Priority

### Phase 1 (Immediate - Next Day)
1. ✅ Document issue in CONTEXT.md and ROADMAP.md
2. ⏳ Implement Fix 1 (diff check in update-device-map.sh)
3. ⏳ Test Fix 1 with manual device rename

### Phase 2 (Short Term - Next Week)
4. ⏳ Implement Fix 2 (mqtt-cleanup.sh script)
5. ⏳ Add `iot mqtt-cleanup` command
6. ⏳ Run cleanup on current system to clear existing ghosts
7. ⏳ Test workflow: rename device → verify ghost → run cleanup → verify cleared

### Phase 3 (Medium Term - Consider for v2.0)
8. ⏳ Evaluate Fix 3 (MAC-based topics)
9. ⏳ If approved, plan migration strategy
10. ⏳ Test in dev environment before production

---

## Testing Checklist

### Before Fixes
- [ ] Capture list of all current retained messages
- [ ] Capture current InfluxDB device_name values
- [ ] Document known ghost data instances

### Fix 1 Testing
- [ ] Run update-device-map.sh manually, verify no restart when unchanged
- [ ] Rename device in Govee app
- [ ] Wait for hourly cron, verify restart occurs
- [ ] Check log shows "Config changed"
- [ ] Rename back, verify no restart on next cron

### Fix 2 Testing
- [ ] Create test ghost (rename device, wait for update)
- [ ] Run mqtt-cleanup.sh, verify detection
- [ ] Clear ghost, verify removal
- [ ] Subscribe to MQTT, confirm ghost topic gone
- [ ] Check InfluxDB, verify ghost time series stops updating

### Post-Fix Validation
- [ ] Monitor for 24 hours, verify no new ghosts
- [ ] Verify Grafana dashboards show correct data
- [ ] Document any edge cases discovered

---

## Maintenance

### Regular Checks
- Run `iot mqtt-cleanup` monthly (or after device renames)
- Review update-device-map.log for restart frequency
- Monitor InfluxDB for duplicate device_name entries

### Future Improvements
- Consider adding cleanup to update-device-map.sh (detect stale topics, auto-clear)
- Add Grafana alert for duplicate device_name values
- Log device renames for audit trail

---

## References

- **ble_decoder.py**: Line 179 (`retain=True`), Line 176 (topic structure)
- **update-device-map.sh**: Line 47 (unconditional restart)
- **telegraf.conf**: Lines 58-75 (BLE topic regex processors)
- **CONTEXT.md**: TROUBLESHOOTING > MQTT Retained Message Ghost Data
- **ROADMAP.md**: Phase 4 > Outstanding Items > Critical #1

---

**Last Updated**: 2026-02-09
**Status**: Fix 1 & 2 ready for implementation
