"""Security utilities for authentication."""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Optional

import bcrypt

from config import settings


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash using constant-time comparison.

    Falls back to a constant-time plain-text comparison for unhashed
    values such as ADMIN_PASS set directly in the environment.
    """
    try:
        # Try bcrypt first
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        # Fallback to constant-time comparison for plain text
        # This handles the case where ADMIN_PASS is a plain text password
        return hmac.compare_digest(password, hashed)


def generate_session_id(username: str) -> str:
    """Generate a secure session ID."""
    timestamp = datetime.now(timezone.utc).isoformat()
    random_bytes = secrets.token_hex(32)
    data = f"{username}:{timestamp}:{random_bytes}"
    return hashlib.sha256(data.encode()).hexdigest()


def generate_nonce() -> str:
    """Generate a CSP nonce."""
    return secrets.token_urlsafe(16)


def should_use_secure_cookie(request_scheme: str, headers: dict) -> bool:
    """Decide whether to set the Secure flag on cookies.

    Browsers reject Secure cookies over plain HTTP, so base the decision on
    how the client actually reached us instead of the debug flag. When behind
    a reverse proxy or tunnel, the request scheme is http but the client
    connection may still be https — check X-Forwarded-Proto in that case.
    """
    if request_scheme == "https":
        return True
    if settings.behind_proxy or settings.cloudflare_tunnel:
        proto = headers.get("x-forwarded-proto", "")
        return proto.split(",")[0].strip() == "https"
    return False


def get_client_ip(
    headers: dict,
    client_host: Optional[str] = None,
    behind_proxy: bool = False,
) -> str:
    """Extract client IP from request headers."""
    if behind_proxy:
        # Check Cloudflare headers first
        if cf_ip := headers.get("cf-connecting-ip"):
            return cf_ip
        # Then X-Real-IP
        if real_ip := headers.get("x-real-ip"):
            return real_ip
        # Then X-Forwarded-For (first IP in chain)
        if forwarded := headers.get("x-forwarded-for"):
            return forwarded.split(",")[0].strip()
    return client_host or "unknown"
