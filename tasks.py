# tasks.py — Celery tasks for BSIE pipeline
from __future__ import annotations
import json
import logging
import threading
from pathlib import Path

try:
    from celery_app import celery_app
    _CELERY_AVAILABLE = True
except ImportError:
    _CELERY_AVAILABLE = False
    celery_app = None

from database import (
    get_session, Job,
    db_create_job, db_update_job, db_append_log, db_get_job, insert_job_meta
)

log = logging.getLogger(__name__)


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
        line = self.format(record)
        with self._lock:
            self._buffer.append(line)
            if len(self._buffer) >= self.flush_every:
                self._flush()

    def _flush(self):
        if not self._buffer:
            return
        lines = "\n".join(self._buffer)
        self._buffer.clear()
        try:
            db_append_log(self.job_id, lines)
        except Exception as exc:
            log.warning("Log flush failed: %s", exc)

    def flush_all(self):
        with self._lock:
            self._flush()


def run_pipeline_sync(job_id: str, upload_path_str: str, bank_key: str,
                      account: str, name: str, confirmed_mapping: dict) -> None:
    """Core pipeline runner — called by both Celery task and direct thread."""
    import pandas as pd
    from pipeline.process_account import process_account

    upload_path = Path(upload_path_str)
    handler = _JobHandler(job_id)
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)

    _stop_timer = threading.Event()

    def _periodic_flush():
        while not _stop_timer.wait(3):
            handler.flush_all()

    flush_thread = threading.Thread(target=_periodic_flush, daemon=True)
    flush_thread.start()

    try:
        db_update_job(job_id, status="running")

        output_dir = process_account(
            input_file=upload_path,
            subject_account=account,
            subject_name=name,
            bank_key=bank_key,
            confirmed_mapping=confirmed_mapping,
        )

        meta = {}
        meta_path = output_dir / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        txn_path = output_dir / "processed" / "transactions.csv"
        txn_data = []
        if txn_path.exists():
            df = pd.read_csv(txn_path, dtype=str, encoding="utf-8-sig", nrows=500)
            txn_data = df.fillna("").to_dict(orient="records")

        ent_path = output_dir / "processed" / "entities.csv"
        ent_data = []
        if ent_path.exists():
            df = pd.read_csv(ent_path, dtype=str, encoding="utf-8-sig")
            ent_data = df.fillna("").to_dict(orient="records")

        lnk_path = output_dir / "processed" / "links.csv"
        lnk_data = []
        if lnk_path.exists():
            df = pd.read_csv(lnk_path, dtype=str, encoding="utf-8-sig")
            lnk_data = df.fillna("").to_dict(orient="records")

        serializable = {
            "meta": meta,
            "transactions": txn_data,
            "entities": ent_data,
            "links": lnk_data,
            "output_dir": str(output_dir),
            "account": account,
        }

        db_update_job(job_id, status="done", result_json=json.dumps(serializable, default=str), account=account)
        insert_job_meta(job_id, account, meta)
        log.info("Pipeline complete for job %s", job_id)
    except Exception as exc:
        log.exception("Pipeline failed for job %s: %s", job_id, exc)
        db_update_job(job_id, status="error", error=str(exc))
    finally:
        _stop_timer.set()
        handler.flush_all()
        root_logger.removeHandler(handler)


if _CELERY_AVAILABLE and celery_app:
    @celery_app.task(bind=True, name="bsie.run_pipeline", max_retries=0, acks_late=True)
    def run_pipeline_task(self, job_id, upload_path_str, bank_key, account, name, confirmed_mapping):
        run_pipeline_sync(job_id, upload_path_str, bank_key, account, name, confirmed_mapping)
else:
    def run_pipeline_task(*args, **kwargs):
        run_pipeline_sync(*args, **kwargs)
