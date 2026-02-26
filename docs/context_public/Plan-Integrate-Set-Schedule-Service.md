# Set-Schedule Service Integration Guide

## Architecture Overview

The set-schedule service (festival schedule tracking app) is integrated into the DPX_SHOWSITE_OPS stack using a **dual-instance approach**:

| Instance | Location | Port | Management | Purpose |
|----------|----------|------|------------|---------|
| **Production** | `services/set-schedule` (submodule) | 8000 | docker-compose | Stable production service, pinned to specific commit |
| **Development** | `../COACHELLA_SET_SCHEDULE` (standalone folder) | 8001 | Direct docker commands | Active development workspace |

### Why Two Instances?

**During live shows**, you need the ability to develop features without touching production:
- Production instance runs stable code (never modified during shows)
- Dev instance allows rapid feature development and testing on port 8001
- If a feature is approved, promote it by updating the submodule pointer
- Provides safe rollback if something goes wrong

### Git Workflow Pattern

**IMPORTANT**: Never edit code directly in the submodule folder. The submodule is a "pointer" to a specific commit in the remote repository, not a development workspace.

```
Development Flow:
1. Edit in standalone folder (COACHELLA_SET_SCHEDULE)
2. Commit & push to dubpixel/coachella_set_schedule fork
3. Merge feature branch to main
4. Update submodule pointer in DPX_SHOWSITE_OPS to reference new commit
5. Rebuild production service

The submodule just points to a commit hash - it doesn't store code!
```

---

## Initial Setup (One-Time)

### Prerequisites
- Docker and docker-compose installed
- Git submodule initialized: `git submodule update --init --recursive`
- Standalone development folder exists as sibling to DPX_SHOWSITE_OPS

### 1. Verify Submodule

```bash
cd DPX_SHOWSITE_OPS
cat .gitmodules
# Should show: url = https://github.com/dubpixel/coachella_set_schedule.git
```

```bash
cd services/set-schedule
git status  # Should be on a commit (detached HEAD or main)
cd ../..
```

### 2. Configure Production Environment

The production service reads configuration from the stack's `.env` file.

**Edit** `DPX_SHOWSITE_OPS/.env` (copy from `.env.example` if needed):

```bash
cp .env.example .env  # If .env doesn't exist
nano .env
```

**Add set-schedule variables**:
```bash
# Set-Schedule Service Configuration
SCHEDULE_PORT=8000
STAGE_NAME="Main Stage"
USE_GOOGLE_SHEETS=false
TIMEZONE=America/Los_Angeles

# Optional: Google Sheets integration
# GOOGLE_SHEETS_ID=your-spreadsheet-id
# GOOGLE_SHEET_TAB=Schedule
# GOOGLE_SERVICE_ACCOUNT_FILE=/app/secret/set-schedule-service-account.json

# Optional: Art-Net DMX
# ARTNET_ENABLED=false
```

### 3. Configure Shared Secrets Folder

Google Sheets credentials (if used) are shared between production and dev via a centralized secret folder:

```bash
mkdir -p secret
# Place your service account JSON here:
# secret/set-schedule-service-account.json
# This folder is gitignored
```

### 4. Configure Development Instance

The standalone folder is your development workspace.

```bash
cd ../COACHELLA_SET_SCHEDULE
cp .env.example .env
nano .env
```

**Important**: Set `PORT=8001` for dev instance:
```bash
HOST=0.0.0.0
PORT=8001
STAGE_NAME="Dev Stage"
USE_GOOGLE_SHEETS=false
TIMEZONE=America/Los_Angeles
GOOGLE_SERVICE_ACCOUNT_FILE=/app/secret/set-schedule-service-account.json
```

### 5. Start Production Instance

```bash
cd DPX_SHOWSITE_OPS
./scripts/manage.sh schedule-rebuild
./scripts/manage.sh schedule-status
```

Access at: **http://localhost:8000**

### 6. Test Development Instance

```bash
./scripts/manage.sh schedule-dev-rebuild
```

Access at: **http://localhost:8001**

Both instances should run simultaneously without port conflicts.

---

## Daily Development Workflow

### Making Changes to the Application

**Always work in the standalone folder**, never in the submodule:

