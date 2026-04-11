from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from filelock import FileLock
from alembic.config import Config
from alembic.script import ScriptDirectory

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
)
_VALID_TEST_DB_NAME = re.compile(r"[a-z0-9_]+")
_MIGRATION_DATABASE_LOCK = Path(__file__).resolve().parents[1] / ".pytest-migration-db.lock"
_TEMPLATE_DATABASE_NAME = "finos_test_integration_template"


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_database(raw_url: str, database: str) -> str:
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _database_exists(conn: asyncpg.Connection, database_name: str) -> bool:
    existing = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", database_name)
    return existing == 1


async def _create_database(
    conn: asyncpg.Connection,
    database_name: str,
    *,
    template_name: str | None = None,
) -> None:
    if not _VALID_TEST_DB_NAME.fullmatch(database_name):
        raise RuntimeError(f"Invalid temp database name: {database_name}")
    if template_name is None:
        await conn.execute(f'CREATE DATABASE "{database_name}"')
        return
    if not _VALID_TEST_DB_NAME.fullmatch(template_name):
        raise RuntimeError(f"Invalid temp template database name: {template_name}")
    await conn.execute(f'CREATE DATABASE "{database_name}" TEMPLATE "{template_name}"')


def _current_alembic_head() -> str:
    cfg = Config(str(_backend_dir() / "alembic.ini"))
    cfg.set_main_option("script_location", str(_backend_dir() / "migrations"))
    script_dir = ScriptDirectory.from_config(cfg)
    return script_dir.get_current_head() or ""


async def _template_revision(database_url: str) -> str | None:
    conn = await asyncpg.connect(_to_asyncpg_dsn(database_url))
    try:
        return await conn.fetchval("SELECT version_num FROM alembic_version LIMIT 1")
    except Exception:
        return None
    finally:
        await conn.close()


async def _ensure_migrated_template_database(*, admin_url: str, error_context: str) -> None:
    template_url = _with_database(os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL), _TEMPLATE_DATABASE_NAME)
    desired_head = _current_alembic_head()

    with FileLock(str(_MIGRATION_DATABASE_LOCK)):
        admin_conn = await asyncpg.connect(_to_asyncpg_dsn(admin_url))
        try:
            if await _database_exists(admin_conn, _TEMPLATE_DATABASE_NAME):
                existing_revision = await _template_revision(template_url)
                if existing_revision == desired_head:
                    return
                await admin_conn.execute(
                    """
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = $1
                      AND pid <> pg_backend_pid()
                    """,
                    _TEMPLATE_DATABASE_NAME,
                )
                await admin_conn.execute(f'DROP DATABASE IF EXISTS "{_TEMPLATE_DATABASE_NAME}"')

            await _create_database(admin_conn, _TEMPLATE_DATABASE_NAME)
        finally:
            await admin_conn.close()

        env = os.environ.copy()
        env["DATABASE_URL"] = template_url
        env["MIGRATION_DATABASE_URL"] = template_url
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
            await drop_temp_database(admin_url=admin_url, database_name=_TEMPLATE_DATABASE_NAME)
            raise RuntimeError(
                f"alembic upgrade head failed for {error_context}\n"
                f"stdout:\n{migration.stdout}\n"
                f"stderr:\n{migration.stderr}"
            )


async def drop_temp_database(*, admin_url: str, database_name: str) -> None:
    cleanup_conn = await asyncpg.connect(_to_asyncpg_dsn(admin_url))
    try:
        await cleanup_conn.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = $1
              AND pid <> pg_backend_pid()
            """,
            database_name,
        )
        await cleanup_conn.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
    finally:
        await cleanup_conn.close()


async def create_migrated_temp_database(
    *,
    prefix: str,
    error_context: str,
) -> tuple[str, str, str]:
    base_url = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    admin_db = os.getenv("TEST_DATABASE_ADMIN_DB", "postgres")
    suffix = uuid.uuid4().hex[:10]
    temp_db = f"{prefix}_{suffix}"
    if not _VALID_TEST_DB_NAME.fullmatch(temp_db):
        raise RuntimeError(f"Invalid temp database name: {temp_db}")

    admin_url = _with_database(base_url, admin_db)
    target_url = _with_database(base_url, temp_db)

    await _ensure_migrated_template_database(
        admin_url=admin_url,
        error_context=error_context,
    )

    with FileLock(str(_MIGRATION_DATABASE_LOCK)):
        conn = await asyncpg.connect(_to_asyncpg_dsn(admin_url))
        try:
            await _create_database(conn, temp_db, template_name=_TEMPLATE_DATABASE_NAME)
        finally:
            await conn.close()

    return target_url, temp_db, admin_url
