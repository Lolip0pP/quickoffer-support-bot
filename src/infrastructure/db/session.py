"""SQLAlchemy AsyncSession configuration with asyncpg."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from src.core.config import settings


def create_engine() -> AsyncEngine:
    """Create async SQLAlchemy engine with asyncpg.

    Returns:
        AsyncEngine: Configured async engine for PostgreSQL.
    """
    return create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_size=20,
        max_overflow=0,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


async_engine = create_engine()

async_session_maker: sessionmaker[AsyncSession] = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for database sessions.

    Yields:
        AsyncSession: Database session.
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
