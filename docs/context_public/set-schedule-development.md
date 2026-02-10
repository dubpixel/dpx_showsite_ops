# Set Schedule App - Development & Contribution Workflow

**For production integration** into dpx_showsite_ops stack:  
See [CONTEXT.md](CONTEXT.md#phase-6---set-schedule-integration)

---

## Repository Info
- **Upstream**: https://github.com/macswg/coachella_set_schedule (Sean's original)
- **Fork**: https://github.com/dubpixel/coachella_set_schedule

## Contribution History

### 1. First PR - Reset Endpoint (✅ MERGED by Sean)
**PR**: #2
**Branch**: `add-reset-endpoint`
Added `/api/reset` endpoint to clear all actual times programmatically.

### 2. Second PR - Reset Button (CLEAN, PENDING)
**Branch**: `add-reset-button-clean`
**Commit**: `648aec2`

**What We Did (Feb 7, 2026)**:
- ✅ Updated local `main` from Sean's upstream (he had merged more changes)
- ✅ Created NEW clean branch `add-reset-button-clean` from updated main
- ✅ Manually added ONLY the button changes (no accidental JS refactoring)
- ✅ Clean commit with proper message
- ✅ Pushed to fork and created PR

**Changes**:
- Added "Reset All Times" button to schedule header (edit mode only)
- Uses existing confirmation modal
- Styled as red warning button
- Button calls the `/api/reset` endpoint that's already merged

**Files Modified**:
- `templates/index.html` - Added button at lines 46-50
- `static/styles.css` - Added `.btn-reset-all` styling (RED button)

**Key Learning**: The old `add-reset-endpoint` branch had messy commits mixing endpoint + button + accidental JS changes. We created a fresh branch and cherry-picked only the button code to keep the PR clean.

## Local Deployment

**Location**: `~/coachella_set_schedule/`

### Docker Commands

**Initial Build & Run** (first time only):
```bash
cd ~/coachella_set_schedule

# Build image
docker build -t set-schedule:test .

# Create and start container
docker run -d \
  --name set-schedule-test \
  -p 8000:8000 \
  --env-file .env \
  set-schedule:test
  
```

**Regular Operations** (after container exists):
```bash
# Start the container (after reboot, etc)
docker start set-schedule-test

# Stop the container
docker stop set-schedule-test

# Restart the container
docker restart set-schedule-test

# Check status
docker ps              # Running containers only
docker ps -a           # All containers (running + stopped)

# View logs
docker logs set-schedule-test
docker logs -f set-schedule-test  # Follow logs
```

**Complete Rebuild** (when you need to recreate):
```bash
# Stop and remove old container
docker stop set-schedule-test
docker rm set-schedule-test

# Rebuild image (if code changed)
docker build -t set-schedule:test .

# Create new container
docker run -d \
  --name set-schedule-test \
  -p 8000:8000 \
  --env-file .env \
  set-schedule:test
```

**Access**:
- View: http://192.168.1.100:8000
- Edit: http://192.168.1.100:8000/edit

### Environment (`.env`)
```
USE_GOOGLE_SHEETS=false
STAGE_NAME=Main Stage
TIMEZONE=America/Los_Angeles
HOST=0.0.0.0
PORT=8000
ARTNET_ENABLED=false
```

## Remote Access

**Cloudflare Tunnel** (running in screen 36203):
```bash
# Tunnel for port 8000 is already running
screen -r 36203  # Attach to see both tunnels
# Ctrl+A, N to switch between windows
```

## Git Workflow

### Git Configuration
```bash
# Set vim as default editor
git config --global core.editor "vim"
```

### Remotes
```bash
origin    # Your fork (dubpixel/coachella_set_schedule)
upstream  # Sean's repo (macswg/coachella_set_schedule)
```

### Proper Workflow for New Features

**ALWAYS start fresh from Sean's latest code:**

```bash
# 1. Fetch Sean's latest changes
git fetch upstream

# 2. Update your local main
git checkout main
git pull upstream main

# 3. Push updated main to your fork
git push origin main

# 4. Create new feature branch from updated main
git checkout -b feature-name

# 5. Make changes, test locally

# 6. Commit with clear message
git add <files>
git commit -m "Clear description of changes"

# 7. Push to YOUR fork
git push origin feature-name

# 8. Create PR from your fork to Sean's repo
# Go to GitHub and create PR from dubpixel:feature-name to macswg:main
```


## Project Structure

**Key Files**:
- `main.py` - FastAPI backend, includes `/api/reset` endpoint
- `templates/index.html` - Main UI template
- `static/styles.css` - All CSS styling
- `Dockerfile` - Container configuration
- `.env` - Environment variables (not committed to git)

## Lessons Learned

1. **Always pull from upstream first** before creating a new branch
2. **One feature per branch** - keep commits clean and focused
3. **Docker lifecycle**: `run` creates, then just `start`/`stop` after that
4. **Git hygiene**: Don't mix multiple features in one commit
5. **Test locally** before pushing - use the Docker container to verify

## Next Session Checklist

- [ ] Check if Sean merged the button PR
- [ ] If making more changes, pull from upstream first!
- [ ] Document any new features discussed with Sean as GitHub issues
- [ ] Remember to rebuild Docker image after code changes
