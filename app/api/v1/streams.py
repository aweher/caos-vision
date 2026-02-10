"""Stream management API endpoints."""

from fastapi import APIRouter, Depends, status

from api.deps import get_stream_service, require_auth
from api.websocket import broadcast_stream_added, broadcast_stream_muted, broadcast_stream_removed
from models.auth import SessionInfo
from models.stream import StreamCreate, StreamListResponse, StreamResponse
from services.stream_service import StreamService

router = APIRouter(prefix="/streams", tags=["streams"])


@router.get("", response_model=StreamListResponse)
async def list_streams(
    stream_service: StreamService = Depends(get_stream_service),
) -> StreamListResponse:
    """Get all streams with layout information. Public endpoint."""
    streams = await stream_service.get_all_streams()
    layout = StreamService.calculate_layout(len(streams))
    return StreamListResponse(
        streams=streams,
        layout=layout,
        total=len(streams),
    )


@router.post("", response_model=StreamResponse, status_code=status.HTTP_201_CREATED)
async def add_stream(
    stream_data: StreamCreate,
    stream_service: StreamService = Depends(get_stream_service),
    _: SessionInfo = Depends(require_auth),
) -> StreamResponse:
    """Add a new stream. Requires authentication."""
    stream = await stream_service.add_stream(stream_data)

    # Broadcast to all connected clients
    count = await stream_service.get_stream_count()
    layout = StreamService.calculate_layout(count)
    await broadcast_stream_added(stream, layout)

    return stream


@router.delete("/{stream_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stream(
    stream_id: str,
    stream_service: StreamService = Depends(get_stream_service),
    _: SessionInfo = Depends(require_auth),
) -> None:
    """Delete a stream. Requires authentication."""
    await stream_service.delete_stream(stream_id)

    # Broadcast to all connected clients
    count = await stream_service.get_stream_count()
    layout = StreamService.calculate_layout(count)
    await broadcast_stream_removed(stream_id, layout)


@router.post("/{stream_id}/mute", response_model=dict)
async def toggle_mute(
    stream_id: str,
    stream_service: StreamService = Depends(get_stream_service),
    _: SessionInfo = Depends(require_auth),
) -> dict:
    """Toggle mute state of a stream. Requires authentication."""
    new_mute_state = await stream_service.toggle_mute(stream_id)

    # Broadcast to all connected clients
    await broadcast_stream_muted(stream_id, new_mute_state)

    return {"stream_id": stream_id, "muted": new_mute_state}
