#!/bin/bash
API="http://localhost:8056/api/devices"
CONF="$HOME/dpx_govee_stack/telegraf/conf.d/device-mappings.conf"
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

cat > "$CONF" << EOF
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

docker compose -f "$HOME/dpx_govee_stack/docker-compose.yml" restart telegraf
echo "$(date) - Device mappings updated:" >> "$LOG"
echo "$DEVICES" | python3 -c "
import json, sys
for d in json.load(sys.stdin):
    did = d['id'].replace(':','')
    name = d['name'].lower().replace(' ','_')
    room = (d.get('room') or 'unassigned').lower().replace(' ','_')
    print(f'  {did}: {name} in {room}')
" >> "$LOG"
echo "" >> "$LOG"
