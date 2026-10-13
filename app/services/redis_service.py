"""Redis service for data persistence."""

import json
import logging
from typing import Any, Dict, List, Optional

from redis.asyncio import ConnectionPool, Redis
from redis.asyncio.client import PubSub

logger = logging.getLogger(__name__)


class RedisService:
    """Async Redis service for stream and session management."""

    STREAMS_KEY = "caos:streams"
    SESSION_PREFIX = "caos:session:"
    RATE_LIMIT_PREFIX = "caos:ratelimit:"
    BROADCAST_CHANNEL = "caos:broadcasts"
    SPOTLIGHT_KEY = "caos:spotlight"

    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool
        self.redis = Redis(connection_pool=pool)

    @classmethod
    async def create(cls, url: str) -> "RedisService":
        """Create a new RedisService instance."""
        pool = ConnectionPool.from_url(url, decode_responses=True)
        instance = cls(pool)
        # Test connection
        await instance.redis.ping()
        logger.info("Redis connection established")
        return instance

    async def close(self) -> None:
        """Close Redis connections."""
        await self.redis.close()
        await self.pool.disconnect()
        logger.info("Redis connection closed")

    # Stream operations

    async def get_all_streams(self) -> List[Dict[str, Any]]:
        """Get all streams."""
        streams_data = await self.redis.hgetall(self.STREAMS_KEY)
        streams = []
        for stream_json in streams_data.values():
            try:
                streams.append(json.loads(stream_json))
            except json.JSONDecodeError:
                logger.warning("Invalid stream data in Redis")
        # Sort by created_at
        streams.sort(key=lambda x: x.get("created_at", ""), reverse=False)
        return streams

    async def get_stream(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get a single stream by ID."""
        stream_json = await self.redis.hget(self.STREAMS_KEY, stream_id)
        if stream_json:
            try:
                return json.loads(stream_json)
            except json.JSONDecodeError:
                return None
        return None

    async def add_stream(self, stream_id: str, data: Dict[str, Any]) -> bool:
        """Add a new stream."""
        serialized = dict(data)
        created_at = serialized.get("created_at")
        if hasattr(created_at, "isoformat"):
            serialized["created_at"] = created_at.isoformat()
        stream_json = json.dumps(serialized)
        await self.redis.hset(self.STREAMS_KEY, stream_id, stream_json)
        logger.info("Stream added: %s", stream_id)
        return True

    async def delete_stream(self, stream_id: str) -> bool:
        """Delete a stream."""
        result = await self.redis.hdel(self.STREAMS_KEY, stream_id)
        if result:
            logger.info("Stream deleted: %s", stream_id)
        return bool(result)

    # Lua script for atomic toggle_mute (avoids read-modify-write race condition)
    _TOGGLE_MUTE_SCRIPT = """
    local stream_json = redis.call('HGET', KEYS[1], ARGV[1])
    if not stream_json then
        return nil
    end
    local stream = cjson.decode(stream_json)
    if stream['muted'] then
        stream['muted'] = false
    else
        stream['muted'] = true
    end
    local updated = cjson.encode(stream)
    redis.call('HSET', KEYS[1], ARGV[1], updated)
    if stream['muted'] then
        return 1
    else
        return 0
    end
    """

    async def toggle_mute(self, stream_id: str) -> Optional[bool]:
        """Toggle mute state of a stream atomically. Returns new mute state."""
        result = await self.redis.eval(
            self._TOGGLE_MUTE_SCRIPT, 1, self.STREAMS_KEY, stream_id
        )
        if result is None:
            return None
        new_mute = bool(int(result))
        logger.info("Stream %s mute toggled to: %s", stream_id, new_mute)
        return new_mute

    async def get_stream_count(self) -> int:
        """Get total number of streams."""
        return await self.redis.hlen(self.STREAMS_KEY)

    # Session operations

    async def save_session(
        self, session_id: str, data: Dict[str, Any], expiry: int = 3600
    ) -> bool:
        """Save session data with expiry."""
        key = f"{self.SESSION_PREFIX}{session_id}"
        session_json = json.dumps(data)
        await self.redis.setex(key, expiry, session_json)
        logger.debug("Session saved: %s", session_id)
        return True

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data."""
        key = f"{self.SESSION_PREFIX}{session_id}"
        session_json = await self.redis.get(key)
        if session_json:
            try:
                return json.loads(session_json)
            except json.JSONDecodeError:
                return None
        return None

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        key = f"{self.SESSION_PREFIX}{session_id}"
        result = await self.redis.delete(key)
        if result:
            logger.debug("Session deleted: %s", session_id)
        return bool(result)

    async def refresh_session(self, session_id: str, expiry: int = 3600) -> bool:
        """Refresh session expiry."""
        key = f"{self.SESSION_PREFIX}{session_id}"
        return bool(await self.redis.expire(key, expiry))

    # Rate limiting

    _RATE_LIMIT_SCRIPT = """
    local current = redis.call('INCR', KEYS[1])
    if current == 1 then
        redis.call('EXPIRE', KEYS[1], ARGV[1])
    end
    if current > tonumber(ARGV[2]) then
        return {0, redis.call('TTL', KEYS[1])}
    end
    return {1, 0}
    """

    async def check_and_increment_rate_limit(
        self, identifier: str, max_attempts: int, window: int
    ) -> tuple[bool, int]:
        """Atomically check and increment the rate limit counter.

        Returns (is_allowed, retry_after): retry_after is the remaining
        window TTL when not allowed, 0 otherwise.
        """
        key = f"{self.RATE_LIMIT_PREFIX}{identifier}"
        allowed, retry_after = await self.redis.eval(
            self._RATE_LIMIT_SCRIPT, 1, key, window, max_attempts
        )
        return bool(allowed), max(0, int(retry_after))

    async def reset_rate_limit(self, identifier: str) -> bool:
        """Reset rate limit counter."""
        key = f"{self.RATE_LIMIT_PREFIX}{identifier}"
        return bool(await self.redis.delete(key))

    # Spotlight

    async def get_spotlight(self) -> Optional[str]:
        """Get the currently spotlighted stream ID."""
        return await self.redis.get(self.SPOTLIGHT_KEY)

    async def set_spotlight(self, stream_id: Optional[str]) -> None:
        """Set or clear the spotlighted stream."""
        if not stream_id:
            await self.redis.delete(self.SPOTLIGHT_KEY)
            logger.info("Spotlight cleared")
            return
        await self.redis.set(self.SPOTLIGHT_KEY, stream_id)
        logger.info("Spotlight set to: %s", stream_id)

    # Pub/Sub for cross-service WebSocket broadcasts

    async def publish(self, channel: str, message: str) -> int:
        """Publish a message to a Redis Pub/Sub channel."""
        return await self.redis.publish(channel, message)

    async def subscribe(self, channel: str) -> PubSub:
        """Subscribe to a Redis Pub/Sub channel. Returns the PubSub object."""
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        return pubsub

    # Health check

    async def ping(self) -> bool:
        """Check Redis connection."""
        try:
            await self.redis.ping()
            return True
        except Exception:
            return False
