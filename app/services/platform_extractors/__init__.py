# Platform extractors module
from typing import Optional, List
from services.platform_extractors.base import BasePlatformExtractor
from services.platform_extractors.youtube import YouTubeExtractor
from services.platform_extractors.twitch import TwitchExtractor
from services.platform_extractors.vimeo import VimeoExtractor


class PlatformExtractorRegistry:
    """Registry for platform extractors."""

    def __init__(self) -> None:
        self.extractors: List[BasePlatformExtractor] = [
            YouTubeExtractor(),
            TwitchExtractor(),
            VimeoExtractor(),
        ]

    def get_extractor(self, url: str) -> Optional[BasePlatformExtractor]:
        """Find an extractor that can handle the given URL."""
        for extractor in self.extractors:
            if extractor.can_handle(url):
                return extractor
        return None

    def get_supported_platforms(self) -> List[str]:
        """Get list of supported platform names."""
        return [e.platform.value for e in self.extractors]


registry = PlatformExtractorRegistry()

__all__ = [
    "BasePlatformExtractor",
    "YouTubeExtractor",
    "TwitchExtractor",
    "VimeoExtractor",
    "PlatformExtractorRegistry",
    "registry",
]
