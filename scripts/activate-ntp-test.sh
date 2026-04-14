#!/bin/bash

# === NTP Test Virtual Environment Activation Helper ===
# Usage: source ./scripts/activate-ntp-test.sh

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/venv-ntp-test"

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
  echo "❌ Virtual environment not found at $VENV_DIR"
  echo "   Run ./scripts/setup-ntp-test.sh first to create it"
  return 1 2>/dev/null || exit 1
fi

# Activate virtual environment
source "$VENV_DIR/bin/activate"
echo "✓ NTP test virtual environment activated"
echo "  Run: python scripts/test_ntp.py [server]"
echo "  Deactivate with: deactivate"
