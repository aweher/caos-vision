"""Dependency injection for API endpoints."""

import re
from typing import Optional

from fastapi import Cookie, Depends, Request

from core.exceptions import AuthenticationError
from core.security import get_client_ip
from config import settings
from models.auth import SessionInfo
from services.redis_service import RedisService
from services.session_service import SessionService
from services.stream_service import StreamService

_HOST_HEADER_RE = re.compile(r"^[A-Za-z0-9.-]+$|^\[[0-9A-Fa-f:]+\]$")


def sanitize_host(raw_host: Optional[str], fallback: Optional[str]) -> str:
    """Return raw_host if it is a valid hostname/IP, else the fallback."""
    if raw_host:
        candidate = raw_host.strip()
        if _HOST_HEADER_RE.fullmatch(candidate):
            return candidate
    return fallback or "localhost"


async def get_redis(request: Request) -> RedisService:
    """Get Redis service from app state."""
    return request.app.state.redis


async def get_session_service(
    redis: RedisService = Depends(get_redis),
) -> SessionService:
    """Get session service."""
    return SessionService(redis)


async def get_stream_service(
    request: Request,
    redis: RedisService = Depends(get_redis),
) -> StreamService:
    """Get stream service with proper host for embed URLs."""
    raw_host = request.headers.get("host")
    host = sanitize_host(raw_host, request.url.hostname)
    return StreamService(redis, host=host)


async def get_client_ip_dep(request: Request) -> str:
    """Get client IP from request."""
    return get_client_ip(
        dict(request.headers),
        client_host=request.client.host if request.client else None,
        behind_proxy=settings.behind_proxy or settings.cloudflare_tunnel,
    )


async def get_current_session(
    session_id: Optional[str] = Cookie(default=None),
    session_service: SessionService = Depends(get_session_service),
) -> Optional[SessionInfo]:
    """Get current session if valid."""
    if not session_id:
        return None
    return await session_service.validate_session(session_id)


async def require_auth(
    session: Optional[SessionInfo] = Depends(get_current_session),
) -> SessionInfo:
    """Require valid authentication. Raises AuthenticationError if not authenticated."""
    if not session or not session.authenticated:
        raise AuthenticationError()
    return session
