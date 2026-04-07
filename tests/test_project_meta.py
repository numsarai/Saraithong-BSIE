from __future__ import annotations

from pathlib import Path

from project_meta import APP_VERSION


def test_app_version_matches_version_file():
    version_file = Path(__file__).resolve().parents[1] / "VERSION"

    assert APP_VERSION == version_file.read_text(encoding="utf-8").strip()
