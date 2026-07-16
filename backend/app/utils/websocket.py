from fastapi import WebSocket
from collections import defaultdict

class ConnectionManager:
    def __init__(self):
        # Maps listing_id to a list of connected WebSockets
        self.active_connections: defaultdict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, listing_id: str):
        await websocket.accept()
        self.active_connections[listing_id].append(websocket)

    def disconnect(self, websocket: WebSocket, listing_id: str):
        if websocket in self.active_connections[listing_id]:
            self.active_connections[listing_id].remove(websocket)
        # Clean up empty lists
        if not self.active_connections[listing_id]:
            del self.active_connections[listing_id]

    async def send_update(self, listing_id: str, data: dict):
        connections = self.active_connections.get(listing_id, [])
        for connection in connections:
            try:
                await connection.send_json(data)
            except Exception:
                pass

manager = ConnectionManager()
