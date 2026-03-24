# database.py — SQLite engine, session factory, table models, and init_db()

from __future__ import annotations
import json
from datetime import datetime
from typing import Optional
from sqlmodel import Field, Session, SQLModel, create_engine
from paths import DB_PATH

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    # WAL mode for concurrent reads + single-writer safety
    echo=False,
)

# ── Models ────────────────────────────────────────────────────────────────────

class MappingProfile(SQLModel, table=True):
    __tablename__ = "mapping_profile"
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: str = Field(index=True, unique=True)
    bank: str = Field(index=True)
    columns_json: str  # JSON list
    columns_signature: str = Field(index=True, unique=True)
    mapping_json: str  # JSON dict
    usage_count: int = Field(default=0)
    last_used: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def columns(self):
        return json.loads(self.columns_json)

    @property
    def mapping(self):
        return json.loads(self.mapping_json)

    def to_dict(self):
        return {
            "profile_id": self.profile_id,
            "bank": self.bank,
            "columns": self.columns,
            "columns_signature": self.columns_signature,
            "mapping": self.mapping,
            "usage_count": self.usage_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Override(SQLModel, table=True):
    __tablename__ = "override"
    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_id: str = Field(index=True, unique=True)
    override_from_account: str
    override_to_account: str
    override_reason: str = Field(default="")
    override_by: str = Field(default="analyst")
    override_timestamp: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self):
        return {
            "transaction_id": self.transaction_id,
            "override_from_account": self.override_from_account,
            "override_to_account": self.override_to_account,
            "override_reason": self.override_reason,
            "override_by": self.override_by,
            "override_timestamp": self.override_timestamp.isoformat() if self.override_timestamp else None,
        }


class Job(SQLModel, table=True):
    __tablename__ = "job"
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True, unique=True)
    status: str = Field(default="queued", index=True)  # queued|running|done|error
    log_text: str = Field(default="")
    result_json: Optional[str] = Field(default=None)  # JSON blob
    error: Optional[str] = Field(default=None)
    account: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JobMeta(SQLModel, table=True):
    __tablename__ = "job_meta"
    id: Optional[int] = Field(default=None, primary_key=True)
    account_number: str = Field(index=True)
    job_id: str = Field(index=True)
    bank: str = Field(default="")
    total_in: float = Field(default=0.0)
    total_out: float = Field(default=0.0)
    total_circulation: float = Field(default=0.0)
    num_transactions: int = Field(default=0)
    date_range: str = Field(default="")
    num_unknown: int = Field(default=0)
    num_partial_accounts: int = Field(default=0)
    report_filename: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Session helpers ───────────────────────────────────────────────────────────

def get_session() -> Session:
    """Return a new SQLModel Session. Caller must close it (use as context manager)."""
    return Session(engine)


def init_db():
    """Create all tables if they do not exist. Safe to call on every startup."""
    # Enable WAL mode for better concurrent access
    with engine.connect() as conn:
        conn.execute(__import__("sqlalchemy").text("PRAGMA journal_mode=WAL"))
        conn.commit()
    SQLModel.metadata.create_all(engine)


# ── Job helper functions (public API) ─────────────────────────────────────────

def db_create_job(job_id: str, account: str = "") -> None:
    """Create a new Job row with status='queued'."""
    from sqlmodel import select
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
    """Update arbitrary fields on an existing Job row."""
    from sqlmodel import select
    with get_session() as session:
        statement = select(Job).where(Job.job_id == job_id)
        job = session.exec(statement).first()
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)
            job.updated_at = datetime.utcnow()
            session.add(job)
            session.commit()


def db_get_job(job_id: str) -> Optional[dict]:
    """Return a dict of job fields, or None if not found."""
    from sqlmodel import select
    with get_session() as session:
        statement = select(Job).where(Job.job_id == job_id)
        job = session.exec(statement).first()
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
    """Append a log line to the job's log_text in DB."""
    from sqlmodel import select
    with get_session() as session:
        statement = select(Job).where(Job.job_id == job_id)
        job = session.exec(statement).first()
        if job:
            existing = job.log_text or ""
            job.log_text = existing + line + "\n"
            job.updated_at = datetime.utcnow()
            session.add(job)
            session.commit()


def insert_job_meta(job_id: str, account_number: str, meta: dict) -> None:
    """Insert a JobMeta summary row after a successful pipeline run."""
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
    except Exception as e:
        _log.warning("Could not insert JobMeta for job %s: %s", job_id, e)
