#!/bin/bash
# ================================================================================
# INTERACTIVE SETUP WIZARD - dpx-showsite-ops Initial Deployment
# ================================================================================
#
# ================================================================================
# PROJECT: dpx_showsite_ops
# ================================================================================
#
# File: setup.sh
# Purpose: Interactive first-time setup wizard
# Dependencies: bash 4.0+, curl, git
#
# CHANGE LOG:
# 
# 2026-03-06: Complete rewrite - Interactive wizard (v2.1.0)
# → User goal: "hit a few buttons and boom it goes"
# → No more vim/vi required - fully interactive prompts
# → Email and API key validation
# → Timezone auto-detection with override
# → Docker auto-install if missing
# → System optimization prompts (IPv6, avahi, Tailscale)
# → Colored progress indicators and step-by-step wizard
# → Hidden password input for security
# → Auto-deploy stack after configuration
#
# ================================================================================

set -e  # Exit on error

# ================================================================================
# COLOR CONSTANTS
# ================================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ================================================================================
# HELPER FUNCTIONS
# ================================================================================

print_header() {
    echo ""
    echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║${NC}  $1${NC}"
    echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo ""
}

print_step() {
    echo -e "${BOLD}${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC}  $1"
}

print_info() {
    echo -e "${CYAN}ℹ${NC}  $1"
}

# ================================================================================
# VALIDATION FUNCTIONS
# ================================================================================

validate_email() {
    local email="$1"
    # Basic email regex validation
    if [[ "$email" =~ ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$ ]]; then
        return 0
    else
        return 1
    fi
}

