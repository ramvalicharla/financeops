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

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
)

MULTI_ENTITY_CONSOLIDATION_TABLES: tuple[str, ...] = (
    "entity_hierarchies",
    "entity_hierarchy_nodes",
    "consolidation_scopes",
    "consolidation_rule_definitions",
    "intercompany_mapping_rules",
    "consolidation_adjustment_definitions",
    "multi_entity_consolidation_runs",
    "multi_entity_consolidation_metric_results",
    "multi_entity_consolidation_variance_results",
    "multi_entity_consolidation_evidence_links",
)


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_database(raw_url: str, database: str) -> str:
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(scope="session")
async def multi_entity_phase2_3_db_url() -> AsyncGenerator[str, None]:
    base_url = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    admin_db = os.getenv("TEST_DATABASE_ADMIN_DB", "postgres")
    suffix = uuid.uuid4().hex[:10]
    temp_db = f"financeops_multientity_{suffix}"
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
            "alembic upgrade head failed for multi-entity phase2.3 temp database\n"
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


