# Desktop Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package BSIE as a self-contained desktop installer for Windows and macOS using PyInstaller, with a system tray icon, auto-browser-open on launch, and GitHub Actions CI to produce release artifacts.

**Architecture:** A new `paths.py` module centralises all path resolution (bundle vs. source). Six existing modules switch from `Path(__file__)` to `paths.py` imports. A new `main_launcher.py` is the PyInstaller entry point — it creates user data dirs, redirects logs, starts uvicorn, opens the browser, and runs the system tray icon. `bsie.spec` drives the PyInstaller build; platform installer scripts wrap the output.

**Tech Stack:** Python 3.11, PyInstaller 6+, pystray 0.19+, Pillow 10+, FastAPI/uvicorn, Inno Setup 6 (Windows), create-dmg (macOS), GitHub Actions

**Working directory for all commands:** `G:\BSIE\Saraithong-BSIE-feat-multi-bank-support-and-samples\` (the project root)

---

## File Map

### New files
| File | Responsibility |
|------|---------------|
| `paths.py` | Single source of truth for all paths (bundle vs. source mode) |
| `main_launcher.py` | PyInstaller entry point: dirs setup, log redirect, uvicorn, browser, tray |
| `bsie.spec` | PyInstaller build spec |
| `installer/bsie.png` | 256×256 PNG tray icon (placeholder — replace with real art before public release) |
| `installer/bsie.ico` | Windows file-system icon (placeholder) |
| `installer/bsie.icns` | macOS file-system icon (placeholder) |
| `installer/windows/setup.iss` | Inno Setup 6 installer script |
| `installer/macos/build_dmg.sh` | macOS DMG creation script |
| `installer/macos/dmg-readme.md` | Gatekeeper instructions bundled inside the DMG (extension beyond spec) |
| `.github/workflows/build-release.yml` | GitHub Actions release workflow |
| `tests/test_paths.py` | Tests for `paths.py` |
| `tests/test_health.py` | Test for `GET /health` endpoint |
| `tests/test_path_migration.py` | AST-based regression: confirms no `Path(__file__)` constructions remain in migrated files |
| `tests/test_main_launcher.py` | Unit tests for `main_launcher` helper functions |

### Modified files
| File | What changes |
|------|-------------|
| `requirements.txt` | Add `pystray>=0.19`, `Pillow>=10.0`; change `uvicorn[standard]` → `uvicorn` |
| `app.py` | Add `/health` endpoint; replace all `_BASE`-relative paths (static, templates, config glob, upload dir, output dir, overrides dir, profiles dir) with `paths.py` imports; remove `mkdir` calls |
| `core/bank_detector.py` | `_CONFIG_DIR` → `from paths import CONFIG_DIR` |
| `core/loader.py` | Inline config path in `load_config()` → `CONFIG_DIR / f"{bank_key.lower()}.json"` |
| `core/exporter.py` | `BASE_OUTPUT` → `from paths import OUTPUT_DIR as BASE_OUTPUT` |
| `core/mapping_memory.py` | `_PROFILES_DIR` → `from paths import PROFILES_DIR as _PROFILES_DIR` (retain `_dir()` guard) |
| `core/override_manager.py` | `_OVERRIDES_FILE` → `OVERRIDES_DIR / "overrides.json"` (retain `_ensure_file()` guard) |

---

## Task 1: Create `paths.py` and its tests

**Files:**
- Create: `paths.py`
- Create: `tests/test_paths.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_paths.py
"""Tests for paths.py — verifies all constants are defined and correct in dev mode."""
import sys
from pathlib import Path

# Must run outside a PyInstaller bundle
assert not getattr(sys, 'frozen', False), "Tests must run outside a PyInstaller bundle"

import paths


def test_bundle_dir_is_project_root():
    """In dev mode, BUNDLE_DIR should be the directory containing paths.py."""
    expected = Path(paths.__file__).parent
    assert paths.BUNDLE_DIR == expected


def test_user_data_dir_equals_bundle_dir_in_dev():
    """In dev mode, USER_DATA_DIR should equal BUNDLE_DIR (project root)."""
    assert paths.USER_DATA_DIR == paths.BUNDLE_DIR


def test_read_only_dirs_are_under_bundle_dir():
    """CONFIG_DIR, TEMPLATES_DIR, STATIC_DIR must be children of BUNDLE_DIR."""
    assert paths.CONFIG_DIR    == paths.BUNDLE_DIR / "config"
    assert paths.TEMPLATES_DIR == paths.BUNDLE_DIR / "templates"
    assert paths.STATIC_DIR    == paths.BUNDLE_DIR / "static"


