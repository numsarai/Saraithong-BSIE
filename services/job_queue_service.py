"""
job_queue_service.py
--------------------
Simple in-process job queue that serializes pipeline executions
to prevent SQLite database locking when processing multiple files.

Uses a threading Queue + single worker thread pattern instead of
spawning a new thread per job (which caused DB lock errors).
"""
from __future__ import annotations

import logging
import threading
from queue import Queue
from typing import Any

logger = logging.getLogger(__name__)

_job_queue: Queue = Queue()
_worker_thread: threading.Thread | None = None
_worker_running = False


def _worker_loop() -> None:
    """Process jobs one at a time from the queue."""
    global _worker_running
    _worker_running = True
    logger.info("Job queue worker started")

    while _worker_running:
        try:
            job = _job_queue.get(timeout=2.0)
        except Exception:
            continue

        if job is None:  # Shutdown signal
            break

        job_id = job.get("job_id", "?")
        func = job.get("func")
        kwargs = job.get("kwargs", {})

        try:
            logger.info("Job queue: starting job %s", job_id)
            func(**kwargs)
            logger.info("Job queue: completed job %s", job_id)
        except Exception:
            logger.exception("Job queue: failed job %s", job_id)
        finally:
            _job_queue.task_done()

    _worker_running = False
    logger.info("Job queue worker stopped")


def ensure_worker_running() -> None:
    """Start the worker thread if not already running."""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="bsie-job-worker")
    _worker_thread.start()


def enqueue_job(job_id: str, func: Any, **kwargs: Any) -> None:
    """Add a job to the queue. It will be processed serially."""
    ensure_worker_running()
    _job_queue.put({"job_id": job_id, "func": func, "kwargs": kwargs})
    logger.info("Job queue: enqueued job %s (queue size: %d)", job_id, _job_queue.qsize())


def shutdown_worker() -> None:
    """Signal the worker to stop."""
    global _worker_running
    _worker_running = False
    _job_queue.put(None)  # Unblock the worker
