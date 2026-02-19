#!/bin/bash
# dpx-showsite-ops management CLI

# Determine stack directory dynamically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR" || exit 1


case "$1" in
  up)       docker compose up -d ;;
  down)     docker compose down ;;
  restart)  docker compose restart ${2:-} ;;
  status)   docker compose ps ;;
  fixnet)   sudo systemctl restart network-route-fix.service ;;
  ble-decode) cd "$SCRIPT_DIR" && source "$REPO_ROOT/.env" && python3 ble_decoder.py ;;
  ble-up)   docker compose up -d ble-decoder ;;
  ble-down) docker compose stop ble-decoder ;;
  ble-restart) docker compose restart ble-decoder ;;
  ble-rebuild) docker compose up -d --build ble-decoder ;;
  ble-status) docker compose ps ble-decoder ;;
  ble-logs) docker logs ble-decoder 2>&1 | tail -${2:-30} ;;
  ble-follow) docker logs -f ble-decoder ;;
  lg)       docker logs govee2mqtt 2>&1 | tail -${2:-30} ;;
  lt)       docker logs telegraf 2>&1 | tail -${2:-30} ;;
  lm)       docker logs mosquitto 2>&1 | tail -${2:-30} ;;
  li)       docker logs influxdb 2>&1 | tail -${2:-30} ;;
  lf)       docker logs grafana 2>&1 | tail -${2:-30} ;;
  lb)       docker logs ble-decoder 2>&1 | tail -${2:-30} ;;
  la)       for c in govee2mqtt telegraf mosquitto influxdb grafana ble-decoder; do echo "=== $c ===" && docker logs $c 2>&1 | tail -${2:-10} && echo; done ;;
  query)    docker exec influxdb influx query --org home --token my-super-secret-token "from(bucket:\"sensors\") |> range(start: -${2:-30m}) |> limit(n:${3:-5})" ;;
  query-tags) docker exec influxdb influx query --org home --token my-super-secret-token "from(bucket:\"sensors\") |> range(start: -${2:-5m}) |> limit(n:${3:-20})" ;;
  mqtt)     docker exec mosquitto mosquitto_sub -t "${2:-gv2mqtt/#}" -v -C ${3:-5} | ts '[%H:%M:%S]' ;;
  backup)
    mkdir -p ~/backups
    docker run --rm -v dpx_govee_stack_grafana-data:/data -v ~/backups:/backup alpine tar czf /backup/grafana-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .
    docker run --rm -v dpx_govee_stack_influxdb-data:/data -v ~/backups:/backup alpine tar czf /backup/influxdb-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .
    echo "Backups saved to ~/backups/"
    ls -la ~/backups/
    ;;
  nuke)     docker exec influxdb influx delete --org home --token my-super-secret-token --bucket sensors --start 1970-01-01T00:00:00Z --stop 2030-01-01T00:00:00Z && echo "Bucket nuked." ;;
  ip)       ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 ;;
  tunnel)   cloudflared tunnel --url http://localhost:3000 ;;
  tunnel-grafana)   cloudflared tunnel --url http://localhost:3000 ;;
  tunnel-influxdb)   cloudflared tunnel --url http://localhost:8086 ;;
  tunnel-schedule)   cloudflared tunnel --url http://localhost:8000 ;;
  update)   "$REPO_ROOT/scripts/update-device-map.sh" ;;
  list-devices)
    python3 "$REPO_ROOT/scripts/manage-devices.py" list
    ;;
  
  rename-device)
    python3 "$REPO_ROOT/scripts/manage-devices.py" rename
    if [ $? -eq 0 ]; then
      echo ""
      read -p "Restart services to apply changes? [Y/n] " -n 1 -r
      echo
      if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        docker compose restart ble-decoder telegraf
        echo "✓ Services restarted"
      fi
    fi
    ;;
  
  set-room)
    python3 "$REPO_ROOT/scripts/manage-devices.py" set-room
    if [ $? -eq 0 ]; then
      read -p "Restart services to apply changes? [Y/n] " -n 1 -r
      echo
      if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        docker compose restart ble-decoder telegraf
        echo "✓ Services restarted"
      fi
    fi
    ;;
  
  clear-override)
    python3 "$REPO_ROOT/scripts/manage-devices.py" clear-override
    if [ $? -eq 0 ]; then
      read -p "Restart services to apply changes? [Y/n] " -n 1 -r
      echo
      if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        docker compose restart ble-decoder telegraf
        echo "✓ Services restarted"
      fi
    fi
    ;;
  
  delete-device-data)
    python3 "$REPO_ROOT/scripts/manage-devices.py" delete-device-data
    ;;
  
  cron-on)  (crontab -l 2>/dev/null | grep -v update-device-map; echo "0 * * * * $REPO_ROOT/scripts/update-device-map.sh") | crontab - && echo "Cron enabled (hourly)" ;;
  cron-off) crontab -l 2>/dev/null | grep -v update-device-map | crontab - && echo "Cron disabled" ;;
  env)      cat "$REPO_ROOT/.env" ;;
  conf)     cat "$REPO_ROOT/telegraf/telegraf.conf" ;;
  edit)     vim "$REPO_ROOT/${2:-.env}" ;;
  esp32-enable)
    echo "Enabling ESP32 external decoder mode..."
    mosquitto_pub -h localhost \
      -t "demo_showsite/dpx_ops_1/commands/MQTTtoBT/config" \
      -m '{"pubadvdata":true,"extDecoderEnable":true}'
    mosquitto_pub -h localhost \
      -t "demo_showsite/dpx_showsite_2/commands/MQTTtoBT/config" \
      -m '{"pubadvdata":true,"extDecoderEnable":true}'
    echo "✓ ESP32 configured: pubadvdata=true, extDecoderEnable=true"
    ;;
  
  esp32-verbose)
    echo "Configuring ESP32 for maximum verbosity..."
    mosquitto_pub -h localhost \
      -t "demo_showsite/dpx_ops_1/commands/MQTTtoBT/config" \
      -m '{"pubadvdata":true,"extDecoderEnable":true,"BLEinterval":1000,"intervalcnct":5000,"scanbcnct":1}'
    mosquitto_pub -h localhost \
      -t "demo_showsite/dpx_showsite_2/commands/MQTTtoBT/config" \
      -m '{"pubadvdata":true,"extDecoderEnable":true,"BLEinterval":1000,"intervalcnct":5000,"scanbcnct":1}'
    echo "✓ ESP32 configured: faster scanning, more frequent advertising"
    echo "  - BLE scan interval: 1000ms (more frequent scans)"
    echo "  - Connection interval: 5000ms"
    echo "  - Scan before connect: enabled"
    ;;
  
  # Production Set-Schedule Commands (uses docker-compose service)
  schedule-up)
    echo "Starting set-schedule production service..."
    docker compose up -d set-schedule
    echo "✓ Production set-schedule service started"
    echo "Access at: http://localhost:${SCHEDULE_PORT:-8000}"
    ;;
  
  schedule-down)
    echo "Stopping set-schedule production service..."
    docker compose stop set-schedule
    echo "✓ Production set-schedule service stopped"
    ;;
  
  schedule-restart)
    echo "Restarting set-schedule production service..."
    docker compose restart set-schedule
    echo "✓ Production set-schedule service restarted"
    ;;
  
  schedule-status)
    echo "Set-Schedule Production Service Status:"
    echo "========================================"
    docker compose ps set-schedule
    ;;
  
  schedule-logs)
    echo "Set-Schedule Production Logs (last ${2:-30} lines):"
    echo "===================================================="
    docker compose logs set-schedule --tail ${2:-30}
    ;;
  
  schedule-follow)
    echo "Following set-schedule production logs (Ctrl+C to exit)..."
    docker compose logs -f set-schedule
    ;;
  
  schedule-rebuild)
    echo "Rebuilding and redeploying set-schedule production service..."
    docker compose up -d --build set-schedule
    echo "✓ Production set-schedule service rebuilt and redeployed"
    echo "Access at: http://localhost:${SCHEDULE_PORT:-8000}"
    ;;
  
  schedule-shell)
    echo "Opening shell in set-schedule production container..."
    docker compose exec set-schedule /bin/sh
    ;;
  
  # Development Set-Schedule Commands (uses standalone folder)
  schedule-dev-build)
    DEV_DIR="$REPO_ROOT/../COACHELLA_SET_SCHEDULE"
    if [ ! -d "$DEV_DIR" ]; then
      echo "⚠ Development directory not found: $DEV_DIR"
      echo "The COACHELLA_SET_SCHEDULE repo should be a sibling directory to DPX_SHOWSITE_OPS"
      exit 1
    fi
    
    cd "$DEV_DIR"
    echo "Building set-schedule dev image from: $DEV_DIR"
    docker build -t set-schedule:dev .
    echo "✓ Dev image built"
    ;;
  
  schedule-dev-up)
    DEV_DIR="$REPO_ROOT/../COACHELLA_SET_SCHEDULE"
    if [ ! -d "$DEV_DIR" ]; then
      echo "⚠ Development directory not found: $DEV_DIR"
      exit 1
    fi
    
    # Check if dev .env exists
    if [ ! -f "$DEV_DIR/.env" ]; then
      echo "⚠ No .env file found in $DEV_DIR"
      echo "Copy .env.example to .env and configure PORT=8001"
      exit 1
    fi
    
    # Stop and remove old dev container if exists
    if docker ps -a --format '{{.Names}}' | grep -q "^set-schedule-dev$"; then
      echo "Stopping and removing old dev container..."
      docker stop set-schedule-dev 2>/dev/null
      docker rm set-schedule-dev
    fi
    
    echo "Starting dev container on port 8001..."
    docker run -d \
      --name set-schedule-dev \
      -p 8001:8001 \
      --env-file "$DEV_DIR/.env" \
      -v "$REPO_ROOT/secret:/app/secret:ro" \
      set-schedule:dev
    
    echo "✓ Dev set-schedule running"
    echo "Access at: http://localhost:8001"
    ;;
  
  schedule-dev-down)
    echo "Stopping dev set-schedule container..."
    if docker ps -a --format '{{.Names}}' | grep -q "^set-schedule-dev$"; then
      docker stop set-schedule-dev
      docker rm set-schedule-dev
      echo "✓ Dev container stopped and removed"
    else
      echo "⚠ Dev container not found"
    fi
    ;;
  
  schedule-dev-restart)
    echo "Restarting dev set-schedule container..."
    docker restart set-schedule-dev
    echo "✓ Dev container restarted"
    ;;
  
  schedule-dev-logs)
    echo "Set-Schedule Dev Logs (last ${2:-30} lines):"
    echo "============================================="
    docker logs set-schedule-dev 2>&1 | tail -${2:-30}
    ;;
  
  schedule-dev-follow)
    echo "Following dev set-schedule logs (Ctrl+C to exit)..."
    docker logs -f set-schedule-dev
    ;;
  
  schedule-dev-rebuild)
    echo "Rebuilding and redeploying dev set-schedule..."
    $0 schedule-dev-build
    $0 schedule-dev-up
    ;;
  
  schedule-dev-shell)
    echo "Opening shell in dev set-schedule container..."
    docker exec -it set-schedule-dev /bin/sh
    ;;
  
  clear-retained)
    TOPIC="${2:-#}"
    echo "Clearing retained messages from topic: $TOPIC"
    echo "This will remove all retained messages matching the pattern..."
    
    # Get list of topics with retained messages
    TOPICS=$(docker exec mosquitto timeout 5 mosquitto_sub -t "$TOPIC" -v -F "%t" 2>/dev/null | sort -u)
    
    if [ -z "$TOPICS" ]; then
      echo "No retained messages found for topic pattern: $TOPIC"
    else
      COUNT=0
      while IFS= read -r topic; do
        [ -z "$topic" ] && continue
        docker exec mosquitto mosquitto_pub -t "$topic" -r -n
        echo "  ✓ Cleared: $topic"
        ((COUNT++))
      done <<< "$TOPICS"
      echo ""
      echo "Cleared $COUNT retained message(s)"
    fi
    ;;

  backup-dashboards)
    echo "Backing up Grafana dashboards..."
    
    # Check if requests library is installed
    if ! python3 -c "import requests" 2>/dev/null; then
      echo ""
      echo "ERROR: Python 'requests' library not installed on server"
      echo ""
      echo "Install it with (on this server):"
      echo "  sudo pip3 install requests"
      echo "  # or: sudo apt install python3-requests"
      echo ""
      echo "See README.md 'Dashboard Backup & Provisioning' section"
      exit 1
    fi
    
    cd "$REPO_ROOT"
    # Export variables from .env file so Python can access them
    if [ -f "$REPO_ROOT/.env" ]; then
      set -a
      source "$REPO_ROOT/.env"
      set +a
    fi
    python3 "$SCRIPT_DIR/backup-grafana-dashboards.py"
    ;;
  
  provision-dashboard)
    if [ -z "$2" ]; then
      # No file provided - run interactive picker
      python3 "$SCRIPT_DIR/provision-dashboard.py"
    else
      # File path provided - convert it
      python3 "$SCRIPT_DIR/provision-dashboard.py" "$2"
    fi
    ;;
  
  deprovision-dashboard)
    if [ -z "$2" ]; then
      # No file provided - run interactive picker
      python3 "$SCRIPT_DIR/deprovision-dashboard.py"
    else
      # File path provided - remove it
      python3 "$SCRIPT_DIR/deprovision-dashboard.py" "$2"
    fi
    ;;
  
  setup-dashboard-cron)
    CRON_CMD="0 2 * * * cd $REPO_ROOT && source $REPO_ROOT/.env && python3 $SCRIPT_DIR/backup-grafana-dashboards.py >> /var/log/grafana-backup.log 2>&1"
    (crontab -l 2>/dev/null | grep -v backup-grafana-dashboards; echo "$CRON_CMD") | crontab -
    echo "✓ Dashboard backup cron job installed"
    echo "  Schedule: Daily at 2:00 AM"
    echo "  Log: /var/log/grafana-backup.log"
    ;;
  
  remove-dashboard-cron)
    crontab -l 2>/dev/null | grep -v backup-grafana-dashboards | crontab -
    echo "✓ Dashboard backup cron job removed"
    ;;

  web)      echo "Grafana:  http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):3000"
            echo "InfluxDB: http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):8086"
            echo "MQTT:     $(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):1883"
            echo "govee2mqtt: http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):8056"
            echo "Set-Schedule: http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):8000"
            ;;
  *)
    echo ""
    echo "  iot - Govee IoT Stack Manager"
    echo "  ============================================"
    echo ""
    echo "  STACK CONTROL"
    echo "    up                     Start all containers"
    echo "    down                   Stop all containers (keeps data)"
    echo "    restart [service]      Restart all, or just one service"
    echo "                           services: govee2mqtt telegraf mosquitto influxdb grafana ble-decoder"
    echo "    status                 Show running containers"
    echo ""
    echo "  SET-SCHEDULE SERVICE (Production - uses docker-compose)"
    echo "    schedule-up            Start production service on port 8000"
    echo "    schedule-down          Stop production service"
    echo "    schedule-restart       Restart production service"
    echo "    schedule-status        Show production container status"
    echo "    schedule-logs [n]      View production logs (default: 30 lines)"
    echo "    schedule-follow        Follow production logs in real-time"
    echo "    schedule-rebuild       Rebuild and redeploy production service"
    echo "    schedule-shell         Open shell in production container"
    echo ""
    echo "  SET-SCHEDULE DEV (Dev/Test - uses standalone folder)"
    echo "    schedule-dev-build     Build dev image from ../COACHELLA_SET_SCHEDULE"
    echo "    schedule-dev-up        Start dev service on port 8001"
    echo "    schedule-dev-down      Stop dev service"
    echo "    schedule-dev-restart   Restart dev service"
    echo "    schedule-dev-logs [n]  View dev logs (default: 30 lines)"
    echo "    schedule-dev-follow    Follow dev logs in real-time"
    echo "    schedule-dev-rebuild   Build and start dev service"
    echo "    schedule-dev-shell     Open shell in dev container"
    echo ""
    echo "  BLE DECODER SERVICE (Python decoder for Govee BLE broadcasts)"
    echo "    ble-decode             Run decoder manually (foreground, for debugging)"
    echo "    ble-up                 Start BLE decoder service"
    echo "    ble-down               Stop BLE decoder service"
    echo "    ble-restart            Restart BLE decoder service"
    echo "    ble-rebuild            Rebuild and restart BLE decoder"
    echo "    ble-status             Show BLE decoder container status"
    echo "    ble-logs [n]           View logs (default: 30 lines)"
    echo "    ble-follow             Follow logs in real-time"
    echo ""
    echo "  LOGS                     All take optional line count (default 30)"
    echo "    lg [n]                 govee2mqtt logs"
    echo "    lt [n]                 telegraf logs"
    echo "    lm [n]                 mosquitto (MQTT broker) logs"
    echo "    li [n]                 influxdb logs"
    echo "    lf [n]                 grafana logs"
    echo "    lb [n]                 ble-decoder logs"
    echo "    la [n]                 ALL containers (default 10 each)"
    echo ""
    echo "  DATA"
    echo "    query [range] [rows]   Query InfluxDB (default: 30m, 5 rows)"
    echo "                           examples: iot query 1h 10 / iot query 24h"
    echo "    query-tags [range] [rows]  Query with tag columns (default: 5m, 20 rows)"
    echo "                           Shows: device_name, room, source, sensor_type, MAC"
    echo "    mqtt [topic] [count]   Subscribe to MQTT messages"
    echo "                           examples: iot mqtt / iot mqtt gv2mqtt/# 10"
    echo "    nuke                   DELETE all data in govee bucket (no undo!)"
    echo ""
    echo "  CONFIG"
    echo "    env                    Show .env file"
    echo "    conf                   Show telegraf config"
    echo "    edit [file]            Edit a file (default: .env)"
    echo "                           examples: iot edit / iot edit telegraf/telegraf.conf"
    echo "    update                 Refresh device name mappings from govee2mqtt API"
    echo "    list-devices           List all devices with current names and overrides"
    echo "    rename-device          Interactive device rename (prompts for service restart)"
    echo "    set-room               Interactive room change (prompts for service restart)"
    echo "    clear-override         Remove local override for a device (reverts to API name)"
    echo "    delete-device-data     Delete InfluxDB data for renamed devices (interactive)"
    echo ""
    echo "  NETWORK"
    echo "    ip                     Show VM IP address"
    echo "    web                    Show all service URLs"
    echo "    tunnel                 Start Cloudflare tunnel to Grafana"
    echo ""
    echo "  GRAFANA DASHBOARDS"
    echo "    backup-dashboards      Fetch all dashboards via API → ~/backups/grafana/dashboards/YYYY-MM-DD-HHMMSS/"
    echo "    provision-dashboard [file]  Convert backup to provisioning format"
    echo "                           No args = interactive picker (grouped by backup session) | With file = convert that file"
    echo "    deprovision-dashboard [file]  Remove dashboard from provisioning directory"
    echo "                           No args = interactive picker | With file = remove that file"
    echo "    setup-dashboard-cron   Install daily cron job for automatic dashboard backups"
    echo "    remove-dashboard-cron  Remove automatic dashboard backup cron job"
    echo ""
    echo "  MAINTENANCE"
    echo "    backup                 Backup Grafana + InfluxDB volumes to ~/backups/"
    echo "    clear-retained [topic] Clear retained MQTT messages (default: all topics)"
    echo "                           examples: iot clear-retained / iot clear-retained 'gv2mqtt/#'"
    echo ""
    echo "  ESP32 CONFIG"
    echo "    esp32-enable           Enable ESP32 BLE gateway external decoder mode"
    echo "    esp32-verbose          Configure ESP32 for maximum scan frequency"
    echo ""
    echo "  CREDENTIALS"
    echo "    Grafana:   admin / grafanapass123"
    echo "    InfluxDB:  admin / influxpass123  org=home  bucket=sensors"
    echo "    MQTT:      no auth"
    echo ""
    ;;
esac