```bash
cd COACHELLA_SET_SCHEDULE

# Create a feature branch
git checkout -b feature/new-countdown-timer

# Make your changes
nano app/models.py

# Test locally in dev instance (port 8001)
cd ../DPX_SHOWSITE_OPS
./scripts/manage.sh schedule-dev-rebuild
./scripts/manage.sh schedule-dev-logs

# Verify at http://localhost:8001
```

### Committing and Merging Changes

```bash
cd COACHELLA_SET_SCHEDULE

# Commit your changes
git add .
git commit -m "Add new countdown timer feature"
git push origin feature/new-countdown-timer

# Merge to main (when ready)
git checkout main
git merge feature/new-countdown-timer
git push origin main
```

### Promoting Changes to Production

After merging to `main` in your standalone repo, update the production submodule pointer:

```bash
cd DPX_SHOWSITE_OPS/services/set-schedule

# Fetch latest from YOUR fork
git fetch origin
git checkout main
git pull origin main

# Go back to stack root
cd ../..

# Commit the new submodule pointer
git add services/set-schedule
git commit -m "Update set-schedule: Add countdown timer feature"
git push

# Rebuild production
./scripts/manage.sh schedule-rebuild
```

**What just happened?**
- The submodule pointer now references the latest commit hash from `dubpixel/coachella_set_schedule`
- Production rebuilds using that new commit
- Anyone cloning `DPX_SHOWSITE_OPS` will get that exact version

---

## Production Management Commands

All production commands use `docker-compose` and the `iot` wrapper script:

```bash
# Start production service
iot schedule-up

# Stop production service  
iot schedule-down

# Restart production
iot schedule-restart

# Check status
iot schedule-status

# View logs (last 30 lines)
iot schedule-logs

# View logs (last 100 lines)
iot schedule-logs 100

# Follow logs in real-time
iot schedule-follow

# Rebuild after updating submodule
iot schedule-rebuild

# Open shell in production container
iot schedule-shell
```

**Production URL**: `http://localhost:8000` (or `http://VM-IP:8000` from LAN)

---

## Development Instance Commands

Dev commands use direct Docker commands with the standalone folder:

```bash
# Build dev image
iot schedule-dev-build

# Start dev service (port 8001)
iot schedule-dev-up

# Stop dev service
iot schedule-dev-down

# Restart dev service
iot schedule-dev-restart

# View dev logs
iot schedule-dev-logs

# Follow dev logs
iot schedule-dev-follow

# Build and start in one command
iot schedule-dev-rebuild

# Open shell in dev container
iot schedule-dev-shell
```

**Dev URL**: `http://localhost:8001`

---

## Show-Time Emergency Development

**Scenario**: You need to add a feature urgently during a live show.

**Critical Rule**: Never touch production while the show is running!

### Emergency Workflow

1. **Develop in standalone folder**:
   ```bash
   cd COACHELLA_SET_SCHEDULE
   git checkout -b hotfix/urgent-fix
   # Make changes
   git add . && git commit -m "Emergency: Fix critical bug"
   ```

2. **Test in dev instance** (port 8001):
   ```bash
   cd ../DPX_SHOWSITE_OPS
   iot schedule-dev-rebuild
   # Test at http://localhost:8001 with operators
   ```

3. **If approved, hot-swap to production**:
   ```bash
   # Push changes
   cd ../COACHELLA_SET_SCHEDULE
   git push origin hotfix/urgent-fix
   git checkout main
   git merge hotfix/urgent-fix
   git push origin main
   
   # Update production submodule
   cd ../DPX_SHOWSITE_OPS
   iot schedule-down  # Stop prod briefly
   
   cd services/set-schedule
   git fetch origin && git checkout main && git pull origin main
   cd ../..
   
   git add services/set-schedule
   git commit -m "HOTFIX: Update set-schedule to fix urgent bug"
   
   iot schedule-rebuild  # Back online with fix
   ```

4. **Rollback if needed**:
   ```bash
   cd services/set-schedule
   git checkout <previous-commit-hash>
   cd ../..
   git add services/set-schedule
   git commit -m "Rollback set-schedule to stable version"
   iot schedule-rebuild
   ```

---

## Troubleshooting

### Port Conflicts

**Problem**: `Error: address already in use`

**Solution**: Check which instance is using the port:
```bash
lsof -i :8000  # Check port 8000
lsof -i :8001  # Check port 8001

# Stop conflicting instance
iot schedule-down         # Production
iot schedule-dev-down     # Dev
```

