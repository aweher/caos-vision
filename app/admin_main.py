"""FastAPI application entry point for Caos Vision Admin (Stream Manager)."""

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.deps import get_current_session, get_stream_service
from api.v1.admin_router import admin_router
from api.websocket import init_broadcast, start_pubsub_listener, websocket_router
from config import settings
from core.exceptions import setup_exception_handlers
from core.middleware import setup_middleware
from models.auth import SessionInfo
from services.redis_service import RedisService
from services.stream_service import StreamService

BASE_DIR = Path(__file__).resolve().parent

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting %s Admin...", settings.app_name)
    if not settings.debug:
        if settings.admin_pass == "admin":
            logger.warning("ADMIN_PASS is using the default value 'admin' in production")
        if settings.secret_key == "change-me-in-production":
            logger.warning("SECRET_KEY is using the default value in production")
    try:
        app.state.redis = await RedisService.create(settings.redis_url)
        init_broadcast(app.state.redis)
        logger.info("Admin application started successfully")
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        raise

    # Start Pub/Sub listener as background task
    pubsub_task = asyncio.create_task(start_pubsub_listener(app.state.redis))

    yield

    # Shutdown
    logger.info("Shutting down Admin...")
    pubsub_task.cancel()
    try:
        await pubsub_task
    except asyncio.CancelledError:
        pass
    await app.state.redis.close()
    logger.info("Admin application stopped")


# Create FastAPI application
app = FastAPI(
    title=f"{settings.app_name} Admin",
    description="Admin panel for managing video streams",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.debug else None,
    redoc_url="/api/redoc" if settings.debug else None,
)

# Setup middleware
setup_middleware(app)

# Setup exception handlers
setup_exception_handlers(app)

# Mount static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# Include API router (auth + streams + health)
app.include_router(admin_router, prefix="/api/v1")

# Include WebSocket router (only /ws/admin will be used here)
app.include_router(websocket_router)

# Setup templates
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# Page routes


@app.get("/", response_class=HTMLResponse, response_model=None)
async def root_redirect():
    """Redirect root to admin page."""
    return RedirectResponse(url="/admin", status_code=302)


@app.get("/login", response_class=HTMLResponse, response_model=None)
async def login_page(
    request: Request,
    session: Optional[SessionInfo] = Depends(get_current_session),
):
    """Login page."""
    # Redirect if already logged in
    if session and session.authenticated:
        return RedirectResponse(url="/admin", status_code=302)

    # Generate CSRF token using double-submit cookie pattern
    csrf_token = secrets.token_urlsafe(32)

    response = templates.TemplateResponse(
        request,
        "login.html",
        {
            "app_name": settings.app_name,
            "csrf_token": csrf_token,
            "viewer_url": settings.viewer_url,
        },
    )

    # Set CSRF cookie (double-submit pattern)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,  # JS needs to read it
        secure=not settings.debug,
        samesite="strict",
        max_age=600,  # 10 minutes
        path="/",
    )

    return response


@app.get("/admin", response_class=HTMLResponse, response_model=None)
async def admin_page(
    request: Request,
    session: Optional[SessionInfo] = Depends(get_current_session),
    stream_service: StreamService = Depends(get_stream_service),
):
    """Admin control panel. Requires authentication."""
    # Redirect to login if not authenticated
    if not session or not session.authenticated:
        return RedirectResponse(url="/login", status_code=302)

    streams = await stream_service.get_all_streams()
    layout = StreamService.calculate_layout(len(streams))

    return templates.TemplateResponse(
        request,
        "admin.html",
        {
            "streams": streams,
            "layout": layout,
            "session": session,
            "app_name": settings.app_name,
            "viewer_url": settings.viewer_url,
        },
    )