def test_writable_dirs_are_under_user_data_dir():
    """Runtime-writable dirs must be children of USER_DATA_DIR."""
    assert paths.INPUT_DIR     == paths.USER_DATA_DIR / "data" / "input"
    assert paths.OUTPUT_DIR    == paths.USER_DATA_DIR / "data" / "output"
    assert paths.OVERRIDES_DIR == paths.USER_DATA_DIR / "overrides"
    assert paths.PROFILES_DIR  == paths.USER_DATA_DIR / "mapping_profiles"


def test_config_dir_exists_in_project():
    """config/ directory must actually exist for the project to work."""
    assert paths.CONFIG_DIR.is_dir(), f"config/ not found at {paths.CONFIG_DIR}"
```

- [ ] **Step 2: Run tests — expect failure (paths.py does not exist yet)**

```
pytest tests/test_paths.py -v
```
Expected: `ModuleNotFoundError: No module named 'paths'`

- [ ] **Step 3: Create `paths.py`**

```python
# paths.py
"""
Centralised path resolution for BSIE.

All modules must import paths from here. No other file should compute
paths relative to __file__ for app resources or user data.

In bundle mode (PyInstaller frozen):
  BUNDLE_DIR    = sys._MEIPASS  (read-only temp dir unpacked by PyInstaller)
  USER_DATA_DIR = ~/Documents/BSIE  (persistent, user-writable)

In dev mode (running from source):
  BUNDLE_DIR    = project root (the directory containing this file)
  USER_DATA_DIR = project root (data/ lives inside the source tree)
"""
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # Running inside a PyInstaller bundle
    BUNDLE_DIR    = Path(sys._MEIPASS)
    USER_DATA_DIR = Path.home() / "Documents" / "BSIE"
else:
    # Running from source
    BUNDLE_DIR    = Path(__file__).parent
    USER_DATA_DIR = BUNDLE_DIR

# ── Read-only bundled assets (inside the bundle / source tree) ─────────────
CONFIG_DIR    = BUNDLE_DIR / "config"
TEMPLATES_DIR = BUNDLE_DIR / "templates"
STATIC_DIR    = BUNDLE_DIR / "static"

# ── Runtime user data (writable, never inside the bundle) ─────────────────
INPUT_DIR     = USER_DATA_DIR / "data" / "input"
OUTPUT_DIR    = USER_DATA_DIR / "data" / "output"
OVERRIDES_DIR = USER_DATA_DIR / "overrides"
PROFILES_DIR  = USER_DATA_DIR / "mapping_profiles"
```

- [ ] **Step 4: Run tests — expect all 5 pass**

```
pytest tests/test_paths.py -v
```
Expected: 5 passed (`test_bundle_dir_is_project_root`, `test_user_data_dir_equals_bundle_dir_in_dev`, `test_read_only_dirs_are_under_bundle_dir`, `test_writable_dirs_are_under_user_data_dir`, `test_config_dir_exists_in_project`)

- [ ] **Step 5: Commit**

```bash
git add paths.py tests/test_paths.py
git commit -m "feat: add paths.py centralising all bundle/source path resolution"
```

---

## Task 2: Migrate path references in `core/` modules

**Files:**
- Modify: `core/bank_detector.py` (line 18)
- Modify: `core/loader.py` (line 31, inside function body)
- Modify: `core/exporter.py` (line 32)
- Modify: `core/mapping_memory.py` (line 30)
- Modify: `core/override_manager.py` (line 28)
- Create: `tests/test_path_migration.py`

- [ ] **Step 1: Write a test that verifies no `Path(__file__)`-based path construction remains in migrated modules**

The AST check must detect both `.parent` and `.parent.parent` chains from a `Path(__file__)` call:

```python
# tests/test_path_migration.py
"""
Regression test: ensure migrated core modules use paths.py, not Path(__file__).
Catches both Path(__file__).parent and Path(__file__).parent.parent forms.
"""
import ast
import pathlib

MIGRATED_FILES = [
    "core/bank_detector.py",
    "core/loader.py",
    "core/exporter.py",
    "core/mapping_memory.py",
    "core/override_manager.py",
]

ROOT = pathlib.Path(__file__).parent.parent


