#!/bin/bash
# dpx-showsite-ops management CLI

# Determine stack directory dynamically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Helper function to run cloudflared tunnel in background
run_tunnel_background() {
  local NAME="$1"
  local PORT="$2"
  local TUNNEL_DIR="$HOME/logs/tunnel"
  local PID_FILE="$TUNNEL_DIR/$NAME.pid"
  local URL_FILE="$TUNNEL_DIR/$NAME.url"
  local LOG_FILE="$TUNNEL_DIR/$NAME.log"
  
  # Check if cloudflared is installed
  if ! command -v cloudflared >/dev/null 2>&1; then
    echo "✗ cloudflared not found. Install it with:"
    echo "  curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb"
    echo "  sudo dpkg -i cloudflared.deb"
    return 1
  fi
  
  # Create tunnel directory
  mkdir -p "$TUNNEL_DIR" || {
    echo "✗ Failed to create tunnel directory: $TUNNEL_DIR"
    return 1
  }
  
  # Check for existing tunnel on this port
  EXISTING_PID=$(pgrep -f "cloudflared tunnel --url.*:$PORT\b")
  if [ -n "$EXISTING_PID" ]; then
    echo "⚠️  $NAME tunnel already running (PID: $EXISTING_PID)"
    if [ -f "$URL_FILE" ]; then
      echo "   Current URL: $(cat "$URL_FILE")"
    fi
    echo ""
    read -t 10 -n 1 -r -p "[K]ill existing and restart, or [E]xit? (default: E) " REPLY
    echo ""
    
    if [[ $REPLY =~ ^[Kk]$ ]]; then
      echo "Stopping existing tunnel..."
      kill $EXISTING_PID 2>/dev/null
      sleep 2
      if ps -p $EXISTING_PID >/dev/null 2>&1; then
        kill -9 $EXISTING_PID 2>/dev/null
      fi
      rm -f "$PID_FILE" "$URL_FILE"
      echo "✓ Existing tunnel stopped"
    else
      echo "Keeping existing tunnel running"
      return 0
    fi
  fi
  
  # Clear log file
  > "$LOG_FILE"
  
  # Start tunnel in background
  nohup cloudflared tunnel --url http://localhost:$PORT >"$LOG_FILE" 2>&1 &
  TUNNEL_PID=$!
  echo $TUNNEL_PID > "$PID_FILE"
  
  # Wait briefly for process to initialize
  sleep 0.5
  
  # Verify process didn't crash
  if ! ps -p $TUNNEL_PID >/dev/null 2>&1; then
    echo "✗ Tunnel failed to start. Last 20 lines of log:"
    tail -20 "$LOG_FILE"
    return 1
  fi
  
  # Wait for URL to appear in log (up to 10 seconds)
  echo "Starting $NAME tunnel (PID: $TUNNEL_PID), waiting for URL..."
  for i in {1..20}; do
    sleep 0.5
    TUNNEL_URL=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$LOG_FILE" | head -n1)
    if [ -n "$TUNNEL_URL" ]; then
      echo "$TUNNEL_URL" > "$URL_FILE"
      echo "✓ $NAME tunnel ready: $TUNNEL_URL"
      return 0
    fi
  done
  
  # Timeout - tunnel is running but URL not detected yet
  echo "⚠️  Tunnel started but URL not detected yet"
  echo "   Check logs with: iot tunnel-logs $NAME"
  return 0
}

