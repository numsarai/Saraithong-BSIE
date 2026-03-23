#!/usr/bin/env bash
# Creates a macOS DMG disk image for BSIE.
# Prerequisites: brew install create-dmg
# Run from project root: bash installer/macos/build_dmg.sh [version]

set -euo pipefail

VERSION="${1:-1.0.0}"
APP_NAME="BSIE"
DMG_NAME="${APP_NAME}-${VERSION}-macos"
DIST_DIR="dist"
DMG_STAGING="${DIST_DIR}/dmg_staging"

echo "Building DMG: ${DMG_NAME}.dmg"

if [[ ! -d "${DIST_DIR}/${APP_NAME}.app" ]]; then
  echo "Error: ${DIST_DIR}/${APP_NAME}.app not found. Run 'pyinstaller bsie.spec' first." >&2
  exit 1
fi

rm -rf "${DMG_STAGING}"
mkdir -p "${DMG_STAGING}"
cp -r "${DIST_DIR}/${APP_NAME}.app" "${DMG_STAGING}/"
cp "installer/macos/dmg-readme.md" "${DMG_STAGING}/README.md"

mkdir -p "${DIST_DIR}"

create-dmg \
  --volname "${APP_NAME}" \
  --volicon "installer/bsie.icns" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "${APP_NAME}.app" 150 185 \
  --hide-extension "${APP_NAME}.app" \
  --app-drop-link 450 185 \
  "${DIST_DIR}/${DMG_NAME}.dmg" \
  "${DMG_STAGING}"

echo "Created: ${DIST_DIR}/${DMG_NAME}.dmg"