def _is_path_file_call(node) -> bool:
    """Return True if node is Path(__file__)."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Path"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "__file__"
    )


def _contains_file_path_construction(source: str) -> bool:
    """Return True if source contains Path(__file__).parent[.parent...] usage.

    ast.walk() descends into all nodes including function bodies, so inline
    path constructions inside functions (like loader.py's load_config()) are
    correctly detected.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        # node is an Attribute(.parent) access
        if not (isinstance(node, ast.Attribute) and node.attr == "parent"):
            continue
        # Walk the chain to see if it terminates at Path(__file__)
        inner = node.value
        while isinstance(inner, ast.Attribute) and inner.attr == "parent":
            inner = inner.value
        if _is_path_file_call(inner):
            return True
    return False


def test_no_file_relative_paths_in_migrated_modules():
    """None of the migrated files should construct paths from Path(__file__)."""
    for rel_path in MIGRATED_FILES:
        source = (ROOT / rel_path).read_text(encoding="utf-8")
        assert not _contains_file_path_construction(source), (
            f"{rel_path} still contains Path(__file__).parent — "
            "migrate to paths.py imports"
        )
```

- [ ] **Step 2: Run test — expect failure (no migration done yet)**

```
pytest tests/test_path_migration.py -v
```
Expected: FAILED for all 5 files

- [ ] **Step 3: Migrate `core/bank_detector.py`**

Line 18 currently reads:
```python
_CONFIG_DIR = Path(__file__).parent.parent / "config"
```
Replace with:
```python
from paths import CONFIG_DIR as _CONFIG_DIR
```
Remove `Path` from the `from pathlib import Path` import **only if** `Path` is no longer used elsewhere in the file. (Check first — it may be used in other expressions.)

- [ ] **Step 4: Migrate `core/loader.py`**

Line 31 is inside the `load_config()` function body:
```python
config_path = Path(__file__).parent.parent / "config" / f"{bank_key.lower()}.json"
```
Add at the top of the file (after existing imports):
```python
from paths import CONFIG_DIR
```
Replace line 31 with:
```python
config_path = CONFIG_DIR / f"{bank_key.lower()}.json"
```
Do NOT introduce a module-level `_CONFIG_DIR` variable — the import is used inline inside the function.

- [ ] **Step 5: Migrate `core/exporter.py`**

Line 32:
```python
BASE_OUTPUT = Path(__file__).parent.parent / "data" / "output"
```
Replace with:
```python
from paths import OUTPUT_DIR as BASE_OUTPUT
```
`BASE_OUTPUT` is referenced later in the same file — keeping the alias means nothing else needs to change.

- [ ] **Step 6: Migrate `core/mapping_memory.py`**

Line 30:
```python
_PROFILES_DIR = Path(__file__).parent.parent / "mapping_profiles"
```
Replace with:
```python
from paths import PROFILES_DIR as _PROFILES_DIR
```
**Important:** Keep the `_dir()` function unchanged:
```python
def _dir() -> Path:
    _PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return _PROFILES_DIR
```
This is a defensive guard that handles cold-start situations where `main_launcher.py` was not used. Do not remove it.

- [ ] **Step 7: Migrate `core/override_manager.py`**

Line 28:
```python
_OVERRIDES_FILE = Path(__file__).parent.parent / "overrides" / "overrides.json"
```
Replace with:
```python
from paths import OVERRIDES_DIR as _OVERRIDES_DIR
_OVERRIDES_FILE = _OVERRIDES_DIR / "overrides.json"
```
**Important:** Keep `_ensure_file()` exactly as-is:
```python
def _ensure_file() -> Path:
    _OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)  # keep this line
    if not _OVERRIDES_FILE.exists():
        _OVERRIDES_FILE.write_text("[]", encoding="utf-8")
    return _OVERRIDES_FILE
```
After migration, `_OVERRIDES_FILE.parent` equals `OVERRIDES_DIR`. The `mkdir` call becomes a no-op when `main_launcher.py` has already created the directory, but it remains essential when the module is used in source mode without `main_launcher.py`. Do not remove it.

- [ ] **Step 8: Run migration test — expect 1 passed**

```
pytest tests/test_path_migration.py -v
```
Expected: 1 passed

- [ ] **Step 9: Run existing test suite to confirm nothing broke**

```
pytest tests/ -v
```
Expected: all previously passing tests still pass (0 new failures)

- [ ] **Step 10: Commit**

```bash
git add core/bank_detector.py core/loader.py core/exporter.py core/mapping_memory.py core/override_manager.py tests/test_path_migration.py
git commit -m "refactor: migrate core modules from Path(__file__) to paths.py"
```

---

## Task 3: Update `app.py` (health endpoint + path migration)

**Files:**
- Modify: `app.py`
- Modify: `requirements.txt`
- Create: `tests/test_health.py`

**Note on `run_bsie.py`:** The file `run_bsie.py` contains a hardcoded absolute path (`G:\BSIE\...`) from the original developer's machine. The smoke test in Step 8 uses `uvicorn` directly instead. `run_bsie.py` remains unchanged per the spec but is not used for smoke testing.

- [ ] **Step 1: Write the failing health endpoint test**

```python
# tests/test_health.py
"""Regression test: GET /health must return {"status": "ok"} with HTTP 200."""
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_status_ok():
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test — expect failure (endpoint not yet added)**

```
pytest tests/test_health.py -v
```
Expected: FAILED — 404 Not Found

- [ ] **Step 3: Update `requirements.txt`**

Change `uvicorn[standard]>=0.24.0` to `uvicorn>=0.24.0` (removes `httptools` C extension for PyInstaller compatibility).

