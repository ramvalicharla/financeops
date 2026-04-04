from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from financeops.config import settings
from financeops.db.session import _normalise_database_url_and_connect_args

log = logging.getLogger(__name__)

_DATABASE_URL, _DATABASE_CONNECT_ARGS = _normalise_database_url_and_connect_args(
    str(settings.DATABASE_URL)
)

if _DATABASE_CONNECT_ARGS.get("statement_cache_size") == 0:
    log.info("Asyncpg statement cache disabled (PgBouncer mode)")

engine = create_async_engine(
    _DATABASE_URL,
    poolclass=NullPool,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args=_DATABASE_CONNECT_ARGS,
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


@asynccontextmanager
async def tenant_session(tenant_id: UUID | str) -> AsyncGenerator[AsyncSession, None]:
    """
    Context-managed session for worker/background paths where no HTTP Request exists.
    Ensures app.current_tenant_id is set for the connection lifetime.
    """
    async with AsyncSessionLocal() as session:
        try:
            await set_tenant_context(session, str(tenant_id))
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await clear_tenant_context(session)
            await session.close()


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Set PostgreSQL session variable for RLS enforcement."""
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


async def clear_tenant_context(session: AsyncSession) -> None:
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
