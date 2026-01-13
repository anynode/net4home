# Pre-commit hook to automatically bump version and update changelog (PowerShell)
# This script can be used as a git pre-commit hook or run manually

$ErrorActionPreference = "Stop"

$MANIFEST_FILE = "custom_components/net4home/manifest.json"
$CHANGELOG_FILE = "CHANGELOG.md"

Write-Host "Checking version and changelog..." -ForegroundColor Yellow

# Check if files exist
if (-not (Test-Path $MANIFEST_FILE)) {
    Write-Host "Error: $MANIFEST_FILE not found" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $CHANGELOG_FILE)) {
    Write-Host "Error: $CHANGELOG_FILE not found" -ForegroundColor Red
    exit 1
}

# Extract current version from manifest.json
$manifestContent = Get-Content $MANIFEST_FILE -Raw
if ($manifestContent -match '"version":\s*"([^"]+)"') {
    $CURRENT_VERSION = $matches[1]
    Write-Host "Current version: $CURRENT_VERSION" -ForegroundColor Green
} else {
    Write-Host "Error: Could not find version in manifest.json" -ForegroundColor Red
    exit 1
}

# Parse version components
$versionParts = $CURRENT_VERSION -split '\.'
$MAJOR = if ($versionParts[0]) { [int]$versionParts[0] } else { 1 }
$MINOR = if ($versionParts[1]) { [int]$versionParts[1] } else { 0 }
$PATCH = if ($versionParts[2]) { [int]$versionParts[2] } else { 0 }

# Increment minor version
$NEW_MINOR = $MINOR + 1
$NEW_VERSION = "$MAJOR.$NEW_MINOR.0"

Write-Host "New version: $NEW_VERSION" -ForegroundColor Green

# Get current date
$CURRENT_DATE = Get-Date -Format "yyyy-MM-dd"

# Update manifest.json
$manifestContent = $manifestContent -replace "`"version`":\s*`"$CURRENT_VERSION`"", "`"version`": `"$NEW_VERSION`""
Set-Content -Path $MANIFEST_FILE -Value $manifestContent -NoNewline

Write-Host "✓ Updated $MANIFEST_FILE to version $NEW_VERSION" -ForegroundColor Green

# Read changelog
$changelogContent = Get-Content $CHANGELOG_FILE

# Create changelog entry
$CHANGELOG_ENTRY = @"
## [$NEW_VERSION] - $CURRENT_DATE

### Added
- 

### Changed
- 

### Fixed
- 

"@

# Insert new changelog entry after line 6 (after the header)
$newChangelog = $changelogContent[0..5] + $CHANGELOG_ENTRY.Split("`n") + $changelogContent[6..($changelogContent.Length-1)]
Set-Content -Path $CHANGELOG_FILE -Value $newChangelog

Write-Host "✓ Added changelog entry for version $NEW_VERSION" -ForegroundColor Green
Write-Host "⚠ Please edit $CHANGELOG_FILE to add details about your changes" -ForegroundColor Yellow
