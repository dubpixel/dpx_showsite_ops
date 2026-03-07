#!/bin/bash
# ================================================================================
# ONE-LINER INSTALLER - dpx-showsite-ops
# ================================================================================
#
# Purpose: Clone repository and run interactive setup wizard
# Usage:   curl -fsSL https://raw.githubusercontent.com/dubpixel/dpx_showsite_ops/master/install.sh | bash
#
# Optional Arguments:
#   $1 - Installation directory (default: ~/dpx_showsite_ops)
#   $2 - Git branch to clone (default: master)
#
# Examples:
#   # Standard install
#   curl -fsSL https://raw.githubusercontent.com/dubpixel/dpx_showsite_ops/master/install.sh | bash
#
#   # Custom directory
#   curl -fsSL https://raw.githubusercontent.com/dubpixel/dpx_showsite_ops/master/install.sh | bash -s -- /opt/dpx
#
#   # Specific branch
#   curl -fsSL https://raw.githubusercontent.com/dubpixel/dpx_showsite_ops/master/install.sh | bash -s -- ~/dpx develop
#
# ================================================================================

set -e  # Exit on error

# ================================================================================
# CONFIGURATION
# ================================================================================

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Repository details
REPO_URL="https://github.com/dubpixel/dpx_showsite_ops.git"
DEFAULT_INSTALL_DIR="$HOME/dpx_showsite_ops"
DEFAULT_BRANCH="master"

# Parse arguments
INSTALL_DIR="${1:-$DEFAULT_INSTALL_DIR}"
GIT_BRANCH="${2:-$DEFAULT_BRANCH}"

# ================================================================================
# HELPER FUNCTIONS
# ================================================================================

print_header() {
    echo ""
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${BOLD}${CYAN}▶${NC} $1"
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

fatal_error() {
    print_error "$1"
    exit 1
}

# ================================================================================
# PREREQUISITE CHECKS
# ================================================================================

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check for bash version
    if [ -z "$BASH_VERSION" ]; then
        fatal_error "This script requires bash"
    fi
    
    BASH_MAJOR=$(echo "$BASH_VERSION" | cut -d. -f1)
    if [ "$BASH_MAJOR" -lt 4 ]; then
        print_warning "Bash $BASH_VERSION detected (recommend 4.0+)"
    else
        print_success "Bash $BASH_VERSION"
    fi
    
    # Check for curl
    if ! command -v curl &> /dev/null; then
        fatal_error "curl not found. Install with: sudo apt install curl"
    fi
    print_success "curl found"
    
    # Check for git
    if ! command -v git &> /dev/null; then
        fatal_error "git not found. Install with: sudo apt install git"
    fi
    
    GIT_VERSION=$(git --version | grep -oP '\d+\.\d+\.\d+')
    print_success "git $GIT_VERSION"
    
    # Check internet connectivity
    print_step "Testing connectivity to GitHub..."
    if curl -s --connect-timeout 5 https://github.com > /dev/null; then
        print_success "GitHub reachable"
    else
        fatal_error "Cannot reach GitHub. Check your internet connection"
    fi
    
    # Check if sudo is available
    if command -v sudo &> /dev/null; then
        print_success "sudo available"
    else
        print_warning "sudo not found (may need root access later)"
    fi
}

# ================================================================================
# INSTALLATION DIRECTORY HANDLING
# ================================================================================