case "$1" in
  up)       docker compose up -d ;;
  down)     docker compose down ;;
  restart)  docker compose restart ${2:-} ;;
  status)   docker compose ps ;;
  fixnet)   sudo systemctl restart network-route-fix.service ;;
  ble-decode)
    # Kill any existing instances first
    if pgrep -f "python3.*ble_decoder.py" > /dev/null; then
      PIDS=$(pgrep -f "python3.*ble_decoder.py")
      echo "Found running ble_decoder.py instances (PIDs: $PIDS)"
      echo "Stopping existing instances..."
      pkill -f "python3.*ble_decoder.py"
      sleep 1
      # Force kill if any survived
      if pgrep -f "python3.*ble_decoder.py" > /dev/null; then
        echo "Force killing stubborn processes..."
        pkill -9 -f "python3.*ble_decoder.py"
        sleep 1
      fi
      echo "✓ Existing instances stopped"
    fi
    # Start new instance
    cd "$SCRIPT_DIR" && source "$REPO_ROOT/.env" && python3 ble_decoder.py
    ;;
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
  lp)       docker logs physical-control 2>&1 | tail -${2:-30} ;;
  la)       for c in govee2mqtt telegraf mosquitto influxdb grafana ble-decoder physical-control; do echo "=== $c ===" && docker logs $c 2>&1 | tail -${2:-10} && echo; done ;;
  query)    docker exec influxdb influx query --org home --token my-super-secret-token "from(bucket:\"sensors\") |> range(start: -${2:-30m}) |> limit(n:${3:-5})" ;;
  query-tags) docker exec influxdb influx query --org home --token my-super-secret-token "from(bucket:\"sensors\") |> range(start: -${2:-5m}) |> limit(n:${3:-20})" ;;
  mqtt)     docker exec mosquitto mosquitto_sub -t "${2:-gv2mqtt/#}" -v -C ${3:-5} | ts '[%H:%M:%S]' ;;
  watch-gv2) docker exec mosquitto mosquitto_sub -t "gv2mqtt/sensor/+/state" -v ${2:+-C $2} | ts '[%H:%M:%S]' ;;
  backup)
    mkdir -p ~/backups
    docker run --rm -v dpx_govee_stack_grafana-data:/data -v ~/backups:/backup alpine tar czf /backup/grafana-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .
    docker run --rm -v dpx_govee_stack_influxdb-data:/data -v ~/backups:/backup alpine tar czf /backup/influxdb-backup-$(date +%Y%m%d-%H%M%S).tar.gz -C /data .
    echo "Backups saved to ~/backups/"
    ls -la ~/backups/
    ;;
  nuke)     docker exec influxdb influx delete --org home --token my-super-secret-token --bucket sensors --start 1970-01-01T00:00:00Z --stop 2030-01-01T00:00:00Z && echo "Bucket nuked." ;;
  nuke-geist)
    echo "Deleting Geist measurements..."
    for measurement in geist_internal geist_temp_remote geist_airflow_remote; do
      docker exec influxdb influx delete \
        --org home \
        --token my-super-secret-token \
        --bucket sensors \
        --start 1970-01-01T00:00:00Z \
        --stop 2030-01-01T00:00:00Z \
        --predicate "_measurement=\"$measurement\""
      echo "  ✓ Deleted $measurement"
    done
    echo "Geist measurements deleted. Restart Telegraf to recreate with correct schema."
    echo "Run: iot restart telegraf"
    ;;
  
  # M4300 Netgear Backup Commands
  m4300-backup)
    echo "Running M4300 config backup..."
    docker compose run --rm netgear-backup
    echo "✓ Backup complete. Check logs with: iot m4300-logs"
    ;;
  
  m4300-backup-mock)
    echo "Running M4300 backup in MOCK mode (no real switches)..."
    docker compose run --rm netgear-backup python3 netgear_system_backup_TFTP-v0d1.py --mock
    echo "✓ Mock backup complete"
    ;;
  
  m4300-logs)
    echo "M4300 Backup Logs:"
    echo "=================="
    docker compose run --rm netgear-backup ls -lth /backups/logs 2>/dev/null | head -${2:-10}
    echo ""
    echo "View full log: iot m4300-log-view <filename>"
    ;;
  
  m4300-log-view)
    if [ -z "$2" ]; then
      echo "Usage: iot m4300-log-view <filename>"
      echo "List logs with: iot m4300-logs"
    else
      docker compose run --rm netgear-backup cat /backups/logs/$2
    fi
    ;;
  
  m4300-list)
    echo "Recent M4300 backups:"
    echo "====================="
    docker compose run --rm netgear-backup sh -c '
      for dir in $(ls -dt /backups/202* 2>/dev/null | head -'${2:-10}'); do
        echo ""
        echo "📁 $(basename $dir)"
        ls -lh $dir/*.cfg 2>/dev/null | awk "{printf \"  %-25s %5s  %s %s %s\n\", \$9, \$5, \$6, \$7, \$8}" | sed "s|.*/||"
      done
    '
    ;;
  
  m4300-list-all)
    echo "All M4300 backup files:"
    echo "======================="
    docker compose run --rm netgear-backup find /backups -name "*.cfg" -exec ls -lh {} \; | awk "{print \$9, \$5, \$6, \$7, \$8}" | column -t
    ;;
  
  m4300-clean)
    echo "Cleaning up empty backup folders (failed attempts)..."
    docker compose run --rm netgear-backup sh -c '
      for dir in /backups/202*; do
        if [ -d "$dir" ] && [ -z "$(ls -A $dir/*.cfg 2>/dev/null)" ]; then
          echo "Removing empty: $(basename $dir)"
          rm -rf "$dir"
        fi
      done
    '
    echo "✓ Cleanup complete. Use 'iot m4300-list' to see remaining backups."
    ;;
  
  m4300-network-fix)
    "$REPO_ROOT/scripts/setup-m4300-network.sh"
    ;;
  
  m4300-rebuild)
    echo "Rebuilding netgear-backup container image..."
    docker compose build netgear-backup
    echo "✓ Image rebuilt"
    ;;
  
  m4300-list-switches)
    echo "Configured switches (from switches.conf):"
    echo "========================================="
    docker compose run --rm netgear-backup python3 netgear_system_backup_TFTP-v0d1.py --list-switches
    ;;
  
  tftp-rebuild)
    echo "Recreating TFTP server with updated configuration..."
    docker stop tftp-server && docker rm tftp-server && docker compose up -d tftp-server
    echo "✓ TFTP server recreated"
    docker inspect tftp-server --format '{{.Args}}' | grep -q '\-c' && echo "✓ File creation enabled" || echo "⚠️  File creation NOT enabled"
    ;;
  
  tftp-rebuild)
    echo "Recreating TFTP server with updated configuration..."
    docker stop tftp-server && docker rm tftp-server && docker compose up -d tftp-server
    echo "✓ TFTP server recreated"
    docker inspect tftp-server --format '{{.Args}}' | grep -q '\-c' && echo "✓ File creation enabled" || echo "⚠️  File creation NOT enabled"
    ;;
  
  # Physical Control Service Management (Phase 7+8)
  physical-control-logs | pc-logs)
    docker compose logs -f physical-control
    ;;
  
  physical-control-status | pc-status)
    echo "=== Physical Control Service Status ==="
    docker compose ps physical-control
    echo ""
    echo "=== Health Check ==="
    if curl -sf http://localhost:5000/health >/dev/null 2>&1; then
      echo "✓ Service is healthy"
      curl -s http://localhost:5000/ | python3 -m json.tool
    else
      echo "✗ Service is not responding"
      exit 1
    fi
    ;;
  
  physical-control-test | pc-test)
    echo "Testing webhook endpoint..."
    echo "Sending test alert: Temperature Test (state: alerting)"
    curl -X POST http://localhost:5000/webhook \
      -H "Content-Type: application/json" \
      -d '{
        "ruleName": "High Temperature Alert",
        "state": "alerting",
        "message": "Test alert from manage.sh",
        "labels": {"room": "test"},
        "value": 95,
        "threshold": 85
      }' | python3 -m json.tool
    echo ""
    echo "Check logs with: iot physical-control-logs"
    ;;
  
  physical-control-config | pc-config)
    ${EDITOR:-nano} "$REPO_ROOT/services/physical-control/alert_actions.yaml"
    echo ""
    read -p "Restart physical-control service to apply changes? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      docker compose restart physical-control
      echo "✓ Service restarted"
    fi
    ;;
  
  physical-control-restart | pc-restart)
    docker compose restart physical-control
    echo "✓ physical-control service restarted"
    ;;
  
  physical-control-rebuild | pc-rebuild)
    echo "Rebuilding physical-control container..."
    docker compose build physical-control
    echo "✓ Image rebuilt"
    echo ""
    read -p "Restart service with new image? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      docker compose up -d physical-control
      echo "✓ Service restarted"
    fi
    ;;
  
  # Physical Device Control (Phase 7+8)
  geist-relay)
    # Load .env for credentials
    if [ -f "$REPO_ROOT/.env" ]; then
      source "$REPO_ROOT/.env"
    else
      echo "✗ .env file not found. Copy .env.example to .env and configure GEIST_IP and GEIST_SNMP_RW_COMMUNITY"
      exit 1
    fi
    
    # Check required variables
    if [ -z "$GEIST_IP" ] || [ -z "$GEIST_SNMP_RW_COMMUNITY" ]; then
      echo "✗ Missing environment variables. Configure in .env:"
      echo "  GEIST_IP=192.168.1.214"
      echo "  GEIST_SNMP_RW_COMMUNITY=private"
      exit 1
    fi
    
    # Check relay action provided
    if [ -z "$2" ]; then
      echo "Usage: iot geist-relay <on|off|toggle>"
      exit 1
    fi
    
    # Execute control script
    python3 "$SCRIPT_DIR/geist_control.py" \
      --ip "$GEIST_IP" \
      --community "$GEIST_SNMP_RW_COMMUNITY" \
      --relay "$2"
    ;;
  
  x410-relay)
    # Load .env for credentials
    if [ -f "$REPO_ROOT/.env" ]; then
      source "$REPO_ROOT/.env"
    else
      echo "✗ .env file not found. Copy .env.example to .env and configure X410_IP and X410_SNMP_COMMUNITY"
      exit 1
    fi
    
    # Check required variables
    if [ -z "$X410_IP" ]; then
      echo "✗ Missing X410_IP environment variable. Configure in .env:"
      echo "  X410_IP=192.168.1.XXX"
      echo "  X410_SNMP_COMMUNITY=public"
      exit 1
    fi
    
    # Check relay number and action provided
    if [ -z "$2" ] || [ -z "$3" ]; then
      echo "Usage: iot x410-relay <1-4> <on|off|toggle>"
      echo "       iot x410-relay <1-4> pulse <seconds>"
      exit 1
    fi
    
    # Handle pulse mode
    if [ "$3" = "pulse" ]; then
      if [ -z "$4" ]; then
        echo "✗ Pulse duration required"
        echo "Usage: iot x410-relay <1-4> pulse <seconds>"
        exit 1
      fi
      python3 "$SCRIPT_DIR/x410_control.py" \
        --ip "$X410_IP" \
        --community "${X410_SNMP_COMMUNITY:-public}" \
        --relay "$2" \
        --pulse "$4"
    else
      # Regular on/off/toggle
      python3 "$SCRIPT_DIR/x410_control.py" \
        --ip "$X410_IP" \
        --community "${X410_SNMP_COMMUNITY:-public}" \
        --relay "$2" \
        --state "$3"
    fi
    ;;
  
  govee-control)
    # Pass all arguments to govee_control.py (shift removes 'govee-control' from args)
    shift
    python3 "$SCRIPT_DIR/govee_control.py" "$@"
    ;;
  
  list-govee-devices | list-devices)
    # Show all controllable devices
    echo "=== Geist Watchdog ==="
    if [ -f "$REPO_ROOT/.env" ]; then
      source "$REPO_ROOT/.env"
      echo "  Relay: ${GEIST_IP:-192.168.1.214} (SNMP)"
    else
      echo "  Relay: (configure .env)"
    fi
    echo ""
    echo "=== X-410 Relay Controller ==="
    if [ -f "$REPO_ROOT/.env" ]; then
      source "$REPO_ROOT/.env"
      echo "  Relay 1-4: ${X410_IP:-not configured} (SNMP)"
    else
      echo "  Relay 1-4: (configure .env)"
    fi
    echo ""
    echo "=== Govee Devices ==="
    python3 "$SCRIPT_DIR/govee_control.py" --list
    ;;
  
  ip)       ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 ;;
  tunnel)   run_tunnel_background "grafana" 3000 ;;
  tunnel-grafana)   run_tunnel_background "grafana" 3000 ;;
  tunnel-influxdb)   run_tunnel_background "influxdb" 8086 ;;
  tunnel-schedule)   run_tunnel_background "schedule" 8000 ;;
  
  tunnel-stop)
    TUNNEL_DIR="$HOME/logs/tunnel"
    if [ ! -d "$TUNNEL_DIR" ] || [ -z "$(ls -A "$TUNNEL_DIR"/*.pid 2>/dev/null)" ]; then
      echo "No tunnel PID files found in $TUNNEL_DIR"
      exit 0
    fi
    echo "Stopping all tunnels..."
    for pid_file in "$TUNNEL_DIR"/*.pid; do
      [ -f "$pid_file" ] || continue
      PID=$(cat "$pid_file" 2>/dev/null)
      NAME=$(basename "$pid_file" .pid)
      if [ -n "$PID" ] && ps -p $PID >/dev/null 2>&1; then
        echo "  Stopping $NAME tunnel (PID: $PID)..."
        kill $PID 2>/dev/null
        sleep 1
        if ps -p $PID >/dev/null 2>&1; then
          kill -9 $PID 2>/dev/null
        fi
      fi
      rm -f "$pid_file" "$TUNNEL_DIR/$NAME.url"
    done
    echo "✓ All tunnels stopped"
    ;;
  
  tunnel-stop-grafana)
    TUNNEL_DIR="$HOME/logs/tunnel"
    PID_FILE="$TUNNEL_DIR/grafana.pid"
    if [ ! -f "$PID_FILE" ]; then
      echo "No grafana tunnel PID file found"
      exit 0
    fi
    PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$PID" ] && ps -p $PID >/dev/null 2>&1; then
      echo "Stopping grafana tunnel (PID: $PID)..."
      kill $PID 2>/dev/null
      sleep 1
      if ps -p $PID >/dev/null 2>&1; then
        kill -9 $PID 2>/dev/null
      fi
      echo "✓ Grafana tunnel stopped"
    else
      echo "Grafana tunnel not running"
    fi
    rm -f "$PID_FILE" "$TUNNEL_DIR/grafana.url"
    ;;
  
  tunnel-stop-influxdb)
    TUNNEL_DIR="$HOME/logs/tunnel"
    PID_FILE="$TUNNEL_DIR/influxdb.pid"
    if [ ! -f "$PID_FILE" ]; then
      echo "No influxdb tunnel PID file found"
      exit 0
    fi
    PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$PID" ] && ps -p $PID >/dev/null 2>&1; then
      echo "Stopping influxdb tunnel (PID: $PID)..."
      kill $PID 2>/dev/null
      sleep 1
      if ps -p $PID >/dev/null 2>&1; then
        kill -9 $PID 2>/dev/null
      fi
      echo "✓ InfluxDB tunnel stopped"
    else
      echo "InfluxDB tunnel not running"
    fi
    rm -f "$PID_FILE" "$TUNNEL_DIR/influxdb.url"
    ;;
  
  tunnel-stop-schedule)
    TUNNEL_DIR="$HOME/logs/tunnel"
    PID_FILE="$TUNNEL_DIR/schedule.pid"
    if [ ! -f "$PID_FILE" ]; then
      echo "No schedule tunnel PID file found"
      exit 0
    fi
    PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$PID" ] && ps -p $PID >/dev/null 2>&1; then
      echo "Stopping schedule tunnel (PID: $PID)..."
      kill $PID 2>/dev/null
      sleep 1
      if ps -p $PID >/dev/null 2>&1; then
        kill -9 $PID 2>/dev/null
      fi
      echo "✓ Schedule tunnel stopped"
    else
      echo "Schedule tunnel not running"
    fi
    rm -f "$PID_FILE" "$TUNNEL_DIR/schedule.url"
    ;;
  
  tunnel-status)
    TUNNEL_DIR="$HOME/logs/tunnel"
    if [ ! -d "$TUNNEL_DIR" ] || [ -z "$(ls -A "$TUNNEL_DIR"/*.pid 2>/dev/null)" ]; then
      echo "No tunnels configured (no PID files in $TUNNEL_DIR)"
      exit 0
    fi
    echo "Tunnel Status:"
    echo "=============================================="
    printf "%-15s %-10s %-8s %s\n" "NAME" "STATUS" "PID" "URL"
    echo "----------------------------------------------"
    for pid_file in "$TUNNEL_DIR"/*.pid; do
      [ -f "$pid_file" ] || continue
      NAME=$(basename "$pid_file" .pid)
      PID=$(cat "$pid_file" 2>/dev/null)
      URL_FILE="$TUNNEL_DIR/$NAME.url"
      
      if [ -n "$PID" ] && ps -p $PID >/dev/null 2>&1; then
        STATUS="running"
        URL=$(cat "$URL_FILE" 2>/dev/null || echo "(pending)")
      else
        STATUS="stopped"
        URL="(not running)"
        # Clean up stale PID file
        rm -f "$pid_file" "$URL_FILE"
      fi
      printf "%-15s %-10s %-8s %s\n" "$NAME" "$STATUS" "$PID" "$URL"
    done
    ;;
  
  tunnel-logs)
    TUNNEL_DIR="$HOME/logs/tunnel"
    NAME="$2"
    LINES="${3:-30}"
    
    if [ -z "$NAME" ]; then
      # Show all tunnel logs
      if [ ! -d "$TUNNEL_DIR" ] || [ -z "$(ls -A "$TUNNEL_DIR"/*.log 2>/dev/null)" ]; then
        echo "No tunnel logs found in $TUNNEL_DIR"
        exit 0
      fi
      for log_file in "$TUNNEL_DIR"/*.log; do
        [ -f "$log_file" ] || continue
        TUNNEL_NAME=$(basename "$log_file" .log)
        echo "=== $TUNNEL_NAME tunnel logs (last $LINES lines) ==="
        tail -$LINES "$log_file"
        echo ""
      done
    else
      # Show specific tunnel log
      LOG_FILE="$TUNNEL_DIR/$NAME.log"
      if [ ! -f "$LOG_FILE" ]; then
        echo "Log file not found: $LOG_FILE"
        echo -n "Available tunnels: "
        ls "$TUNNEL_DIR"/*.log 2>/dev/null | xargs -n1 basename 2>/dev/null | sed 's/.log$//' | tr '\n' ' ' || echo "(none)"
        echo ""
        exit 1
      fi
      tail -$LINES "$LOG_FILE"
    fi
    ;;
  
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
      -t "coachella_26/dpx_showsite_1/commands/MQTTtoBT/config" \
      -m '{"pubadvdata":true,"extDecoderEnable":true}'
     mosquitto_pub -h localhost \
      -t "coachella_26/dpx_showsite_2/commands/MQTTtoBT/config" \
      -m '{"pubadvdata":true,"extDecoderEnable":true}'
    echo "✓ ESP32 configured: pubadvdata=true, extDecoderEnable=true"
    ;;
  
  esp32-verbose)
    echo "Configuring E
    
    
    SP32 for maximum verbosity..."
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
  
  esp32-decode)
    echo "Enabling ESP32 internal decoder (Theengs library)..."
    mosquitto_pub -h localhost \
      -t "coachella_26/dpx_showsite_1/commands/MQTTtoBT/config" \
      -m '{"pubadvdata":true,"extDecoderEnable":false}'
    mosquitto_pub -h localhost \
      -t "coachella_26/dpx_showsite_2/commands/MQTTtoBT/config" \
      -m '{"pubadvdata":true,"extDecoderEnable":false}'
    echo "✓ ESP32 configured: pubadvdata=true, extDecoderEnable=false"
    echo "  - ESP32 decodes all recognized BLE devices (Govee, iBeacons, etc.)"
    echo "  - More device visibility, ESP32 filters unrecognized devices"
    echo "  - BLE decoder uses pre-decoded data from ESP32"
    ;;
  
  esp32-quiet)
    echo "Configuring ESP32 for minimal verbosity..."
    mosquitto_pub -h localhost \
      -t "coachella_26/dpx_showsite_1/commands/MQTTtoBT/config" \
      -m '{"pubadvdata":false,"extDecoderEnable":false,"BLEinterval":5000}'
    mosquitto_pub -h localhost \
      -t "coachella_26/dpx_showsite_2/commands/MQTTtoBT/config" \
      -m '{"pubadvdata":false,"extDecoderEnable":false,"BLEinterval":5000}'
    echo "✓ ESP32 configured: minimal message mode"
    echo "  - pubadvdata=false, extDecoderEnable=false"
    echo "  - BLE scan interval: 5000ms (slower scanning)"
    echo "  - ESP32 only publishes recognized/decoded devices"
    echo "  - Lowest MQTT message volume"
    ;;
  
  esp32-decode-verbose)
    echo "Configuring ESP32 for maximum visibility + fast scanning..."
    mosquitto_pub -h localhost \
      -t "coachella_26/dpx_showsite_1/commands/MQTTtoBT/config" \
      -m '{"pubadvdata":true,"extDecoderEnable":false,"BLEinterval":1000,"intervalcnct":5000,"scanbcnct":1}'
    mosquitto_pub -h localhost \
      -t "coachella_26/dpx_showsite_2/commands/MQTTtoBT/config" \
      -m '{"pubadvdata":true,"extDecoderEnable":false,"BLEinterval":1000,"intervalcnct":5000,"scanbcnct":1}'
    echo "✓ ESP32 configured: decode mode with maximum verbosity"
    echo "  - pubadvdata=true, extDecoderEnable=false"
    echo "  - BLE scan interval: 1000ms (every second)"
    echo "  - ESP32 decodes ALL recognized BLE devices"
    echo "  - Maximum update frequency + device visibility"
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
  
  restore-dashboard)
    cd "$REPO_ROOT"
    # Export variables from .env file so Python can access them
    if [ -f "$REPO_ROOT/.env" ]; then
      set -a
      source "$REPO_ROOT/.env"
      set +a
    fi
    
    if [ -z "$2" ]; then
      # No file provided - run interactive picker
      python3 "$SCRIPT_DIR/restore-dashboard.py"
    else
      # File path provided - restore it
      python3 "$SCRIPT_DIR/restore-dashboard.py" "$2"
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

  # Guest Alert Button System (Phase 7+8)
  button-status|btn-status)
    echo "=== Guest Alert Button System Status ==="
    echo ""
    if ! docker compose ps dpx-guest-alert-button | grep -q "running"; then
      echo "✗ Service not running"
      echo ""
      echo "Start with: docker compose up -d dpx-guest-alert-button"
      exit 1
    fi
    
    echo "✓ Service running"
    echo ""
    curl -s http://localhost:8080/health | python3 -m json.tool || {
      echo "✗ Health endpoint not responding"
      exit 1
    }
    ;;
  
  button-logs|btn-logs)
    docker logs -f dpx-guest-alert-button
    ;;
  
  button-clear|btn-clear)
    echo "Clearing all lamps..."
    curl -s -X POST http://localhost:8080/clear | python3 -m json.tool
    echo ""
    ;;
  
  button-reset|btn-reset)
    if [ -z "$2" ]; then
      echo "Usage: iot button-reset <red|yellow|green|blue>"
      echo ""
      echo "Examples:"
      echo "  iot button-reset red"
      echo "  iot btn-reset yellow"
      exit 1
    fi
    
    COLOR="$2"
    echo "Resetting $COLOR lamp..."
    curl -s -X POST "http://localhost:8080/reset/$COLOR" | python3 -m json.tool
    echo ""
    ;;
  
  button-metrics|btn-metrics)
    curl -s http://localhost:8080/metrics
    ;;
  
  button-rebuild|btn-rebuild)
    echo "Rebuilding guest alert button container (no cache)..."
    docker compose build dpx-guest-alert-button --no-cache
    echo ""
    echo "✓ Build complete"
    echo "Start with: iot button-start"
    ;;
  
  button-start|btn-start)
    echo "Starting guest alert button service..."
    docker compose up -d dpx-guest-alert-button
    echo ""
    echo "✓ Service started"
    echo "View logs with: iot button-logs"
    echo "Check status with: iot button-status"
    ;;
  
  button-stop|btn-stop)
    echo "Stopping guest alert button service..."
    docker compose stop dpx-guest-alert-button
    echo ""
    echo "✓ Service stopped"
    ;;
  
  button-restart|btn-restart)
    echo "Restarting guest alert button service..."
    docker compose restart dpx-guest-alert-button
    echo ""
    echo "View logs with: iot button-logs"
    ;;

  # NTP Server Management
  ntp-start|ntp-up)
    echo "Starting NTP server..."
    docker compose up -d ntp-server
    echo ""
    echo "✓ NTP server started"
    echo "Check sync status with: iot ntp-status"
    ;;
  
  ntp-stop|ntp-down)
    echo "Stopping NTP server..."
    docker compose stop ntp-server
    echo ""
    echo "✓ NTP server stopped"
    ;;
  
  ntp-restart)
    echo "Restarting NTP server..."
    docker compose restart ntp-server
    echo ""
    echo "✓ NTP server restarted"
    echo "Check sync status with: iot ntp-status"
    ;;
  
  ntp-status)
    echo "=== NTP Server Status ==="
    if ! docker compose ps ntp-server 2>/dev/null | grep -q "Up"; then
      echo "✗ NTP server is not running"
      echo ""
      echo "Start with: iot ntp-start"
      exit 1
    fi
    
    echo "✓ NTP server is running"
    echo ""
    echo "=== Tracking Status ==="
    docker compose exec ntp-server chronyc tracking 2>/dev/null || {
      echo "✗ Unable to get tracking status"
      echo "Container may still be starting up..."
      exit 1
    }
    echo ""
    echo "=== Time Sources ==="
    docker compose exec ntp-server chronyc sources -v 2>/dev/null | head -20
    ;;
  
  ntp-tracking)
    echo "=== NTP Server Tracking ==="
    docker compose exec ntp-server chronyc tracking
    ;;
  
  ntp-sources)
    echo "=== NTP Time Sources ==="
    docker compose exec ntp-server chronyc sources -v
    ;;
  
  ntp-sourcestats)
    echo "=== NTP Source Statistics ==="
    docker compose exec ntp-server chronyc sourcestats
    ;;
  
  ntp-logs)
    docker compose logs ${2:+-f} ntp-server
    ;;
  
  ntp-rebuild)
    echo "Rebuilding NTP server container..."
    docker compose build ntp-server
    echo ""
    echo "✓ Build complete"
    read -p "Restart NTP server with new image? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      docker compose up -d ntp-server
      echo "✓ NTP server restarted"
      sleep 2
      echo ""
      docker compose exec ntp-server chronyc tracking
    fi
    ;;
  
  ntp-clients)
    echo "=== NTP Client Activity ==="
    docker compose exec ntp-server chronyc clients
    echo ""
    echo "Note: Client tracking must be enabled in ntp.conf"
    echo "Add 'clientlog' directive to enable detailed client logging"
    ;;

  # ── WLED Bridge Service ────────────────────────────────────────────────────

  wled-up)
    echo "Starting WLED bridge..."
    cd "$REPO_ROOT" && docker compose up -d wled-bridge
    echo ""
    echo "✓ WLED bridge started"
    echo "View logs with: iot wled-logs"
    ;;

  wled-down)
    echo "Stopping WLED bridge..."
    cd "$REPO_ROOT" && docker compose stop wled-bridge
    echo ""
    echo "✓ WLED bridge stopped"
    ;;

  wled-restart)
    echo "Restarting WLED bridge..."
    cd "$REPO_ROOT" && docker compose restart wled-bridge
    echo ""
    echo "✓ WLED bridge restarted"
    echo "View logs with: iot wled-logs"
    ;;

  wled-rebuild)
    echo "Rebuilding WLED bridge container..."
    cd "$REPO_ROOT" && docker compose build wled-bridge
    echo ""
    echo "✓ Build complete"
    cd "$REPO_ROOT" && docker compose up -d wled-bridge
    echo "✓ WLED bridge restarted with new image"
    echo "View logs with: iot wled-logs"
    ;;

  wled-logs)
    cd "$REPO_ROOT" && docker compose logs --tail="${2:-50}" wled-bridge
    ;;

  wled-follow)
    cd "$REPO_ROOT" && docker compose logs -f wled-bridge
    ;;

  wled-shell)
    cd "$REPO_ROOT" && docker compose exec wled-bridge /bin/bash
    ;;

  # ── WLED Direct Pixel Control ───────────────────────────────────────────────

  wled-set)
    # Publish a segment command directly to WLED via MQTT.
    # Bypasses wled-bridge — useful for testing individual zones.
    if [ -z "$6" ]; then
      echo "Usage: iot wled-set <start> <stop> <r> <g> <b>"
      echo ""
      echo "  Sets pixels start through (stop-1) to the given RGB color."
      echo "  stop is EXCLUSIVE — WLED convention (same as config.yaml)."
      echo ""
      echo "Examples:"
      echo "  iot wled-set 75 100 255 0 0     # pixels 75-99 → red (hot)"
      echo "  iot wled-set 75 100 0 50 255    # pixels 75-99 → blue (cold)"
      echo "  iot wled-set 0 100 0 0 0        # blackout all 100px"
      echo "  iot wled-set 0 25 0 200 0       # pixels 0-24 → green"
      exit 1
    fi

    START="$2"
    STOP="$3"
    R="$4"
    G="$5"
    B="$6"

    # Validate numeric args
    for arg in "$START" "$STOP" "$R" "$G" "$B"; do
      if ! [[ "$arg" =~ ^[0-9]+$ ]]; then
        echo "✗ All arguments must be non-negative integers"
        echo "Usage: iot wled-set <start> <stop> <r> <g> <b>"
        exit 1
      fi
    done

    # Load WLED device topic from .env (fall back to 'wled')
    WLED_DEVICE=$(grep -E '^WLED_DEVICE_TOPIC=' "$REPO_ROOT/.env" 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'")
    WLED_DEVICE="${WLED_DEVICE:-wled}"

    TOPIC="${WLED_DEVICE}/api"
    PAYLOAD="{\"seg\":[{\"start\":${START},\"stop\":${STOP},\"col\":[[${R},${G},${B}]],\"fx\":0,\"on\":true}]}"

    echo "Device:  $WLED_DEVICE"
    echo "Topic:   $TOPIC"
    echo "Pixels:  ${START}–$((STOP - 1))  (${STOP} exclusive)"
    echo "Color:   RGB(${R}, ${G}, ${B})"
    echo "Payload: $PAYLOAD"
    echo ""

    mosquitto_pub -h localhost -p 1883 -t "$TOPIC" -m "$PAYLOAD"
    echo "✓ Sent"
    ;;

  wled-off)
    # Turn off all pixels (brightness 0, keeps segments intact)
    WLED_DEVICE=$(grep -E '^WLED_DEVICE_TOPIC=' "$REPO_ROOT/.env" 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'")
    WLED_DEVICE="${WLED_DEVICE:-wled}"
    TOPIC="${WLED_DEVICE}/api"
    mosquitto_pub -h localhost -p 1883 -t "$TOPIC" -m '{"on":false}'
    echo "✓ WLED off (wled/${WLED_DEVICE}/api)"
    ;;

  # ── WLED Matrix — scrolling text display ──────────────────────────────────

  matrix-text)
    # Blast scrolling text to the matrix via MQTT.
    # Usage: iot matrix-text "YOUR TEXT" [ttl_seconds]
    if [ -z "$2" ]; then
      echo "Usage: iot matrix-text \"YOUR TEXT\" [ttl_seconds]"
      echo ""
      echo "Examples:"
      echo "  iot matrix-text \"DOORS OPEN\""
      echo "  iot matrix-text \"STAGE 1 NOW\" 60"
      exit 1
    fi
    MATRIX_TOPIC=$(grep -E '^WLED_MATRIX_TOPIC=' "$REPO_ROOT/.env" 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'")
    MATRIX_TOPIC="${MATRIX_TOPIC:-wled-matrix}"
    SHOWSITE=$(grep -E '^SHOWSITE_NAME=' "$REPO_ROOT/.env" 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'")
    SHOWSITE="${SHOWSITE:-demo_showsite}"
    TEXT="$2"
    TTL="${3:-30}"
    PAYLOAD="{\"text\":\"${TEXT}\",\"ttl\":${TTL}}"
    PUB_TOPIC="${SHOWSITE}/wled/matrix/text"
    echo "Topic:   $PUB_TOPIC"
    echo "Payload: $PAYLOAD"
    mosquitto_pub -h localhost -p 1883 -t "$PUB_TOPIC" -m "$PAYLOAD"
    echo "✓ Sent — matrix will clear in ${TTL}s"
    ;;

  matrix-text-json)
    # Blast scrolling text with full JSON control (text, color, speed, ttl).
    # Usage: iot matrix-text-json '{"text":"...","color":[R,G,B],"speed":N,"ttl":N}'
    if [ -z "$2" ]; then
      echo "Usage: iot matrix-text-json '<json>'"
      echo ""
      echo "JSON fields:"
      echo "  text    (string)      The message to scroll"
      echo "  color   ([R,G,B])     Text color (0-255 each). Default: [255,220,0] yellow"
      echo "  speed   (0-255)       Scroll speed. Default: 100"
      echo "  ttl     (seconds)     Auto-clear after this many seconds. Default: 30"
      echo ""
      echo "Examples:"
      echo "  iot matrix-text-json '{\"text\":\"DOORS OPEN\"}'"
      echo "  iot matrix-text-json '{\"text\":\"GO\",\"color\":[255,0,100],\"speed\":200,\"ttl\":10}'"
      echo "  iot matrix-text-json '{\"text\":\"SOUND CHECK\",\"color\":[0,200,255],\"speed\":80,\"ttl\":60}'"
      exit 1
    fi
    SHOWSITE=$(grep -E '^SHOWSITE_NAME=' "$REPO_ROOT/.env" 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'")
    SHOWSITE="${SHOWSITE:-demo_showsite}"
    PUB_TOPIC="${SHOWSITE}/wled/matrix/text"
    echo "Topic:   $PUB_TOPIC"
    echo "Payload: $2"
    mosquitto_pub -h localhost -p 1883 -t "$PUB_TOPIC" -m "$2"
    echo "✓ Sent"
    ;;

  matrix-clear)
    # Immediately clear the matrix (solid black) via MQTT.
    MATRIX_TOPIC=$(grep -E '^WLED_MATRIX_TOPIC=' "$REPO_ROOT/.env" 2>/dev/null | cut -d= -f2 | tr -d '"' | tr -d "'")
    MATRIX_TOPIC="${MATRIX_TOPIC:-wled-matrix}"
    TOPIC="${MATRIX_TOPIC}/api"
    PAYLOAD='{"seg":[{"id":0,"start":0,"stop":170,"fx":0,"col":[[0,0,0],[0,0,0],[0,0,0]],"on":true}]}'
    echo "Topic:   $TOPIC"
    mosquitto_pub -h localhost -p 1883 -t "$TOPIC" -m "$PAYLOAD"
    echo "✓ Matrix cleared"
    ;;

  matrix-udp)
    # Send scrolling text to the matrix via UDP (bypasses MQTT).
    # Requires netcat (nc) on the server.
    # Usage: iot matrix-udp "YOUR TEXT"
    if [ -z "$2" ]; then
      echo "Usage: iot matrix-udp \"YOUR TEXT\""
      echo ""
      echo "Examples:"
      echo "  iot matrix-udp \"SOUND CHECK\""
      echo "  iot matrix-udp '{\"text\":\"GO\",\"color\":[0,255,0],\"speed\":200,\"ttl\":15}'"
      echo ""
      echo "Also works from any machine on the network:"
      echo "  echo \"DOORS OPEN\" | nc -u <server_ip> 7777"
      exit 1
    fi
    SERVER_IP=$(ip addr show eth0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
    SERVER_IP="${SERVER_IP:-127.0.0.1}"
    echo "Sending UDP to $SERVER_IP:7777"
    echo "$2" | nc -u -w1 "$SERVER_IP" 7777
    echo "✓ Sent"
    ;;

  web)      echo "Grafana:  http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):3000"
            echo "InfluxDB: http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):8086"
            echo "MQTT:     $(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):1883"
            echo "govee2mqtt: http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):8056"
            echo "Set-Schedule: http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):8000"
            echo "Button Health: http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):8080/health"
            ;;
  *)
    # Read version from VERSION file
    VERSION="$(cat "$REPO_ROOT/VERSION" 2>/dev/null || echo 'unknown')"
    echo ""
    echo "  iot - Govee IoT Stack Manager v$VERSION"
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
    echo "    lp [n]                 physical-control logs"
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
    echo "    nuke-geist             DELETE all Geist measurement data (fixes schema issues)"
    echo ""
    echo "  M4300 NETGEAR BACKUP"
    echo "    m4300-backup           Run M4300 config backup now (containerized)"
    echo "    m4300-backup-mock      Run backup in MOCK mode (no real switches)"
    echo "    m4300-logs [n]         View recent backup logs (default: 10)"
    echo "    m4300-log-view <file>  Display full backup log file"
    echo "    m4300-list [n]         List recent backups with config files (default: 10)"
    echo "    m4300-list-all         List all backup files across all dates"
    echo "    m4300-clean            Remove empty backup folders (failed attempts)"
    echo "    m4300-network-fix      Configure secondary IP for 192.168.0.x access"
    echo "    m4300-build            Rebuild netgear-backup container image"
    echo "    m4300-list-switches    Show parsed switch inventory from switches.conf"
    echo ""
    echo "  PHYSICAL CONTROL SERVICE (Phase 7+8)"
    echo "    physical-control-status (pc-status)  Check service health and stats"
    echo "    physical-control-logs (pc-logs)      View live logs"
    echo "    physical-control-test (pc-test)      Send test webhook"
    echo "    physical-control-config (pc-config)  Edit alert_actions.yaml"
    echo "    physical-control-restart (pc-restart) Restart service"
    echo "    physical-control-rebuild (pc-rebuild) Rebuild container image"
    echo ""
    echo "  PHYSICAL DEVICE CONTROL (Phase 7+8)"
    echo "    geist-relay <action>   Control Geist Watchdog relay"
    echo "                           actions: on, off, toggle"
    echo "    x410-relay <n> <action> Control X-410 relay (1-4)"
    echo "                           actions: on, off, toggle, pulse <seconds>"
    echo "                           examples: iot x410-relay 1 on"
    echo "                                     iot x410-relay 2 pulse 5"
    echo "    govee-control [options] Control Govee lights/plugs"
    echo "                           examples: iot govee-control --device stick --on"
    echo "                                     iot govee-control --device \"stick\" --brightness 75"
    echo "                                     iot govee-control --device strip --color red"
    echo "    list-devices           Show all controllable devices (Geist, X410, Govee)"
    echo "    list-govee-devices     Alias for list-devices"
    echo ""
    echo "  GUEST ALERT BUTTON SYSTEM (Phase 7+8)"
    echo "    button-rebuild (btn-rebuild) Rebuild container (no cache)"
    echo "    button-start (btn-start)     Start button controller service"
    echo "    button-stop (btn-stop)       Stop button controller service"
    echo "    button-restart (btn-restart) Restart button controller service"
    echo "    button-status (btn-status)   Check service health and lamp states"
    echo "    button-logs (btn-logs)       View live service logs"
    echo "    button-clear (btn-clear)     Clear all lamps (turn OFF)"
    echo "    button-reset <color>         Reset specific lamp"
    echo "      (btn-reset)                colors: red, yellow, green, blue"
    echo "                                 example: iot button-reset red"
    echo "    button-metrics (btn-metrics) Show Prometheus metrics"
    echo ""
    echo "  WLED BRIDGE (Sensor → Ropelight zone controller)"
    echo "    wled-up                Start wled-bridge service"
    echo "    wled-down              Stop wled-bridge service"
    echo "    wled-restart           Restart wled-bridge service"
    echo "    wled-rebuild           Rebuild image and restart"
    echo "    wled-logs [n]          View logs (default: 50 lines)"
    echo "    wled-follow            Stream logs in real-time"
    echo "    wled-shell             Open shell in container"
    echo "    wled-set <s> <e> <r> <g> <b>  Set pixels s through e-1 to RGB color"
    echo "                           stop is exclusive (WLED convention)"
    echo "                           examples: iot wled-set 75 100 255 0 0  (red)"
    echo "                                     iot wled-set 0 100 0 0 0    (blackout)"
    echo "    wled-off               Turn off all WLED pixels"
    echo ""
    echo "  WLED MATRIX (17×10 LED matrix — scrolling text display)"
    echo "    matrix-text <msg> [ttl]    Blast scrolling text. TTL in seconds (default: 30)"
    echo "                               examples: iot matrix-text \"DOORS OPEN\""
    echo "                                         iot matrix-text \"STAGE 1 NOW\" 60"
    echo "    matrix-text-json <json>    Full JSON payload blast"
    echo "                               examples: iot matrix-text-json '{\"text\":\"GO\",\"color\":[255,0,100],\"speed\":200,\"ttl\":10}'"
    echo "                               fields:   text (string), color ([R,G,B]), speed (0-255), ttl (seconds)"
    echo "    matrix-clear               Clear matrix immediately (solid black)"
    echo "    matrix-udp <msg>           Send text via UDP (no MQTT needed, port 7777)"
    echo "                               example:  iot matrix-udp \"SOUND CHECK\""
    echo "                               from net: echo \"TEXT\" | nc -u <server_ip> 7777"
    echo ""
    echo "  NTP TIME SERVER"
    echo "    ntp-start (ntp-up)     Start NTP server (accessible on all network interfaces)"
    echo "    ntp-stop (ntp-down)    Stop NTP server"
    echo "    ntp-restart            Restart NTP server"
    echo "    ntp-status             Show container status and time sync details"
    echo "    ntp-tracking           Show chrony tracking status (offset, stratum)"
    echo "    ntp-sources            Show configured time sources (NIST servers)"
    echo "    ntp-sourcestats        Show detailed source statistics"
    echo "    ntp-clients            Show recent NTP client activity"
    echo "    ntp-logs               View NTP server logs (add -f to follow)"
    echo "    ntp-rebuild            Rebuild NTP server container"
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
    echo "    delete-device-data     Delete InfluxDB data (interactive: old/current/all modes)"
    echo ""
    echo "  NETWORK"
    echo "    ip                     Show VM IP address"
    echo "    web                    Show all service URLs"
    echo "    tunnel                 Start Cloudflare tunnel to Grafana (background)"
    echo "    tunnel-grafana         Start tunnel to Grafana (port 3000)"
    echo "    tunnel-influxdb        Start tunnel to InfluxDB (port 8086)"
    echo "    tunnel-schedule        Start tunnel to set-schedule (port 8000)"
    echo "    tunnel-stop            Stop all running tunnels"
    echo "    tunnel-stop-<name>     Stop specific tunnel (grafana/influxdb/schedule)"
    echo "    tunnel-status          Show all tunnels with status and URLs"
    echo "    tunnel-logs [name] [n] View tunnel logs (default: all, 30 lines)"
    echo ""
    echo "  GRAFANA DASHBOARDS"
    echo "    backup-dashboards      Fetch all dashboards via API → ~/backups/grafana/dashboards/YYYY-MM-DD-HHMMSS/"
    echo "    provision-dashboard [file]  Convert backup to provisioning format (read-only, [P] prefix)"
    echo "                           No args = interactive picker (grouped by backup session) | With file = convert that file"
    echo "    restore-dashboard [file]  Restore backup as editable dashboard via API (new UID)"
    echo "                           No args = interactive picker | With file = restore that file"
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
    echo "    esp32-enable           Python decodes only - raw manufacturerdata, Govee sensors only"
    echo "    esp32-verbose          Same as enable but scans every 1s (debugging)"
    echo "    esp32-decode           ESP32 decodes everything - sees ALL BLE devices (RECOMMENDED)"
    echo "    esp32-decode-verbose   ESP32 decodes + 1s scanning - max visibility + speed"
    echo "    esp32-quiet            ESP32 decodes, no raw data, 5s scan interval (low traffic)"
    echo ""
    echo "  CREDENTIALS"
    echo "    Grafana:   admin / grafanapass123"
    echo "    InfluxDB:  admin / influxpass123  org=home  bucket=sensors"
    echo "    MQTT:      no auth"
    echo ""
    ;;
esac
