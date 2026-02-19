#!/usr/bin/env python3
"""
Grafana Dashboard Backup Utility

Fetches all dashboards from Grafana API and saves them to manual_dashboard_backup/
with timestamps. Designed to run via cron for automated backups.

Usage:
  ./scripts/backup-grafana-dashboards.py
  
Environment variables (from .env):
  GRAFANA_URL - Grafana base URL (default: http://localhost:3000)
  GRAFANA_ADMIN_USER - Admin username (default: admin)
  GRAFANA_ADMIN_PASSWORD - Admin password (required)
"""

import json
import os
import re
import sys
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

# Determine paths
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
BACKUP_DIR = REPO_ROOT / 'grafana' / 'manual_dashboard_backup'

# Create backup directory if it doesn't exist
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def fetch_dashboards():
    """Fetch list of all dashboards from Grafana API."""
    url = f"{GRAFANA_URL}/api/search?type=dash-db"
    try:
        response = requests.get(url, auth=(GRAFANA_USER, GRAFANA_PASSWORD), timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to fetch dashboard list: {e}")
        sys.exit(1)


def fetch_dashboard(uid):
    """Fetch full dashboard JSON by UID."""
    url = f"{GRAFANA_URL}/api/dashboards/uid/{uid}"
    try:
        response = requests.get(url, auth=(GRAFANA_USER, GRAFANA_PASSWORD), timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to fetch dashboard {uid}: {e}")
        return None


def main():
    """Main backup workflow."""
    print("Grafana Dashboard Backup")
    print("=" * 50)
    print(f"Grafana URL: {GRAFANA_URL}")
    print(f"Backup directory: {BACKUP_DIR}")
    print()

    # Fetch dashboard list
    print("Fetching dashboard list...")
    dashboards = fetch_dashboards()
    
    if not dashboards:
        print("No dashboards found.")
        return
    
    print(f"Found {len(dashboards)} dashboard(s)")
    print()

    # Backup each dashboard
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backed_up = 0
    
    for dash in dashboards:
        uid = dash.get('uid')
        title = dash.get('title', 'Untitled')
        
        if not uid:
            print(f"  ⚠ Skipping '{title}' (no UID)")
            continue
        
        print(f"  Backing up: {title} (uid: {uid})")
        
        # Fetch full dashboard JSON
        dashboard_data = fetch_dashboard(uid)
        if not dashboard_data:
            print(f"    ✗ Failed to fetch dashboard")
            continue
        
        # Create human-readable filename with title
        # Sanitize title for filesystem
        safe_title = re.sub(r'[^\w\s-]', '', title.lower())
        safe_title = re.sub(r'[-\s]+', '-', safe_title).strip('-')
        safe_title = safe_title[:50]  # Limit length
        
        # Save to file with format: dashboard-{safe-title}-{uid}-{timestamp}.json
        filename = f"dashboard-{safe_title}-{uid}-{timestamp}.json"
        filepath = BACKUP_DIR / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(dashboard_data, f, indent=2, ensure_ascii=False)
            print(f"    ✓ Saved: {filename}")
            backed_up += 1
        except IOError as e:
            print(f"    ✗ Failed to save: {e}")
    
    print()
    print(f"Backup complete: {backed_up}/{len(dashboards)} dashboards saved")
    print(f"Location: {BACKUP_DIR}")


if __name__ == '__main__':
    main()
