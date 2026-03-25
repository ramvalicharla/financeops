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

from financeops.config import settings
from financeops.db.rls import clear_tenant_context, set_tenant_context

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


async def get_raw_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async DB session without JWT/RLS tenant context wiring.
    Intended for token-auth integrations that apply their own scope controls.
    """
    async with AsyncSessionLocal() as session:
        async with session.begin():
            try:
                yield session
                await session.flush()
            except Exception:
                await session.rollback()
                raise


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