Add at the end of the file:
```
pystray>=0.19
Pillow>=10.0
```

- [ ] **Step 4: Install new dependencies**

```
pip install "pystray>=0.19" "Pillow>=10.0"
pip install "uvicorn>=0.24.0"
```

- [ ] **Step 5: Update `app.py` — path setup section**

Find this block near the top of `app.py`:
```python
# ── Path setup ───────────────────────────────────────────────────────────
_BASE = Path(__file__).parent
sys.path.insert(0, str(_BASE))
```
**Keep lines 37-38** (`_BASE = ...` and `sys.path.insert(...)`) — `_BASE` is still needed for `sys.path.insert`. Add the paths imports immediately after:
```python
from paths import (
    CONFIG_DIR, STATIC_DIR, TEMPLATES_DIR,
    INPUT_DIR, OUTPUT_DIR, OVERRIDES_DIR, PROFILES_DIR,
)
```

- [ ] **Step 6: Update `app.py` — directory setup block**

Find and replace the **entire** directory setup block (lines 57-62):
```python
# Before — remove ALL of these lines
UPLOAD_DIR = _BASE / "data" / "input"
OUTPUT_DIR = _BASE / "data" / "output"          ← must be removed (shadowed by import)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)   ← mkdir moved to main_launcher.py
(_BASE / "overrides").mkdir(exist_ok=True)      ← mkdir moved to main_launcher.py
(_BASE / "mapping_profiles").mkdir(exist_ok=True)  ← mkdir moved to main_launcher.py

# After — replace with:
UPLOAD_DIR = INPUT_DIR   # alias kept for any internal references to UPLOAD_DIR
# OUTPUT_DIR imported from paths above — do NOT re-declare it here
# mkdir calls moved to main_launcher.py startup (_setup_user_dirs)
```

**Why removing `OUTPUT_DIR = _BASE / "data" / "output"` matters:** `app.py` uses `OUTPUT_DIR` at multiple points (download endpoint, results endpoint). If the local assignment is not removed, it silently shadows the imported `paths.OUTPUT_DIR` even after the import is added. Removing it ensures the imported constant is used everywhere.

- [ ] **Step 7: Update `app.py` — static mount and templates**

```python
# Before
app.mount("/static", StaticFiles(directory=str(_BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(_BASE / "templates"))

# After
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
```

- [ ] **Step 8: Update `app.py` — `_get_banks()` config glob**

```python
# Before
for f in sorted((_BASE / "config").glob("*.json")):

# After
for f in sorted(CONFIG_DIR.glob("*.json")):
```

- [ ] **Step 9: Add health endpoint to `app.py`**

After the `_get_banks()` function and before the UI routes section, add:

```python
# ═══════════════════════════════════════════════════════════════════════════
# Health check
# ═══════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    """Used by main_launcher.py to poll until the server is ready."""
    return {"status": "ok"}
```

- [ ] **Step 10: Scan for remaining `_BASE /` uses**

Search `app.py` for any remaining `_BASE /` patterns:
```
grep -n "_BASE /" app.py
```
If any are found, replace with the appropriate `paths.py` constant (`CONFIG_DIR`, `STATIC_DIR`, `TEMPLATES_DIR`, `INPUT_DIR`, `OUTPUT_DIR`, `OVERRIDES_DIR`, or `PROFILES_DIR`).

- [ ] **Step 11: Run health test — expect 2 passed**

```
pytest tests/test_health.py -v
```
Expected: 2 passed

- [ ] **Step 12: Run full test suite**

```
pytest tests/ -v
```
Expected: all tests pass

- [ ] **Step 13: Smoke test — start from source (no run_bsie.py)**

```
python -m uvicorn app:app --host 127.0.0.1 --port 5001
```
Open `http://127.0.0.1:5001/health` → `{"status":"ok"}`.
Open `http://127.0.0.1:5001/` → UI loads normally.
Stop with Ctrl+C.

- [ ] **Step 14: Commit**

```bash
git add app.py requirements.txt tests/test_health.py
git commit -m "feat: add GET /health endpoint; migrate app.py to paths.py"
```

---

## Task 4: Create `main_launcher.py`

**Files:**
- Create: `main_launcher.py`
- Create: `tests/test_main_launcher.py`

**Contract for `_setup_user_dirs`:** It must create exactly these four directories (all from `paths.py`):
- `INPUT_DIR` (`USER_DATA_DIR / "data" / "input"`)
- `OUTPUT_DIR` (`USER_DATA_DIR / "data" / "output"`)
- `OVERRIDES_DIR` (`USER_DATA_DIR / "overrides"`)
- `PROFILES_DIR` (`USER_DATA_DIR / "mapping_profiles"`)

