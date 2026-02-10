"""Health check endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.deps import get_redis
from services.redis_service import RedisService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health() -> dict:
    """Basic health check."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    redis: RedisService = Depends(get_redis),
) -> JSONResponse:
    """Readiness probe - checks Redis connection.

    Returns 503 if Redis is unavailable so orchestrators detect unhealthy state.
    """
    redis_ok = await redis.ping()
    if not redis_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "redis": "disconnected"},
        )
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "redis": "connected"},
    )
