"""Async engine + session factory (FastAPI request scope)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    echo=False,
    pool_pre_ping=True,
    # In tests every function-scoped event loop would inherit pooled asyncpg
    # connections bound to a dead loop — NullPool sidesteps that entirely.
    poolclass=NullPool if _settings.environment == "test" else None,
    **({} if _settings.environment == "test" else {"pool_size": 10, "max_overflow": 10}),
)

SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session (FastAPI dependency)."""
    async with SessionFactory() as session:
        yield session
