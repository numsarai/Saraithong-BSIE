# celery_app.py — Celery application instance for BSIE
from __future__ import annotations
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path (needed when worker subprocess starts)
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from celery import Celery

REDIS_URL = os.environ.get("BSIE_REDIS_URL", "redis://127.0.0.1:6379/0")
REDIS_BACKEND = os.environ.get("BSIE_REDIS_BACKEND", "redis://127.0.0.1:6379/1")

celery_app = Celery(
    "bsie",
    broker=REDIS_URL,
    backend=REDIS_BACKEND,
    include=["tasks"],  # auto-discover tasks.py
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    result_expires=3600,
    worker_concurrency=int(os.environ.get("BSIE_WORKER_CONCURRENCY", "1")),
    worker_prefetch_multiplier=1,
)