This covers all three `mkdir` calls removed from `app.py` (INPUT_DIR, OVERRIDES_DIR, PROFILES_DIR) plus OUTPUT_DIR (which `app.py` never created — `exporter.py` creates per-account subdirs on demand, but the parent `OUTPUT_DIR` itself must exist first).

- [ ] **Step 1: Write unit tests for helper functions (TDD)**

```python
# tests/test_main_launcher.py
"""Unit tests for main_launcher helper functions."""
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def test_setup_user_dirs_creates_expected_directories(tmp_path):
    """_setup_user_dirs must create all four user data directories."""
    import paths
    original_input    = paths.INPUT_DIR
    original_output   = paths.OUTPUT_DIR
    original_overrides = paths.OVERRIDES_DIR
    original_profiles  = paths.PROFILES_DIR

    # Patch paths module constants to use tmp_path
    paths.INPUT_DIR     = tmp_path / "data" / "input"
    paths.OUTPUT_DIR    = tmp_path / "data" / "output"
    paths.OVERRIDES_DIR = tmp_path / "overrides"
    paths.PROFILES_DIR  = tmp_path / "mapping_profiles"

    try:
        import importlib
        import main_launcher
        importlib.reload(main_launcher)
        main_launcher._setup_user_dirs()
        assert (tmp_path / "data" / "input").is_dir()
        assert (tmp_path / "data" / "output").is_dir()
        assert (tmp_path / "overrides").is_dir()
        assert (tmp_path / "mapping_profiles").is_dir()
    finally:
        paths.INPUT_DIR     = original_input
        paths.OUTPUT_DIR    = original_output
        paths.OVERRIDES_DIR = original_overrides
        paths.PROFILES_DIR  = original_profiles


def test_wait_for_server_returns_true_when_server_responds():
    """_wait_for_server should return True when /health returns 200."""
    import main_launcher

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = main_launcher._wait_for_server()

    assert result is True


def test_wait_for_server_returns_false_on_timeout():
    """_wait_for_server should return False if the server never responds."""
    import main_launcher

    original_max = main_launcher.MAX_WAIT_SECONDS
    main_launcher.MAX_WAIT_SECONDS = 0.1  # Very short timeout for test speed

    with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
        result = main_launcher._wait_for_server()

    main_launcher.MAX_WAIT_SECONDS = original_max
    assert result is False
```

- [ ] **Step 2: Run tests — expect ImportError (module not yet created)**

```
pytest tests/test_main_launcher.py -v
```
Expected: `ModuleNotFoundError: No module named 'main_launcher'`

- [ ] **Step 3: Create `main_launcher.py`**

```python
"""
main_launcher.py
----------------
PyInstaller entry point for the BSIE desktop application.

Responsibilities (in order):
  1. Create user data directories if they don't exist (first-run setup)
  2. Redirect stdout/stderr to bsie.log in the user data directory
  3. Start uvicorn (FastAPI server) in a background thread on port 5001
  4. Poll GET /health until the server is ready (max 10 seconds)
  5. Open the user's default browser to http://127.0.0.1:5001
  6. Show a system tray icon with a "Quit BSIE" menu item
  7. On "Quit BSIE": stop uvicorn, remove tray icon, exit process
"""

import sys
import os
import time
import threading
import webbrowser
import urllib.request
import urllib.error
import logging
from pathlib import Path

# Import paths first — works in both bundle and source mode
from paths import (
    INPUT_DIR, OUTPUT_DIR, OVERRIDES_DIR, PROFILES_DIR,
    BUNDLE_DIR, USER_DATA_DIR,
)

PORT = 5001
BASE_URL = f"http://127.0.0.1:{PORT}"
HEALTH_URL = f"{BASE_URL}/health"
MAX_WAIT_SECONDS = 10


def _setup_user_dirs() -> None:
    """Create user data directories on first launch (idempotent)."""
    for directory in [INPUT_DIR, OUTPUT_DIR, OVERRIDES_DIR, PROFILES_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def _redirect_output_to_log() -> None:
    """Redirect stdout/stderr to bsie.log (PyInstaller suppresses the console)."""
    log_path = USER_DATA_DIR / "bsie.log"
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)
    sys.stdout = log_file
    sys.stderr = log_file
    logging.basicConfig(
        stream=log_file,
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


def _start_server() -> None:
    """Start the uvicorn server in a daemon thread. Stores server ref for shutdown."""
    import uvicorn
    config = uvicorn.Config(
        "app:app",
        host="127.0.0.1",
        port=PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    _start_server.server = server
    server.run()


def _wait_for_server() -> bool:
    """Poll /health until the server responds or MAX_WAIT_SECONDS is reached."""
    deadline = time.time() + MAX_WAIT_SECONDS
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def _load_tray_icon():
    """Load the tray icon PNG. Falls back to a coloured square if not found."""
    from PIL import Image
    icon_path = BUNDLE_DIR / "installer" / "bsie.png"
    if not icon_path.exists():
        return Image.new("RGB", (64, 64), color=(30, 100, 200))
    return Image.open(icon_path)


def _quit_app(icon, item) -> None:
    """Called when user selects 'Quit BSIE' from the tray menu."""
    icon.stop()
    if hasattr(_start_server, "server"):
        _start_server.server.should_exit = True
    time.sleep(1)
    os._exit(0)


def main() -> None:
    _setup_user_dirs()
    _redirect_output_to_log()

    logger = logging.getLogger("bsie.launcher")
    logger.info("BSIE launcher starting — user data: %s", USER_DATA_DIR)

    # Start uvicorn in a background daemon thread
    server_thread = threading.Thread(target=_start_server, daemon=True)
    server_thread.start()

    if not _wait_for_server():
        import tkinter.messagebox as mb
        mb.showerror(
            "BSIE",
            f"Server failed to start on port {PORT}.\n"
            "Check bsie.log for details."
        )
        sys.exit(1)

    logger.info("Server ready — opening browser")
    webbrowser.open(BASE_URL)

    # System tray icon (blocks until icon.stop() is called)
    import pystray
    tray_image = _load_tray_icon()
    menu = pystray.Menu(
        pystray.MenuItem("Quit BSIE", _quit_app),
    )
    icon = pystray.Icon("BSIE", tray_image, "BSIE", menu)
    logger.info("Tray icon running")
    icon.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run unit tests — expect 3 passed**

```
pytest tests/test_main_launcher.py -v
```
Expected: 3 passed (`test_setup_user_dirs_creates_expected_directories`, `test_wait_for_server_returns_true_when_server_responds`, `test_wait_for_server_returns_false_on_timeout`)

- [ ] **Step 5: Verify clean import**

```
python -c "import main_launcher; print('import OK')"
```
Expected: `import OK`

- [ ] **Step 6: Manual end-to-end test**

```
python main_launcher.py
```
Verify:
- Browser opens to `http://127.0.0.1:5001`
- System tray icon appears (Windows: bottom-right; macOS: top-right menu bar)
- App keeps running when browser tab is closed
- "Quit BSIE" option stops the server and exits

