# Version Bump Scripts

These scripts automatically increment the version number and update the changelog before committing to GitHub.

## Usage

### Option 1: Python Script (Recommended - Cross-platform)

```bash
python scripts/pre-commit-version-bump.py
```

Or on Windows:
```powershell
python scripts/pre-commit-version-bump.py
```

### Option 2: Shell Scripts

**Linux/Mac:**
```bash
chmod +x scripts/pre-commit-version-bump.sh
./scripts/pre-commit-version-bump.sh
```

**Windows (PowerShell):**
```powershell
.\scripts\pre-commit-version-bump.ps1
```

### Option 3: Git Pre-commit Hook (Automated)

**Linux/Mac:**
```bash
chmod +x scripts/pre-commit-version-bump.sh
ln -s ../../scripts/pre-commit-version-bump.sh .git/hooks/pre-commit
```

**Windows:**
```powershell
# Copy script to .git/hooks/
Copy-Item scripts/pre-commit-version-bump.ps1 .git/hooks/pre-commit.ps1
```

## What It Does

1. Reads current version from `custom_components/net4home/manifest.json`
2. Increments the MINOR version (e.g., 1.1.0 → 1.2.0)
3. Updates `manifest.json` with new version
4. Adds a new entry to `CHANGELOG.md` with:
   - New version number
   - Current date
   - Template for changes (you fill in details)

## Important Notes

- **Always review and edit** the changelog entry before committing
- The script creates a template - you must add actual change descriptions
- Version follows semantic versioning (MAJOR.MINOR.PATCH)
- For bug fixes only, you may want to increment PATCH instead of MINOR

## Manual Version Bump

If you need to bump MAJOR or PATCH version instead:

1. Edit `custom_components/net4home/manifest.json` manually
2. Add entry to `CHANGELOG.md` manually
3. Follow the same format
