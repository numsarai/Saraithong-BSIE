"""Central project metadata for BSIE."""

from __future__ import annotations

from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parent
_VERSION_FILE = _PROJECT_ROOT / "VERSION"


def _read_version() -> str:
    """Load the canonical app version from the repo root."""
    try:
        value = _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"
    return value or "0.0.0"


APP_VERSION = _read_version()
APP_OWNER_NAME = "ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง"
APP_DEVELOPER_NAME = "ร้อยตำรวจเอกณัฐวุฒิ สาหร่ายทอง"
APP_CONTACT_PHONE = "๐๙๖๗๗๖๘๗๕๗"
