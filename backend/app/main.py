from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.utils.websocket import manager

app = FastAPI(title="AgriConnect API")

from app.routers import listings, negotiation, catalog, cart, orders, chat, admin, auth

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.websocket("/ws/negotiation/{listing_id}")
async def websocket_negotiation(websocket: WebSocket, listing_id: str):
    await manager.connect(websocket, listing_id)
    try:
        while True:
            # Keep connection alive, wait for client disconnect
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, listing_id)

# Include Routers
app.include_router(auth.router)
app.include_router(listings.router, prefix="/api/v1")
app.include_router(negotiation.router, prefix="/api/v1")
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(cart.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