validate_api_key() {
    local key="$1"
    # Govee API keys are typically 32+ characters
    if [ ${#key} -ge 20 ]; then
        return 0
    else
        return 1
    fi
}

# ================================================================================
# SYSTEM CHECK FUNCTIONS
# ================================================================================

check_docker() {
    if command -v docker &> /dev/null && docker compose version &> /dev/null; then
        return 0
    else
        return 1
    fi
}

check_docker_group() {
    if groups | grep -q docker; then
        return 0
    else
        return 1
    fi
}

auto_install_docker() {
    print_step "Installing Docker..."
    
    if curl -fsSL https://get.docker.com -o /tmp/get-docker.sh; then
        if sudo sh /tmp/get-docker.sh; then
            rm -f /tmp/get-docker.sh
            print_success "Docker installed successfully"
            
            # Add current user to docker group
            sudo usermod -aG docker "$USER"
            print_info "Added $USER to docker group (requires logout to take effect)"
            
            return 0
        fi
    fi
    
    rm -f /tmp/get-docker.sh
    print_error "Docker installation failed"
    return 1
}

# ================================================================================
# CONFIGURATION WIZARD
# ================================================================================

configure_env_interactive() {
    local env_file="$1"
    
    print_header "STEP 3 of 7: Configure Govee Credentials"
    
    print_info "Get your API key from: Govee Home app → Account → Apply for API Key"
    print_info "This usually takes 1-2 business days to approve"
    echo ""
    
    # Email
    while true; do
        read -p "Govee account email: " GOVEE_EMAIL
        if validate_email "$GOVEE_EMAIL"; then
            print_success "Valid email format"
            break
        else
            print_error "Invalid email format. Please try again."
        fi
    done
    
    # Password (hidden input)
    while true; do
        read -s -p "Govee account password (hidden): " GOVEE_PASSWORD
        echo ""
        if [ -n "$GOVEE_PASSWORD" ]; then
            print_success "Password received"
            break
        else
            print_error "Password cannot be empty"
        fi
    done
    
    # API Key
    while true; do
        read -p "Govee API key: " GOVEE_API_KEY
        if validate_api_key "$GOVEE_API_KEY"; then
            print_success "API key format looks good"
            break
        else
            print_error "API key seems too short (should be 20+ characters)"
            read -p "Use it anyway? [y/N] " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                break
            fi
        fi
    done
    
    # Timezone detection
    print_header "STEP 4 of 7: Configure Timezone & Display"
    
    DETECTED_TZ=$(timedatectl show --property=Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null || echo "America/New_York")
    print_info "Detected timezone: $DETECTED_TZ"
    read -p "Use this timezone? [Y/n] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        read -p "Enter timezone (e.g., America/Los_Angeles): " TZ
    else
        TZ="$DETECTED_TZ"
    fi
    print_success "Timezone: $TZ"
    
    # Showsite name
    HOSTNAME=$(hostname)
    print_info "This identifier will be used in MQTT topics and metrics"
    read -p "Showsite name [$HOSTNAME]: " SHOWSITE_NAME
    SHOWSITE_NAME="${SHOWSITE_NAME:-$HOSTNAME}"
    print_success "Showsite: $SHOWSITE_NAME"
    
    # Temperature scale
    read -p "Temperature scale - [F]ahrenheit or [C]elsius? [F/c] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Cc]$ ]]; then
        TEMP_SCALE="C"
    else
        TEMP_SCALE="F"
    fi
    print_success "Temperature scale: $TEMP_SCALE"
    
    # Grafana password
    print_header "STEP 5 of 7: Configure Grafana Dashboard"
    
    read -s -p "Set Grafana admin password (hidden): " GRAFANA_PASSWORD
    echo ""
    if [ -z "$GRAFANA_PASSWORD" ]; then
        GRAFANA_PASSWORD="grafanapass123"
        print_warning "Using default password: grafanapass123"
    else
        print_success "Custom password set"
    fi
    
    # Write .env file
    print_step "Writing configuration to .env file..."
    
    cat > "$env_file" << EOF
# Govee Cloud API Credentials
# Get API key from: https://developer.govee.com
GOVEE_API_KEY='$GOVEE_API_KEY'
GOVEE_EMAIL='$GOVEE_EMAIL'
GOVEE_PASSWORD='$GOVEE_PASSWORD'

# MQTT Broker Connection
# Leave these as localhost/127.0.0.1 unless using external MQTT broker
GOVEE_MQTT_HOST=127.0.0.1
GOVEE_MQTT_PORT=1883

# Timezone
TZ=$TZ

# Logging Level
# Options: error, warn, info, debug, trace
RUST_LOG=govee=info

# Temperature Display Units
# Options: F (Fahrenheit) or C (Celsius)
GOVEE_TEMPERATURE_SCALE=$TEMP_SCALE

# BLE Decoder Configuration
# Site identifier for MQTT topic structure
SHOWSITE_NAME=$SHOWSITE_NAME

# Set-Schedule Service Configuration
# Port for the schedule web interface (production instance)
SCHEDULE_PORT=8000

# Stage/Festival Configuration
STAGE_NAME="Main Stage"
TIMEZONE=$TZ

# Google Sheets Integration (optional)
# Set to 'true' to enable real-time schedule sync from Google Sheets
USE_GOOGLE_SHEETS=false
GOOGLE_SHEETS_ID=your-google-sheet-id-here
GOOGLE_SHEET_TAB=Schedule

# Path to Google service account JSON file (inside container)
# Place actual file in: secret/set-schedule-service-account.json
GOOGLE_SERVICE_ACCOUNT_FILE=/app/secret/set-schedule-service-account.json

# Art-Net DMX Integration (optional)
# Set to 'true' to enable brightness control via Art-Net
ARTNET_ENABLED=false
ARTNET_LISTEN_IP=0.0.0.0
ARTNET_PORT=6454
ARTNET_UNIVERSE=0
ARTNET_CHANNEL_START=1
ARTNET_CHANNEL_COUNT=3

# Grafana Dashboard Backup Configuration
# Used by backup-grafana-dashboards.py for automated backups
GRAFANA_URL=http://localhost:3000
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=$GRAFANA_PASSWORD

# Geist Watchdog Environmental Monitor (optional)
# SNMP-based temperature/humidity monitoring
# IP address is configured in telegraf/conf.d/geist-watchdog.conf
GEIST_IP=10.0.10.162

# Netgear M4300 Backup System (Phase 5)
# Automated config backup for network switches via TFTP
M4300_USERNAME=admin
M4300_PASSWORD_M4300=password
M4300_PASSWORD_OTHER=Password1!
# IMPORTANT: TFTP server uses host networking mode
# Set this to your host machine's IP address on the same network as your switches
M4300_TFTP_SERVER=192.168.1.100  # Change to your host LAN IP
M4300_BACKUP_RETENTION_DAYS=30

# InfluxDB Connection (for metrics and monitoring)
# Used by netgear-backup service to publish backup metrics
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_TOKEN=my-super-secret-token
INFLUXDB_ORG=home
INFLUXDB_BUCKET=sensors
EOF
    
    print_success "Configuration saved to $env_file"
}

# ================================================================================
# SYSTEM OPTIMIZATION
# ================================================================================

offer_system_optimizations() {
    print_header "STEP 6 of 7: System Optimizations (Optional)"
    
    print_info "The following optimizations improve reliability and functionality"
    echo ""
    
    # IPv6 disable (fixes govee2mqtt connectivity)
    print_step "Option 1: Disable IPv6"
    print_info "Govee2mqtt works better with IPv6 disabled on some systems"
    read -p "Disable IPv6 now? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null 2>&1; then
            sudo sysctl -w net.ipv6.conf.default.disable_ipv6=1 >/dev/null 2>&1
            # Make it persistent
            echo "net.ipv6.conf.all.disable_ipv6 = 1" | sudo tee -a /etc/sysctl.conf >/dev/null
            echo "net.ipv6.conf.default.disable_ipv6 = 1" | sudo tee -a /etc/sysctl.conf >/dev/null
            print_success "IPv6 disabled"
        else
            print_error "Failed to disable IPv6"
        fi
    else
        print_info "Skipped"
    fi
    echo ""
    
    # Avahi daemon (.local hostnames)
    print_step "Option 2: Install avahi-daemon"
    print_info "Enables .local hostname resolution (e.g., http://yourhostname.local:3000)"
    if command -v avahi-daemon &> /dev/null; then
        print_success "Already installed"
    else
        read -p "Install avahi-daemon? [y/N] " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if sudo apt update >/dev/null 2>&1 && sudo apt install -y avahi-daemon >/dev/null 2>&1; then
                sudo systemctl enable avahi-daemon >/dev/null 2>&1
                sudo systemctl start avahi-daemon >/dev/null 2>&1
                print_success "avahi-daemon installed and started"
            else
                print_error "Failed to install avahi-daemon"
            fi
        else
            print_info "Skipped"
        fi
    fi
    echo ""
    
    # Tailscale VPN
    print_step "Option 3: Install Tailscale VPN"
    print_info "Enables secure remote access to your stack from anywhere"
    if command -v tailscale &> /dev/null; then
        print_success "Already installed"
    else
        read -p "Install Tailscale? [y/N] " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if curl -fsSL https://tailscale.com/install.sh | sh; then
                print_success "Tailscale installed"
                print_info "Run 'sudo tailscale up' to connect to your network"
            else
                print_error "Failed to install Tailscale"
            fi
        else
            print_info "Skipped"
        fi
    fi
    echo ""
    
    # Cloudflared tunnel
    print_step "Option 4: Install cloudflared"
    print_info "Enables 'iot tunnel' commands for temporary public URLs"
    if command -v cloudflared &> /dev/null; then
        print_success "Already installed"
    else
        read -p "Install cloudflared? [y/N] " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            CLOUDFLARED_URL="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb"
            TEMP_DEB="/tmp/cloudflared-$$.deb"
            
            if curl -L --silent --show-error --fail "$CLOUDFLARED_URL" -o "$TEMP_DEB"; then
                if sudo dpkg -i "$TEMP_DEB" &>/dev/null; then
                    rm -f "$TEMP_DEB"
                    print_success "cloudflared installed"
                else
                    rm -f "$TEMP_DEB"
                    print_error "Failed to install cloudflared"
                fi
            else
                rm -f "$TEMP_DEB"
                print_error "Failed to download cloudflared"
            fi
        else
            print_info "Skipped"
        fi
    fi
}

# ================================================================================
# DEPENDENCY INSTALLATION
# ================================================================================

install_dependencies() {
    print_header "STEP 7 of 7: Install Additional Dependencies"
    
    # Python3 and paho-mqtt (for manual BLE decoder mode)
    print_step "Installing Python dependencies..."
    if ! command -v python3 &> /dev/null; then
        print_warning "Python3 not found. Install with: sudo apt install python3"
    else
        print_success "Python3 found"
        
        # Install paho-mqtt
        if command -v apt &> /dev/null; then
            if dpkg -l python3-paho-mqtt 2>/dev/null | grep -q ^ii; then
                print_success "python3-paho-mqtt already installed"
            else
                if sudo apt install -y python3-paho-mqtt &>/dev/null; then
                    print_success "python3-paho-mqtt installed"
                else
                    print_warning "Failed to install python3-paho-mqtt"
                fi
            fi
        fi
    fi
    
    # Git submodule (set-schedule)
    print_step "Initializing set-schedule submodule..."
    if [ -f "$SCRIPT_DIR/services/set-schedule/main.py" ]; then
        print_success "Submodule already initialized"
    else
        if git submodule init && git submodule update; then
            print_success "Submodule initialized"
        else
            print_warning "Submodule initialization may have failed"
        fi
    fi
    
    # Netgear-backup dependencies
    if [ -f "$SCRIPT_DIR/services/netgear-backup/requirements.txt" ]; then
        print_step "Installing netgear-backup dependencies..."
        if pip3 install -q -r "$SCRIPT_DIR/services/netgear-backup/requirements.txt" 2>/dev/null; then
            print_success "Dependencies installed"
        else
            print_warning "Some dependencies may have failed"
        fi
    fi
    
    # Install iot wrapper
    print_step "Installing 'iot' command..."
    if [ -f "/usr/local/bin/iot" ]; then
        read -p "'iot' command already exists. Overwrite? [Y/n] " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            print_info "Skipped iot installation"
            return
        fi
    fi
    
    sudo tee /usr/local/bin/iot > /dev/null << WRAPPER
#!/bin/bash
cd $SCRIPT_DIR
exec $SCRIPT_DIR/scripts/manage.sh "\$@"
WRAPPER
    sudo chmod +x /usr/local/bin/iot
    
    if iot help &> /dev/null; then
        print_success "'iot' command installed successfully"
    else
        print_warning "'iot' command installed but test failed"
    fi
    
    # Offer cron job
    echo ""
    print_step "Device mapping updates (optional)"
    print_info "Automatically sync device names/rooms from Govee API every hour"
    read -p "Enable hourly device-map updates via cron? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        CRON_CMD="0 * * * * $SCRIPT_DIR/scripts/update-device-map.sh"
        if crontab -l 2>/dev/null | grep -q "update-device-map.sh"; then
            print_success "Cron job already exists"
        else
            (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
            print_success "Cron job installed (disable with: iot cron-off)"
        fi
    else
        print_info "Skipped (enable later with: iot cron-on)"
    fi
}

# ================================================================================
# DEPLOY STACK
# ================================================================================

deploy_stack() {
    print_header "Deploying Docker Stack"
    
    print_step "Starting all services..."
    if docker compose up -d; then
        print_success "Stack deployed successfully"
        echo ""
        print_info "Services starting (this takes 30-60 seconds)"
        
        # Show status
        sleep 5
        docker compose ps
        
        return 0
    else
        print_error "Stack deployment failed"
        return 1
    fi
}

# ================================================================================
# MAIN WIZARD
# ================================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Read version
VERSION="$(cat "$SCRIPT_DIR/VERSION" 2>/dev/null || echo 'unknown')"

clear
echo -e "${BOLD}${MAGENTA}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║                    DPX SHOWSITE OPS SETUP WIZARD                     ║
║                                                                      ║
║            IoT Monitoring • Grafana Dashboards • Live Data           ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"
echo -e "${CYAN}Version: $VERSION${NC}"
echo -e "${CYAN}This wizard will guide you through the setup process (7 steps)${NC}"
echo ""
read -p "Press Enter to begin..."

# ============================================================
# STEP 1: Check Docker
# ============================================================
print_header "STEP 1 of 7: Check Docker Installation"

if check_docker; then
    print_success "Docker is installed"
    docker --version | head -n1
    docker compose version | head -n1
else
    print_warning "Docker not found"
    read -p "Install Docker automatically? [Y/n] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        if auto_install_docker; then
            print_info "You must log out and back in for docker group to take effect"
            read -p "Continue anyway? [Y/n] " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Nn]$ ]]; then
                echo ""
                print_info "Run this script again after logging back in"
                exit 0
            fi
        else
            print_error "Cannot proceed without Docker"
            exit 1
        fi
    else
        print_error "Cannot proceed without Docker"
        echo ""
        print_info "Install Docker manually:"
        echo "  curl -fsSL https://get.docker.com -o get-docker.sh"
        echo "  sudo sh get-docker.sh"
        exit 1
    fi
