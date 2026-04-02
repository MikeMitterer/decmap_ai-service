import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services import websocket_service

logger = structlog.get_logger()

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time event broadcasting.

    Clients connect here to receive live events:
    - problem.approved / problem.rejected / problem.deleted
    - cluster.updated
    - solution.approved / solution.deleted
    - vote.changed

    The connection is held open until the client disconnects.
    All events are JSON-serialised Pydantic models.
    """
    await websocket.accept()
    websocket_service.register(websocket)
    log = logger.bind(client=str(websocket.client))
    log.info("websocket_client_connected")

    try:
        while True:
            # Keep the connection alive — we only send, never expect data from clients
            await websocket.receive_text()
    except WebSocketDisconnect:
        log.info("websocket_client_disconnected")
    except Exception as exc:
        log.warning("websocket_error", error=str(exc))
    finally:
        websocket_service.unregister(websocket)
