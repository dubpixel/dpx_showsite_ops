#!/bin/bash

# === NTP Test Script: Environment Setup ===
# Sets up a Python virtual environment and installs dependencies
# Run from DPX_SHOWSITE_OPS root: ./scripts/setup-ntp-test.sh

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/venv-ntp-test"
REQUIREMENTS="$SCRIPT_DIR/requirements-ntp-test.txt"

echo "🔧 Setting up NTP test environment..."

# Check if requirements file exists
if [ ! -f "$REQUIREMENTS" ]; then
  echo "❌ Requirements file not found: $REQUIREMENTS"
  exit 1
fi

# Remove existing venv if --clean flag is passed
if [[ "$1" == "--clean" ]]; then
  echo "🧹 Cleaning existing virtual environment..."
  rm -rf "$VENV_DIR"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
  echo "📦 Creating virtual environment at $VENV_DIR..."
  python3 -m venv "$VENV_DIR"
else
  echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing dependencies from $REQUIREMENTS..."
pip install -r "$REQUIREMENTS"

echo ""
echo "✅ Setup complete!"
echo ""
echo "To use the NTP test script:"
echo "  1. Activate venv:  source scripts/venv-ntp-test/bin/activate"
echo "  2. Run test:       python scripts/test_ntp.py"
echo "  3. Deactivate:     deactivate"
echo ""
