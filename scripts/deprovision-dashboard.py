#!/usr/bin/env python3
"""
Grafana Dashboard Deprovision Utility

Removes dashboards from the provisioning directory. Grafana will automatically
remove the dashboard from its database within ~10 seconds.

Usage:
  ./scripts/deprovision-dashboard.py [path-to-provisioned-dashboard.json]
  
Examples:
  # Interactive picker - shows all provisioned dashboards
  ./scripts/deprovision-dashboard.py
  
  # Direct removal
  ./scripts/deprovision-dashboard.py grafana/provisioning/dashboards/dashboard-xyz.json
"""

import sys
from pathlib import Path


def list_provisioned():
    """List provisioned dashboards and let user choose."""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    provision_dir = repo_root / 'grafana' / 'provisioning' / 'dashboards'
    
    if not provision_dir.exists():
        print(f"ERROR: Provisioning directory not found: {provision_dir}")
        sys.exit(1)
    
    # Find all JSON files (dashboards), exclude YAML config files
    dashboards = sorted([f for f in provision_dir.glob('*.json') if f.is_file()])
    
    if not dashboards:
        print("No provisioned dashboards found.")
        print(f"Location: {provision_dir}")
        sys.exit(1)
    
    # Display list
    print("Provisioned Dashboards:")
    print("=" * 70)
    
    choice_map = {}
    for idx, filepath in enumerate(dashboards, start=1):
        choice_map[idx] = filepath
        # Try to extract title from JSON if possible
        try:
            import json
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                title = data.get('title', 'Unknown')
                uid = data.get('uid', 'no-uid')
                print(f"  {idx:2d}. {title}")
                print(f"      File: {filepath.name}")
                print(f"      UID: {uid}")
        except:
            # If can't read JSON, just show filename
            print(f"  {idx:2d}. {filepath.name}")
        print()
    
    # Prompt for choice
    try:
        choice = input("Enter number to deprovision (or 'q' to quit): ").strip()
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


def deprovision_dashboard(filepath):
    """Remove dashboard file from provisioning directory."""
    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}")
        sys.exit(1)
    
    # Show what will be removed
    print(f"Dashboard to deprovision: {filepath.name}")
    print(f"Location: {filepath}")
    print()
    
    # Confirm deletion
    try:
        confirm = input("Are you sure you want to remove this dashboard? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("Cancelled.")
            sys.exit(0)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)
    
    # Remove file
    try:
        filepath.unlink()
        print()
        print("✓ Dashboard removed from provisioning directory!")
        print(f"  File deleted: {filepath.name}")
        print()
        print("Grafana will automatically remove the dashboard within ~10 seconds")
        print("(provisioning updateIntervalSeconds: 10)")
    except IOError as e:
        print(f"ERROR: Failed to remove file: {e}")
        sys.exit(1)


def main():
    """Main deprovision workflow."""
    if len(sys.argv) < 2:
        # No argument - show interactive picker
        filepath = list_provisioned()
    else:
        # File path provided
        filepath = Path(sys.argv[1])
    
    deprovision_dashboard(filepath)


if __name__ == '__main__':
    main()
