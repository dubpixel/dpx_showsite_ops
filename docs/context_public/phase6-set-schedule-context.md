# Set Schedule App - Fork & Contributions Context

## Repository Info
- **Upstream**: https://github.com/macswg/coachella_set_schedule (Sean's original)
- **Fork**: https://github.com/dubpixel/coachella_set_schedule
- **Branch**: `add-reset-button-clean` (or `add-reset-endpoint` if still using that)

## What We Did

### 1. First PR - Reset Endpoint (MERGED by Sean)
Added `/api/reset` endpoint to clear all actual times programmatically.

### 2. Second PR - Reset Button (PENDING)
**Branch**: `add-reset-endpoint` (confusing name, but it's the button PR)
**Changes**:
- Added "Reset All Times" button to schedule header (edit mode only)
- Uses existing confirmation modal
- Styled as red warning button
- Button calls the `/api/reset` endpoint that's already merged

**Files Modified**:
- `templates/index.html` - Added button to schedule header
- `static/styles.css` - Added `.btn-reset-all` styling (RED button)

**PR Link**: https://github.com/macswg/coachella_set_schedule/compare/main...dubpixel:coachella_set_schedule:add-reset-endpoint

## Local Deployment

**Location**: `~/coachella_set_schedule/`

**Docker Setup**:
```bash
cd ~/coachella_set_schedule

# Build
docker build -t set-schedule:test .

# Run
docker run -d \
  --name set-schedule-test \
  -p 8000:8000 \
  --env-file .env \
  set-schedule:test

# Access
# View: http://192.168.1.100:8000
# Edit: http://192.168.1.100:8000/edit
```

**Environment** (`.env`):
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

## Git Workflow Notes

**Remotes**:
```bash
origin    # Your fork (dubpixel/coachella_set_schedule)
upstream  # Sean's repo (macswg/coachella_set_schedule)
```

**Proper workflow for next time**:
1. `git fetch upstream` - Get Sean's latest
2. `git checkout main && git pull upstream main` - Update your main
3. `git checkout -b new-feature` - Create branch from updated main
4. Make changes, commit, push to YOUR fork
5. Create PR from your fork to Sean's repo

## Current Issue
The `add-reset-endpoint` branch has commits for both the endpoint AND the button, but Sean already merged the endpoint. GitHub's PR will show only the NEW changes (button) when comparing against his main, so it should be fine. The commit history is messy but the PR diff will be clean.

## Files to Remember
- `templates/index.html` - Button is around line 46-49
- `static/styles.css` - Button styles at bottom (`.btn-reset-all`)
- `main.py` - Reset endpoint at bottom (if you need to reference it)

## Next Session
- Check if Sean merged the button PR
- If making more changes, pull from upstream first!
- Consider adding Google Sheets integration if needed
