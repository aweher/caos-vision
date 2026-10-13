"""Twitch platform extractor."""

import logging
import re
from typing import Optional

from models.stream import StreamMetadata, StreamPlatform
from services.platform_extractors.base import BasePlatformExtractor, extract_hostname

logger = logging.getLogger(__name__)


class TwitchExtractor(BasePlatformExtractor):
    """Extractor for Twitch channels and VODs."""

    platform = StreamPlatform.TWITCH

    def can_handle(self, url: str) -> bool:
        """Check if URL is a Twitch URL."""
        hostname = extract_hostname(url)
        if not hostname:
            return False
        return hostname == "twitch.tv" or hostname.endswith(".twitch.tv")

    def extract_id(self, url: str) -> Optional[str]:
        """Extract Twitch channel name or VOD ID from URL.

        Returns format: 'channel:name' for live streams or 'video:id' for VODs.
        """
        # VOD pattern: twitch.tv/videos/123456789
        vod_match = re.search(r"twitch\.tv/videos/(\d+)", url)
        if vod_match:
            return f"video:{vod_match.group(1)}"

        # Channel pattern: twitch.tv/channelname (not /videos, /directory, etc.)
        channel_match = re.search(
            r"twitch\.tv/([a-zA-Z0-9_]+)(?:\?|$|/(?!videos|directory|settings))",
            url,
        )
        if channel_match:
            channel_name = channel_match.group(1).lower()
            # Exclude known non-channel paths
            if channel_name not in ["videos", "directory", "settings", "downloads"]:
                return f"channel:{channel_name}"

        return None

    def get_embed_url(self, video_id: str, host: str = "localhost") -> str:
        """Generate Twitch embed URL.

        Args:
            video_id: Format 'channel:name' or 'video:id'
            host: Parent domain for Twitch embed security
        """
        id_type, id_value = video_id.split(":", 1)

        if id_type == "channel":
            return (
                f"https://player.twitch.tv/?channel={id_value}"
                f"&parent={host}&muted=true"
            )
        else:  # video
            return (
                f"https://player.twitch.tv/?video={id_value}"
                f"&parent={host}&muted=true"
            )

    async def get_metadata(self, video_id: str) -> StreamMetadata:
        """Get basic metadata for Twitch stream.

        Note: Full metadata would require Twitch API authentication.
        """
        id_type, id_value = video_id.split(":", 1)

        if id_type == "channel":
            return StreamMetadata(
                title=f"Twitch: {id_value}",
                thumbnail=None,  # Would need API for channel avatar
                author=id_value,
            )
        else:
            return StreamMetadata(
                title=f"Twitch VOD: {id_value}",
                thumbnail=None,
            )