Stop the app via "Quit BSIE" before continuing.

- [ ] **Step 7: Commit**

```bash
git add main_launcher.py tests/test_main_launcher.py
git commit -m "feat: add main_launcher.py PyInstaller entry point with tray icon"
```

---

## Task 5: Create `bsie.spec` (PyInstaller spec)

**Files:**
- Create: `bsie.spec`
- Create: `installer/bsie.png` (placeholder)
- Create: `installer/bsie.ico` (placeholder)

**Note on TDD:** There is no meaningful automated test for a PyInstaller spec file — its correctness can only be verified by running the build and exercising the produced binary. The manual smoke test in Step 6 serves as the functional verification, with explicit pass/fail criteria.

**Tray icon path consistency check:** `bsie.spec` bundles `installer/bsie.png` with destination `"installer"` inside the bundle, placing it at `sys._MEIPASS/installer/bsie.png`. `main_launcher._load_tray_icon()` loads it from `BUNDLE_DIR / "installer" / "bsie.png"`. In bundle mode `BUNDLE_DIR = Path(sys._MEIPASS)`, so the path resolves to `sys._MEIPASS/installer/bsie.png`. ✓ These are consistent.

**`paths.py` OUTPUT_DIR semantics:** `OUTPUT_DIR = USER_DATA_DIR / "data" / "output"`. In dev mode this is `<project_root>/data/output`. In bundle mode this is `~/Documents/BSIE/data/output`. This is the correct user-writable path used by both `app.py` and `core/exporter.py`.

- [ ] **Step 1: Install PyInstaller**

```
pip install pyinstaller
```

- [ ] **Step 2: Create placeholder icon files**

```bash
python -c "
from PIL import Image
import os
os.makedirs('installer', exist_ok=True)
img = Image.new('RGB', (256, 256), color=(30, 100, 200))
img.save('installer/bsie.png')
img.save('installer/bsie.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(32,32),(16,16)])
print('Created installer/bsie.png and installer/bsie.ico')
"
```

On macOS, also create a placeholder `.icns`:
```bash
python -c "
from PIL import Image
img = Image.open('installer/bsie.png')
img.save('installer/bsie.icns')
print('Created installer/bsie.icns')
"
```

- [ ] **Step 3: Create `bsie.spec`**

