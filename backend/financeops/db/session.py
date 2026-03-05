from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from financeops.config import settings

log = logging.getLogger(__name__)

engine = create_async_engine(
    str(settings.DATABASE_URL),
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def set_rls_context(session: AsyncSession, tenant_id: str) -> None:
    """Set PostgreSQL session variable for RLS enforcement."""
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


async def clear_rls_context(session: AsyncSession) -> None:
    """Clear the RLS context (sets empty string)."""
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', '', true)")
    )


async def check_db_health() -> dict[str, Any]:
    """Return DB health status. Used by /health/deep endpoint."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
        return {"status": "ok", "latency_ms": None}
    except Exception as exc:
        log.error("DB health check failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
