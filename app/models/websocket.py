"""WebSocket message models."""

from typing import List, Literal, Optional, Tuple, Union

from pydantic import BaseModel

from models.stream import StreamResponse


class WSMessageBase(BaseModel):
    """Base WebSocket message."""

    type: str


# Server -> Client messages


class StreamUpdateMessage(WSMessageBase):
    """Full stream list update."""

    type: Literal["stream_update"] = "stream_update"
    streams: List[StreamResponse]
    layout: Tuple[int, int]
    spotlight: Optional[str] = None


class StreamAddedMessage(WSMessageBase):
    """Single stream added notification."""

    type: Literal["stream_added"] = "stream_added"
    stream: StreamResponse
    layout: Tuple[int, int]


class StreamRemovedMessage(WSMessageBase):
    """Stream removed notification."""

    type: Literal["stream_removed"] = "stream_removed"
    stream_id: str
    layout: Tuple[int, int]


class StreamMutedMessage(WSMessageBase):
    """Stream mute state changed."""

    type: Literal["stream_muted"] = "stream_muted"
    stream_id: str
    muted: bool


class StreamSpotlightMessage(WSMessageBase):
    """Stream spotlight (fullscreen) state changed."""

    type: Literal["stream_spotlight"] = "stream_spotlight"
    stream_id: Optional[str]  # None = exit spotlight


class ErrorMessage(WSMessageBase):
    """Error message."""

    type: Literal["error"] = "error"
    message: str


class PingMessage(WSMessageBase):
    """Ping keepalive."""

    type: Literal["ping"] = "ping"


class PongMessage(WSMessageBase):
    """Pong response."""

    type: Literal["pong"] = "pong"


class ForceRefreshMessage(WSMessageBase):
    """Force viewers to reload the page."""

    type: Literal["force_refresh"] = "force_refresh"


# Client -> Server messages


class RequestRefreshMessage(WSMessageBase):
    """Request full refresh."""

    type: Literal["request_refresh"] = "request_refresh"


class SpotlightCommandMessage(WSMessageBase):
    """Admin command to enter/exit spotlight mode."""

    type: Literal["spotlight_stream"] = "spotlight_stream"
    stream_id: Optional[str] = None  # None = exit spotlight


class ForceViewerRefreshMessage(WSMessageBase):
    """Admin command to force all viewers to refresh."""

    type: Literal["force_viewer_refresh"] = "force_viewer_refresh"


# Type aliases for message unions
WSServerMessage = Union[
    StreamUpdateMessage,
    StreamAddedMessage,
    StreamRemovedMessage,
    StreamMutedMessage,
    StreamSpotlightMessage,
    ErrorMessage,
    PongMessage,
    ForceRefreshMessage,
]

WSClientMessage = Union[
    RequestRefreshMessage,
    PingMessage,
    SpotlightCommandMessage,
    ForceViewerRefreshMessage,
]
