"""Stream-related Pydantic models."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator


class StreamPlatform(str, Enum):
    """Supported streaming platforms."""

    YOUTUBE = "youtube"
    TWITCH = "twitch"
    VIMEO = "vimeo"
    GENERIC = "generic"


class StreamMetadata(BaseModel):
    """Metadata fetched from streaming platform."""

    title: str
    thumbnail: Optional[str] = None
    author: Optional[str] = None


class StreamCreate(BaseModel):
    """Request model for creating a stream."""

    url: str = Field(..., min_length=1, max_length=500)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class StreamUpdate(BaseModel):
    """Request model for updating stream settings."""

    muted: Optional[bool] = None


class StreamInDB(BaseModel):
    """Internal stream representation stored in Redis."""

    id: str
    url: str
    embed_url: str
    platform: StreamPlatform
    title: str
    thumbnail: Optional[str] = None
    muted: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_response(self) -> "StreamResponse":
        return StreamResponse(
            id=self.id,
            url=self.url,
            embed_url=self.embed_url,
            platform=self.platform,
            title=self.title,
            thumbnail=self.thumbnail,
            muted=self.muted,
        )


class StreamResponse(BaseModel):
    """Response model for stream data."""

    id: str
    url: str
    embed_url: str
    platform: StreamPlatform
    title: str
    thumbnail: Optional[str] = None
    muted: bool


class StreamListResponse(BaseModel):
    """Response model for list of streams with layout info."""

    streams: List[StreamResponse]
    layout: Tuple[int, int]
    total: int
