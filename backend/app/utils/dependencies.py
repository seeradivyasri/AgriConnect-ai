from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.database import get_db

async def get_or_create_dummy(db: AsyncSession, role: str, phone: str, name: str) -> User:
    result = await db.execute(select(User).where(User.role == role))
    user = result.scalars().first()
    if not user:
        user = User(phone=phone, name=name, role=role, verified=True)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user

async def require_farmer(db: AsyncSession = Depends(get_db)) -> User:
    return await get_or_create_dummy(db, "farmer", "+919999999999", "Dummy Farmer")

async def get_current_user(db: AsyncSession = Depends(get_db)) -> User:
    return await require_farmer(db)

async def require_customer(db: AsyncSession = Depends(get_db)) -> User:
    return await get_or_create_dummy(db, "customer", "+918888888888", "Dummy Customer")

async def require_admin(db: AsyncSession = Depends(get_db)) -> User:
    return await get_or_create_dummy(db, "admin", "+917777777777", "Dummy Admin")
