"""Compatibility database facade for existing BSIE callers."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from sqlmodel import select

from persistence.base import engine, get_legacy_session, init_database
from persistence.legacy_models import BankFingerprint, Job, JobMeta, MappingProfile, Override


def get_session():
    """Return a SQLModel-compatible session. Existing callers use this API."""
    return get_legacy_session()


def init_db():
    """Create all tables if they do not exist. Safe to call on every startup."""
    init_database()


def db_create_job(job_id: str, account: str = "") -> None:
    with get_session() as session:
        job = Job(
            job_id=job_id,
            status="queued",
            log_text="",
            result_json=None,
            error=None,
            account=account,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(job)
        session.commit()


def db_update_job(job_id: str, **kwargs) -> None:
    with get_session() as session:
        job = session.exec(select(Job).where(Job.job_id == job_id)).first()
        if job:
            for key, value in kwargs.items():
                setattr(job, key, value)
            job.updated_at = datetime.utcnow()
            session.add(job)
            session.commit()


def db_get_job(job_id: str) -> Optional[dict]:
    with get_session() as session:
        job = session.exec(select(Job).where(Job.job_id == job_id)).first()
        if not job:
            return None
        return {
            "status": job.status,
            "log_text": job.log_text,
            "result_json": job.result_json,
            "error": job.error,
            "account": job.account,
        }


def db_append_log(job_id: str, line: str) -> None:
    with get_session() as session:
        job = session.exec(select(Job).where(Job.job_id == job_id)).first()
        if job:
            existing = job.log_text or ""
            separator = "\n" if existing and not existing.endswith("\n") else ""
            job.log_text = existing + separator + line + "\n"
            job.updated_at = datetime.utcnow()
            session.add(job)
            session.commit()


def insert_job_meta(job_id: str, account_number: str, meta: dict) -> None:
    import logging as _logging

    _log = _logging.getLogger(__name__)
    try:
        with get_session() as session:
            row = JobMeta(
                account_number=account_number,
                job_id=job_id,
                bank=meta.get("bank", ""),
                total_in=float(meta.get("total_in", 0.0)),
                total_out=float(meta.get("total_out", 0.0)),
                total_circulation=float(meta.get("total_circulation", 0.0)),
                num_transactions=int(meta.get("num_transactions", 0)),
                date_range=meta.get("date_range", ""),
                num_unknown=int(meta.get("num_unknown", 0)),
                num_partial_accounts=int(meta.get("num_partial_accounts", 0)),
                report_filename=meta.get("report_filename", ""),
                created_at=datetime.utcnow(),
            )
            session.add(row)
            session.commit()
    except Exception as exc:
        _log.warning("Could not insert JobMeta for job %s: %s", job_id, exc)


__all__ = [
    "engine",
    "get_session",
    "init_db",
    "db_create_job",
    "db_update_job",
    "db_get_job",
    "db_append_log",
    "insert_job_meta",
    "MappingProfile",
    "BankFingerprint",
    "Override",
    "Job",
    "JobMeta",
]
