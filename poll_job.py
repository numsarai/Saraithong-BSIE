#!/usr/bin/env python3
"""Submit a local file to BSIE and poll the processing job until completion."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def _validate_base_url(value: str) -> str:
    """Reject non-http(s) schemes so local files cannot be fetched via urllib."""
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("base-url must start with http:// or https://")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("base-url must be a plain network location without credentials")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit a statement to BSIE and poll the job")
    parser.add_argument("file", help="Path to the statement file to process")
    parser.add_argument("--bank", required=True, help="Bank key to process with")
    parser.add_argument("--account", required=True, help="Subject account number")
    parser.add_argument("--name", required=True, help="Subject account holder name")
    parser.add_argument("--base-url", default="http://127.0.0.1:8757", help="BSIE base URL")
    parser.add_argument("--operator", default="analyst", help="Operator name for the run")
    parser.add_argument("--timeout-seconds", type=int, default=60, help="Overall poll timeout")
    args = parser.parse_args()

    file_path = Path(args.file).expanduser().resolve()
    if not file_path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        return 1

    try:
        base_url = _validate_base_url(args.base_url)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        boundary = f"----BSIEBoundary{uuid.uuid4().hex}"
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        fields = {
            "bank": args.bank,
            "account": args.account,
            "name": args.name,
            "operator": args.operator,
        }

        body = bytearray()
        for key, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
            body.extend(str(value).encode("utf-8"))
            body.extend(b"\r\n")

        file_bytes = file_path.read_bytes()
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
                f"Content-Type: {mime_type}\r\n\r\n"
            ).encode("utf-8")
        )
        body.extend(file_bytes)
        body.extend(b"\r\n")
        body.extend(f"--{boundary}--\r\n".encode("utf-8"))

        request = urllib.request.Request(
            f"{base_url}/api/process",
            method="POST",
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- base_url is restricted to validated http(s) endpoints by _validate_base_url().
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        return 1

    job_id = payload.get("job_id")
    if not job_id:
        print(f"Unexpected response: {json.dumps(payload, ensure_ascii=False)}", file=sys.stderr)
        return 1

    print(f"Started job {job_id}")
    deadline = time.time() + args.timeout_seconds

    while time.time() < deadline:
        time.sleep(2)
        try:
            # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected -- base_url is restricted to validated http(s) endpoints by _validate_base_url().
            with urllib.request.urlopen(f"{base_url}/api/job/{job_id}", timeout=15) as response:
                status = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            print(f"Polling failed: {exc}", file=sys.stderr)
            return 1

        state = status.get("status")
        if state in {"done", "error"}:
            print(f"STATUS: {state}")
            if status.get("error"):
                print(f"ERROR: {status['error']}")
            for line in status.get("log", []):
                print(line)
            return 0 if state == "done" else 1

    print("Timeout", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