fi

# Check docker group
if ! check_docker_group; then
    print_warning "You are not in the 'docker' group"
    print_info "Adding you to docker group..."
    sudo usermod -aG docker "$USER"
    print_warning "You must log out and back in for this to take effect"
    read -p "Continue anyway? (you may need sudo for docker commands) [Y/n] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        exit 0
    fi
fi

# ============================================================
# STEP 2: Environment File
# ============================================================
print_header "STEP 2 of 7: Check Configuration File"

if [ -f "$SCRIPT_DIR/.env" ]; then
    print_warning ".env file already exists"
    read -p "Reconfigure credentials? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        mv "$SCRIPT_DIR/.env" "$SCRIPT_DIR/.env.backup.$(date +%s)"
        print_info "Existing .env backed up"
        configure_env_interactive "$SCRIPT_DIR/.env"
    else
        print_info "Using existing .env file"
    fi
else
    if [ ! -f "$SCRIPT_DIR/.env.example" ]; then
        print_error ".env.example not found"
        exit 1
    fi
    configure_env_interactive "$SCRIPT_DIR/.env"
fi

# ============================================================
# STEP 6: System Optimizations
# ============================================================
offer_system_optimizations

# ============================================================
# STEP 7: Dependencies
# ============================================================
install_dependencies

