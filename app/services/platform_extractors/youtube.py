"""YouTube platform extractor."""

import logging
import re
from typing import Optional

from models.stream import StreamMetadata, StreamPlatform
from services.platform_extractors.base import (
    BasePlatformExtractor,
    extract_hostname,
    get_oembed_client,
)

logger = logging.getLogger(__name__)


class YouTubeExtractor(BasePlatformExtractor):
    """Extractor for YouTube videos and streams."""

    platform = StreamPlatform.YOUTUBE

    PATTERNS = [
        # Standard watch URL: youtube.com/watch?v=VIDEO_ID
        r"(?:youtube\.com/watch\?.*v=)([a-zA-Z0-9_-]{11})",
        # Short URL: youtu.be/VIDEO_ID
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        # Embed URL: youtube.com/embed/VIDEO_ID
        r"(?:youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
        # Shorts: youtube.com/shorts/VIDEO_ID
        r"(?:youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
        # Live: youtube.com/live/VIDEO_ID
        r"(?:youtube\.com/live/)([a-zA-Z0-9_-]{11})",
    ]

    def can_handle(self, url: str) -> bool:
        """Check if URL is a YouTube URL."""
        hostname = extract_hostname(url)
        if not hostname:
            return False
        if hostname in ("youtube.com", "youtu.be", "youtube-nocookie.com"):
            return True
        return hostname.endswith(".youtube.com")

    def extract_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL."""
        for pattern in self.PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def get_embed_url(self, video_id: str, host: str = "localhost") -> str:
        """Generate YouTube embed URL (privacy-enhanced)."""
        return f"https://www.youtube-nocookie.com/embed/{video_id}"

    async def get_metadata(self, video_id: str) -> StreamMetadata:
        """Fetch video metadata from YouTube oEmbed API."""
        try:
            response = await get_oembed_client().get(
                "https://www.youtube.com/oembed",
                params={
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "format": "json",
                },
            )
            if response.status_code == 200:
                data = response.json()
                return StreamMetadata(
                    title=data.get("title", f"YouTube Video {video_id}"),
                    thumbnail=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                    author=data.get("author_name"),
                )
        except Exception as e:
            logger.warning("Failed to fetch YouTube metadata for %s: %s", video_id, e)

        return StreamMetadata(
            title=f"YouTube Video {video_id}",
            thumbnail=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        )
