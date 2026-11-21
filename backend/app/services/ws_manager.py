from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Tracks live authenticated WebSocket connections per user and role."""

    def __init__(self) -> None:
        self._user_connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._role_connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, *, user_id: str, role: str) -> None:
        await websocket.accept()
        self._user_connections[user_id].add(websocket)
        self._role_connections[role].add(websocket)

    def disconnect(self, websocket: WebSocket, *, user_id: str, role: str) -> None:
        self._user_connections[user_id].discard(websocket)
        if not self._user_connections[user_id]:
            self._user_connections.pop(user_id, None)
        self._role_connections[role].discard(websocket)
        if not self._role_connections[role]:
            self._role_connections.pop(role, None)

    def _prune_socket(self, websocket: WebSocket) -> None:
        for uid in list(self._user_connections.keys()):
            self._user_connections[uid].discard(websocket)
            if not self._user_connections[uid]:
                self._user_connections.pop(uid, None)
        for role in list(self._role_connections.keys()):
            self._role_connections[role].discard(websocket)
            if not self._role_connections[role]:
                self._role_connections.pop(role, None)

    async def send_to_user(self, user_id: str, event: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for ws in list(self._user_connections.get(user_id, set())):
            try:
                await ws.send_json(event)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self._prune_socket(ws)

    async def broadcast_to_role(self, role: str, event: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for ws in list(self._role_connections.get(role, set())):
            try:
                await ws.send_json(event)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self._prune_socket(ws)

    def active_count(self) -> int:
        return sum(len(conns) for conns in self._user_connections.values())


ws_manager = ConnectionManager()
