"""Vimeo platform extractor."""

import logging
import re
from typing import Optional

import httpx

from models.stream import StreamMetadata, StreamPlatform
from services.platform_extractors.base import BasePlatformExtractor

logger = logging.getLogger(__name__)


class VimeoExtractor(BasePlatformExtractor):
    """Extractor for Vimeo videos."""

    platform = StreamPlatform.VIMEO

    PATTERNS = [
        # Standard URL: vimeo.com/123456789
        r"vimeo\.com/(\d+)",
        # Player URL: player.vimeo.com/video/123456789
        r"player\.vimeo\.com/video/(\d+)",
    ]

    def can_handle(self, url: str) -> bool:
        """Check if URL is a Vimeo URL."""
        return "vimeo.com" in url.lower()

    def extract_id(self, url: str) -> Optional[str]:
        """Extract Vimeo video ID from URL."""
        for pattern in self.PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_embed_url(self, video_id: str, host: str = "localhost") -> str:
        """Generate Vimeo embed URL."""
        return f"https://player.vimeo.com/video/{video_id}"

    async def get_metadata(self, video_id: str) -> StreamMetadata:
        """Fetch video metadata from Vimeo oEmbed API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://vimeo.com/api/oembed.json",
                    params={"url": f"https://vimeo.com/{video_id}"},
                    timeout=5.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    return StreamMetadata(
                        title=data.get("title", f"Vimeo Video {video_id}"),
                        thumbnail=data.get("thumbnail_url"),
                        author=data.get("author_name"),
                    )
        except Exception as e:
            logger.warning("Failed to fetch Vimeo metadata for %s: %s", video_id, e)

        return StreamMetadata(title=f"Vimeo Video {video_id}")