```python
# bsie.spec
# PyInstaller spec for BSIE desktop application.
# Build: pyinstaller bsie.spec
# Output: dist/BSIE (one-dir) or dist/BSIE.exe (Windows), dist/BSIE.app (macOS)

import sys
from pathlib import Path

_ico  = str(Path("installer/bsie.ico"))
_icns = str(Path("installer/bsie.icns"))
_icon = _icns if sys.platform == "darwin" else _ico

block_cipher = None

a = Analysis(
    ["main_launcher.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("templates",          "templates"),
        ("static",             "static"),
        ("config",             "config"),
        ("installer/bsie.png", "installer"),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        "fastapi",
        "starlette",
        "starlette.routing",
        "starlette.middleware",
        "starlette.middleware.base",
        "starlette.staticfiles",
        "starlette.templating",
        "pystray._win32",
        "pystray._darwin",
        "pystray._xorg",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="BSIE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="BSIE.app",
        icon=_icns,
        bundle_identifier="com.bsie.app",
    )
```

- [ ] **Step 4: Add `dist/` and `build/` to `.gitignore`**

If `.gitignore` exists, append to it. If not, create it:
```
dist/
build/
*.spec.bak
```

- [ ] **Step 5: Run PyInstaller to validate the spec**

```
pyinstaller bsie.spec
```
Expected: Build completes. On Windows: `dist/BSIE/BSIE.exe`. On macOS: `dist/BSIE.app`.

If PyInstaller warns about missing imports during analysis, add them to `hiddenimports` in `bsie.spec` and re-run.

- [ ] **Step 6: Test the built executable**

On Windows:
```
dist\BSIE\BSIE.exe
```
On macOS:
```
open dist/BSIE.app
```

Pass criteria:
- Browser opens automatically to `http://127.0.0.1:5001`
- `GET http://127.0.0.1:5001/health` returns `{"status": "ok"}`
- System tray icon appears
- `~/Documents/BSIE/` directory created with `data/input/`, `data/output/`, `overrides/`, `mapping_profiles/`
- `~/Documents/BSIE/bsie.log` is written and growing
- Upload a test Excel file → processing completes → output appears in `~/Documents/BSIE/data/output/`
- "Quit BSIE" exits cleanly

Stop via "Quit BSIE" before continuing.

- [ ] **Step 7: Commit**

```bash
git add bsie.spec installer/bsie.png installer/bsie.ico .gitignore
git commit -m "feat: add bsie.spec PyInstaller build configuration and placeholder icons"
```

---

## Task 6: Create platform installer scripts

**Files:**
- Create: `installer/windows/setup.iss`
- Create: `installer/macos/build_dmg.sh`
- Create: `installer/macos/dmg-readme.md`

- [ ] **Step 1: Create directories**

```bash
mkdir -p installer/windows
mkdir -p installer/macos
```

- [ ] **Step 2: Create Inno Setup script `installer/windows/setup.iss`**

```ini
; Inno Setup 6 installer for BSIE.
; Build: ISCC installer\windows\setup.iss
; Prerequisites: Inno Setup 6 (https://jrsoftware.org/isinfo.php)

#define MyAppName "BSIE"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "BSIE Project"
#define MyAppExeName "BSIE.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=BSIE-Setup-{#MyAppVersion}-windows
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Include the entire PyInstaller output directory
Source: "..\..\dist\BSIE\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
```

- [ ] **Step 3: Create macOS DMG build script `installer/macos/build_dmg.sh`**

```bash
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
```

- [ ] **Step 4: Create Gatekeeper instructions `installer/macos/dmg-readme.md`**

```markdown
# BSIE — First Launch Instructions

## Installation

1. Drag **BSIE.app** to your **Applications** folder.
2. Launch BSIE from Launchpad or the Applications folder.

## If macOS blocks the app

BSIE is not signed with an Apple Developer certificate.

### macOS 12 (Monterey)
Right-click (or Control-click) **BSIE.app** → **Open** → click **Open** in the dialog.

### macOS 13 (Ventura) and later
1. Try to open BSIE — macOS will block it with a security dialog.
2. Open **System Settings → Privacy & Security**.
3. Scroll down to the **Security** section.
4. Find "BSIE was blocked" and click **Open Anyway**.
5. Authenticate when prompted.

You only need to do this once.
```

- [ ] **Step 5: Make the DMG script executable**

```bash
chmod +x installer/macos/build_dmg.sh
```

- [ ] **Step 6: Commit**

```bash
git add installer/windows/setup.iss installer/macos/build_dmg.sh installer/macos/dmg-readme.md
git commit -m "feat: add Inno Setup and macOS DMG installer scripts"
```

---

## Task 7: Create GitHub Actions release workflow

**Files:**
- Create: `.github/workflows/build-release.yml`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Create `.github/workflows/build-release.yml`**

