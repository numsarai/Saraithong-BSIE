from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module(relative_path: str, module_name: str):
    target = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, target)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_poll_job_validate_base_url_rejects_file_scheme():
    poll_job = _load_module("poll_job.py", "poll_job_test_module")

    with pytest.raises(ValueError):
        poll_job._validate_base_url("file:///etc/passwd")

    assert poll_job._validate_base_url("http://127.0.0.1:8757") == "http://127.0.0.1:8757"


def test_smoke_bundle_validate_local_base_url_rejects_remote_hosts():
    smoke_bundle = _load_module("scripts/smoke_bundle.py", "smoke_bundle_test_module")

    with pytest.raises(ValueError):
        smoke_bundle._validate_local_base_url("http://example.com:8761")

    assert (
        smoke_bundle._validate_local_base_url("http://localhost:8761/")
        == "http://localhost:8761"
    )
