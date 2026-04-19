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
from tests.integration.temp_db_helpers import create_migrated_temp_database, drop_temp_database

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.base import Base
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


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def erp_sync_phase4c_db_url() -> AsyncGenerator[str, None]:
    target_url, temp_db, admin_url = await create_migrated_temp_database(
        prefix="financeops_erp_sync",
        error_context="erp_sync temp database",
    )

    try:
        yield target_url
    finally:
        await drop_temp_database(admin_url=admin_url, database_name=temp_db)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def erp_sync_phase4c_engine(erp_sync_phase4c_db_url: str):
    engine = create_async_engine(erp_sync_phase4c_db_url, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        missing = []
        for table_name in ERP_SYNC_TABLES:
            exists = await conn.scalar(text("SELECT to_regclass(:table_name)"), {"table_name": f"public.{table_name}"})
            if exists is None:
                missing.append(table_name)
        if missing:
            await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(append_only_function_sql()))
        for table_name in ERP_SYNC_TABLES:
            await conn.execute(text(drop_trigger_sql(table_name)))
            await conn.execute(text(create_trigger_sql(table_name)))
            await conn.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY"))
            await conn.execute(text(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY"))
            await conn.execute(text(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name}"))
            await conn.execute(
                text(
                    f"CREATE POLICY tenant_isolation ON {table_name} "
                    "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
                    "current_setting('app.current_tenant_id', true))::uuid)"
                )
            )
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

