# worker_entry.py — Celery worker entrypoint for PyInstaller bundle
from __future__ import annotations
import sys
from pathlib import Path

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from celery_app import celery_app

if __name__ == "__main__":
    celery_app.worker_main(argv=[
        "worker",
        "--loglevel=info",
        "--concurrency=1",
        "-P", "solo",
        "-n", "bsie@%h",
    ])
