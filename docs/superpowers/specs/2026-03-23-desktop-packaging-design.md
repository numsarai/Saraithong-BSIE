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
- **macOS** (12+, Intel x64 and Apple Silicon — built as separate platform-native binaries, not a universal binary; the macOS runner on GitHub Actions (`macos-latest`) targets arm64)
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
Creates user data directories (first-run setup):
  ~/Documents/BSIE/data/input/
  ~/Documents/BSIE/data/output/
  ~/Documents/BSIE/overrides/
  ~/Documents/BSIE/mapping_profiles/
(mkdir calls live in main_launcher.py so they run on every launch, safely)
        ↓
Redirects stdout/stderr to ~/Documents/BSIE/bsie.log
(PyInstaller bundles suppress the console; log file is the only debug output)
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

**Port conflict:** If port 5001 is already in use, the health poll will time out and the app will show an OS error dialog. This is a known v1 limitation; port selection is not in scope.

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
└── installer/bsie.png  ← tray icon image (read-only, bundled via datas)
```

`overrides/` and `mapping_profiles/` are **not** bundled — they are runtime-writable user data and live in the user data directory (see below).

### What stays outside the bundle (user data directory)

```
~/Documents/BSIE/
├── data/
│   ├── input/              ← files the user uploads
│   └── output/
│       └── {account_no}/   ← one folder per processed account
│           ├── raw/        ← original Excel file copy
│           └── processed/  ← transactions.csv, entities.csv, links.csv, .anx
├── mapping_profiles/       ← self-learned column mapping profiles
├── overrides/
│   └── overrides.json      ← manual relationship overrides (runtime-writable)
└── bsie.log                ← application log
```

Keeping user data outside the bundle ensures it survives app updates and uninstalls (unless user explicitly deletes the folder).

### Bundle path detection — paths.py

The new `paths.py` module at the project root centralises all path resolution (bundle vs source). All other modules import their paths from here; no file should call `Path(__file__)` to locate app resources or user data.

```python
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # Running inside PyInstaller bundle
    BUNDLE_DIR   = Path(sys._MEIPASS)
    USER_DATA_DIR = Path.home() / "Documents" / "BSIE"
else:
    # Running from source
    BUNDLE_DIR   = Path(__file__).parent
    USER_DATA_DIR = BUNDLE_DIR

# Read-only bundled assets
CONFIG_DIR    = BUNDLE_DIR / "config"
TEMPLATES_DIR = BUNDLE_DIR / "templates"
STATIC_DIR    = BUNDLE_DIR / "static"

# Runtime user data (writable)
INPUT_DIR     = USER_DATA_DIR / "data" / "input"
OUTPUT_DIR    = USER_DATA_DIR / "data" / "output"
OVERRIDES_DIR = USER_DATA_DIR / "overrides"
PROFILES_DIR  = USER_DATA_DIR / "mapping_profiles"
```

`main_launcher.py` calls `mkdir(parents=True, exist_ok=True)` on `INPUT_DIR`, `OUTPUT_DIR`, `OVERRIDES_DIR`, and `PROFILES_DIR` at startup, before starting the server. The per-account `raw/` and `processed/` subdirectories inside `OUTPUT_DIR` continue to be created by `core/exporter.py` on demand.

### PyInstaller spec file: bsie.spec

Key directives:
- `datas` includes `templates/`, `static/`, `config/`, `installer/bsie.png` (read-only assets only)
- `hiddenimports` covers FastAPI/uvicorn dynamic imports:
  ```
  uvicorn.logging
  uvicorn.loops
  uvicorn.loops.auto
  uvicorn.protocols
  uvicorn.protocols.http
  uvicorn.protocols.http.auto
  uvicorn.protocols.http.h11_impl
  uvicorn.protocols.websockets
  uvicorn.protocols.websockets.auto
  uvicorn.lifespan
  uvicorn.lifespan.on
  uvicorn.lifespan.off
  fastapi
  starlette
  ```
- `console=False` on Windows (no terminal window popup)
- **File system icon** (shown in Explorer/Finder): `EXE(icon="installer/bsie.ico")` on Windows, `BUNDLE(icon="installer/bsie.icns")` on macOS — set in `bsie.spec`. These are distinct from the tray icon.
- **System tray icon** (shown at runtime by pystray): loaded as a PIL Image from `BUNDLE_DIR / "installer" / "bsie.png"`. `installer/bsie.png` must be in `datas`.
- **`uvicorn[standard]` note:** Pin `uvicorn` without `[standard]` in the build environment to avoid bundling `httptools` (a C extension). This ensures uvicorn uses `h11_impl`, which is already listed in `hiddenimports`.

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

**Gatekeeper:** The app is not code-signed with an Apple Developer certificate. On macOS 12 the workaround is right-click → Open → Open. On macOS 13 (Ventura) and later the system blocks the app and the user must go to **System Settings → Privacy & Security → scroll to "Security" section → click "Open Anyway"**. Both procedures are documented in the README bundled inside the DMG.

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
│           latest        │    │   (arm64)                │
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
├── paths.py                      ← centralised path resolution (bundle vs source)
├── main_launcher.py              ← entry point for packaged builds
├── bsie.spec                     ← PyInstaller spec
├── installer/
│   ├── bsie.ico                  ← Windows icon (256x256)
│   ├── bsie.icns                 ← macOS icon
│   ├── bsie.png                  ← tray icon image (bundled via datas)
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
| `app.py` | Add `GET /health` endpoint; replace all `_BASE`-relative paths with imports from `paths.py`: static mount → `STATIC_DIR`, templates → `TEMPLATES_DIR`, `_get_banks()` config glob → `CONFIG_DIR`, upload dir → `INPUT_DIR`, output dir → `OUTPUT_DIR`, overrides dir → `OVERRIDES_DIR`, profiles dir → `PROFILES_DIR`; remove existing `mkdir` calls (moved to `main_launcher.py` startup) |
| `core/bank_detector.py` | Replace `_CONFIG_DIR = Path(__file__).parent.parent / "config"` with `from paths import CONFIG_DIR` |
| `core/loader.py` | Replace `Path(__file__).parent.parent / "config"` config lookup with `from paths import CONFIG_DIR` |
| `core/exporter.py` | Replace `BASE_OUTPUT = Path(__file__).parent.parent / "data" / "output"` with `from paths import OUTPUT_DIR` |
| `core/mapping_memory.py` | Replace `_PROFILES_DIR = Path(__file__).parent.parent / "mapping_profiles"` with `from paths import PROFILES_DIR`; retain internal mkdir guard (`_dir()`) — it is defensive and intentional |
| `core/override_manager.py` | Replace `_OVERRIDES_FILE = Path(__file__).parent.parent / "overrides" / "overrides.json"` with `from paths import OVERRIDES_DIR`; derive file path as `OVERRIDES_DIR / "overrides.json"`; retain internal mkdir guard (`_ensure_file()`) — it is defensive and intentional |
| `requirements.txt` | Add `pystray>=0.19`, `Pillow>=10.0` |
| `run_bsie.py` | Keep unchanged — still works for running from source; excluded from bundle datas |

---

## Not in Scope (v1)

- Code signing / Apple Developer certificate
- Auto-update mechanism
- Linux packaging
- Microsoft Store / Mac App Store distribution
- Custom app window (Electron/Tauri) — browser-based UI is retained
- Universal macOS binary (Intel + Apple Silicon in one file) — separate platform builds only
- Automatic port conflict resolution
