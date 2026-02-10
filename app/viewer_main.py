"""FastAPI application entry point for Caos Vision Viewer (Public Stream Display)."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.deps import get_stream_service
from api.v1.viewer_router import viewer_router
from api.websocket import init_broadcast, start_pubsub_listener, websocket_router
from config import settings
from core.exceptions import setup_exception_handlers
from core.middleware import setup_middleware
from services.redis_service import RedisService
from services.stream_service import StreamService

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
    logger.info("Starting %s Viewer...", settings.app_name)
    try:
        app.state.redis = await RedisService.create(settings.redis_url)
        init_broadcast(app.state.redis)
        logger.info("Viewer application started successfully")
    except Exception as e:
        logger.error("Failed to connect to Redis: %s", e)
        raise

    # Start Pub/Sub listener as background task
    pubsub_task = asyncio.create_task(start_pubsub_listener(app.state.redis))

    yield

    # Shutdown
    logger.info("Shutting down Viewer...")
    pubsub_task.cancel()
    try:
        await pubsub_task
    except asyncio.CancelledError:
        pass
    await app.state.redis.close()
    logger.info("Viewer application stopped")


# Create FastAPI application
app = FastAPI(
    title=f"{settings.app_name} Viewer",
    description="Public video wall viewer",
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
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API router (streams GET + health)
app.include_router(viewer_router, prefix="/api/v1")

# Include WebSocket router (only /ws/viewer will be used here)
app.include_router(websocket_router)

# Setup templates
templates = Jinja2Templates(directory="templates")


# Page routes


@app.get("/", response_class=HTMLResponse)
async def viewer_page(
    request: Request,
    stream_service: StreamService = Depends(get_stream_service),
) -> HTMLResponse:
    """Public viewer page with video grid."""
    streams = await stream_service.get_all_streams()
    layout = StreamService.calculate_layout(len(streams))

    return templates.TemplateResponse(
        "viewer.html",
        {
            "request": request,
            "streams": streams,
            "layout": layout,
            "app_name": settings.app_name,
        },
    )