prepare_install_dir() {
    print_header "Installation Directory"
    
    # Expand tilde
    INSTALL_DIR="${INSTALL_DIR/#\~/$HOME}"
    
    print_info "Target directory: $INSTALL_DIR"
    
    # Check if directory exists
    if [ -d "$INSTALL_DIR" ]; then
        if [ -f "$INSTALL_DIR/.git/config" ]; then
            print_warning "Directory exists and contains a git repository"
            echo ""
            echo "Options:"
            echo "  1) Backup existing installation and reinstall"
            echo "  2) Pull latest changes and re-run setup"
            echo "  3) Cancel installation"
            echo ""
            read -p "Choose [1/2/3]: " -n 1 -r
            echo ""
            
            case $REPLY in
                1)
                    BACKUP_DIR="${INSTALL_DIR}.backup.$(date +%s)"
                    print_step "Backing up to $BACKUP_DIR..."
                    mv "$INSTALL_DIR" "$BACKUP_DIR"
                    print_success "Backup created"
                    ;;
                2)
                    print_step "Pulling latest changes..."
                    cd "$INSTALL_DIR"
                    git pull
                    print_success "Repository updated"
                    SKIP_CLONE=true
                    ;;
                3)
                    print_info "Installation cancelled"
                    exit 0
                    ;;
                *)
                    fatal_error "Invalid choice"
                    ;;
            esac
        elif [ "$(ls -A "$INSTALL_DIR")" ]; then
            print_warning "Directory exists and is not empty"
            read -p "Remove and reinstall? [y/N] " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                rm -rf "$INSTALL_DIR"
                print_success "Directory cleared"
            else
                fatal_error "Cannot proceed with non-empty directory"
            fi
        else
            print_success "Empty directory found"
        fi
    else
        # Create parent directory if needed
        PARENT_DIR=$(dirname "$INSTALL_DIR")
        if [ ! -d "$PARENT_DIR" ]; then
            print_step "Creating parent directory: $PARENT_DIR"
            mkdir -p "$PARENT_DIR"
        fi
        print_success "Directory ready"
    fi
}

# ================================================================================
# CLONE REPOSITORY
# ================================================================================

clone_repository() {
    if [ "$SKIP_CLONE" = true ]; then
        return
    fi
    
    print_header "Cloning Repository"
    
    print_step "Cloning from: $REPO_URL"
    print_info "Branch: $GIT_BRANCH"
    print_info "Destination: $INSTALL_DIR"
    echo ""
    
    if git clone --branch "$GIT_BRANCH" --recurse-submodules "$REPO_URL" "$INSTALL_DIR"; then
        print_success "Repository cloned successfully"
    else
        fatal_error "Failed to clone repository"
    fi
}

# ================================================================================
# RUN SETUP WIZARD
# ================================================================================

run_setup_wizard() {
    print_header "Running Setup Wizard"
    
    cd "$INSTALL_DIR"
    
    if [ ! -f "$INSTALL_DIR/setup.sh" ]; then
        fatal_error "setup.sh not found in repository"
    fi
    
    chmod +x "$INSTALL_DIR/setup.sh"
    
    print_info "Starting interactive wizard..."
    echo ""
    
    # Run setup wizard
    if bash "$INSTALL_DIR/setup.sh"; then
        return 0
    else
        print_error "Setup wizard failed"
        return 1
    fi
}

# ================================================================================
# MAIN INSTALLATION
# ================================================================================

clear
echo -e "${BOLD}${CYAN}"
cat << "EOF"
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║                  DPX SHOWSITE OPS ONE-LINER INSTALLER                ║
║                                                                      ║
║            Get IoT monitoring running in minutes!                    ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"
echo ""

# Run installation steps
check_prerequisites
prepare_install_dir
clone_repository

# Separator
echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo ""

# Run setup wizard
if run_setup_wizard; then
    echo ""
    print_header "🎉 Installation Complete!"
    echo ""
    print_info "Installation directory: $INSTALL_DIR"
    print_info "Management command: iot (system-wide)"
    echo ""
    print_success "Your DPX Showsite Ops stack is ready!"
    echo ""
else
    echo ""
    print_error "Setup wizard encountered errors"
    echo ""
    print_info "You can re-run the wizard manually:"
    echo -e "  ${CYAN}cd $INSTALL_DIR${NC}"
    echo -e "  ${CYAN}./setup.sh${NC}"
    echo ""
    exit 1
fi