# ============================================================
# Final Step: Deploy
# ============================================================
echo ""
print_header "Ready to Deploy!"

print_info "The wizard has completed configuration"
read -p "Deploy the stack now? [Y/n] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    if deploy_stack; then
        echo ""
        print_header "🎉 Setup Complete!"
        
        # Get IP address
        IP_ADDR=$(hostname -I 2>/dev/null | awk '{print $1}')
        if [ -z "$IP_ADDR" ]; then
            IP_ADDR="<your-ip>"
        fi
        
        echo ""
        print_success "Next steps:"
        echo ""
        echo "  1. Wait 30 seconds for services to start"
        echo ""
        echo "  2. Update device mappings:"
        echo -e "     ${CYAN}iot update${NC}"
        echo ""
        echo "  3. Access Grafana dashboard:"
        echo -e "     ${CYAN}http://$IP_ADDR:3000${NC}"
        echo -e "     Username: ${BOLD}admin${NC}"
        echo -e "     Password: ${BOLD}(see .env file)${NC}"
        echo ""
        echo "  4. Check service status:"
        echo -e "     ${CYAN}iot status${NC}"
        echo ""
        echo "  5. View logs:"
        echo -e "     ${CYAN}iot la${NC}    # All services"
        echo -e "     ${CYAN}iot lg${NC}    # Govee2mqtt"
        echo ""
        print_info "For help: ${CYAN}iot help${NC}"
        print_info "Docs: ${CYAN}docs/APPLICATION_SETUP_GUIDE_COMPLETE.md${NC}"
        echo ""
        
    else
        print_error "Deployment failed"
        echo ""
        print_info "Check logs with: docker compose logs"
        exit 1
    fi
else
    print_info "Skipped deployment"
    echo ""
    print_info "Deploy manually with: ${CYAN}iot up${NC}"
fi

echo ""
