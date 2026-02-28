## Plan: Integrate dpx-netgear-backup into DPX Stack (Full Phase 5)

Rolls the working netgear backup script into the DPX showsite stack as git submodule with full monitoring integration. Deploys TFTP server, fixes network connectivity (temporary lash-up until management VLAN), refactors script to use .env config pattern, adds `iot` CLI commands, sets up daily cron automation, enables M4300 SNMP monitoring, and writes backup metrics to InfluxDB with Grafana dashboard. All 5 sub-phases (5.1 → 5.5) completed in one integration.

**Steps**

**Phase 5.1: TFTP Server Deployment**
1. Add `tftpd-hpa` service to [docker-compose.yml](docker-compose.yml) following pattern from `mosquitto` service:
   - Base image: `pghalliday/tftp:latest` or similar lightweight TFTP server
   - Port mapping: `69:69/udp`
   - Named volume: `tftp-data:/var/tftpboot`
   - Restart policy: `unless-stopped`
   - Network: `iot` bridge
   - Container name: `tftp-server`

2. Create [.env.example](.env.example) entries (append at end, before M4300 section header):
   ```bash
   # Netgear M4300 Backup System (Phase 5)
   M4300_USERNAME=admin
   M4300_PASSWORD_M4300=password
   M4300_PASSWORD_OTHER=Password1!
   M4300_TFTP_SERVER=192.168.0.1  # VM IP on 192.168.0.x network
   M4300_BACKUP_RETENTION_DAYS=30
   M4300_SWITCHES=192.168.0.238:FOH:M4300,192.168.0.239:SR:other  # Format: IP:NAME:MODEL
   ```

**Phase 5.2: Git Submodule Integration**

3. Add dpx-netgear-backup as submodule to `services/`:
   ```bash
   cd DPX_SHOWSITE_OPS/
   git submodule add https://github.com/dubpixel/dpx-netgear-backup.git services/netgear-backup
   git submodule update --init --recursive
   ```

4. Update [setup.sh](setup.sh) after line containing `git submodule update`:
   - Add: `echo "Installing netgear-backup dependencies..."`
   - Add: `pip install -r services/netgear-backup/requirements.txt`

5. Create [services/netgear-backup/netgear_backup.py](services/netgear-backup/netgear_backup.py) — refactored version of `netgear_system_backup_TFTP-v0d1.py`:
   - Replace hardcoded `switches` list with `os.environ['M4300_SWITCHES'].split(',')` parsing
   - Replace hardcoded `username` with `os.environ['M4300_USERNAME']`
   - Replace hardcoded passwords with model-based lookup from `M4300_PASSWORD_M4300` and `M4300_PASSWORD_OTHER`
   - Replace hardcoded `tftp_server_ip` with `os.environ['M4300_TFTP_SERVER']`
   - Change backup path from `backups/` to `~/backups/netgear/{iso_timestamp}/`
   - Change log path from `logs/` to `~/backups/netgear/logs/backup_log_{iso_timestamp}.txt`
   - Add metrics publishing function `publish_backup_metrics()` (called after each switch backup)
   - Remove `USE_MOCK` toggle (keep mock functions but driven by CLI flag `--mock`)

6. Create [services/netgear-backup/metrics.py](services/netgear-backup/metrics.py):
   - Function: `publish_to_influxdb(switch_name, switch_ip, success, duration_seconds, error_msg="")`
   - Uses `influxdb_client` library (add to [services/netgear-backup/requirements.txt](services/netgear-backup/requirements.txt))
   - Writes to `netgear_backup` measurement with tags `{switch_name, switch_ip, result}` and fields `{success, duration_seconds}`
   - On failure, add field `error_msg`
   - Connection from env vars: InfluxDB at `http://influxdb:8086`, token `my-super-secret-token`, org `home`, bucket `sensors`

**Phase 5.3: Network Connectivity (Temporary Fix)**

7. Add secondary IP to VM's network interface for 192.168.0.x network access:
   - Create [scripts/setup-m4300-network.sh](scripts/setup-m4300-network.sh):
     ```bash
     #!/bin/bash
     # Temporary network fix for M4300 OOB access until management VLAN deployed
     # Adds secondary IP on 192.168.0.x network
     INTERFACE="${1:-eth0}"
     SECONDARY_IP="192.168.0.1/24"
     
     echo "Adding secondary IP $SECONDARY_IP to $INTERFACE..."
     sudo ip addr add $SECONDARY_IP dev $INTERFACE
     
     # Verify
     ip addr show $INTERFACE | grep 192.168.0.1
     echo "✓ M4300 network accessible. TEMPORARY until mgmt VLAN deployed."
     ```
   - Make executable: `chmod +x scripts/setup-m4300-network.sh`
   - Add to [docs/APPLICATION_SETUP_GUIDE_COMPLETE.md](docs/APPLICATION_SETUP_GUIDE_COMPLETE.md) as Phase 5 prerequisite (append new section before "Docker Setup")

