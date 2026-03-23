# BSIE Desktop Packaging — Design Spec
**Date:** 2026-03-23
**Status:** Approved
**Approach:** PyInstaller self-contained bundle + platform installers

---

## Goal

Package BSIE as an installable desktop application that works on Windows and macOS with a few clicks, requiring no technical knowledge beyond running an installer.

---

## Target Users

Mixed audience — some technical (investigators, analysts), some non-technical. All users must be able to install and launch the app without a README.

---

## Platforms

- **Windows** (10/11, x64)
- **macOS** (12+, Intel and Apple Silicon via universal binary)
- Linux: not in scope for v1

---

## Approach: PyInstaller Self-Contained Bundle

PyInstaller compiles Python + all dependencies + app assets into a single executable. Each platform gets a proper native installer. No Python installation required on the user's machine.

---

## Section 1 — App Launch & Shutdown Flow

```
User double-clicks BSIE icon
        ↓
main_launcher.py starts (PyInstaller entry point)
        ↓
Starts uvicorn server in a background thread (port 5001)
        ↓
Polls GET /health until ready (max ~10 seconds)
        ↓
Opens user's default browser to http://127.0.0.1:5001
        ↓
System tray icon appears:
  Windows → system tray (bottom-right)
  macOS   → menu bar icon (top-right)
  └── "Quit BSIE" option shuts down cleanly
        ↓
Closing browser tab → app keeps running in background
Clicking "Quit BSIE" → server stops → process exits
```

### New endpoint in app.py
```python
@app.get("/health")
def health():
    return {"status": "ok"}
```

### Dependencies added
- `pystray` — cross-platform system tray / menu bar icon
- `Pillow` — required by pystray for the tray icon image
- `pyinstaller` — build-time only, not shipped

---

## Section 2 — PyInstaller Bundle Structure

### What goes inside the bundle

```
BSIE.exe / BSIE.app
├── Python runtime + stdlib
├── All pip packages (fastapi, uvicorn, pandas, openpyxl, rapidfuzz, jinja2, etc.)
├── core/               ← all processing modules
├── pipeline/
├── utils/
├── config/             ← bank JSON configs (bay, scb, ktb, gsb, ttb, kbank, bbl, generic)
├── templates/          ← Jinja2 HTML templates
├── static/             ← CSS + JS assets
└── overrides/overrides.json
```

### What stays outside the bundle (user data directory)

```
~/Documents/BSIE/
├── data/
│   ├── uploads/        ← files the user uploads
│   └── output/         ← processed results (CSV, Excel, ANX)
├── mapping_profiles/   ← self-learned column mapping profiles
└── bsie.log            ← application log
```

Keeping user data outside the bundle ensures it survives app updates and uninstalls (unless user explicitly deletes the folder).

### Bundle path detection

The launcher detects whether the app is running from a PyInstaller bundle and sets paths accordingly:

```python
import sys, os
from pathlib import Path

if getattr(sys, 'frozen', False):
    # Running inside PyInstaller bundle
    BUNDLE_DIR = Path(sys._MEIPASS)
    USER_DATA_DIR = Path.home() / "Documents" / "BSIE"
else:
    # Running from source
    BUNDLE_DIR = Path(__file__).parent
    USER_DATA_DIR = BUNDLE_DIR / "data"
```

### PyInstaller spec file: bsie.spec

Key directives:
- `datas` includes `templates/`, `static/`, `config/`, `overrides/`
- `hiddenimports` covers FastAPI/uvicorn dynamic imports
- `console=False` on Windows (no terminal window popup)
- `icon` points to `installer/bsie.ico` (Windows) or `installer/bsie.icns` (macOS)

---

## Section 3 — Platform Installers

### Windows — Inno Setup (.exe installer)

**Artifact:** `BSIE-Setup-{version}-windows.exe`

**User experience:**
1. Download `.exe`
2. Double-click → installer wizard
3. Next → Next → Install → Finish

**What the installer creates:**
- Install location: `C:\Program Files\BSIE\`
- Start Menu shortcut: `BSIE`
- Desktop shortcut (user opt-in during install)
- Add/Remove Programs entry for clean uninstall

**Script:** `installer/windows/setup.iss` (Inno Setup 6)

---

### macOS — DMG disk image

**Artifact:** `BSIE-{version}-macos.dmg`

**User experience:**
1. Download `.dmg`
2. Open → drag `BSIE.app` to Applications folder shortcut
3. Launch from Launchpad or Applications

**Gatekeeper:** Since the app is not code-signed with an Apple Developer certificate, first launch requires right-click → Open → Open (standard workaround for internal tools). This is documented in the installer README and in a first-launch dialog.

**Script:** `installer/macos/build_dmg.sh` using `create-dmg`

---

## Section 4 — Build Pipeline (GitHub Actions)

Triggered by pushing a version tag (`v*.*.*`). Two parallel jobs.

**Workflow file:** `.github/workflows/build-release.yml`

```
git tag v1.0.0
git push --tags
        ↓
GitHub Actions: build-release.yml
        ↓
┌─────────────────────────┐    ┌─────────────────────────┐
│   Job: build-windows    │    │   Job: build-macos       │
│   runs-on: windows-     │    │   runs-on: macos-latest  │
│           latest        │    │                          │
│ 1. Setup Python 3.11    │    │ 1. Setup Python 3.11     │
│ 2. pip install -r       │    │ 2. pip install -r        │
│    requirements.txt     │    │    requirements.txt      │
│ 3. pip install          │    │ 3. pip install           │
│    pyinstaller pystray  │    │    pyinstaller pystray   │
│ 4. pyinstaller bsie.spec│    │ 4. pyinstaller bsie.spec │
│ 5. choco install        │    │ 5. brew install          │
│    innosetup            │    │    create-dmg            │
│ 6. ISCC setup.iss       │    │ 6. build_dmg.sh          │
│ 7. Upload to Release    │    │ 7. Upload to Release     │
└─────────────────────────┘    └─────────────────────────┘
        ↓
GitHub Release page:
  - BSIE-Setup-1.0.0-windows.exe
  - BSIE-1.0.0-macos.dmg
```

Users download from the GitHub Releases page. No external hosting required.

---

## New Files Added to Project

```
BSIE/
├── main_launcher.py              ← new entry point for packaged builds
├── bsie.spec                     ← PyInstaller spec
├── installer/
│   ├── bsie.ico                  ← Windows icon (256x256)
│   ├── bsie.icns                 ← macOS icon
│   ├── windows/
│   │   └── setup.iss             ← Inno Setup script
│   └── macos/
│       └── build_dmg.sh          ← DMG creation script
└── .github/
    └── workflows/
        └── build-release.yml     ← GitHub Actions workflow
```

---

## Changes to Existing Files

| File | Change |
|------|--------|
| `app.py` | Add `GET /health` endpoint |
| `requirements.txt` | Add `pystray>=0.19`, `Pillow>=10.0` |
| `run_bsie.py` | Keep unchanged — still works for running from source |
| `core/loader.py` | Use `USER_DATA_DIR` from a shared `paths.py` module |
| `pipeline/process_account.py` | Same — use `USER_DATA_DIR` |

A new `paths.py` module at the project root centralises all path resolution (bundle vs source), keeping the path detection logic in one place.

---

## Not in Scope (v1)

- Code signing / Apple Developer certificate
- Auto-update mechanism
- Linux packaging
- Microsoft Store / Mac App Store distribution
- Custom app window (Electron/Tauri) — browser-based UI is retained
