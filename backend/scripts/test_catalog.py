import asyncio
import os
import sys
from datetime import date
from httpx import AsyncClient, ASGITransport
import redis.asyncio as redis

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.main import app

async def main():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        print("1. First call to /api/v1/catalog...")
        res1 = await client.get("/api/v1/catalog")
        print("Status:", res1.status_code)
        
        print("2. Second call to /api/v1/catalog...")
        res2 = await client.get("/api/v1/catalog")
        print("Status:", res2.status_code)
        
    print(f"\n3. Checking Redis for cache key...")
    r = redis.from_url("redis://localhost:6379/0")
    today = date.today()
    key = f"catalog:all:{today}"
    cached = await r.get(key)
    if cached:
        print(f"CACHE HIT for {key}:")
        print(cached.decode('utf-8'))
    else:
        print(f"CACHE MISS for {key}")
        
    await r.aclose()

if __name__ == "__main__":
    asyncio.run(main())
