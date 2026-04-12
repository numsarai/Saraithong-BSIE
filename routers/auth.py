"""
routers/auth.py
---------------
Authentication API routes: login, register, current user, user management.
Security-hardened: rate limiting considerations, admin checks, input validation.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from persistence.base import get_db_session
from services.auth_service import (
    authenticate_user,
    create_token,
    create_user,
    get_user_by_token,
    list_users,
    require_admin,
    require_auth,
    serialize_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)

ALLOWED_ROLES = {"analyst", "viewer", "admin"}


@router.post("/login")
@limiter.limit("10/minute")
async def api_login(request: Request):
    """Authenticate with username/password and receive JWT token."""
    payload = await request.json()
    username = str(payload.get("username", ""))[:128]
    password = str(payload.get("password", ""))[:1024]

    if not username or not password:
        raise HTTPException(400, "username and password required")

    with get_db_session() as session:
        user = authenticate_user(session, username, password)
        if not user:
            raise HTTPException(401, "Invalid credentials")
        if not user.is_active:
            raise HTTPException(403, "Account disabled")

        token = create_token({"sub": user.id, "username": user.username, "role": user.role})
        return JSONResponse({
            "token": token,
            "user": serialize_user(user),
        })


@router.post("/register")
async def api_register(request: Request, _admin=Depends(require_admin)):
    """Create a new user account — requires admin authentication (CRIT-4 fix)."""
    payload = await request.json()
    username = str(payload.get("username", ""))[:128]
    password = str(payload.get("password", ""))[:1024]
    email = str(payload.get("email", ""))[:255]
    role = str(payload.get("role", "analyst"))

    if not username:
        raise HTTPException(400, "username required")
    if role not in ALLOWED_ROLES:
        raise HTTPException(400, f"Invalid role. Must be one of: {ALLOWED_ROLES}")

    with get_db_session() as session:
        try:
            user = create_user(session, username=username, password=password, email=email, role=role)
            return JSONResponse({"user": serialize_user(user)})
        except Exception:
            raise HTTPException(400, "Could not create user. Username may already be taken.")


@router.get("/me")
async def api_current_user(request: Request):
    """Get current authenticated user from JWT token."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = auth[7:]

    with get_db_session() as session:
        user = get_user_by_token(session, token)
        if not user:
            raise HTTPException(401, "Invalid or expired token")
        return JSONResponse({"user": serialize_user(user)})


@router.get("/users")
async def api_list_users(_admin=Depends(require_admin)):
    """List all users — requires admin authentication (CRIT-6 fix)."""
    with get_db_session() as session:
        return JSONResponse({"items": list_users(session)})
