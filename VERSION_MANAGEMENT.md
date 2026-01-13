# Version Management Guide

This project uses automated version bumping before commits to GitHub. The version is managed in two places:

1. **`custom_components/net4home/manifest.json`** - Version number (read by HACS)
2. **`CHANGELOG.md`** - Release notes (displayed by HACS)

## How It Works

### Automatic (Cursor AI)

When you ask Cursor AI to commit to GitHub, it will automatically:

1. ✅ Read current version from `manifest.json`
2. ✅ Increment MINOR version (e.g., 1.1.0 → 1.2.0)
3. ✅ Update `manifest.json` with new version
4. ✅ Add new entry to `CHANGELOG.md` with current date
5. ✅ Fill in changelog with changes from the commit

### Manual

You can also run the script manually:

```bash
python scripts/pre-commit-version-bump.py
```

Then edit `CHANGELOG.md` to add details about your changes.

## Version Format

Follows [Semantic Versioning](https://semver.org/):

- **MAJOR.MINOR.PATCH** (e.g., 1.2.0)
- **MAJOR**: Breaking changes
- **MINOR**: New features, improvements (default)
- **PATCH**: Bug fixes only

## HACS Integration

HACS will:
- ✅ Detect new version from `manifest.json`
- ✅ Display changelog from `CHANGELOG.md`
- ✅ Show update notification in HACS UI

## GitHub Release Tags

After committing, create a GitHub release tag:

```bash
git tag v1.2.0
git push origin v1.2.0
```

Or create a release on GitHub with the tag matching the version.

## Current Status

- ✅ `.cursorrules` - AI instructions for version bumping
- ✅ `scripts/pre-commit-version-bump.py` - Python script (cross-platform)
- ✅ `scripts/pre-commit-version-bump.sh` - Bash script (Linux/Mac)
- ✅ `scripts/pre-commit-version-bump.ps1` - PowerShell script (Windows)
- ✅ `CHANGELOG.md` - Release notes file
- ✅ `manifest.json` - Contains version number

## Example Workflow

1. Make your code changes
2. Ask Cursor AI: "Commit these changes to GitHub"
3. AI automatically:
   - Bumps version (1.1.0 → 1.2.0)
   - Updates manifest.json
   - Adds changelog entry
   - Fills in changelog with your changes
4. Review and edit `CHANGELOG.md` if needed
5. Commit and push
6. Create GitHub release tag (e.g., v1.2.0)
