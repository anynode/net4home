#!/usr/bin/env python3
"""
Pre-commit hook to automatically bump version and update changelog.
This script can be used as a git pre-commit hook or run manually.
"""

import json
import re
from datetime import datetime
from pathlib import Path

MANIFEST_FILE = Path("custom_components/net4home/manifest.json")
CHANGELOG_FILE = Path("CHANGELOG.md")


def get_current_version():
    """Read current version from manifest.json."""
    if not MANIFEST_FILE.exists():
        raise FileNotFoundError(f"{MANIFEST_FILE} not found")
    
    with open(MANIFEST_FILE, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    version = manifest.get('version', '1.0.0')
    print(f"Current version: {version}")
    return version


def increment_minor_version(version):
    """Increment minor version (e.g., 1.1.0 -> 1.2.0)."""
    parts = version.split('.')
    major = int(parts[0]) if len(parts) > 0 and parts[0] else 1
    minor = int(parts[1]) if len(parts) > 1 and parts[1] else 0
    patch = int(parts[2]) if len(parts) > 2 and parts[2] else 0
    
    new_minor = minor + 1
    new_version = f"{major}.{new_minor}.0"
    print(f"New version: {new_version}")
    return new_version


def update_manifest(version):
    """Update version in manifest.json."""
    with open(MANIFEST_FILE, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    
    manifest['version'] = version
    
    with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
        f.write('\n')
    
    print(f"✓ Updated {MANIFEST_FILE} to version {version}")


def update_changelog(version):
    """Add new version entry to CHANGELOG.md."""
    if not CHANGELOG_FILE.exists():
        raise FileNotFoundError(f"{CHANGELOG_FILE} not found")
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    changelog_entry = f"""## [{version}] - {current_date}

### Added
- 

### Changed
- 

### Fixed
- 

"""
    
    with open(CHANGELOG_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the line after the header (usually after line 6)
    insert_line = 6
    for i, line in enumerate(lines):
        if line.startswith('## ['):
            insert_line = i
            break
    
    # Insert new entry
    new_lines = lines[:insert_line] + [changelog_entry] + lines[insert_line:]
    
    with open(CHANGELOG_FILE, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"✓ Added changelog entry for version {version}")
    print(f"⚠ Please edit {CHANGELOG_FILE} to add details about your changes")


def main():
    """Main function."""
    print("Checking version and changelog...")
    
    try:
        current_version = get_current_version()
        new_version = increment_minor_version(current_version)
        update_manifest(new_version)
        update_changelog(new_version)
        print("\n✓ Version bump completed successfully!")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