```yaml
# Triggered by: git tag v1.0.0 && git push --tags
# Produces: BSIE-Setup-{version}-windows.exe + BSIE-{version}-macos.dmg
# Both uploaded to a GitHub Release.

name: Build and Release

on:
  push:
    tags:
      - "v*.*.*"

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller pystray Pillow

      - name: Generate placeholder icons
        run: |
          python -c "
          from PIL import Image
          import os
          os.makedirs('installer', exist_ok=True)
          img = Image.new('RGB', (256, 256), color=(30, 100, 200))
          img.save('installer/bsie.png')
          img.save('installer/bsie.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(32,32),(16,16)])
          "

      - name: Build with PyInstaller
        run: pyinstaller bsie.spec

      - name: Install Inno Setup
        run: choco install innosetup --no-progress -y

      - name: Build Windows installer
        shell: pwsh
        run: |
          $version = "${{ github.ref_name }}".TrimStart("v")
          (Get-Content installer\windows\setup.iss) -replace '#define MyAppVersion "1.0.0"', "#define MyAppVersion `"$version`"" | Set-Content installer\windows\setup.iss
          New-Item -ItemType Directory -Force -Path dist\installer
          ISCC installer\windows\setup.iss

      - uses: actions/upload-artifact@v4
        with:
          name: windows-installer
          path: dist/installer/BSIE-Setup-*-windows.exe

  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pyinstaller pystray Pillow

      - name: Generate placeholder icons
        run: |
          python -c "
          from PIL import Image
          import os
          os.makedirs('installer', exist_ok=True)
          img = Image.new('RGB', (256, 256), color=(30, 100, 200))
          img.save('installer/bsie.png')
          img.save('installer/bsie.icns')
          "

      - name: Build with PyInstaller
        run: pyinstaller bsie.spec

      - name: Install create-dmg
        run: brew install create-dmg

      - name: Build macOS DMG
        run: |
          version="${{ github.ref_name }}"
          version="${version#v}"
          bash installer/macos/build_dmg.sh "$version"

      - uses: actions/upload-artifact@v4
        with:
          name: macos-dmg
          path: dist/BSIE-*-macos.dmg

  release:
    needs: [build-windows, build-macos]
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: windows-installer
          path: artifacts/

      - uses: actions/download-artifact@v4
        with:
          name: macos-dmg
          path: artifacts/

      - uses: softprops/action-gh-release@v2
        with:
          files: artifacts/*
          generate_release_notes: true
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/build-release.yml
git commit -m "ci: add GitHub Actions build-release workflow for Windows and macOS"
```

---

## Task 8: End-to-end verification and final commit

- [ ] **Step 1: Run the full test suite**

```
pytest tests/ -v
```
Expected: all tests pass (test_paths, test_path_migration, test_health, test_main_launcher, test_config_regression, and any others)

- [ ] **Step 2: Smoke test — source mode via uvicorn**

```
python -m uvicorn app:app --host 127.0.0.1 --port 5001
```
- Upload a bank statement → pipeline completes → output in `data/output/`
- Stop with Ctrl+C

- [ ] **Step 3: Smoke test — main_launcher source mode**

```
python main_launcher.py
```
Verify:
- `data/input/`, `data/output/`, `overrides/`, `mapping_profiles/` created (idempotent)
- Browser opens, `/health` returns 200, UI works end-to-end
- Quit via tray

- [ ] **Step 4: Full PyInstaller build test (local, on target OS)**

```
pyinstaller bsie.spec
```

Run the produced binary. Pass criteria:
1. Browser opens automatically to `http://127.0.0.1:5001`
2. `GET /health` → `{"status": "ok"}`
3. `~/Documents/BSIE/` created with correct subdirs
4. `~/Documents/BSIE/bsie.log` exists and is written
5. Upload a bank statement → processing completes → output in `~/Documents/BSIE/data/output/`
6. "Quit BSIE" exits cleanly

- [ ] **Step 5: Final commit**

```bash
git add .
git status   # confirm nothing sensitive or unexpected
git commit -m "chore: final desktop packaging integration"
```

- [ ] **Step 6: Tag when ready to release**

```bash
git tag v1.0.0
git push && git push --tags
```
This triggers the GitHub Actions workflow to build and publish the installers to the GitHub Releases page.

---

## Implementation Notes

**Icon art:** Replace the placeholder icons (blue 256×256 squares) with real artwork before any public release. Files to replace: `installer/bsie.png`, `installer/bsie.ico`, `installer/bsie.icns`.

**`conftest.py`:** The existing test fixtures use `ROOT / "config" / ...` directly and do not need updating — `paths.py` is not involved in test fixture loading.

**macOS icns generation:** The placeholder `.icns` created by Pillow is a lossy fallback. For production, generate a proper icns from `bsie.png` using:
```bash
mkdir -p bsie.iconset
sips -z 1024 1024 installer/bsie.png --out bsie.iconset/icon_1024x1024.png
iconutil -c icns bsie.iconset -o installer/bsie.icns
```

**uvicorn without `[standard]`:** Removing `[standard]` drops `httptools` (a C extension that is hard to bundle). The `h11` HTTP implementation is the fallback and is already in `hiddenimports`. Performance difference is negligible for a local-only server.
