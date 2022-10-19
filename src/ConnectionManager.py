from typing import Any
from fastapi.websockets import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections = list[WebSocket]()

    async def connect(self, sock: WebSocket):
        await sock.accept()
        self.active_connections.append(sock)

    def disconnect(self, sock: WebSocket):
        self.active_connections.remove(sock)

    async def broadcast(self, message: Any):
        for connection in self.active_connections:
            await connection.send_json(message)