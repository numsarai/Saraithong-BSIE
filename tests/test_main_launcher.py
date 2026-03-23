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
