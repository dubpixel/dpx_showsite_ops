#!/usr/bin/env python3
"""
Grafana Dashboard Restore Utility

Restores a dashboard backup as a fully editable dashboard via Grafana API.
Generates a new UID to avoid conflicts with existing dashboards.

Usage:
  ./scripts/restore-dashboard.py [path-to-backup.json]
  
  # Interactive picker (if no path provided)
  ./scripts/restore-dashboard.py
  
Environment variables (from .env):
  GRAFANA_URL - Grafana base URL (default: http://localhost:3000)
  GRAFANA_ADMIN_USER - Admin username (default: admin)
  GRAFANA_ADMIN_PASSWORD - Admin password (required)
"""

import json
import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests library not installed. Run: pip install requests")
    sys.exit(1)

# Configuration from environment
GRAFANA_URL = os.getenv('GRAFANA_URL', 'http://localhost:3000')
GRAFANA_USER = os.getenv('GRAFANA_ADMIN_USER', 'admin')
GRAFANA_PASSWORD = os.getenv('GRAFANA_ADMIN_PASSWORD', '')

if not GRAFANA_PASSWORD:
    print("ERROR: GRAFANA_ADMIN_PASSWORD not set in environment")
    print("Set it in .env file or export GRAFANA_ADMIN_PASSWORD=your-password")
    sys.exit(1)


def list_backups():
    """List available backup files and let user choose."""
    home_dir = Path.home()
    backup_base = home_dir / 'backups' / 'grafana' / 'dashboards'
    
    if not backup_base.exists():
        print(f"ERROR: Backup directory not found: {backup_base}")
        print("Run backup-grafana-dashboards.py first to create backups.")
        sys.exit(1)
    
    # Find all backup session folders, sorted newest first
    session_folders = [d for d in backup_base.iterdir() if d.is_dir()]
    session_folders = sorted(session_folders, key=lambda d: d.name, reverse=True)
    
    if not session_folders:
        print("No dashboard backup folders found.")
        print("Run backup-grafana-dashboards.py first to create backups.")
        sys.exit(1)
    
    # Build a flat list of all dashboards with their session
    all_dashboards = []
    for session_dir in session_folders:
        dashboards = list(session_dir.glob('dashboard-*.json'))
        if dashboards:
            all_dashboards.append({
                'session': session_dir.name,
                'path': session_dir,
                'dashboards': sorted(dashboards, key=lambda p: p.name)
            })
    
    if not all_dashboards:
        print("No dashboard files found in backup folders.")
        print("Run backup-grafana-dashboards.py first to create backups.")
        sys.exit(1)
    
    # Display grouped by session
    print("Available dashboard backups (grouped by backup session):")
    print("=" * 70)
    
    idx = 0
    choice_map = {}
    for session_info in all_dashboards:
        session_name = session_info['session']
        print(f"\n📁 Backup session: {session_name}")
        print("-" * 70)
        
        for filepath in session_info['dashboards']:
            idx += 1
            choice_map[idx] = filepath
            print(f"  {idx:2d}. {filepath.name}")
    
    print()
    try:
        choice = input("Enter number to restore (or 'q' to quit): ").strip()
        if choice.lower() == 'q':
            sys.exit(0)
        
        idx = int(choice)
        if idx in choice_map:
            return choice_map[idx]
        else:
            print(f"Invalid choice: {choice}")
            sys.exit(1)
    except (ValueError, KeyboardInterrupt):
        print("\nCancelled.")
        sys.exit(1)


def generate_new_uid(original_uid):
    """Generate a new unique UID based on original."""
    # Use first 4 chars of original + timestamp-based suffix
    prefix = original_uid[:4] if original_uid else 'rest'
    timestamp = datetime.now().strftime('%m%d%H%M')
    return f"{prefix}-{timestamp}"


def restore_dashboard(dashboard_data):
    """Restore dashboard via Grafana API."""
    url = f"{GRAFANA_URL}/api/dashboards/db"
    
    # Prepare payload
    payload = {
        "dashboard": dashboard_data,
        "overwrite": False,  # Don't overwrite existing dashboards
        "message": "Restored from backup"
    }
    
    try:
        response = requests.post(
            url,
            auth=(GRAFANA_USER, GRAFANA_PASSWORD),
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        return result
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to restore dashboard: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"Details: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"Response: {e.response.text}")
        sys.exit(1)


def main():
    """Main restore workflow."""
    if len(sys.argv) < 2:
        # No argument provided - show interactive picker
        input_path = list_backups()
    else:
        input_path = Path(sys.argv[1])
    
    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)
    
    print("\nGrafana Dashboard Restore Utility")
    print("=" * 50)
    print(f"Input: {input_path}")
    print(f"Grafana URL: {GRAFANA_URL}")
    print()
    
    # Load dashboard JSON
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        sys.exit(1)
    except IOError as e:
        print(f"ERROR: Failed to read file: {e}")
        sys.exit(1)
    
    # Extract dashboard title and original UID
    original_title = data.get('title', 'Untitled')
    original_uid = data.get('uid', '')
    
    print(f"Dashboard: {original_title}")
    print(f"Original UID: {original_uid}")
    print()
    
    # Generate new UID to avoid conflicts
    new_uid = generate_new_uid(original_uid)
    data['uid'] = new_uid
    
    # Remove instance-specific fields
    data.pop('id', None)
    data.pop('version', None)
    
    print(f"Restoring with new UID: {new_uid}")
    print("This will create a new editable dashboard...")
    print()
    
    # Restore via API
    result = restore_dashboard(data)
    
    print("✓ Dashboard restored successfully!")
    print()
    print(f"  Title: {original_title}")
    print(f"  UID: {result.get('uid', new_uid)}")
    print(f"  URL: {GRAFANA_URL}{result.get('url', '')}")
    print()
    print("The dashboard is now fully editable in Grafana.")


if __name__ == '__main__':
    main()
