"""Session management service."""

import hmac
import logging
from datetime import datetime, timezone
from typing import Optional

from config import settings
from core.exceptions import AuthenticationError, RateLimitError
from core.security import generate_session_id, verify_password
from models.auth import LoginRequest, SessionInfo
from services.redis_service import RedisService

logger = logging.getLogger(__name__)


class SessionService:
    """Service for managing user sessions."""

    def __init__(self, redis: RedisService) -> None:
        self.redis = redis

    async def authenticate(
        self, credentials: LoginRequest, client_ip: str
    ) -> tuple[str, SessionInfo]:
        """Authenticate user and create session.

        Returns:
            Tuple of (session_id, session_info)

        Raises:
            RateLimitError: If too many failed attempts
            AuthenticationError: If credentials are invalid
        """
        # Atomically check and increment rate limit
        allowed, retry_after = await self.redis.check_and_increment_rate_limit(
            client_ip,
            max_attempts=settings.rate_limit_attempts,
            window=settings.rate_limit_window,
        )

        if not allowed:
            logger.warning("Rate limit exceeded for IP: %s", client_ip)
            raise RateLimitError(retry_after=retry_after)

        # Verify credentials using constant-time comparison
        username_valid = hmac.compare_digest(
            credentials.username.encode(), settings.admin_user.encode()
        )
        password_valid = verify_password(credentials.password, settings.admin_pass)

        if not (username_valid and password_valid):
            logger.warning("Failed login attempt from IP: %s", client_ip)
            raise AuthenticationError("Invalid username or password")

        # Reset rate limit on successful login
        await self.redis.reset_rate_limit(client_ip)

        # Create session
        session_id = generate_session_id(credentials.username)
        session_info = SessionInfo(
            authenticated=True,
            username=credentials.username,
            login_time=datetime.now(timezone.utc),
            ip=client_ip,
        )

        await self.redis.save_session(
            session_id,
            session_info.model_dump(mode="json"),
            expiry=settings.session_expire_seconds,
        )

        logger.info("User %s logged in from %s", credentials.username, client_ip)
        return session_id, session_info

    async def validate_session(self, session_id: Optional[str]) -> Optional[SessionInfo]:
        """Validate session and return session info."""
        if not session_id:
            return None

        session_data = await self.redis.get_session(session_id)
        if not session_data:
            return None

        # Refresh session expiry
        await self.redis.refresh_session(
            session_id, expiry=settings.session_expire_seconds
        )

        return SessionInfo(**session_data)

    async def logout(self, session_id: str) -> bool:
        """Invalidate session."""
        result = await self.redis.delete_session(session_id)
        if result:
            logger.info("Session invalidated: %s...", session_id[:8])
        return result
