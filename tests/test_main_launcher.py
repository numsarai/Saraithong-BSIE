# tests/test_main_launcher.py
"""Unit tests for main_launcher helper functions."""
import importlib
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def test_setup_user_dirs_creates_expected_directories(tmp_path):
    """_setup_user_dirs must create all runtime user data directories."""
    import paths
    import main_launcher

    with (
        patch.object(paths, "USER_DATA_DIR", tmp_path),
        patch.object(paths, "INPUT_DIR", tmp_path / "data" / "input"),
        patch.object(paths, "EVIDENCE_DIR", tmp_path / "data" / "evidence"),
        patch.object(paths, "OUTPUT_DIR", tmp_path / "data" / "output"),
        patch.object(paths, "EXPORTS_DIR", tmp_path / "data" / "exports"),
        patch.object(paths, "BACKUPS_DIR", tmp_path / "data" / "backups"),
        patch.object(paths, "OVERRIDES_DIR", tmp_path / "overrides"),
        patch.object(paths, "PROFILES_DIR", tmp_path / "mapping_profiles"),
        patch.object(paths, "CONFIG_DIR", tmp_path / "config"),
    ):
        importlib.reload(main_launcher)
        main_launcher._setup_user_dirs()

    assert tmp_path.is_dir()
    assert (tmp_path / "data" / "input").is_dir()
    assert (tmp_path / "data" / "evidence").is_dir()
    assert (tmp_path / "data" / "output").is_dir()
    assert (tmp_path / "data" / "exports").is_dir()
    assert (tmp_path / "data" / "backups").is_dir()
    assert (tmp_path / "overrides").is_dir()
    assert (tmp_path / "mapping_profiles").is_dir()
    assert (tmp_path / "config").is_dir()


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

    with patch.object(main_launcher, "MAX_WAIT_SECONDS", 0.1):
        with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
            result = main_launcher._wait_for_server()

    assert result is False


def test_startup_failure_message_includes_last_error():
    import main_launcher

    with patch.object(main_launcher, "PORT", 8757), patch.object(
        main_launcher, "USER_DATA_DIR", Path("/tmp/BSIE")
    ):
        main_launcher._start_server.error = RuntimeError("boom")
        message = main_launcher._startup_failure_message()

    assert "8757" in message
    assert "boom" in message


def test_show_startup_error_logs_when_dialog_command_fails():
    import main_launcher

    with patch("subprocess.run", side_effect=RuntimeError("dialog unavailable")), patch.object(
        main_launcher.logging.getLogger("bsie.launcher"), "error"
    ) as error_log:
        main_launcher._show_startup_error("Server failed")

    error_log.assert_called()


def test_env_enabled_defaults_and_falsey_values(monkeypatch):
    import main_launcher

    monkeypatch.delenv("BSIE_ENABLE_TRAY", raising=False)
    assert main_launcher._env_enabled("BSIE_ENABLE_TRAY", True) is True

    monkeypatch.setenv("BSIE_ENABLE_TRAY", "0")
    assert main_launcher._env_enabled("BSIE_ENABLE_TRAY", True) is False

    monkeypatch.setenv("BSIE_ENABLE_TRAY", "false")
    assert main_launcher._env_enabled("BSIE_ENABLE_TRAY", True) is False

    monkeypatch.setenv("BSIE_ENABLE_TRAY", "yes")
    assert main_launcher._env_enabled("BSIE_ENABLE_TRAY", False) is True


def test_is_safe_local_http_url_accepts_localhost_only():
    import main_launcher

    assert main_launcher._is_safe_local_http_url("http://127.0.0.1:8757/health") is True
    assert main_launcher._is_safe_local_http_url("https://localhost:8757/health") is True
    assert main_launcher._is_safe_local_http_url("file:///etc/passwd") is False
    assert main_launcher._is_safe_local_http_url("http://example.com/health") is False


def test_register_current_instance_writes_instance_record(tmp_path):
    import paths
    import main_launcher

    with patch.object(paths, "USER_DATA_DIR", tmp_path):
        importlib.reload(main_launcher)
        main_launcher._register_current_instance()
        record = main_launcher._read_instance_record()

    assert record["pid"] == main_launcher.os.getpid()
    assert record["port"] == main_launcher.PORT
    assert record["app"] == "BSIE"
    assert record["executable"]


def test_stop_previous_instance_clears_stale_record(tmp_path):
    import paths
    import main_launcher

    with patch.object(paths, "USER_DATA_DIR", tmp_path):
        importlib.reload(main_launcher)
        main_launcher._write_instance_record({"pid": 999999, "port": 8757, "app": "BSIE"})
        with patch.object(main_launcher, "_is_process_running", return_value=False):
            main_launcher._stop_previous_instance()

    assert main_launcher._read_instance_record() is None


def test_stop_previous_instance_force_terminates_running_instance_before_restart(tmp_path):
    import paths
    import main_launcher

    with patch.object(paths, "USER_DATA_DIR", tmp_path):
        importlib.reload(main_launcher)
        main_launcher._write_instance_record(
            {
                "pid": 4321,
                "port": 8757,
                "app": "BSIE",
                "frozen": True,
                "executable": main_launcher.sys.executable,
            }
        )
        with (
            patch.object(main_launcher, "_is_process_running", return_value=True),
            patch.object(main_launcher, "_wait_for_process_exit", return_value=True),
            patch.object(main_launcher, "_force_terminate_process") as force_terminate,
        ):
            main_launcher._stop_previous_instance()

    force_terminate.assert_called_once_with(4321)
