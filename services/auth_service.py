"""
auth_service.py
---------------
User authentication — JWT tokens, password hashing, user management.
OAuth support via provider/id fields (callback handling separate).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import hashlib
import hmac
import logging
import secrets

from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.base import utcnow
from persistence.models import User

_logger = logging.getLogger(__name__)

# CRIT-2 fix: No hardcoded default — auto-generate ephemeral secret in dev
_jwt_secret_env = os.getenv("BSIE_JWT_SECRET", "")
if not _jwt_secret_env:
    _jwt_secret_env = secrets.token_hex(32)
    _logger.warning("BSIE_JWT_SECRET not set — generated ephemeral secret. Set in .env for production!")
SECRET_KEY = _jwt_secret_env
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.getenv("BSIE_TOKEN_EXPIRE_MINUTES", "120"))  # 2 hours (reduced from 8)


def hash_password(password: str) -> str:
    """Hash password with PBKDF2-SHA256 (100k iterations) — HIGH-1 fix."""
    if len(password) > 1024:
        raise ValueError("Password too long")
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"pbkdf2${salt}${h}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password — supports PBKDF2 (new) and SHA-256 (legacy)."""
    if len(plain) > 1024:
        return False
    if hashed.startswith("pbkdf2$"):
        _, salt, expected = hashed.split("$", 2)
        h = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 100_000).hex()
        return hmac.compare_digest(h, expected)
    # Legacy SHA-256 fallback
    if "$" not in hashed:
        return False
    salt, expected = hashed.split("$", 1)
    h = hashlib.sha256(f"{salt}:{plain}".encode()).hexdigest()
    return hmac.compare_digest(h, expected)


def create_token(data: dict[str, Any], expires_minutes: int = TOKEN_EXPIRE_MINUTES) -> str:
    payload = {**data, "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def create_user(
    session: Session,
    *,
    username: str,
    password: str = "",
    email: str = "",
    role: str = "analyst",
    oauth_provider: str = "",
    oauth_id: str = "",
) -> User:
    """Create a new user account."""
    user = User(
        username=username,
        email=email or None,
        hashed_password=hash_password(password) if password else None,
        role=role,
        is_active=True,
        oauth_provider=oauth_provider or None,
        oauth_id=oauth_id or None,
        created_at=utcnow(),
    )
    session.add(user)
    session.commit()
    return user


def authenticate_user(session: Session, username: str, password: str) -> User | None:
    """Verify username/password and return user if valid."""
    user = session.scalars(select(User).where(User.username == username)).first()
    if not user or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    user.last_login_at = utcnow()
    session.add(user)
    session.commit()
    return user


def get_user_by_token(session: Session, token: str) -> User | None:
    """Decode JWT token and return the corresponding user."""
    payload = decode_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return session.get(User, user_id)


def list_users(session: Session) -> list[dict[str, Any]]:
    """List all users (admin function)."""
    users = session.scalars(select(User).order_by(User.created_at.asc())).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email or "",
            "role": u.role,
            "is_active": u.is_active,
            "oauth_provider": u.oauth_provider or "",
            "created_at": str(u.created_at),
            "last_login_at": str(u.last_login_at) if u.last_login_at else None,
        }
        for u in users
    ]


def ensure_default_admin(session: Session) -> None:
    """Create a default admin user if no users exist. CRIT-3 fix: random password."""
    count = session.scalar(select(User.id).limit(1))
    if count:
        return
    initial_username = os.getenv("BSIE_ADMIN_USERNAME", "admin")
    initial_pw = os.getenv("BSIE_ADMIN_INITIAL_PASSWORD", "")
    if not initial_pw:
        initial_pw = secrets.token_urlsafe(16)
        # Print to stderr only — never to log file
        import sys
        print("=" * 60, file=sys.stderr)
        print(f"  DEFAULT ADMIN CREATED", file=sys.stderr)
        print(f"  Username: {initial_username}", file=sys.stderr)
        print(f"  Password: {initial_pw}", file=sys.stderr)
        print(f"  CHANGE THIS PASSWORD IMMEDIATELY!", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        _logger.warning("Default admin user '%s' created — password shown in stderr only", initial_username)
    else:
        _logger.info("Admin user '%s' created with configured password", initial_username)
    create_user(
        session,
        username=initial_username,
        password=initial_pw,
        email="admin@bsie.local",
        role="admin",
    )


def serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email or "",
        "role": user.role,
        "is_active": user.is_active,
    }


# ── FastAPI Dependency for protected routes ──────────────────────────────

AUTH_REQUIRED = os.getenv("BSIE_AUTH_REQUIRED", "").strip().lower() in ("1", "true", "yes")


async def get_current_user_optional(request: Any) -> User | None:
    """Extract current user from JWT if present. Returns None if auth disabled or no token."""
    if not AUTH_REQUIRED:
        return None
    auth = getattr(request, "headers", {}).get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    from persistence.base import get_db_session
    with get_db_session() as session:
        return get_user_by_token(session, token)


async def require_auth(request: Any) -> User | None:
    """Dependency that enforces authentication when BSIE_AUTH_REQUIRED=true."""
    if not AUTH_REQUIRED:
        return None  # Auth disabled — allow all
    user = await get_current_user_optional(request)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(401, "Authentication required")
    return user


async def require_admin(request: Any) -> User | None:
    """Dependency that enforces admin role when auth is enabled."""
    user = await require_auth(request)
    if user and user.role != "admin":
        from fastapi import HTTPException
        raise HTTPException(403, "Admin access required")
    return user
