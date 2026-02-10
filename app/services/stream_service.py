"""Stream management service."""

import hashlib
import logging
import math
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from core.exceptions import DuplicateStreamError, InvalidURLError, StreamNotFoundError
from models.stream import StreamCreate, StreamInDB, StreamResponse
from services.platform_extractors import registry
from services.redis_service import RedisService

logger = logging.getLogger(__name__)


class StreamService:
    """Service for managing streams."""

    def __init__(self, redis: RedisService, host: str = "localhost") -> None:
        self.redis = redis
        self.host = host

    async def add_stream(self, stream_data: StreamCreate) -> StreamResponse:
        """Add a new stream from URL."""
        url = str(stream_data.url)

        # Find appropriate extractor
        extractor = registry.get_extractor(url)
        if not extractor:
            raise InvalidURLError(
                f"Unsupported platform. Supported: {', '.join(registry.get_supported_platforms())}"
            )

        # Extract video ID
        video_id = extractor.extract_id(url)
        if not video_id:
            raise InvalidURLError("Could not extract video ID from URL")

        # Generate unique stream ID
        stream_id = self._generate_stream_id(extractor.platform.value, video_id)

        # Check if already exists
        existing = await self.redis.get_stream(stream_id)
        if existing:
            raise DuplicateStreamError("This stream is already in the list")

        # Get metadata
        metadata = await extractor.get_metadata(video_id)

        # Create stream record
        stream = StreamInDB(
            id=stream_id,
            url=url,
            embed_url=extractor.get_embed_url(video_id, self.host),
            platform=extractor.platform,
            title=metadata.title,
            thumbnail=metadata.thumbnail,
            muted=True,
            created_at=datetime.now(timezone.utc),
        )

        await self.redis.add_stream(stream_id, stream.model_dump())
        logger.info("Stream added: %s (%s)", stream_id, extractor.platform.value)

        return stream.to_response()

    def _generate_stream_id(self, platform: str, video_id: str) -> str:
        """Generate a consistent stream ID using SHA-256."""
        return hashlib.sha256(f"{platform}:{video_id}".encode()).hexdigest()[:12]

    async def get_all_streams(self) -> List[StreamResponse]:
        """Get all streams."""
        streams_data = await self.redis.get_all_streams()
        return [StreamResponse(**s) for s in streams_data]

    async def get_stream(self, stream_id: str) -> StreamResponse:
        """Get a single stream by ID."""
        stream_data = await self.redis.get_stream(stream_id)
        if not stream_data:
            raise StreamNotFoundError(stream_id)
        return StreamResponse(**stream_data)

    async def delete_stream(self, stream_id: str) -> bool:
        """Delete a stream."""
        # Check if exists
        existing = await self.redis.get_stream(stream_id)
        if not existing:
            raise StreamNotFoundError(stream_id)

        result = await self.redis.delete_stream(stream_id)
        if result:
            logger.info("Stream deleted: %s", stream_id)
        return result

    async def toggle_mute(self, stream_id: str) -> bool:
        """Toggle mute state of a stream. Returns new mute state."""
        result = await self.redis.toggle_mute(stream_id)
        if result is None:
            raise StreamNotFoundError(stream_id)
        logger.info("Stream %s mute toggled to: %s", stream_id, result)
        return result

    async def get_stream_count(self) -> int:
        """Get total number of streams."""
        return await self.redis.get_stream_count()

    @staticmethod
    def calculate_layout(stream_count: int) -> Tuple[int, int]:
        """Calculate optimal grid layout (rows, cols) for given stream count."""
        if stream_count == 0:
            return (0, 0)
        if stream_count == 1:
            return (1, 1)
        if stream_count == 2:
            return (1, 2)
        if stream_count <= 4:
            return (2, 2)
        if stream_count <= 6:
            return (2, 3)
        if stream_count <= 9:
            return (3, 3)
        if stream_count <= 12:
            return (3, 4)
        if stream_count <= 16:
            return (4, 4)

        # For larger counts, calculate based on aspect ratio
        cols = math.ceil(math.sqrt(stream_count * 16 / 9))
        rows = math.ceil(stream_count / cols)
        return (rows, cols)
