"""API v1 router for admin application."""

from fastapi import APIRouter

from api.v1 import auth, health, streams

admin_router = APIRouter()

admin_router.include_router(auth.router)
admin_router.include_router(streams.router)
admin_router.include_router(health.router)
