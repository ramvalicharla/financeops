from __future__ import annotations

import logging
import ssl
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID
from uuid import uuid4

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from financeops.config import settings
from financeops.db.rls import (
    _TENANT_CONTEXT_SESSION_KEY,
    clear_tenant_context,
    set_tenant_context,
)

log = logging.getLogger(__name__)

_SSL_REQUIRED_MODES = {"require", "verify-ca", "verify-full"}
_DB_ROLE_SESSION_KEY = "app.current_db_role"


def _is_supabase_host(host: str) -> bool:
    return (
        host.endswith(".supabase.co")
        or host.endswith(".supabase.com")
        or host.endswith(".pooler.supabase.com")
    )


def _build_ssl_context() -> ssl.SSLContext:
    """
    Build TLS context for asyncpg connections.

    Render/Supabase deployments can present a self-signed certificate in the
    chain, so disable hostname and certificate verification in the driver SSL
    context used by SQLAlchemy's asyncpg engine.
    """
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


def _prepared_statement_name() -> str:
    """Generate unique prepared statement names for PgBouncer transaction mode."""
    return f"__fo_stmt_{uuid4().hex}__"


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
    if url_obj.port == 5432 and (
        host.endswith(".pooler.supabase.com")
        or (_is_supabase_host(host) and not host.startswith("db."))
    ):
        url_obj = url_obj.set(port=6543)

    connect_args: dict[str, Any] = {
        "timeout": 10,
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": _prepared_statement_name,
    }
    if (
        sslmode in _SSL_REQUIRED_MODES
        or _is_supabase_host(host)
    ):
        connect_args["ssl"] = _build_ssl_context()

    normalized_url = url_obj.set(query=query).render_as_string(hide_password=False)
    return normalized_url, connect_args


_DATABASE_URL, _DATABASE_CONNECT_ARGS = _normalise_database_url_and_connect_args(
    str(settings.DATABASE_URL)
)
_READ_DATABASE_CONFIGURED = bool(
    settings.DATABASE_READ_REPLICA_URL and str(settings.DATABASE_READ_REPLICA_URL).strip()
)
_READ_DATABASE_URL, _READ_DATABASE_CONNECT_ARGS = _normalise_database_url_and_connect_args(
    str(settings.DATABASE_READ_REPLICA_URL or settings.DATABASE_URL)
)

if _DATABASE_CONNECT_ARGS.get("statement_cache_size") == 0:
    log.info("Asyncpg statement cache disabled (PgBouncer mode)")

engine = create_async_engine(
    _DATABASE_URL,
    poolclass=NullPool,
    connect_args=_DATABASE_CONNECT_ARGS,
    echo=settings.DEBUG,
)

if _READ_DATABASE_CONFIGURED:
    read_engine = create_async_engine(
        _READ_DATABASE_URL,
        poolclass=NullPool,
        connect_args=_READ_DATABASE_CONNECT_ARGS,
        echo=settings.DEBUG,
    )
else:
    read_engine = engine

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

AsyncReadSessionLocal = (
    AsyncSessionLocal
    if read_engine is engine
    else async_sessionmaker(
        read_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
)


@event.listens_for(AsyncSession.sync_session_class, "after_begin")
def _reapply_tenant_context(sync_session, transaction, connection) -> None:
    db_role = sync_session.info.get(_DB_ROLE_SESSION_KEY)
    if db_role:
        quoted_role = '"' + str(db_role).replace('"', '""') + '"'
        connection.exec_driver_sql(f"SET LOCAL ROLE {quoted_role}")
    tenant_id = sync_session.info.get(_TENANT_CONTEXT_SESSION_KEY)
    if not tenant_id:
        return
    connection.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


async def set_session_db_role(session: AsyncSession, role_name: str) -> None:
    """Remember and apply a DB role for the current and future transactions."""
    session.info[_DB_ROLE_SESSION_KEY] = role_name
    quoted_role = '"' + str(role_name).replace('"', '""') + '"'
    await session.execute(text(f"SET LOCAL ROLE {quoted_role}"))


async def clear_session_db_role(session: AsyncSession) -> None:
    """Forget any remembered DB role and reset the active transaction role."""
    session.info.pop(_DB_ROLE_SESSION_KEY, None)
    await session.execute(text("RESET ROLE"))


async def finalize_session_success(session: AsyncSession) -> None:
    """
    Flush pending writes and commit when the session implementation supports it.

    Some lightweight test doubles only implement ``flush()``/``rollback()``/``close()``.
    Keeping the commit step behind this helper lets the API dependency remain
    framework-agnostic while still persisting real request-scoped sessions.
    """
    await session.flush()
    commit = getattr(session, "commit", None)
    if callable(commit):
        await commit()


async def finalize_session_read_only(session: AsyncSession) -> None:
    if session.in_transaction():
        await session.rollback()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await finalize_session_success(session)
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_read_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncReadSessionLocal() as session:
        try:
            yield session
            await finalize_session_read_only(session)
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
async def tenant_read_session(tenant_id: UUID | str) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncReadSessionLocal() as session:
        try:
            await set_tenant_context(session, str(tenant_id))
            yield session
            await finalize_session_read_only(session)
        except Exception:
            await session.rollback()
            raise
        finally:
            await clear_tenant_context(session)
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
            await finalize_session_success(session)
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


def is_read_replica_configured() -> bool:
    return _READ_DATABASE_CONFIGURED
