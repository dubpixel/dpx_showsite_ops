#!/bin/bash
# Auto-update Telegraf config with device mappings from govee2mqtt API

API="http://localhost:8056/api/devices"
CONF="$HOME/dpx_govee_stack/telegraf/telegraf.conf"
BACKUP_DIR="$HOME/dpx_govee_stack/telegraf/backups"
LOG="$HOME/dpx_govee_stack/scripts/update-device-map.log"

mkdir -p "$BACKUP_DIR"

# Backup existing config (keep last 10)
if [ -f "$CONF" ]; then
  cp "$CONF" "$BACKUP_DIR/telegraf.conf.$(date +%Y%m%d-%H%M%S)"
fi

ls -t "$BACKUP_DIR"/telegraf.conf.* 2>/dev/null | tail -n +11 | xargs rm -f

# Fetch device list from govee2mqtt
DEVICES=$(curl -s --max-time 10 "$API")
if [ -z "$DEVICES" ] || [ "$DEVICES" = "[]" ]; then
  echo "$(date) - Failed to fetch devices or empty response. Skipping." >> "$LOG"
  exit 1
fi

# Generate device name mappings
NAME_MAPPINGS=$(echo "$DEVICES" | python3 -c "
import json, sys
devices = json.load(sys.stdin)
for d in devices:
    did = d['id'].replace(':','')
    name = d['name'].lower().replace(' ','_')
    print(f'      \"{did}\" = \"{name}\"')
")

# Generate room mappings
ROOM_MAPPINGS=$(echo "$DEVICES" | python3 -c "
import json, sys
devices = json.load(sys.stdin)
for d in devices:
    did = d['id'].replace(':','')
    room = (d.get('room') or 'unassigned').lower().replace(' ','_')
    print(f'      \"{did}\" = \"{room}\"')
")

# Generate new config
NEWCONF=$(cat << 'CONFEOF'
[agent]
  interval = "10s"
  omit_hostname = true

[[outputs.influxdb_v2]]
  urls = ["http://influxdb:8086"]
  token = "my-super-secret-token"
  organization = "home"
  bucket = "govee"

[[inputs.mqtt_consumer]]
  servers = ["tcp://mosquitto:1883"]
  topics = [
    "gv2mqtt/sensor/+/state"
  ]
  data_format = "value"
  data_type = "float"
  topic_tag = "topic"

[[processors.regex]]
  [[processors.regex.tags]]
    key = "topic"
    pattern = "gv2mqtt/sensor/sensor-([A-F0-9]+)-sensor([a-z]+)/state"
    replacement = "${1}"
    result_key = "device_id"

  [[processors.regex.tags]]
    key = "topic"
    pattern = "gv2mqtt/sensor/sensor-([A-F0-9]+)-sensor([a-z]+)/state"
    replacement = "${2}"
    result_key = "sensor_type"

[[processors.enum]]
  [[processors.enum.mapping]]
    tag = "device_id"
    dest = "device_name"
    [processors.enum.mapping.value_mappings]
CONFEOF
)

NEWCONF="${NEWCONF}
${NAME_MAPPINGS}

  [[processors.enum.mapping]]
    tag = \"device_id\"
    dest = \"room\"
    [processors.enum.mapping.value_mappings]
${ROOM_MAPPINGS}"

# Only update if config changed
if [ -f "$CONF" ] && [ "$(cat "$CONF")" = "$NEWCONF" ]; then
  echo "$(date) - No changes detected. Skipping restart." >> "$LOG"
  exit 0
fi

# Write new config and restart telegraf
echo "$NEWCONF" > "$CONF"
cd "$HOME/dpx_govee_stack" && docker compose restart telegraf
echo "$(date) - Config updated and telegraf restarted." >> "$LOG"
