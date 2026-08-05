from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        try:
            self.active.remove(websocket)
        except ValueError:
            pass

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        await websocket.send_text(message)

    async def broadcast(self, message: str) -> None:
        for connection in list(self.active):
            try:
                await connection.send_text(message)
            except Exception:
                # ignore send errors; cleanup happens elsewhere
                pass
