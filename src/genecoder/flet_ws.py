import asyncio
import logging
from types import ModuleType
from typing import Any, TYPE_CHECKING, Set, cast

_websockets: ModuleType | None
try:
    import websockets as _ws
    _websockets = _ws
except Exception:  # pragma: no cover - optional dependency
    _websockets = None

websockets = _websockets

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from websockets.legacy.server import WebSocketServerProtocol
else:
    WebSocketServerProtocol = Any

logger = logging.getLogger(__name__)

ws_clients: Set[WebSocketServerProtocol] = set()


def start_server() -> None:
    """Start the local WebSocket server if possible."""

    if not websockets:
        return

    async def _ws_handler(websocket: WebSocketServerProtocol) -> None:
        ws_clients.add(websocket)
        try:
            async for _ in websocket:
                pass
        finally:
            ws_clients.discard(websocket)

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.error("No running event loop; WebSocket server not started")
            return
        loop.create_task(cast(Any, websockets.serve(_ws_handler, "localhost", 8765)))
    except OSError as exc:  # pragma: no cover - depends on environment
        logger.error("Failed to start WebSocket server: %s", exc)


# Start server on import for backwards compatibility
start_server()
