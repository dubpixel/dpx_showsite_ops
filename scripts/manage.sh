#!/bin/bash
# dpx-showsite-ops management CLI

# Determine stack directory dynamically
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1


case "$1" in
  up)       docker compose up -d ;;
  down)     docker compose down ;;
  restart)  docker compose restart ${2:-} ;;
  status)   docker compose ps ;;
  fixnet)   sudo systemctl restart network-route-fix.service ;;
  ble-decode) source ../.env && python3 ble_decoder.py ;;
  lg)       docker logs govee2mqtt 2>&1 | tail -${2:-30} ;;
  lt)       docker logs telegraf 2>&1 | tail -${2:-30} ;;
  lm)       docker logs mosquitto 2>&1 | tail -${2:-30} ;;
  li)       docker logs influxdb 2>&1 | tail -${2:-30} ;;
  lf)       docker logs grafana 2>&1 | tail -${2:-30} ;;
  la)       for c in govee2mqtt telegraf mosquitto influxdb grafana; do echo "=== $c ===" && docker logs $c 2>&1 | tail -${2:-10} && echo; done ;;
  query)    docker exec influxdb influx query --org home --token my-super-secret-token "from(bucket:\"sensors\") |> range(start: -${2:-30m}) |> limit(n:${3:-5})" ;;
  query-tags) docker exec influxdb influx query --org home --token my-super-secret-token "from(bucket:\"sensors\") |> range(start: -${2:-5m}) |> limit(n:${3:-20}) |> pivot(rowKey:[\"_time\"], columnKey: [\"_field\"], valueColumn: \"_value\") |> keep(columns: [\"_time\", \"device_name\", \"room\", \"source\", \"source_node\", \"sensor_type\", \"z_device_id\", \"_value\"])" ;;
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
  tunnel)   cloudflared tunnel --url http://localhost:8080 ;;
  tunnel-grafana)   cloudflared tunnel --url http://localhost:3000 ;;
  tunnel-influxdb)   cloudflared tunnel --url http://localhost:8086 ;;
  tunnel-schedule)   cloudflared tunnel --url http://localhost:8000 ;;
  update)   ~/dpx_govee_stack/scripts/update-device-map.sh ;;
  cron-on)  (crontab -l 2>/dev/null | grep -v update-device-map; echo "0 * * * * $HOME/dpx_govee_stack/scripts/update-device-map.sh") | crontab - && echo "Cron enabled (hourly)" ;;
  cron-off) crontab -l 2>/dev/null | grep -v update-device-map | crontab - && echo "Cron disabled" ;;
  env)      cat ~/dpx_govee_stack/.env ;;
  conf)     cat ~/dpx_govee_stack/telegraf/telegraf.conf ;;
  edit)     vim ~/dpx_govee_stack/${2:-.env} ;;
  esp32-enable)
    echo "Enabling ESP32 external decoder mode..."
    mosquitto_pub -h localhost \
      -t "demo_showsite/dpx_ops_1/commands/MQTTtoBT/config" \
      -m '{"pubadvdata":true,"extDecoderEnable":true}'
    echo "✓ ESP32 configured: pubadvdata=true, extDecoderEnable=true"
    ;;

  web)      echo "Grafana:  http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):3000"
            echo "InfluxDB: http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):8086"
            echo "MQTT:     $(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):1883"
            echo "govee2mqtt: http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):8056"
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
    echo "                           services: govee2mqtt telegraf mosquitto influxdb grafana"
    echo "    status                 Show running containers"
    echo ""
    echo "  LOGS                     All take optional line count (default 30)"
    echo "    lg [n]                 govee2mqtt logs"
    echo "    lt [n]                 telegraf logs"
    echo "    lm [n]                 mosquitto (MQTT broker) logs"
    echo "    li [n]                 influxdb logs"
    echo "    lf [n]                 grafana logs"
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
    echo ""
    echo "  NETWORK"
    echo "    ip                     Show VM IP address"
    echo "    web                    Show all service URLs"
    echo "    tunnel                 Start Cloudflare tunnel to Grafana"
    echo ""
    echo "  MAINTENANCE"
    echo "    backup                 Backup Grafana + InfluxDB volumes to ~/backups/"
    echo ""
    echo "  CREDENTIALS"
    echo "    Grafana:   admin / grafanapass123"
    echo "    InfluxDB:  admin / influxpass123  org=home  bucket=sensors"
    echo "    MQTT:      no auth"
    echo ""
    ;;
esac
