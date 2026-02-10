"""Security utilities for authentication."""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Optional

import bcrypt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash using constant-time comparison.

    Also supports legacy SHA-256 hashes for backward compatibility with
    plain-text passwords in environment variables.
    """
    try:
        # Try bcrypt first
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        # Fallback to constant-time comparison for plain text or SHA-256
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


class CSRFProtection:
    """CSRF token generation and validation."""

    def __init__(self, secret_key: str):
        self.serializer = URLSafeTimedSerializer(secret_key)

    def generate_token(self, session_id: str) -> str:
        """Generate a CSRF token tied to the session."""
        return self.serializer.dumps(session_id, salt="csrf-token")

    def validate_token(self, token: str, session_id: str, max_age: int = 3600) -> bool:
        """Validate CSRF token."""
        try:
            data = self.serializer.loads(token, salt="csrf-token", max_age=max_age)
            return hmac.compare_digest(data, session_id)
        except (BadSignature, SignatureExpired):
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
