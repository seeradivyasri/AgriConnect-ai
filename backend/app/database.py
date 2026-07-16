from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

# Create the async engine using the URL from our config
engine = create_async_engine(settings.DATABASE_URL, echo=(settings.APP_ENV == "development"))

# Create a session factory
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# Dependency for FastAPI to inject the database session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# Dependency for FastAPI to inject the redis connection
async def get_redis():
    from redis.asyncio import Redis
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=False)
    try:
        yield redis
    finally:
        await redis.aclose()
