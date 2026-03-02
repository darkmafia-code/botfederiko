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


# helper to provide session via dependency/middleware
async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session


from aiogram.middleware.base import BaseMiddleware


class DBSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data: dict):
        # attach a session for each update
        async with SessionLocal() as session:
            data['db'] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
