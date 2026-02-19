#!/usr/bin/env python3
"""
Grafana Dashboard Provisioning Converter

Converts exported Grafana dashboards to provisioning-ready format by:
- Detecting and converting v2beta1 format to legacy JSON
- Removing instance-specific metadata (version, id, timestamps)
- Preserving essential fields (uid, panel IDs, queries)
- Saving to provisioning directory for auto-loading

Usage:
  ./scripts/provision-dashboard.py <path-to-exported-dashboard.json>
  
Example:
  ./scripts/provision-dashboard.py grafana/manual_dashboard_backup/dashboard-abc123-20260218-120000.json
"""

import json
import re
import sys
from pathlib import Path


def sanitize_filename(title):
    """Convert dashboard title to safe filename."""
    # Remove special chars, lowercase, replace spaces/dashes with hyphens
    safe = re.sub(r'[^\w\s-]', '', title.lower())
    safe = re.sub(r'[-\s]+', '-', safe)
    return safe.strip('-')


def convert_v2beta1_to_legacy(data):
    """Convert v2beta1 (Kubernetes-style) format to legacy JSON format."""
    if data.get('apiVersion') != 'dashboard.grafana.app/v2beta1':
        # Not v2beta1 format, return as-is
        return data
    
    print("  ℹ Detected v2beta1 format, converting to legacy JSON...")
    
    # Extract spec contents (this is the actual dashboard)
    if 'spec' not in data:
        print("  ⚠ Warning: v2beta1 format but no 'spec' field found")
        return data
    
    return data['spec']


def clean_metadata(data):
    """Remove instance-specific metadata fields."""
    # Top-level fields to remove
    fields_to_remove = ['id', 'version', 'iteration']
    
    for field in fields_to_remove:
        if field in data:
            old_value = data.pop(field)
            print(f"  ✓ Removed '{field}': {old_value}")
    
    # Reset version to 1 (Grafana will manage it)
    if 'version' not in data:
        data['version'] = 1
        print("  ✓ Set version: 1")
    
    return data


def validate_dashboard(data):
    """Validate essential dashboard fields are present."""
    required_fields = ['uid', 'title']
    missing = [f for f in required_fields if f not in data]
    
    if missing:
        print(f"  ⚠ Warning: Missing required fields: {', '.join(missing)}")
        return False
    
    return True


def list_backups():
    """List available backup files and let user choose."""
    home_dir = Path.home()
    backup_base = home_dir / 'backups' / 'grafana' / 'dashboards'
    
    if not backup_base.exists():
        print(f"ERROR: Backup directory not found: {backup_base}")
        print("Run 'iot backup-dashboards' first to create backups.")
        sys.exit(1)
    
    # Find all JSON files across all dated folders, sorted by modification time
    backup_files = []
    for date_dir in sorted(backup_base.iterdir(), reverse=True):
        if date_dir.is_dir():
            backup_files.extend(date_dir.glob('dashboard-*.json'))
    
    # Sort by modification time, newest first
    backup_files = sorted(backup_files, key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not backup_files:
        print("No dashboard backup files found.")
        print(f"Run 'iot backup-dashboards' first to create backups.")
        sys.exit(1)
    
    print("Available dashboard backups:")
    print("=" * 70)
    for idx, filepath in enumerate(backup_files, 1):
        # Show file with date folder and timestamp
        date_folder = filepath.parent.name
        mtime = filepath.stat().st_mtime
        from datetime import datetime
        timestamp = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"{idx:2d}. [{date_folder}] {filepath.name}")
        print(f"    {timestamp}")
    
    print()
    try:
        choice = input("Enter number to provision (or 'q' to quit): ").strip()
        if choice.lower() == 'q':
            sys.exit(0)
        
        idx = int(choice)
        if 1 <= idx <= len(backup_files):
            return backup_files[idx - 1]
        else:
            print(f"Invalid choice: {choice}")
            sys.exit(1)
    except (ValueError, KeyboardInterrupt):
        print("\nCancelled.")
        sys.exit(1)


def main():
    """Main conversion workflow."""
    if len(sys.argv) < 2:
        # No argument provided - show interactive picker
        input_path = list_backups()
    else:
        input_path = Path(sys.argv[1])
    
    if not input_path.exists():
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)
    
    print("Grafana Dashboard Provisioning Converter")
    print("=" * 50)
    print(f"Input: {input_path}")
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
    
    # Convert format if needed
    print("Processing dashboard...")
    data = convert_v2beta1_to_legacy(data)
    
    # Clean metadata
    data = clean_metadata(data)
    
    # Validate
    if not validate_dashboard(data):
        print()
        print("⚠ Dashboard may be invalid, but continuing anyway...")
    
    # Determine output path
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    provision_dir = repo_root / 'grafana' / 'provisioning' / 'dashboards'
    
    # Create provision directory if needed
    provision_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename from title
    title = data.get('title', 'untitled')
    safe_title = sanitize_filename(title)
    output_filename = f"dashboard-{safe_title}.json"
    output_path = provision_dir / output_filename
    
    # Save provisioning version
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print()
        print("✓ Conversion complete!")
        print(f"  Output: {output_path}")
        print()
        print("Dashboard will be auto-loaded by Grafana within ~10 seconds")
        print("(provisioning updateIntervalSeconds: 10)")
    except IOError as e:
        print(f"ERROR: Failed to save file: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
