from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from financeops.config import settings
from financeops.db.rls import clear_tenant_context, set_tenant_context

log = logging.getLogger(__name__)

_SSL_REQUIRED_MODES = {"require", "verify-ca", "verify-full"}


def _normalise_database_url_and_connect_args(raw_url: str) -> tuple[str, dict[str, Any]]:
    """
    Normalize SQLAlchemy URL for asyncpg and derive connect_args.

    asyncpg does not support `sslmode=` in DSN query params.
    Supabase requires TLS, so we map sslmode/host to connect_args['ssl'].
    """
    url_obj = make_url(raw_url)
    query = dict(url_obj.query)
    sslmode = str(query.pop("sslmode", "")).lower()
    host = (url_obj.host or "").lower()
    if host.endswith(".supabase.co") and url_obj.port == 5432:
        url_obj = url_obj.set(port=6543)

    connect_args: dict[str, Any] = {
        "timeout": 10,
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    }
    if sslmode in _SSL_REQUIRED_MODES or host.endswith(".supabase.co"):
        connect_args["ssl"] = True

    normalized_url = url_obj.set(query=query).render_as_string(hide_password=False)
    return normalized_url, connect_args


_DATABASE_URL, _DATABASE_CONNECT_ARGS = _normalise_database_url_and_connect_args(
    str(settings.DATABASE_URL)
)

engine = create_async_engine(
    _DATABASE_URL,
    poolclass=NullPool,
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
