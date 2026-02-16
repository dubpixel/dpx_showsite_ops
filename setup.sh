#!/bin/bash
# ================================================================================
# SETUP SCRIPT - dpx-showsite-ops Initial Deployment
# ================================================================================
#
# This project includes AI-generated code assistance provided by GitHub Copilot,
# Claude Code, and other AI programming assistants.
# 
# Ground Rules for AI Assistance:
# - No modifications to working code without explicit request
# - Comprehensive commenting of all code (preserve existing, remove obsolete)
# - Small, incremental changes to maintain code stability
# - Verification before implementation of any suggestions
# - Stay focused on the current task
# - Answer only what is asked
# - All user prompts and AI solutions documented in change log
#
# ================================================================================
# PROJECT: dpx_showsite_ops
# ================================================================================
#
# File: setup.sh
# Purpose: First-time setup and installation script
# Dependencies: Docker, Docker Compose, git
#
# CHANGE LOG:
# 
# 2026-02-16: Initial creation
# → User prompt: Create missing setup.sh referenced in docs
# → Check Docker prerequisites
# → Auto-detect installation directory for iot wrapper
# → Copy .env.example to .env if needed
# → Prompt to edit .env (nano/vi)
# → Initialize git submodule services/set-schedule
# → Install iot wrapper to /usr/local/bin/iot
# → Optional cron job installation for device-map updates
# → Print next steps
#
# ================================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get absolute path to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=================================="
echo "dpx-showsite-ops Setup"
echo "=================================="
echo ""

# Check for Docker
echo -n "Checking Docker installation... "
if ! command -v docker &> /dev/null; then
    echo -e "${RED}FAILED${NC}"
    echo "Docker is not installed. Please install Docker first:"
    echo "  curl -fsSL https://get.docker.com -o get-docker.sh"
    echo "  sudo sh get-docker.sh"
    exit 1
fi
echo -e "${GREEN}OK${NC}"

# Check for Docker Compose
echo -n "Checking Docker Compose... "
if ! docker compose version &> /dev/null; then
    echo -e "${RED}FAILED${NC}"
    echo "Docker Compose is not available. Please install Docker Compose v2."
    exit 1
fi
echo -e "${GREEN}OK${NC}"

# Check if user is in docker group
echo -n "Checking docker group membership... "
if ! groups | grep -q docker; then
    echo -e "${YELLOW}WARNING${NC}"
    echo "You are not in the 'docker' group. You'll need sudo for docker commands."
    echo "To fix: sudo usermod -aG docker $USER"
    echo "Then log out and back in."
    echo ""
else
    echo -e "${GREEN}OK${NC}"
fi

# Create .env if it doesn't exist
echo -n "Checking .env file... "
if [ -f "$SCRIPT_DIR/.env" ]; then
    echo -e "${YELLOW}EXISTS${NC} (not overwriting)"
else
    if [ ! -f "$SCRIPT_DIR/.env.example" ]; then
        echo -e "${RED}ERROR${NC}"
        echo ".env.example not found. Cannot create .env"
        exit 1
    fi
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    echo -e "${GREEN}CREATED${NC}"
fi

# Prompt to edit .env
echo ""
echo "You need to configure Govee credentials in .env"
echo "Get your API key from: Govee Home app → My Account → Apply for API Key"
echo ""
read -p "Open .env for editing now? [Y/n] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    # Detect available editor (prefer vim)
    if command -v vim &> /dev/null; then
        vim "$SCRIPT_DIR/.env"
    elif command -v vi &> /dev/null; then
        vi "$SCRIPT_DIR/.env"
    else
        echo -e "${YELLOW}WARNING${NC}: No editor found (vim/vi)"
        echo "Edit .env manually before running 'iot up'"
    fi
fi

# Initialize git submodule if needed
echo ""
echo -n "Checking set-schedule submodule... "
if [ -f "$SCRIPT_DIR/services/set-schedule/main.py" ]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${YELLOW}INITIALIZING${NC}"
    git submodule init
    git submodule update
    if [ -f "$SCRIPT_DIR/services/set-schedule/main.py" ]; then
        echo -e "${GREEN}DONE${NC}"
    else
        echo -e "${YELLOW}WARNING${NC}: Submodule initialization may have failed"
        echo "Run manually: git submodule init && git submodule update"
    fi
fi

# Install iot wrapper
echo ""
echo -n "Installing 'iot' command... "
if [ -f "/usr/local/bin/iot" ]; then
    echo -e "${YELLOW}EXISTS${NC}"
    read -p "Overwrite existing iot command? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping iot installation"
        SKIP_IOT=true
    fi
fi

if [ "$SKIP_IOT" != "true" ]; then
    sudo tee /usr/local/bin/iot > /dev/null << WRAPPER
#!/bin/bash
cd $SCRIPT_DIR
exec $SCRIPT_DIR/scripts/manage.sh "\$@"
WRAPPER
    sudo chmod +x /usr/local/bin/iot
    echo -e "${GREEN}INSTALLED${NC}"
    
    # Test it
    if iot help &> /dev/null; then
        echo "  Test passed: 'iot help' works"
    else
        echo -e "${YELLOW}WARNING${NC}: 'iot help' test failed"
    fi
fi

# Offer cron job installation
echo ""
echo "Device mapping updates can run automatically every hour via cron."
echo "This keeps device names and rooms synchronized from Govee API."
read -p "Enable hourly device-map updates? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    CRON_CMD="0 * * * * $SCRIPT_DIR/scripts/update-device-map.sh"
    # Check if already installed
    if crontab -l 2>/dev/null | grep -q "update-device-map.sh"; then
        echo -e "${YELLOW}Cron job already exists${NC}"
    else
        (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
        echo -e "${GREEN}Cron job installed${NC}"
        echo "To disable later: iot cron-off"
    fi
else
    echo "Skipped. You can enable later with: iot cron-on"
fi

# Success message
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo ""
echo "1. Verify .env has your Govee credentials:"
echo "   nano $SCRIPT_DIR/.env"
echo ""
echo "2. Start the stack:"
echo "   iot up"
echo ""
echo "3. Wait 30 seconds, then update device mappings:"
echo "   iot update"
echo ""
echo "4. Check that services are running:"
echo "   iot status"
echo ""
echo "5. Access Grafana in your browser:"
echo "   http://$(hostname -I | awk '{print $1}'):3000"
echo "   Username: admin"
echo "   Password: (see .env file)"
echo ""
echo "For help: iot help"
echo ""
echo "Installation directory: $SCRIPT_DIR"
echo ""
