import asyncio
import logging
from typing import Any

try:
    import websockets
except Exception:  # pragma: no cover - optional dependency
    websockets = None

logger = logging.getLogger(__name__)

ws_clients: set[Any] = set()


def start_server() -> None:
    """Start the local WebSocket server if possible."""

    if not websockets:
        return

    async def _ws_handler(websocket: Any) -> None:
        ws_clients.add(websocket)
        try:
            async for _ in websocket:
                pass
        finally:
            ws_clients.discard(websocket)

    try:
        try:
            loop: asyncio.AbstractEventLoop | None = asyncio.get_event_loop()
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = None
        if loop:
            loop.create_task(websockets.serve(_ws_handler, "localhost", 8765))
        else:  # pragma: no cover - depends on environment
            logger.error("No running event loop; WebSocket server not started")
    except OSError as exc:  # pragma: no cover - depends on environment
        logger.error("Failed to start WebSocket server: %s", exc)


# Start server on import for backwards compatibility
start_server()