8. Update [docker-compose.yml](docker-compose.yml) TFTP service environment:
   - Set TFTP listen IP to `192.168.0.1` (the secondary IP)
   - Add comment: `# Temporary IP until management VLAN deployed`

**Phase 5.4: M4300 SNMP Monitoring**

9. Create [telegraf/conf.d/m4300-switches.conf](telegraf/conf.d/m4300-switches.conf) following pattern from [telegraf/conf.d/geist-watchdog.conf](telegraf/conf.d/geist-watchdog.conf):
   - `[[inputs.snmp]]` with `agents = ["192.168.0.238:161", "192.168.0.239:161"]` (parsed from `M4300_SWITCHES` env var in future)
   - `community = "public"`, `version = 2`
   - Poll interval: `30s`
   - Measurements: `m4300_system` (sysUpTime, sysDescr), `m4300_interfaces` (ifTable), `m4300_temp` (temperature OIDs)
   - Standard IF-MIB OIDs for port stats: `1.3.6.1.2.1.2.2` (ifTable), `1.3.6.1.2.1.31.1.1` (ifXTable)
   - Netgear-specific temperature OID: `1.3.6.1.4.1.4526.10.43.1.8.1.3` (temp sensors)

10. Update [docker-compose.yml](docker-compose.yml) telegraf service `extra_hosts`:
    - Add: `- "dpx-m4300-foh:192.168.0.238"`
    - Add: `- "dpx-m4300-sr:192.168.0.239"`
    - Pattern matches existing `dpx-geist.local` entry

**Phase 5.5: Monitoring & Dashboard Integration**

11. Add to [services/netgear-backup/requirements.txt](services/netgear-backup/requirements.txt):
    ```
    influxdb-client>=1.38.0
    ```

12. Update [services/netgear-backup/netgear_backup.py](services/netgear-backup/netgear_backup.py) to call `metrics.publish_to_influxdb()`:
    - After successful SSH connection: `start_time = time.time()`
    - After backup complete: `duration = time.time() - start_time`
    - Call: `publish_to_influxdb(switch_name, switch_ip, success=True, duration_seconds=duration)`
    - On exception: `publish_to_influxdb(switch_name, switch_ip, success=False, duration_seconds=0, error_msg=str(e))`

13. Create [grafana/provisioning/dashboards/m4300-monitoring.json](grafana/provisioning/dashboards/m4300-monitoring.json):
    - Panel: "Backup Status Timeline" — stat panel showing last backup time per switch
    - Panel: "Backup Success Rate (7d)" — pie chart of success vs failure
    - Panel: "Config Backup History" — table with timestamp, switch, status, duration
    - Panel: "Switch Port Status" — heatmap from SNMP data (ifOperStatus)
    - Panel: "Switch Temperature" — time series graph from SNMP temp sensors
    - Panel: "Backup Duration Trends" — line graph of backup duration over time
    - Alert: "Backup Overdue" — trigger if last successful backup > 26 hours old

14. Create Grafana dashboard provisioning config [grafana/provisioning/dashboards/m4300.yaml](grafana/provisioning/dashboards/m4300.yaml):
    ```yaml
    apiVersion: 1
    providers:
      - name: 'M4300 Network'
        folder: 'Infrastructure'
        type: file
        options:
          path: /etc/grafana/provisioning/dashboards/m4300-monitoring.json
    ```

**iot CLI Commands**

15. Add to [scripts/manage.sh](scripts/manage.sh) after the `nuke-geist` case (around line 79), before `ip)` case:
    ```bash
    m4300-backup)
      echo "Running M4300 config backup..."
      cd "$REPO_ROOT" && source .env
      python3 services/netgear-backup/netgear_backup.py
      echo "✓ Backup complete. Files in ~/backups/netgear/"
      ;;
    m4300-backup-mock)
      echo "Running M4300 backup in MOCK mode (no real switches)..."
      cd "$REPO_ROOT" && source .env
      python3 services/netgear-backup/netgear_backup.py --mock
      ;;
    m4300-logs)
      ls -lt ~/backups/netgear/logs/ | head -${2:-10}
      echo ""
      read -p "View log file? Enter number or [Enter] to skip: " choice
      if [ -n "$choice" ]; then
        log_file=$(ls -t ~/backups/netgear/logs/ | sed -n "${choice}p")
        less ~/backups/netgear/logs/$log_file
      fi
      ;;
    m4300-list)
      echo "Recent M4300 backups:"
      ls -ltd ~/backups/netgear/202* 2>/dev/null | head -${2:-10}
      ;;
    m4300-cron-on)
      CRON_CMD="0 2 * * * $REPO_ROOT/scripts/m4300-backup-wrapper.sh"
      (crontab -l 2>/dev/null | grep -v m4300-backup; echo "$CRON_CMD") | crontab -
      echo "✓ M4300 backup cron enabled (daily at 2 AM)"
      ;;
    m4300-cron-off)
      crontab -l 2>/dev/null | grep -v m4300-backup | crontab -
      echo "✓ M4300 backup cron disabled"
      ;;
    m4300-network-fix)
      "$REPO_ROOT/scripts/setup-m4300-network.sh"
      ;;
    ```

