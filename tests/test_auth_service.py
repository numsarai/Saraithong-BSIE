"""Tests for services/auth_service.py."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

from persistence.base import Base
from persistence.models import User
from services.auth_service import (
    create_token,
    create_user,
    decode_token,
    ensure_default_admin,
    hash_password,
    verify_password,
)


def _make_engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'auth.sqlite'}", future=True)
    Base.metadata.create_all(engine)
    SQLModel.metadata.create_all(engine)
    return engine


# ── hash_password / verify_password ──────────────────────────────────


def test_hash_verify_round_trip():
    hashed = hash_password("s3cret")
    assert verify_password("s3cret", hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False


def test_hash_produces_salted_format():
    hashed = hash_password("test")
    assert hashed.startswith("pbkdf2$")
    parts = hashed.split("$")
    assert len(parts) == 3  # pbkdf2$salt$hash
    assert len(parts[1]) == 32  # 16 bytes hex = 32 chars


def test_hash_is_unique_per_call():
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2  # different salts


def test_verify_rejects_malformed_hash():
    assert verify_password("test", "no-dollar-sign") is False


# ── create_token / decode_token ──────────────────────────────────────


def test_token_round_trip():
    data = {"sub": "user-123", "role": "analyst"}
    token = create_token(data, expires_minutes=60)
    decoded = decode_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user-123"
    assert decoded["role"] == "analyst"
    assert "exp" in decoded


def test_decode_invalid_token():
    result = decode_token("not.a.valid.jwt.token")
    assert result is None


def test_decode_empty_string():
    result = decode_token("")
    assert result is None


def test_token_contains_expiration():
    token = create_token({"sub": "u1"}, expires_minutes=30)
    decoded = decode_token(token)
    assert decoded is not None
    assert "exp" in decoded


# ── ensure_default_admin ─────────────────────────────────────────────


def test_ensure_default_admin_creates_admin_when_empty(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BSIE_ADMIN_USERNAME", "testadmin")
    monkeypatch.setenv("BSIE_ADMIN_INITIAL_PASSWORD", "testpw123")
    engine = _make_engine(tmp_path)

    with Session(engine) as session:
        ensure_default_admin(session)

    with Session(engine) as session:
        users = session.scalars(select(User)).all()
    assert len(users) == 1
    assert users[0].username == "testadmin"
    assert users[0].role == "admin"


def test_ensure_default_admin_skips_when_users_exist(tmp_path: Path):
    engine = _make_engine(tmp_path)

    with Session(engine) as session:
        create_user(session, username="existing", password="pw", role="analyst")

    with Session(engine) as session:
        ensure_default_admin(session)

    with Session(engine) as session:
        users = session.scalars(select(User)).all()
    assert len(users) == 1
    assert users[0].username == "existing"


def test_ensure_default_admin_is_idempotent(tmp_path: Path):
    engine = _make_engine(tmp_path)

    with Session(engine) as session:
        ensure_default_admin(session)
    with Session(engine) as session:
        ensure_default_admin(session)

    with Session(engine) as session:
        users = session.scalars(select(User)).all()
    assert len(users) == 1


def test_default_admin_password_verifies(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BSIE_ADMIN_USERNAME", "testadmin")
    monkeypatch.setenv("BSIE_ADMIN_INITIAL_PASSWORD", "test-admin-pw-123")
    engine = _make_engine(tmp_path)

    with Session(engine) as session:
        ensure_default_admin(session)

    with Session(engine) as session:
        admin = session.scalars(select(User).where(User.username == "testadmin")).first()
    assert admin is not None
    assert admin.hashed_password is not None
    assert verify_password("test-admin-pw-123", admin.hashed_password) is True
