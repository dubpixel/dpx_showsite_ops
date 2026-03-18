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

echo ""
echo "Device mappings configuration updated: $CONF"
echo ""
echo "Which services need to be restarted?"
echo "  - telegraf: Needs reload for device-mappings.conf enum processors"
echo "  - ble-decoder: Needs reload for device-overrides.json"
echo "  - physical-control: Needs reload for device-overrides.json (if running)"
echo ""

RESTART_SERVICES=()

# Prompt for telegraf
read -p "Restart telegraf? (y/n) [n]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  RESTART_SERVICES+=("telegraf")
fi

# Prompt for ble-decoder
read -p "Restart ble-decoder? (y/n) [n]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  RESTART_SERVICES+=("ble-decoder")
fi

# Prompt for physical-control (check if it exists first)
if docker compose -f "$REPO_ROOT/docker-compose.yml" ps physical-control &>/dev/null; then
  read -p "Restart physical-control? (y/n) [n]: " -n 1 -r
  echo
  if [[ $REPLY =~ ^[Yy]$ ]]; then
    RESTART_SERVICES+=("physical-control")
  fi
fi

# Restart selected services
if [ ${#RESTART_SERVICES[@]} -gt 0 ]; then
  echo ""
  echo "Restarting: ${RESTART_SERVICES[*]}"
  docker compose -f "$REPO_ROOT/docker-compose.yml" restart "${RESTART_SERVICES[@]}"
  echo "✓ Services restarted"
else
  echo ""
  echo "No services restarted. Changes will take effect on next container restart."
fi

# Log the update
echo "$(date) - Device mappings updated (with overrides). Restarted: ${RESTART_SERVICES[*]:-none}" >> "$LOG"
echo "$DEVICES" | python3 -c "
import json, sys
for d in json.load(sys.stdin):
    did = d['id'].replace(':','')
    name = d['name'].lower().replace(' ','_')
    room = (d.get('room') or 'unassigned').lower().replace(' ','_')
    print(f'  {did}: {name} in {room}')
" >> "$LOG"
echo "" >> "$LOG"