### Submodule Out of Sync

**Problem**: Submodule shows modified files or wrong commit

**Solution**:
```bash
cd DPX_SHOWSITE_OPS/services/set-schedule
git status
git reset --hard HEAD  # Discard any local changes
git checkout main
git pull origin main
cd ../..
git add services/set-schedule
```

### Google Sheets Authentication Fails

**Problem**: `Error: service account file not found`

**Solution**:
1. Verify file exists: `ls -la secret/set-schedule-service-account.json`
2. Check .env path matches volume mount: `/app/secret/...`
3. Verify volume mount in docker-compose.yml: `./secret:/app/secret:ro`

### Dev and Prod Running Different Code (Expected)

This is **normal behavior**! Production runs the commit referenced by the submodule, dev runs whatever's in your working directory.

**Check production version**:
```bash
cd services/set-schedule
git log -1  # Shows current commit
```

**Check dev version**:
```bash
cd $REPO_ROOT/../COACHELLA_SET_SCHEDULE
git log -1
```

### Container Won't Start

**Check logs**:
```bash
iot schedule-logs 100      # Production
iot schedule-dev-logs 100  # Dev
```

**Common issues**:
- Missing `.env` file
- Invalid environment variable syntax
- Port already in use
- Dockerfile syntax error (check after edits)

---

## Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULE_PORT` | 8000 | Production port (host) |
| `PORT` | 8000 | Container internal port |
| `HOST` | 0.0.0.0 | Bind address |
| `USE_GOOGLE_SHEETS` | false | Enable Google Sheets sync |
| `STAGE_NAME` | Main Stage | Display name for stage |
| `TIMEZONE` | America/Los_Angeles | Timezone for schedule |
| `GOOGLE_SHEETS_ID` | - | Spreadsheet ID from URL |
| `GOOGLE_SHEET_TAB` | Schedule | Tab/worksheet name |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | - | Path to service account JSON |
| `ARTNET_ENABLED` | false | Enable Art-Net DMX brightness control |
| `ARTNET_PORT` | 6454 | Art-Net UDP port |
| `ARTNET_UNIVERSE` | 0 | DMX universe number |

---

## File Paths Reference

| Path | Purpose |
|------|---------|
| `DPX_SHOWSITE_OPS/services/set-schedule/` | Production submodule (DO NOT EDIT) |
| `DPX_SHOWSITE_OPS/secret/` | Shared secrets folder (gitignored) |
| `DPX_SHOWSITE_OPS/.env` | Production environment config |
| `DPX_SHOWSITE_OPS/docker-compose.yml` | Stack definition with set-schedule service |
| `COACHELLA_SET_SCHEDULE/` | Development workspace (EDIT HERE) |
| `COACHELLA_SET_SCHEDULE/.env` | Dev environment config (PORT=8001) |

---

## Command Quick Reference

| Task | Command |
|------|---------|
| Start production | `iot schedule-up` |
| Stop production | `iot schedule-down` |
| Rebuild production | `iot schedule-rebuild` |
| View prod logs | `iot schedule-logs` |
| Start dev | `iot schedule-dev-up` |
| Stop dev | `iot schedule-dev-down` |
| Rebuild dev | `iot schedule-dev-rebuild` |
| View dev logs | `iot schedule-dev-logs` |
| Update submodule | `cd services/set-schedule && git pull` |
| Both instances status | `docker ps \| grep schedule` |

---

## Repository Links

- **Your fork (production source)**: https://github.com/dubpixel/coachella_set_schedule
- **Upstream (Sean's original)**: https://github.com/macswg/coachella_set_schedule

---

## Additional Notes

- ✅ Dockerfile has been updated to respect `PORT` environment variable
- ✅ Production uses docker-compose service `set-schedule`
- ✅ Dev uses standalone container `set-schedule-dev`
- ✅ Shared secrets via `./secret` volume mount
- ✅ Both instances can run simultaneously (ports 8000 and 8001)
- ✅ VS Code workspace shows both folders for easy access during shows
- ⚠️ Never commit secrets files (`.env`, service account JSON)
- ⚠️ Never develop in the submodule folder - always use standalone folder
- ⚠️ Submodule is a pointer to a commit, not a workspace
