"""Tests for paths.py — verifies all constants are defined and correct in dev mode."""
import os
import sys
from pathlib import Path

# Must run outside a PyInstaller bundle
if getattr(sys, "frozen", False):
    import pytest
    pytest.skip("test_paths must run outside a PyInstaller bundle", allow_module_level=True)

import paths


def test_bundle_dir_is_project_root():
    """In dev mode, BUNDLE_DIR should be the directory containing paths.py."""
    expected = Path(paths.__file__).parent
    assert paths.BUNDLE_DIR == expected


def test_user_data_dir_uses_isolated_runtime_root_under_pytest():
    """Pytest should isolate writable runtime state away from the project root."""
    configured_runtime = os.environ.get("BSIE_TEST_RUNTIME_DIR")
    assert configured_runtime
    assert paths.USER_DATA_DIR == Path(configured_runtime)
    assert paths.USER_DATA_DIR != paths.BUNDLE_DIR


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


def test_platform_user_data_home_for_macos():
    home = Path("/Users/tester")
    assert paths._platform_user_data_home("darwin", env={}, home=home) == (
        home / "Library" / "Application Support"
    )


def test_platform_user_data_home_for_windows_prefers_localappdata():
    env = {"LOCALAPPDATA": r"C:\Users\tester\AppData\Local"}
    home = Path(r"C:\Users\tester")
    assert paths._platform_user_data_home("win32", env=env, home=home) == Path(
        r"C:\Users\tester\AppData\Local"
    )


def test_bundled_user_data_dir_prefers_env_override():
    env = {"BSIE_USER_DATA_DIR": "~/Custom/BSIE"}
    home = Path("/Users/tester")
    assert paths._bundled_user_data_dir("darwin", env=env, home=home) == (
        home / "Custom" / "BSIE"
    )


def test_bundled_user_data_dir_uses_legacy_documents_dir_if_present(tmp_path):
    legacy = tmp_path / "Documents" / "BSIE"
    legacy.mkdir(parents=True)
    preferred = tmp_path / "Library" / "Application Support" / "BSIE"

    resolved = paths._bundled_user_data_dir("darwin", env={}, home=tmp_path)

    assert resolved == legacy
    assert resolved != preferred


def test_bundled_user_data_dir_uses_platform_default_when_no_legacy_exists(tmp_path):
    preferred = tmp_path / "Library" / "Application Support" / "BSIE"

    resolved = paths._bundled_user_data_dir("darwin", env={}, home=tmp_path)

    assert resolved == preferred
