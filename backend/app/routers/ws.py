import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.security import decode_token
from app.services.ws_manager import ws_manager

router = APIRouter(tags=["WebSockets"])


@router.websocket("/ws/results")
async def results_websocket(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
) -> None:
    try:
        payload = decode_token(token, expected_type="access")
        user_id = str(payload["sub"])
        role = str(payload["role"])
    except (jwt.PyJWTError, KeyError, ValueError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws_manager.connect(websocket, user_id=user_id, role=role)
    try:
        await websocket.send_json(
            {
                "event": "CONNECTION_ESTABLISHED",
                "user_id": user_id,
                "role": role,
            }
        )
        while True:
            message = await websocket.receive_text()
            if message.strip().lower() == "ping":
                await websocket.send_json({"event": "PONG"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, user_id=user_id, role=role)
