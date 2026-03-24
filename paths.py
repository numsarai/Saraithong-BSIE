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
DB_PATH       = USER_DATA_DIR / "bsie.db"
