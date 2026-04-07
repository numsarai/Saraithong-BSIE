# tasks.py — Background pipeline helpers for BSIE
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

import pandas as pd

from database import (
    db_update_job,
    insert_job_meta,
)

log = logging.getLogger(__name__)

_JOB_LOGGER_PREFIXES = (
    "pipeline.",
    "core.",
    "services.",
    "tasks",
    "bsie.",
)
_IGNORED_JOB_LOGGER_PREFIXES = (
    "uvicorn.",
    "fastapi.",
    "httpx",
    "httpcore",
    "asyncio",
    "watchfiles",
)
_RUNTIME_JOBS: dict[str, dict] = {}
_RUNTIME_JOBS_LOCK = threading.Lock()


def _merge_runtime_job(job_id: str, **updates) -> None:
    with _RUNTIME_JOBS_LOCK:
        existing = _RUNTIME_JOBS.get(job_id, {
            "status": "queued",
            "log": [],
            "result": None,
            "error": None,
        })
        existing.update(updates)
        _RUNTIME_JOBS[job_id] = existing


def _append_runtime_job_log(job_id: str, lines: list[str]) -> None:
    if not lines:
        return
    with _RUNTIME_JOBS_LOCK:
        existing = _RUNTIME_JOBS.get(job_id, {
            "status": "queued",
            "log": [],
            "result": None,
            "error": None,
        })
        existing_log = list(existing.get("log") or [])
        existing_log.extend(lines)
        existing["log"] = existing_log[-400:]
        _RUNTIME_JOBS[job_id] = existing


def get_runtime_job(job_id: str) -> dict | None:
    with _RUNTIME_JOBS_LOCK:
        existing = _RUNTIME_JOBS.get(job_id)
        if not existing:
            return None
        return {
            "status": existing.get("status"),
            "log": list(existing.get("log") or []),
            "result": existing.get("result"),
            "error": existing.get("error"),
        }


def _load_csv_preview(csv_path: Path, *, limit: int) -> list[dict]:
    if not csv_path.exists():
        return []
    df = pd.read_csv(csv_path, dtype=str, encoding="utf-8-sig", nrows=limit).fillna("")
    return df.to_dict(orient="records")


class _JobHandler(logging.Handler):
    """Logging handler that buffers lines and flushes to the Job.log_text DB column."""

    def __init__(self, job_id: str, flush_every: int = 20):
        super().__init__()
        self.job_id = job_id
        self.flush_every = flush_every
        self._buffer: list[str] = []
        self._lock = threading.Lock()
        self.setFormatter(logging.Formatter("%(levelname)-8s %(name)s — %(message)s"))

    def emit(self, record: logging.LogRecord):
        if not self._should_capture(record):
            return
        line = self.format(record)
        with self._lock:
            self._buffer.append(line)
            if len(self._buffer) >= self.flush_every:
                self._flush()

    def _should_capture(self, record: logging.LogRecord) -> bool:
        logger_name = str(record.name or "")
        if logger_name.startswith(_IGNORED_JOB_LOGGER_PREFIXES):
            return False
        return logger_name.startswith(_JOB_LOGGER_PREFIXES)

    def _flush(self):
        if not self._buffer:
            return
        lines = list(self._buffer)
        self._buffer.clear()
        _append_runtime_job_log(self.job_id, lines)

    def flush_all(self):
        with self._lock:
            self._flush()


def run_pipeline_sync(job_id: str, upload_path_str: str, bank_key: str,
                      account: str, name: str, confirmed_mapping: dict,
                      file_id: str = "", parser_run_id: str = "",
                      operator: str = "analyst", header_row: int = 0,
                      sheet_name: str = "") -> None:
    """Core pipeline runner for the in-process background thread."""
    from pipeline.process_account import process_account

    upload_path = Path(upload_path_str)
    handler = _JobHandler(job_id)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    _merge_runtime_job(job_id, status="queued", log=[], result=None, error=None)

    _stop_timer = threading.Event()

    def _periodic_flush():
        while not _stop_timer.wait(3):
            handler.flush_all()

    flush_thread = threading.Thread(target=_periodic_flush, daemon=True)
    flush_thread.start()

    try:
        db_update_job(job_id, status="running")
        _merge_runtime_job(job_id, status="running", error=None)

        output_dir = process_account(
            input_file=upload_path,
            subject_account=account,
            subject_name=name,
            bank_key=bank_key,
            confirmed_mapping=confirmed_mapping,
            file_id=file_id,
            parser_run_id=parser_run_id,
            operator=operator,
        )

        meta = {}
        meta_path = output_dir / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        processed_dir = output_dir / "processed"
        transaction_preview = _load_csv_preview(processed_dir / "transactions.csv", limit=25)
        entity_preview = _load_csv_preview(processed_dir / "entities.csv", limit=25)
        link_preview = _load_csv_preview(processed_dir / "links.csv", limit=25)

        runtime_result = {
            "meta": meta,
            "output_dir": str(output_dir),
            "account": account,
            "report_filename": meta.get("report_filename", ""),
            "transactions": transaction_preview,
            "entities": entity_preview,
            "links": link_preview,
        }
        persisted_result = {
            "meta": meta,
            "output_dir": str(output_dir),
            "account": account,
            "report_filename": meta.get("report_filename", ""),
        }

        handler.flush_all()
        runtime_snapshot = get_runtime_job(job_id) or {"log": []}
        _merge_runtime_job(job_id, status="done", result=runtime_result, error=None)
        db_update_job(
            job_id,
            status="done",
            result_json=json.dumps(persisted_result, default=str),
            account=account,
            log_text="\n".join(runtime_snapshot.get("log") or []),
        )
        insert_job_meta(job_id, account, meta)
        log.info("Pipeline complete for job %s", job_id)
    except Exception as exc:
        log.exception("Pipeline failed for job %s: %s", job_id, exc)
        handler.flush_all()
        runtime_snapshot = get_runtime_job(job_id) or {"log": []}
        _merge_runtime_job(job_id, status="error", error=str(exc), result=None)
        if parser_run_id:
            try:
                from services.persistence_pipeline_service import mark_parser_run_failed

                mark_parser_run_failed(parser_run_id, str(exc))
            except Exception as mark_exc:
                log.warning("Could not mark parser run failed: %s", mark_exc)
        db_update_job(job_id, status="error", error=str(exc), log_text="\n".join(runtime_snapshot.get("log") or []))
    finally:
        _stop_timer.set()
        handler.flush_all()
        root_logger.removeHandler(handler)


def run_pipeline_task(*args, **kwargs):
    """Compatibility wrapper kept for older import sites."""
    run_pipeline_sync(*args, **kwargs)
