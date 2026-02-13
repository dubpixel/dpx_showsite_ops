# Plan: Integrate Set-Schedule Service into DPX_SHOWSITE_OPS Stack

## Current State
- ✅ Submodule added at `services/set-schedule` pointing to dubpixel/coachella_set_schedule fork
- ✅ Submodule committed
- ❌ **BLOCKER**: Dockerfile hardcodes port 8000, ignoring PORT env var
- ❌ Not yet in docker-compose.yml
- ❌ manage.sh still has old standalone docker commands

## Configuration Decision
- **Production (stack)**: Port 8000 - use YOUR fork (`dubpixel/coachella_set_schedule`)
- **Dev instance** (`~/coachella_set_schedule`): Port 8001 for testing/development
- Can swap submodule to Sean's repo later when ready

## Critical Issue: Dockerfile Port Hardcoding

The Dockerfile currently hardcodes `--port 8000`:
```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

This prevents running two instances simultaneously because:
- The app's config.py correctly reads `PORT` env var ✅
- But the Dockerfile CMD ignores it and always uses 8000 ❌
- Port mapping `8001:8001` won't work if the app only listens on 8000 internally

**Must fix FIRST** before dual instances can work.

## Steps to Complete

### 1. Fix Dockerfile PORT handling (CRITICAL - DO FIRST)

**In BOTH repositories:**
- `~/coachella_set_schedule/Dockerfile` (dev instance)
- `services/set-schedule/Dockerfile` (production submodule)

Change the CMD line from:
```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

To:
```dockerfile
CMD ["sh", "-c", "uvicorn main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
```

This allows the container to respect the PORT environment variable while defaulting to 8000.

**Commit to your fork:**
```bash
cd ~/coachella_set_schedule
# Edit Dockerfile
git add Dockerfile
git commit -m "Fix Dockerfile to respect PORT env var for multi-instance support"
git push origin main
```

**Update submodule:**
```bash
cd ~/dpx_govee_stack/services/set-schedule
git pull origin main
cd ../..
git add services/set-schedule
git commit -m "Update set-schedule: Dockerfile now respects PORT env var"
```

### 2. Add to docker-compose.yml
Add after telegraf service, before networks section:

```yaml
  set-schedule:
    build:
      context: ./services/set-schedule
      dockerfile: Dockerfile
    container_name: set-schedule
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - USE_GOOGLE_SHEETS=false
      - STAGE_NAME=Main Stage
      - TIMEZONE=America/Los_Angeles
      - HOST=0.0.0.0
      - PORT=8000
      - ARTNET_ENABLED=false
    networks:
      - iot
```

**Note:** Add `.env` or `env_file` directive if you need Google Sheets credentials.

### 3. Update manage.sh
Replace all `schedule-*` commands with docker-compose versions:

```bash
  schedule-up)
    echo "Starting set-schedule service..."
    docker compose up -d set-schedule
    echo "✓ set-schedule service started"
    echo "Access at: http://localhost:8000"
    ;;
  
  schedule-down)
    echo "Stopping set-schedule service..."
    docker compose stop set-schedule
    echo "✓ set-schedule service stopped"
    ;;
  
  schedule-restart)
    echo "Restarting set-schedule service..."
    docker compose restart set-schedule
    echo "✓ set-schedule service restarted"
    ;;
  
  schedule-status)
    echo "Set-Schedule Service Status:"
    echo "================================"
    docker compose ps set-schedule
    ;;
  
  schedule-logs)
    docker compose logs set-schedule --tail=${2:-30}
    ;;
  
  schedule-follow)
    echo "Following set-schedule logs (Ctrl+C to exit)..."
    docker compose logs -f set-schedule
    ;;
  
  schedule-build | schedule-rebuild)
    echo "Building and starting set-schedule service..."
    docker compose up -d --build set-schedule
    echo "✓ set-schedule built and running"
    ;;
  
  schedule-update)
    echo "Updating from upstream repo..."
    git submodule update --remote services/set-schedule
    echo "Rebuilding with latest code..."
    docker compose up -d --build set-schedule
    echo "✓ Updated to latest and rebuilt"
    ;;
  
  schedule-shell)
    echo "Opening shell in set-schedule container..."
    docker compose exec set-schedule /bin/sh
    ;;
```

### 4. Update web command in manage.sh
Add set-schedule URL to the output:

```bash
  web)      echo "Grafana:  http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):3000"
            echo "InfluxDB: http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):8086"
            echo "MQTT:     $(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):1883"
            echo "govee2mqtt: http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):8056"
            echo "Set-Schedule: http://$(ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d/ -f1):8000"
            ;;
```

### 5. Update help text in manage.sh
Update the schedule section to reflect docker-compose commands:

```bash
  SET-SCHEDULE SERVICE (Production Instance via docker-compose)
    schedule-up            Start set-schedule service
    schedule-down          Stop set-schedule service
    schedule-restart       Restart set-schedule service
    schedule-status        Show set-schedule container status
    schedule-logs [n]      View logs (default: 30 lines)
    schedule-follow        Follow logs in real-time
    schedule-build         Build and start from submodule
    schedule-rebuild       Rebuild and restart (alias for schedule-build)
    schedule-update        Update submodule from upstream and rebuild
    schedule-shell         Open shell in container
```

### 6. Configure dev instance to use port 8001
Edit `~/coachella_set_schedule/.env`:
```bash
PORT=8001
STAGE_NAME=Test Stage
USE_GOOGLE_SHEETS=false
```

**Run dev instance:**
```bash
cd ~/coachella_set_schedule
docker build -t set-schedule:dev .
docker run -d \
  --name set-schedule-dev \
  -p 8001:8001 \
  --env-file .env \
  set-schedule:dev
```

### 7. Deploy production instance
```bash
cd ~/dpx_govee_stack
git pull
git submodule update --init --recursive
docker compose up -d --build set-schedule
```

### 8. Verify both instances running
```bash
# Check production (port 8000)
curl http://localhost:8000
docker compose ps set-schedule

# Check dev (port 8001)
curl http://localhost:8001
docker ps --filter "name=set-schedule-dev"
```

### 9. Clean up old standalone container (if exists)
```bash
docker stop set-schedule-test 2>/dev/null
docker rm set-schedule-test 2>/dev/null
```

## Future: Switch to Sean's Repo
When ready to use Sean's upstream instead of your fork:

```bash
cd services/set-schedule
git remote set-url origin https://github.com/macswg/coachella_set_schedule.git
git fetch origin
git checkout main
git pull
cd ../..
git add services/set-schedule
git commit -m "Switch set-schedule submodule to upstream (macswg)"
docker compose up -d --build set-schedule
```

## Notes
- **Critical:** Dockerfile PORT fix is mandatory before dual instances work
- Production uses port 8000 (standard)
- Dev uses port 8001 (requires Dockerfile fix to respect PORT env var)
- Submodule already points to dubpixel fork (set up correctly)
- Using your fork gives you control over what's deployed
- Easy to switch to Sean's repo when ready
- `schedule-update` command pulls latest from whichever repo the submodule points to
- Both instances can run simultaneously after Dockerfile fix
- Production managed via `iot schedule-*` commands
- Dev managed via direct `docker` commands
