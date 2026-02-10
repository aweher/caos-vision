"""Custom middleware for security and request processing."""

import logging
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from core.security import generate_nonce

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Generate CSP nonce BEFORE processing request so templates can use it
        nonce = generate_nonce()
        request.state.csp_nonce = nonce

        response = await call_next(request)

        # Check if behind Cloudflare
        behind_cloudflare = bool(request.headers.get("cf-ray"))

        # Build CSP directives
        csp_parts = [
            "default-src 'self'",
            f"script-src 'self' 'nonce-{nonce}'",
            "style-src 'self' 'unsafe-inline'",
            (
                "img-src 'self' data: https://i.ytimg.com "
                "https://static-cdn.jtvnw.net https://i.vimeocdn.com"
            ),
            (
                "frame-src 'self' https://www.youtube.com "
                "https://www.youtube-nocookie.com https://player.twitch.tv "
                "https://player.vimeo.com"
            ),
            "connect-src 'self' wss: ws:",
            "font-src 'self'",
            "form-action 'self'",
            "base-uri 'self'",
            "object-src 'none'",
        ]

        if not behind_cloudflare:
            csp_parts.append("frame-ancestors 'none'")

        response.headers["Content-Security-Policy"] = "; ".join(csp_parts)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = (
            "SAMEORIGIN" if behind_cloudflare else "DENY"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

        return response


def setup_middleware(app: FastAPI) -> None:
    """Setup all middleware for the application."""

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_allowed_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["*"],
    )

    # Security headers middleware
    app.add_middleware(SecurityHeadersMiddleware)

    logger.info("Middleware configured")
