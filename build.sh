#!/usr/bin/env bash
# build.sh — One-command BSIE build: React + PyInstaller + installer
# Usage: bash build.sh [--dmg] [--skip-frontend]
# Output: dist/BSIE.app (macOS) or dist/BSIE/ (Windows) + installer package

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VERSION=$(cat VERSION 2>/dev/null || echo "2.0.0")
PLATFORM=$(python3 -c "import sys; print(sys.platform)")

BUILD_DMG=false
SKIP_FRONTEND=false

for arg in "$@"; do
  case $arg in
    --dmg)           BUILD_DMG=true ;;
    --skip-frontend) SKIP_FRONTEND=true ;;
  esac
done

echo "============================================================"
echo "  BSIE Build v${VERSION} — ${PLATFORM}"
echo "============================================================"

# ── Step 1: Build React frontend ────────────────────────────────
if [ "$SKIP_FRONTEND" = false ]; then
  echo ""
  echo "▶ [1/4] Building React frontend..."
  if [ ! -d "frontend/node_modules" ]; then
    (cd frontend && npm install)
  fi
  (cd frontend && npm run build)
  echo "  ✓ React build → static/dist/"
else
  echo "▶ [1/4] Skipping React frontend build"
fi

# ── Step 2: Install Python deps ─────────────────────────────────
echo ""
echo "▶ [2/4] Installing Python dependencies..."
pip3 install -r requirements.txt --quiet
pip3 install pyinstaller --quiet
echo "  ✓ Python deps installed"

# ── Step 3: PyInstaller ─────────────────────────────────────────
echo ""
echo "▶ [3/4] Running PyInstaller..."
rm -rf build/ dist/
python3 -m PyInstaller bsie.spec --noconfirm
echo "  ✓ PyInstaller complete"

if [ "$PLATFORM" = "darwin" ] && [ -d "dist/BSIE.app" ]; then
  echo "  → Normalizing macOS app bundle metadata..."
  TMP_APP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/bsie-sign.XXXXXX")"
  TMP_APP="${TMP_APP_DIR}/BSIE.app"
  ditto "dist/BSIE.app" "$TMP_APP"
  xattr -cr "$TMP_APP" || true
  if command -v codesign &>/dev/null; then
    codesign --force --deep --sign - "$TMP_APP" || true
  fi
  rm -rf "dist/BSIE.app"
  mv "$TMP_APP" "dist/BSIE.app"
  rmdir "$TMP_APP_DIR" 2>/dev/null || true
fi

# ── Step 4: Package installer ───────────────────────────────────
echo ""
echo "▶ [4/4] Packaging installer..."

if [ "$PLATFORM" = "darwin" ]; then
  if [ "$BUILD_DMG" = true ]; then
    if command -v create-dmg &>/dev/null; then
      bash installer/macos/build_dmg.sh
      echo "  ✓ DMG created → dist/BSIE-${VERSION}-macos.dmg"
    else
      echo "  ⚠ create-dmg not found — install with: brew install create-dmg"
      echo "  ✓ App bundle at: dist/BSIE.app"
    fi
  else
    echo "  ✓ App bundle at: dist/BSIE.app"
    echo "  ℹ To create DMG: bash build.sh --dmg"
  fi
elif [ "$PLATFORM" = "win32" ]; then
  if command -v iscc &>/dev/null; then
    iscc installer/windows/setup.iss
    echo "  ✓ Windows installer → dist/BSIE-Setup-${VERSION}-windows.exe"
  else
    echo "  ⚠ Inno Setup (iscc) not found — install from https://jrsoftware.org/isinfo.php"
    echo "  ✓ App folder at: dist/BSIE/"
  fi
fi

echo ""
echo "============================================================"
echo "  ✅ Build complete!"
if [ "$PLATFORM" = "darwin" ]; then
  echo "  📦 Output: dist/BSIE.app"
  echo "  ▶  Run: open dist/BSIE.app"
elif [ "$PLATFORM" = "win32" ]; then
  echo "  📦 Output: dist/BSIE/"
fi
echo "============================================================"
