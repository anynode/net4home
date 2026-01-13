#!/bin/bash
# Pre-commit hook to automatically bump version and update changelog
# This script can be used as a git pre-commit hook or run manually

set -e

MANIFEST_FILE="custom_components/net4home/manifest.json"
CHANGELOG_FILE="CHANGELOG.md"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Checking version and changelog...${NC}"

# Check if files exist
if [ ! -f "$MANIFEST_FILE" ]; then
    echo -e "${RED}Error: $MANIFEST_FILE not found${NC}"
    exit 1
fi

if [ ! -f "$CHANGELOG_FILE" ]; then
    echo -e "${RED}Error: $CHANGELOG_FILE not found${NC}"
    exit 1
fi

# Extract current version from manifest.json
CURRENT_VERSION=$(grep -o '"version": "[^"]*"' "$MANIFEST_FILE" | cut -d'"' -f4)
echo -e "Current version: ${GREEN}$CURRENT_VERSION${NC}"

# Parse version components
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR=${VERSION_PARTS[0]:-1}
MINOR=${VERSION_PARTS[1]:-0}
PATCH=${VERSION_PARTS[2]:-0}

# Increment minor version
NEW_MINOR=$((MINOR + 1))
NEW_VERSION="$MAJOR.$NEW_MINOR.0"

echo -e "New version: ${GREEN}$NEW_VERSION${NC}"

# Get current date
CURRENT_DATE=$(date +%Y-%m-%d)

# Update manifest.json
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/\"version\": \"$CURRENT_VERSION\"/\"version\": \"$NEW_VERSION\"/" "$MANIFEST_FILE"
else
    # Linux
    sed -i "s/\"version\": \"$CURRENT_VERSION\"/\"version\": \"$NEW_VERSION\"/" "$MANIFEST_FILE"
fi

echo -e "${GREEN}✓ Updated $MANIFEST_FILE to version $NEW_VERSION${NC}"

# Create changelog entry (user should fill in details)
CHANGELOG_ENTRY="## [$NEW_VERSION] - $CURRENT_DATE

### Added
- 

### Changed
- 

### Fixed
- 

"

# Insert new changelog entry after the header (after line 6)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "6a\\
$CHANGELOG_ENTRY
" "$CHANGELOG_FILE"
else
    # Linux
    sed -i "6a\\$CHANGELOG_ENTRY" "$CHANGELOG_FILE"
fi

echo -e "${GREEN}✓ Added changelog entry for version $NEW_VERSION${NC}"
echo -e "${YELLOW}⚠ Please edit $CHANGELOG_FILE to add details about your changes${NC}"
