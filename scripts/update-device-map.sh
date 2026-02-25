#!/bin/bash

# Determine stack directory dynamically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

API="http://localhost:8056/api/devices"
CONF="$REPO_ROOT/telegraf/conf.d/device-mappings.conf"
LOG="$REPO_ROOT/scripts/update-device-map.log"

mkdir -p "$(dirname "$CONF")"
mkdir -p "$(dirname "$LOG")"

# Use manage-devices.py to merge API data with local overrides
DEVICES=$(python3 "$SCRIPT_DIR/manage-devices.py" merge 2>&1 | grep -v "^Applied")
MERGE_EXIT=$?

# Check for errors
if [ $MERGE_EXIT -ne 0 ] || [ -z "$DEVICES" ] || [ "$DEVICES" = "[]" ]; then
  echo "$(date) - Failed to fetch/merge devices. Skipping." >> "$LOG"
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

(cd "$REPO_ROOT" && docker compose restart telegraf ble-decoder)
echo "$(date) - Device mappings updated (with overrides):" >> "$LOG"
echo "$DEVICES" | python3 -c "
import json, sys
for d in json.load(sys.stdin):
    did = d['id'].replace(':','')
    name = d['name'].lower().replace(' ','_')
    room = (d.get('room') or 'unassigned').lower().replace(' ','_')
    print(f'  {did}: {name} in {room}')
" >> "$LOG"
echo "" >> "$LOG"