16. Create [scripts/m4300-backup-wrapper.sh](scripts/m4300-backup-wrapper.sh):
    ```bash
    #!/bin/bash
    # Wrapper for cron execution with proper environment
    REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    cd "$REPO_ROOT" || exit 1
    source .env
    python3 services/netgear-backup/netgear_backup.py >> ~/backups/netgear/logs/cron_$(date +%Y%m%d).log 2>&1
    ```
    - Make executable: `chmod +x scripts/m4300-backup-wrapper.sh`

**Cleanup & Rotation**

17. Create [scripts/cleanup-m4300-backups.sh](scripts/cleanup-m4300-backups.sh):
    - Find backup folders in `~/backups/netgear/` older than `$M4300_BACKUP_RETENTION_DAYS` (default 30)
    - Delete old folders and log the cleanup
    - Add to cron as weekly job: `0 3 * * 0 $REPO_ROOT/scripts/cleanup-m4300-backups.sh`

**Documentation**

18. Update [docs/ROADMAP.md](docs/ROADMAP.md) Phase 5 status:
    - Change status from `🚧 In Progress` to `✅ Complete` for phases 5.1-5.5
    - Add "Completed: [date]" timestamp
    - Add note: "Network connectivity via secondary IP — temporary until management VLAN deployed"

19. Add to [README.md](README.md) after existing backup section:
    ```markdown
    ### Network Infrastructure Backups
    
    **M4300 Switch Backup:**
    - `iot m4300-backup` - Run backup now
    - `iot m4300-logs` - View recent logs
    - `iot m4300-list` - List backup history
    - `iot m4300-cron-on` - Enable daily 2 AM backups
    
    Configs saved to `~/backups/netgear/`, monitored via Grafana.
    ```

**Verification**

**Manual Testing:**
1. Run `iot m4300-network-fix` — verify secondary IP added: `ip addr show | grep 192.168.0.1`
2. Test TFTP server: `echo "test" | tftp 192.168.0.1 -c put /dev/stdin test.txt`, verify volume contains file
3. Run mock backup: `iot m4300-backup-mock` — should complete without errors, generate logs
4. Run real backup: `iot m4300-backup` — should connect to switches, save configs to `~/backups/netgear/`
5. Verify InfluxDB metrics: `iot query "from(bucket:\"sensors\") |> range(start: -1h) |> filter(fn: (r) => r._measurement == \"netgear_backup\")"`
6. Open Grafana dashboard at `http://localhost:3000/d/m4300-monitoring` — verify backup status panels populate
7. Check SNMP data: `iot query "from(bucket:\"sensors\") |> range(start: -5m) |> filter(fn: (r) => r._measurement == \"m4300_system\")"`
8. Enable cron: `iot m4300-cron-on`, verify: `crontab -l | grep m4300`

**Automated Testing (future):**
- Add pytest tests for `metrics.py` InfluxDB writes
- Add integration test for SSH mock mode

**Decisions**

- **Architecture:** Git submodule in `services/` but script runs on host (not containerized) for simpler debugging and filesystem access
- **Network fix:** Temporary secondary IP on VM until proper management VLAN deployed (noted as TODO in all docs)
- **TFTP deployment:** Docker container for portability, but could switch to host-based `apt install tftpd-hpa` if performance issues
- **Credentials:** Use .env pattern matching stack conventions rather than separate config file
- **Backup storage:** Host filesystem (`~/backups/netgear/`) for easy manual access, matches existing `iot backup` pattern
- **Metrics timing:** Write to InfluxDB immediately after each switch backup rather than batch at end for real-time dashboard updates
- **Monitoring integration:** Full Phase 5.5 included now (not deferred) since InfluxDB/Grafana already in place and metrics code is straightforward
