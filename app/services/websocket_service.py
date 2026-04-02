import structlog
from fastapi import WebSocket

from app.models.events import WebSocketEvent

logger = structlog.get_logger()

# Module-level singleton — shared across all requests
connected_clients: set[WebSocket] = set()


def register(websocket: WebSocket) -> None:
    """Add a WebSocket connection to the active clients set."""
    connected_clients.add(websocket)
    logger.info("websocket_connected", total=len(connected_clients))


def unregister(websocket: WebSocket) -> None:
    """Remove a WebSocket connection from the active clients set."""
    connected_clients.discard(websocket)
    logger.info("websocket_disconnected", total=len(connected_clients))


async def broadcast(event: WebSocketEvent) -> None:
    """Broadcast a typed WebSocket event to all connected clients.

    Automatically removes any clients that have disconnected.

    Args:
        event: A typed WebSocketEvent (Pydantic model). Serialised as JSON.
    """
    message = event.model_dump_json()
    disconnected: set[WebSocket] = set()

    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:  # noqa: BLE001
            disconnected.add(client)

    connected_clients.difference_update(disconnected)

    if disconnected:
        logger.debug(
            "websocket_clients_cleaned",
            removed=len(disconnected),
            remaining=len(connected_clients),
        )

    logger.debug("event_broadcast", event_type=event.type, recipients=len(connected_clients))
