"""Authentication API endpoints."""

import hmac
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status

from api.deps import (
    get_client_ip_dep,
    get_current_session,
    get_session_service,
    require_auth,
)
from config import settings
from models.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    SessionInfo,
)
from services.session_service import SessionService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    credentials: LoginRequest,
    response: Response,
    x_csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token"),
    csrf_token: Optional[str] = Cookie(None),
    client_ip: str = Depends(get_client_ip_dep),
    session_service: SessionService = Depends(get_session_service),
) -> LoginResponse:
    """Authenticate and create session."""
    # Validate CSRF token (double-submit cookie pattern)
    if not x_csrf_token or not csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing",
        )

    if not hmac.compare_digest(x_csrf_token, csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token invalid",
        )

    session_id, _ = await session_service.authenticate(credentials, client_ip)

    # Set session cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
        max_age=settings.session_expire_seconds,
        path="/",
    )

    # Clear CSRF token cookie after successful login
    response.delete_cookie(key="csrf_token", path="/")

    return LoginResponse(message="Login successful", redirect_url="/admin")


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    session_id: Optional[str] = Cookie(default=None),
    session: SessionInfo = Depends(require_auth),
    session_service: SessionService = Depends(get_session_service),
) -> LogoutResponse:
    """Invalidate server-side session and logout."""
    if session_id:
        await session_service.logout(session_id)
    response.delete_cookie(key="session_id", path="/")

    return LogoutResponse(message="Logout successful")


@router.get("/me", response_model=SessionInfo)
async def get_me(
    session: SessionInfo = Depends(get_current_session),
) -> SessionInfo:
    """Get current session info."""
    if not session:
        return SessionInfo(authenticated=False)
    return session
