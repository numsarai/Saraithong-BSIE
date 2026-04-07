#!/usr/bin/env python3
"""Smoke-test a packaged BSIE desktop bundle.

This script launches a built bundle/executable in headless mode, waits for the
embedded FastAPI server to respond, and verifies that the packaged app creates
its writable runtime directories correctly.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def _resolve_target_command(target: Path) -> list[str]:
    """Resolve a platform-appropriate executable from a target path."""
    if target.suffix == ".app":
        executable = target / "Contents" / "MacOS" / "BSIE"
        return [str(executable)]
    return [str(target)]


def _wait_for_health(base_url: str, timeout: float) -> None:
    """Poll /health until the bundle is ready."""
    deadline = time.time() + timeout
    health_url = f"{base_url}/health"
    while time.time() < deadline:
        try:
            # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- base_url is produced from a local smoke-test port and validated by _validate_local_base_url().
            with urllib.request.urlopen(health_url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for {health_url}")


def _http_status(url: str) -> int:
    request = urllib.request.Request(url, method="GET")
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- url is derived from a validated local smoke-test base URL.
    with urllib.request.urlopen(request, timeout=5.0) as response:
        return response.status


def _http_json(url: str) -> object:
    request = urllib.request.Request(url, method="GET")
    # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- url is derived from a validated local smoke-test base URL.
    with urllib.request.urlopen(request, timeout=5.0) as response:
        return json.loads(response.read().decode("utf-8"))


def _validate_local_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("smoke-test base URL must use http:// or https://")
    if parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("smoke-test base URL must target localhost")
    if parsed.username or parsed.password:
        raise ValueError("smoke-test base URL must not include credentials")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _assert_runtime_dirs(user_data_dir: Path) -> None:
    expected = [
        user_data_dir / "bsie.log",
        user_data_dir / "bsie.db",
        user_data_dir / "config",
        user_data_dir / "mapping_profiles",
        user_data_dir / "overrides",
        user_data_dir / "data" / "input",
        user_data_dir / "data" / "evidence",
        user_data_dir / "data" / "output",
        user_data_dir / "data" / "exports",
        user_data_dir / "data" / "backups",
    ]
    missing = [str(path) for path in expected if not path.exists()]
    if missing:
        raise AssertionError(f"Bundle did not create runtime paths: {missing}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a packaged BSIE bundle")
    parser.add_argument("--target", required=True, help="Path to BSIE.app or BSIE.exe/BSIE binary")
    parser.add_argument("--port", type=int, default=8761, help="Port to run the bundle on")
    parser.add_argument(
        "--user-data-dir",
        required=True,
        help="Temporary writable directory for the bundle runtime",
    )
    parser.add_argument("--timeout", type=float, default=20.0, help="Health check timeout in seconds")
    args = parser.parse_args()

    target = Path(args.target).expanduser().resolve()
    user_data_dir = Path(args.user_data_dir).expanduser().resolve()
    shutil.rmtree(user_data_dir, ignore_errors=True)
    user_data_dir.mkdir(parents=True, exist_ok=True)

    command = _resolve_target_command(target)
    env = os.environ.copy()
    env["PORT"] = str(args.port)
    env["BSIE_USER_DATA_DIR"] = str(user_data_dir)
    env["BSIE_OPEN_BROWSER"] = "0"
    env["BSIE_ENABLE_TRAY"] = "0"

    process = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    base_url = _validate_local_base_url(f"http://127.0.0.1:{args.port}")

    try:
        _wait_for_health(base_url, args.timeout)
        if _http_status(f"{base_url}/") != 200:
            raise AssertionError("Root route did not return HTTP 200")
        if _http_status(f"{base_url}/favicon.png") != 200:
            raise AssertionError("favicon.png did not return HTTP 200")
        if _http_status(f"{base_url}/favicon.ico") != 200:
            raise AssertionError("favicon.ico did not return HTTP 200")
        catalog = _http_json(f"{base_url}/api/bank-logo-catalog")
        if isinstance(catalog, dict):
            items = catalog.get("items")
        else:
            items = catalog
        if not isinstance(items, list):
            raise AssertionError("Bank logo catalog did not return the expected payload")
        scb_entry = next(
            (
                item
                for item in items
                if isinstance(item, dict) and item.get("key") == "scb"
            ),
            None,
        )
        if not scb_entry:
            raise AssertionError("Bank logo catalog did not include the SCB entry")
        if scb_entry.get("logo_source") != "static_asset":
            raise AssertionError("SCB logo is not served from the packaged static asset set")
        logo_url = scb_entry.get("logo_url")
        if not logo_url or _http_status(f"{base_url}{logo_url}") != 200:
            raise AssertionError("Packaged SCB logo asset did not return HTTP 200")
        _assert_runtime_dirs(user_data_dir)
        print(f"bundle smoke ok: {target}")
        return 0
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5.0)


if __name__ == "__main__":
    sys.exit(main())
