from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from financeops.db.rls import set_tenant_context

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
)

ERP_SYNC_TABLES: tuple[str, ...] = (
    "external_connections",
    "external_connection_versions",
    "external_sync_definitions",
    "external_sync_definition_versions",
    "external_sync_runs",
    "external_raw_snapshots",
    "external_normalized_snapshots",
    "external_mapping_definitions",
    "external_mapping_versions",
    "external_sync_evidence_links",
    "external_sync_errors",
    "external_sync_publish_events",
    "external_connector_capability_registry",
    "external_connector_version_registry",
    "external_period_locks",
    "external_backdated_modification_alerts",
    "external_sync_drift_reports",
    "external_sync_health_alerts",
    "external_data_consent_logs",
    "external_sync_sla_configs",
)


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_database(raw_url: str, database: str) -> str:
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(scope="session")
async def erp_sync_phase4c_db_url() -> AsyncGenerator[str, None]:
    base_url = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    admin_db = os.getenv("TEST_DATABASE_ADMIN_DB", "postgres")
    suffix = uuid.uuid4().hex[:10]
    temp_db = f"financeops_erp_sync_{suffix}"
    if not re.fullmatch(r"[a-z0-9_]+", temp_db):
        raise RuntimeError(f"Invalid temp database name: {temp_db}")

    admin_url = _with_database(base_url, admin_db)
    target_url = _with_database(base_url, temp_db)

    conn = await asyncpg.connect(_to_asyncpg_dsn(admin_url))
    try:
        await conn.execute(f'CREATE DATABASE "{temp_db}"')
    finally:
        await conn.close()

    env = os.environ.copy()
    env["DATABASE_URL"] = target_url
    env.setdefault("DEBUG", "false")
    env.setdefault("SECRET_KEY", "test-secret-key")
    env.setdefault("JWT_SECRET", "test-jwt-secret-32-characters-long-000")
    env.setdefault("FIELD_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    env.setdefault("REDIS_URL", "redis://localhost:6380/0")

    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=str(_backend_dir()),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if migration.returncode != 0:
        raise RuntimeError(
            "alembic upgrade head failed for erp_sync temp database\n"
            f"stdout:\n{migration.stdout}\n"
            f"stderr:\n{migration.stderr}"
        )

    try:
        yield target_url
    finally:
        cleanup_conn = await asyncpg.connect(_to_asyncpg_dsn(admin_url))
        try:
            await cleanup_conn.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = $1
                  AND pid <> pg_backend_pid()
                """,
                temp_db,
            )
            await cleanup_conn.execute(f'DROP DATABASE IF EXISTS "{temp_db}"')
        finally:
            await cleanup_conn.close()


@pytest_asyncio.fixture(scope="session")
async def erp_sync_phase4c_engine(erp_sync_phase4c_db_url: str):
    engine = create_async_engine(erp_sync_phase4c_db_url, echo=False, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def erp_sync_phase4c_session(
    erp_sync_phase4c_engine,
) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(erp_sync_phase4c_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()


async def ensure_erp_sync_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await set_tenant_context(session, tenant_id)
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )

