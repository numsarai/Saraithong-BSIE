from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlmodel import Session as SQLModelSession, SQLModel

from paths import DB_PATH

if "pytest" not in sys.modules and not os.getenv("PYTEST_CURRENT_TEST"):
    load_dotenv()


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def is_local_only_mode() -> bool:
    """Runtime compatibility helper: BSIE is permanently local-only."""
    return True


def get_database_url() -> tuple[str, str]:
    """Return the fixed local SQLite runtime URL and its source."""
    return f"sqlite:///{DB_PATH}", "local_sqlite"


DATABASE_URL, DATABASE_RUNTIME_SOURCE = get_database_url()
IS_SQLITE = True

engine = create_engine(
    DATABASE_URL,
    future=True,
    echo=False,
    pool_pre_ping=False,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)

LegacySessionLocal = sessionmaker(
    bind=engine,
    class_=SQLModelSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for new SQLAlchemy declarative models."""


@contextmanager
def get_db_session() -> Iterator[Session]:
    """Yield a SQLAlchemy ORM session for new persistence services."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_legacy_session() -> SQLModelSession:
    """Return a SQLModel-compatible session for existing callers."""
    return LegacySessionLocal()


def init_database() -> None:
    """Create runtime tables for both new persistence models and legacy compatibility tables."""
    from persistence import models  # noqa: F401
    from persistence import legacy_models  # noqa: F401

    if IS_SQLITE:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()

    Base.metadata.create_all(engine)
    SQLModel.metadata.create_all(engine)
