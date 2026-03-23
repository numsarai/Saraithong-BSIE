"""Tests for paths.py — verifies all constants are defined and correct in dev mode."""
import sys
from pathlib import Path
import pytest

# Must run outside a PyInstaller bundle
if getattr(sys, 'frozen', False):
    pytest.skip("test_paths must run outside a PyInstaller bundle", allow_module_level=True)

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
