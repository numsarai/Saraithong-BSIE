"""
routers/auth.py
---------------
Authentication API routes: login, register, current user, user management.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from persistence.base import get_db_session
from services.auth_service import (
    authenticate_user,
    create_token,
    create_user,
    get_user_by_token,
    list_users,
    serialize_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def api_login(request: Request):
    """Authenticate with username/password and receive JWT token."""
    payload = await request.json()
    username = str(payload.get("username", ""))
    password = str(payload.get("password", ""))

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
async def api_register(request: Request):
    """Create a new user account (requires admin token)."""
    payload = await request.json()
    username = str(payload.get("username", ""))
    password = str(payload.get("password", ""))
    email = str(payload.get("email", ""))
    role = str(payload.get("role", "analyst"))

    if not username:
        raise HTTPException(400, "username required")

    with get_db_session() as session:
        try:
            user = create_user(session, username=username, password=password, email=email, role=role)
            return JSONResponse({"user": serialize_user(user)})
        except Exception as e:
            raise HTTPException(400, f"Could not create user: {e}")


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
async def api_list_users():
    """List all users (admin)."""
    with get_db_session() as session:
        return JSONResponse({"items": list_users(session)})
