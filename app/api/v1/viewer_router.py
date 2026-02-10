"""API v1 router for viewer application (public, read-only)."""

from fastapi import APIRouter

from api.v1 import health
from api.v1.streams import list_streams

viewer_router = APIRouter()

# Re-use the list_streams endpoint from the streams module (DRY)
viewer_router.add_api_route(
    "/streams",
    list_streams,
    methods=["GET"],
    tags=["streams"],
)

viewer_router.include_router(health.router)
