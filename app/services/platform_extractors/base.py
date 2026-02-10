"""Base class for platform extractors."""

from abc import ABC, abstractmethod
from typing import Optional

from models.stream import StreamMetadata, StreamPlatform


class BasePlatformExtractor(ABC):
    """Abstract base class for platform-specific URL extractors."""

    platform: StreamPlatform

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Check if this extractor can handle the given URL."""
        pass

    @abstractmethod
    def extract_id(self, url: str) -> Optional[str]:
        """Extract the video/stream ID from URL."""
        pass

    @abstractmethod
    def get_embed_url(self, video_id: str, host: str = "localhost") -> str:
        """Generate the embed URL for the platform."""
        pass

    @abstractmethod
    async def get_metadata(self, video_id: str) -> StreamMetadata:
        """Fetch video metadata (title, thumbnail, etc.)."""
        pass
