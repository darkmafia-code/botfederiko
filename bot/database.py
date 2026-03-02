from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from .models import Base
import os

# use aiosqlite for async sqlite, or adjust for other dbs via env
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///gamification.db")

engine = create_async_engine(DATABASE_URL, future=True, echo=False)
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
