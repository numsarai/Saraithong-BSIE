"""
Centralised path resolution for BSIE.

All modules must import paths from here. No other file should compute
paths relative to __file__ for app resources or user data.

In bundle mode (PyInstaller frozen):
  BUNDLE_DIR    = sys._MEIPASS  (read-only temp dir unpacked by PyInstaller)
  USER_DATA_DIR = platform-appropriate app data dir
                    macOS   -> ~/Library/Application Support/BSIE
                    Windows -> %LOCALAPPDATA%\\BSIE
                    Linux   -> ~/.local/share/BSIE
  Legacy support: if ~/Documents/BSIE already exists, keep using it.
  Override: BSIE_USER_DATA_DIR=/custom/path

In dev mode (running from source):
  BUNDLE_DIR    = project root (the directory containing this file)
  USER_DATA_DIR = project root (data/ lives inside the source tree)
"""
import os
import sys
from pathlib import Path

APP_NAME = "BSIE"


def _platform_user_data_home(
    platform: str | None = None,
    *,
    env: dict[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the preferred writable app-data base directory for a platform."""
    platform = platform or sys.platform
    env = os.environ if env is None else env
    home = Path.home() if home is None else home

    if platform == "darwin":
        return home / "Library" / "Application Support"

    if platform.startswith("win"):
        local_app_data = env.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data).expanduser()
        return home / "AppData" / "Local"

    xdg_data_home = env.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser()
    return home / ".local" / "share"


def _bundled_user_data_dir(
    platform: str | None = None,
    *,
    env: dict[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the writable runtime directory used by packaged installs."""
    platform = platform or sys.platform
    env = os.environ if env is None else env
    home = Path.home() if home is None else home

    override = env.get("BSIE_USER_DATA_DIR")
    if override:
        if override.startswith("~"):
            return home / override.lstrip("~/")
        return Path(override).expanduser()

    preferred = _platform_user_data_home(platform, env=env, home=home) / APP_NAME
    legacy = home / "Documents" / APP_NAME

    # Existing desktop installs may already persist data in Documents/BSIE.
    if preferred.exists():
        return preferred
    if legacy.exists():
        return legacy
    return preferred


if getattr(sys, "frozen", False):
    # Running inside a PyInstaller bundle
    BUNDLE_DIR = Path(sys._MEIPASS)
    USER_DATA_DIR = _bundled_user_data_dir()
else:
    # Running from source
    BUNDLE_DIR = Path(__file__).parent
    USER_DATA_DIR = BUNDLE_DIR

# ── Read-only bundled assets (inside the bundle / source tree) ─────────────
BUILTIN_CONFIG_DIR = BUNDLE_DIR / "config"
TEMPLATES_DIR      = BUNDLE_DIR / "templates"
STATIC_DIR         = BUNDLE_DIR / "static"

# ── Writable config dir (user-created banks go here; falls back to bundled) ──
CONFIG_DIR = USER_DATA_DIR / "config" if getattr(sys, 'frozen', False) else BUILTIN_CONFIG_DIR

# ── Runtime user data (writable, never inside the bundle) ─────────────────
INPUT_DIR     = USER_DATA_DIR / "data" / "input"
EVIDENCE_DIR  = USER_DATA_DIR / "data" / "evidence"
OUTPUT_DIR    = USER_DATA_DIR / "data" / "output"
EXPORTS_DIR   = USER_DATA_DIR / "data" / "exports"
BACKUPS_DIR   = USER_DATA_DIR / "data" / "backups"
OVERRIDES_DIR = USER_DATA_DIR / "overrides"
PROFILES_DIR  = USER_DATA_DIR / "mapping_profiles"
DB_PATH       = USER_DATA_DIR / "bsie.db"
