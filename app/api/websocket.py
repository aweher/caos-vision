"""WebSocket endpoints and connection management."""

import asyncio
import json
import logging
from typing import Optional, Set, Tuple

from fastapi import APIRouter, Cookie, WebSocket, WebSocketDisconnect

from api.deps import sanitize_host
from models.stream import StreamResponse
from models.websocket import (
    ErrorMessage,
    ForceRefreshMessage,
    StreamAddedMessage,
    StreamMutedMessage,
    StreamRemovedMessage,
    StreamSpotlightMessage,
    StreamUpdateMessage,
)
from services.redis_service import RedisService
from services.session_service import SessionService
from services.stream_service import StreamService

logger = logging.getLogger(__name__)

websocket_router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for viewers and admins."""

    def __init__(self) -> None:
        self.viewer_connections: Set[WebSocket] = set()
        self.admin_connections: Set[WebSocket] = set()

    async def connect_viewer(self, websocket: WebSocket) -> None:
        """Accept and track a viewer connection."""
        await websocket.accept()
        self.viewer_connections.add(websocket)
        logger.debug(
            "Viewer connected. Total viewers: %s", len(self.viewer_connections)
        )

    async def connect_admin(self, websocket: WebSocket) -> None:
        """Accept and track an admin connection."""
        await websocket.accept()
        self.admin_connections.add(websocket)
        logger.debug(
            "Admin connected. Total admins: %s", len(self.admin_connections)
        )

    def disconnect_viewer(self, websocket: WebSocket) -> None:
        """Remove a viewer connection."""
        self.viewer_connections.discard(websocket)
        logger.debug(
            "Viewer disconnected. Total viewers: %s", len(self.viewer_connections)
        )

    def disconnect_admin(self, websocket: WebSocket) -> None:
        """Remove an admin connection."""
        self.admin_connections.discard(websocket)
        logger.debug(
            "Admin disconnected. Total admins: %s", len(self.admin_connections)
        )

    async def broadcast_to_all(self, message: dict) -> None:
        """Broadcast message to all connected clients (viewers and admins)."""
        all_connections = self.viewer_connections | self.admin_connections
        await self._broadcast(all_connections, message)

    async def broadcast_to_viewers(self, message: dict) -> None:
        """Broadcast message only to viewers."""
        await self._broadcast(self.viewer_connections, message)

    async def broadcast_to_admins(self, message: dict) -> None:
        """Broadcast message only to admins."""
        await self._broadcast(self.admin_connections, message)

    async def _broadcast(self, connections: Set[WebSocket], message: dict) -> None:
        """Send message to a set of connections."""
        disconnected = []
        for connection in set(connections):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.viewer_connections.discard(conn)
            self.admin_connections.discard(conn)

    @property
    def viewer_count(self) -> int:
        return len(self.viewer_connections)

    @property
    def admin_count(self) -> int:
        return len(self.admin_connections)


# Global connection manager (per-process; Redis Pub/Sub bridges across services)
manager = ConnectionManager()

# Module-level reference to redis, set during app lifespan via init_broadcast()
_redis: Optional[RedisService] = None


def init_broadcast(redis: RedisService) -> None:
    """Initialize the broadcast system with a Redis instance.

    Must be called during app startup (lifespan) before any broadcasts.
    """
    global _redis
    _redis = redis


# --- Broadcast helper functions (called from API endpoints) ---
# These publish to Redis Pub/Sub so ALL services receive the message.


async def broadcast_stream_added(
    stream: StreamResponse, layout: Tuple[int, int]
) -> None:
    """Broadcast stream added event to all clients across all services."""
    message = StreamAddedMessage(stream=stream, layout=layout)
    await _publish_broadcast(message.model_dump(), target="all")


async def broadcast_stream_removed(
    stream_id: str, layout: Tuple[int, int]
) -> None:
    """Broadcast stream removed event to all clients across all services."""
    message = StreamRemovedMessage(stream_id=stream_id, layout=layout)
    await _publish_broadcast(message.model_dump(), target="all")


async def broadcast_stream_muted(stream_id: str, muted: bool) -> None:
    """Broadcast stream mute state change to all clients across all services."""
    message = StreamMutedMessage(stream_id=stream_id, muted=muted)
    await _publish_broadcast(message.model_dump(), target="all")


async def broadcast_full_update(
    streams: list[StreamResponse], layout: Tuple[int, int]
) -> None:
    """Broadcast full stream list update to all clients across all services."""
    spotlight = await _redis.get_spotlight() if _redis is not None else None
    message = StreamUpdateMessage(streams=streams, layout=layout, spotlight=spotlight)
    await _publish_broadcast(message.model_dump(), target="all")


async def broadcast_stream_spotlight(stream_id: Optional[str]) -> None:
    """Broadcast stream spotlight (fullscreen) command to all clients across all services."""
    message = StreamSpotlightMessage(stream_id=stream_id)
    await _publish_broadcast(message.model_dump(), target="all")


async def broadcast_force_refresh() -> None:
    """Broadcast force refresh command to all viewers across all services."""
    message = ForceRefreshMessage()
    await _publish_broadcast(message.model_dump(), target="viewers")


async def _publish_broadcast(message: dict, target: str = "all") -> None:
    """Publish a broadcast message to the Redis Pub/Sub channel.

    Args:
        message: The WebSocket message dict to broadcast.
        target: 'all' to broadcast to all clients, 'viewers' for viewers only.
    """
    if _redis is None:
        logger.warning("Broadcast called before init_broadcast(); falling back to local")
        if target == "viewers":
            await manager.broadcast_to_viewers(message)
        else:
            await manager.broadcast_to_all(message)
        return

    envelope = json.dumps({"target": target, "payload": message})
    await _redis.publish(RedisService.BROADCAST_CHANNEL, envelope)


# --- Pub/Sub listener (runs as background task per service) ---


async def start_pubsub_listener(redis: RedisService) -> None:
    """Subscribe to the Redis broadcast channel and forward messages to local
    WebSocket connections. Intended to run as a background asyncio task.

    Reconnects automatically on errors.
    """
    while True:
        try:
            pubsub = await redis.subscribe(RedisService.BROADCAST_CHANNEL)
            logger.info("Pub/Sub listener started on channel: %s", RedisService.BROADCAST_CHANNEL)

            async for raw_message in pubsub.listen():
                if raw_message["type"] != "message":
                    continue

                try:
                    envelope = json.loads(raw_message["data"])
                    target = envelope.get("target", "all")
                    payload = envelope.get("payload", {})

                    if target == "viewers":
                        await manager.broadcast_to_viewers(payload)
                    else:
                        await manager.broadcast_to_all(payload)
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.warning("Invalid Pub/Sub message: %s", exc)

        except asyncio.CancelledError:
            logger.info("Pub/Sub listener cancelled, shutting down")
            raise
        except Exception as exc:
            logger.error("Pub/Sub listener error, reconnecting in 2s: %s", exc)
            await asyncio.sleep(2)


# --- WebSocket endpoint handlers ---


@websocket_router.websocket("/ws/viewer")
async def viewer_websocket(
    websocket: WebSocket,
) -> None:
    """WebSocket endpoint for viewers (public, no auth required)."""
    redis: RedisService = websocket.app.state.redis
    host = sanitize_host(websocket.headers.get("host"), websocket.url.hostname)
    stream_service = StreamService(redis, host=host)

    await manager.connect_viewer(websocket)

    try:
        # Send initial state
        streams = await stream_service.get_all_streams()
        layout = StreamService.calculate_layout(len(streams))
        spotlight = await redis.get_spotlight()

        await websocket.send_json(
            StreamUpdateMessage(
                streams=streams, layout=layout, spotlight=spotlight
            ).model_dump()
        )

        # Keep connection alive and handle client messages
        awaiting_pong = False
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30)
            except asyncio.TimeoutError:
                if awaiting_pong:
                    logger.debug("Viewer WebSocket missed pong, closing connection")
                    try:
                        await websocket.close()
                    except Exception:
                        pass
                    break
                try:
                    await websocket.send_json({"type": "ping"})
                    awaiting_pong = True
                except Exception:
                    break
                continue
            except json.JSONDecodeError:
                await websocket.close(code=1003)
                break

            if not isinstance(data, dict):
                await websocket.close(code=1003)
                break

            msg_type = data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "pong":
                awaiting_pong = False

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("Viewer WebSocket error: %s", e)
    finally:
        manager.disconnect_viewer(websocket)


@websocket_router.websocket("/ws/admin")
async def admin_websocket(
    websocket: WebSocket,
    session_id: Optional[str] = Cookie(default=None),
) -> None:
    """WebSocket endpoint for admins (requires authentication)."""
    redis: RedisService = websocket.app.state.redis

    # Validate session
    if not session_id:
        await websocket.close(code=4001, reason="Authentication required")
        return

    session_service = SessionService(redis)
    session = await session_service.validate_session(session_id)

    if not session or not session.authenticated:
        await websocket.close(code=4001, reason="Invalid session")
        return

    host = sanitize_host(websocket.headers.get("host"), websocket.url.hostname)
    stream_service = StreamService(redis, host=host)

    await manager.connect_admin(websocket)

    try:
        # Send initial state
        streams = await stream_service.get_all_streams()
        layout = StreamService.calculate_layout(len(streams))
        spotlight = await redis.get_spotlight()

        await websocket.send_json(
            StreamUpdateMessage(
                streams=streams, layout=layout, spotlight=spotlight
            ).model_dump()
        )

        # Handle client messages
        missed_pings = 0
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60)
            except asyncio.TimeoutError:
                missed_pings += 1
                if missed_pings >= 2:
                    logger.debug("Admin WebSocket missed pongs, closing connection")
                    try:
                        await websocket.close()
                    except Exception:
                        pass
                    break
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
                continue
            except json.JSONDecodeError:
                await websocket.close(code=1003)
                break

            if not isinstance(data, dict):
                await websocket.close(code=1003)
                break

            missed_pings = 0
            msg_type = data.get("type")

            if msg_type == "request_refresh":
                streams = await stream_service.get_all_streams()
                layout = StreamService.calculate_layout(len(streams))
                spotlight = await redis.get_spotlight()
                await websocket.send_json(
                    StreamUpdateMessage(
                        streams=streams, layout=layout, spotlight=spotlight
                    ).model_dump()
                )
            elif msg_type == "force_viewer_refresh":
                await broadcast_force_refresh()
                logger.info("Admin triggered force refresh for all viewers")
            elif msg_type == "spotlight_stream":
                stream_id = data.get("stream_id")  # None to clear spotlight
                if stream_id is not None and not isinstance(stream_id, str):
                    await websocket.send_json(
                        ErrorMessage(message="stream_id inválido").model_dump()
                    )
                    continue
                if stream_id is not None:
                    stream = await redis.get_stream(stream_id)
                    if not stream:
                        await websocket.send_json(
                            ErrorMessage(
                                message=f"Stream no encontrado: {stream_id}"
                            ).model_dump()
                        )
                        continue
                await redis.set_spotlight(stream_id)
                await broadcast_stream_spotlight(stream_id)
                logger.info("Admin toggled spotlight: %s", stream_id or "off")
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("Admin WebSocket error: %s", e)
    finally:
        manager.disconnect_admin(websocket)
