"""Base class for platform extractors."""

from abc import ABC, abstractmethod
from typing import Optional
from urllib.parse import urlparse

import httpx

from models.stream import StreamMetadata, StreamPlatform


def extract_hostname(url: str) -> Optional[str]:
    """Return the lowercase hostname of a URL, or None if it has no host."""
    try:
        return urlparse(url).hostname
    except ValueError:
        return None


_oembed_client: Optional[httpx.AsyncClient] = None


def get_oembed_client() -> httpx.AsyncClient:
    """Shared async HTTP client for oEmbed requests (lazy singleton)."""
    global _oembed_client
    if _oembed_client is None:
        _oembed_client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            timeout=5.0,
        )
    return _oembed_client


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
