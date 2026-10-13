"""Custom exceptions and exception handlers."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
import logging

logger = logging.getLogger(__name__)


class CaosVisionException(Exception):
    """Base exception for Caos Vision."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(CaosVisionException):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401)


class RateLimitError(CaosVisionException):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int = 300):
        self.retry_after = retry_after
        super().__init__(
            f"Too many attempts. Try again in {retry_after} seconds.",
            status_code=429,
        )


class StreamLimitError(CaosVisionException):
    """Maximum number of streams reached."""

    def __init__(self, max_streams: int):
        super().__init__(
            f"Límite máximo de streams alcanzado ({max_streams})",
            status_code=429,
        )


class StreamNotFoundError(CaosVisionException):
    """Stream not found."""

    def __init__(self, stream_id: str):
        super().__init__(f"Stream not found: {stream_id}", status_code=404)


class InvalidURLError(CaosVisionException):
    """Invalid or unsupported URL."""

    def __init__(self, message: str = "Invalid or unsupported URL"):
        super().__init__(message, status_code=400)


class DuplicateStreamError(CaosVisionException):
    """Stream already exists."""

    def __init__(self, message: str = "Stream already exists"):
        super().__init__(message, status_code=409)


def setup_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers with the FastAPI app."""

    @app.exception_handler(CaosVisionException)
    async def caos_exception_handler(
        request: Request, exc: CaosVisionException
    ) -> JSONResponse:
        logger.warning("CaosVisionException: %s", exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(RateLimitError)
    async def rate_limit_handler(
        request: Request, exc: RateLimitError
    ) -> JSONResponse:
        client_host = getattr(request.client, "host", None)
        logger.warning("Rate limit exceeded for %s", client_host)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
            headers={"Retry-After": str(exc.retry_after)},
        )

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(
        request: Request, exc: AuthenticationError
    ) -> JSONResponse | RedirectResponse:
        # For API requests, return JSON
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.message},
            )
        # For page requests, redirect to login
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
