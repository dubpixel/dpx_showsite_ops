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
import random
import re
import string
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


def apply_customizations(data, custom_title=None, custom_uid=None):
    """Apply custom title and UID to dashboard.
    
    Args:
        data: Dashboard JSON data
        custom_title: Optional custom title (includes [P] prefix if not present)
        custom_uid: Optional custom UID (if not provided, generates random)
    """
    # Handle title
    original_title = data.get('title', 'untitled')
    
    if custom_title:
        # Use custom title, add [P] prefix if not present
        if not custom_title.lower().startswith('[p]'):
            new_title = f"[P] {custom_title}"
        else:
            new_title = custom_title
        data['title'] = new_title
        print(f"  ✓ Set custom title: '{original_title}' → '{new_title}'")
    else:
        # Add [P] prefix to existing title
        if not original_title.lower().startswith('[p]'):
            new_title = f"[P] {original_title}"
            data['title'] = new_title
            print(f"  ✓ Added provision prefix: '{original_title}' → '{new_title}'")
        else:
            print(f"  ℹ Title already has [P] prefix: '{original_title}'")
    
    # Handle UID
    original_uid = data.get('uid', '')
    
    if custom_uid:
        # Use custom UID as-is
        data['uid'] = custom_uid
        print(f"  ✓ Set custom UID: '{original_uid}' → '{custom_uid}'")
    else:
        # Generate random UID (8 chars, similar to Grafana style)
        random_uid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        data['uid'] = random_uid
        print(f"  ✓ Generated random UID: '{original_uid}' → '{random_uid}'")
    
    return data
    
    return data


def list_backups():
    """List available backup files and let user choose."""
    home_dir = Path.home()
    backup_base = home_dir / 'backups' / 'grafana' / 'dashboards'
    
    if not backup_base.exists():
        print(f"ERROR: Backup directory not found: {backup_base}")
        print("Run 'iot backup-dashboards' first to create backups.")
        sys.exit(1)
    
    # Find all backup session folders, sorted newest first
    session_folders = [d for d in backup_base.iterdir() if d.is_dir()]
    session_folders = sorted(session_folders, key=lambda d: d.name, reverse=True)
    
    if not session_folders:
        print("No dashboard backup folders found.")
        print(f"Run 'iot backup-dashboards' first to create backups.")
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
        print(f"Run 'iot backup-dashboards' first to create backups.")
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
            mtime = filepath.stat().st_mtime
            from datetime import datetime
            timestamp = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
            print(f"  {idx:2d}. {filepath.name}")
    
    print()
    try:
        choice = input("Enter number to provision (or 'q' to quit): ").strip()
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


def check_duplicate_title(provision_dir, proposed_title):
    """Check if a dashboard with the same title already exists in provisioning.
    
    Args:
        provision_dir: Path to provisioning dashboards directory
        proposed_title: Title to check for duplicates
    
    Returns:
        list: List of filenames with matching titles (empty if no duplicates)
    """
    duplicates = []
    
    if not provision_dir.exists():
        return duplicates
    
    for dashboard_file in provision_dir.glob('*.json'):
        try:
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                existing_title = existing_data.get('title', '')
                if existing_title.lower() == proposed_title.lower():
                    duplicates.append(dashboard_file.name)
        except (json.JSONDecodeError, IOError):
            # Skip files that can't be read
            continue
    
    return duplicates


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
    
    # Interactive prompts for customization
    print()
    print("Customization Options:")
    print("-" * 50)
    
    # Prompt 1: Dashboard title
    original_title = data.get('title', 'untitled')
    print(f"Current title: {original_title}")
    custom_title_input = input("Enter new title (without [P] prefix) or press Enter to keep current: ").strip()
    custom_title = custom_title_input if custom_title_input else None
    
    # Prompt 2: Dashboard UID
    original_uid = data.get('uid', '')
    print(f"\nCurrent UID: {original_uid}")
    custom_uid_input = input("Enter custom UID (e.g., 'sensor-v2', 'temp-prod') or press Enter for random: ").strip()
    custom_uid = custom_uid_input if custom_uid_input else None
    
    # Prompt 3: Filename
    # Use custom title if provided, otherwise use original/modified title
    title_for_filename = custom_title if custom_title else original_title
    if not title_for_filename.lower().startswith('[p]'):
        title_for_filename = f"[P] {title_for_filename}"
    safe_default = sanitize_filename(title_for_filename)
    print(f"\nDefault filename: dashboard-{safe_default}.json")
    custom_filename = input("Enter custom filename (without .json) or press Enter for default: ").strip()
    
    print()
    
    # Apply customizations
    data = apply_customizations(data, custom_title=custom_title, custom_uid=custom_uid)
    
    # Determine output path
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    provision_dir = repo_root / 'grafana' / 'provisioning' / 'dashboards'
    
    # Create provision directory if needed
    provision_dir.mkdir(parents=True, exist_ok=True)
    
    # Check for duplicate titles (Grafana will refuse to load duplicates)
    final_title = data.get('title', 'untitled')
    duplicates = check_duplicate_title(provision_dir, final_title)
    if duplicates:
        print()
        print("⚠ ERROR: Duplicate title detected!")
        print(f"Title '{final_title}' already exists in:")
        for dup in duplicates:
            print(f"  - {dup}")
        print()
        print("Grafana will refuse to load dashboards with duplicate titles.")
        print("Please choose a different title.")
        sys.exit(1)
    
    # Generate filename
    if custom_filename:
        output_filename = f"{custom_filename}.json"
    else:
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
