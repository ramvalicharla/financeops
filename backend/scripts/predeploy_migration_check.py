from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

def _alembic_script_dir():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend_root = Path(__file__).resolve().parents[1]
    alembic_ini = backend_root / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(backend_root / "migrations"))
    return ScriptDirectory.from_config(cfg)


def _resolved_url() -> tuple[str | None, str]:
    migration_url = os.getenv("MIGRATION_DATABASE_URL", "").strip()
    if migration_url:
        return migration_url, "MIGRATION_DATABASE_URL"
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return database_url, "DATABASE_URL"
    return None, "unset"


def _collect_import_errors(script_dir: ScriptDirectory) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for revision in script_dir.walk_revisions():
        try:
            _ = revision.module
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(
                {
                    "revision": str(revision.revision),
                    "error": str(exc) or exc.__class__.__name__,
                }
            )
    return errors


async def _read_current_revision(url: str) -> tuple[str | None, str | None]:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={
            "ssl": True,
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "timeout": 10,
        },
    )
    try:
        async with engine.connect() as conn:
            current = (
                await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            ).scalar_one_or_none()
            return current, None
    except Exception as exc:
        return None, str(exc) or exc.__class__.__name__
    finally:
        await engine.dispose()


async def main() -> int:
    try:
        import alembic  # noqa: F401
        import sqlalchemy  # noqa: F401
    except ModuleNotFoundError as exc:
        payload = {
            "status": "failed",
            "reason": "missing_dependency",
            "detail": str(exc),
            "hint": "Install backend dependencies before running this check.",
        }
        print(json.dumps(payload, indent=2))
        return 1

    url, source = _resolved_url()
    script_dir = _alembic_script_dir()
    heads = [str(item) for item in script_dir.get_heads()]
    expected_head = script_dir.get_current_head()
    import_errors = _collect_import_errors(script_dir)

    if not url:
        payload = {
            "status": "failed",
            "reason": "DATABASE_URL/MIGRATION_DATABASE_URL not set",
            "source": source,
            "expected_head": expected_head,
            "known_heads": heads,
            "import_errors": import_errors,
        }
        print(json.dumps(payload, indent=2))
        return 1

    current_revision, db_error = await _read_current_revision(url)
    known_revision = bool(current_revision and script_dir.get_revision(current_revision))
    single_head = len(heads) == 1
    at_head = bool(current_revision and expected_head and current_revision == expected_head)

    passed = single_head and at_head and known_revision and not import_errors and db_error is None
    payload: dict[str, Any] = {
        "status": "passed" if passed else "failed",
        "source": source,
        "expected_head": expected_head,
        "known_heads": heads,
        "single_head": single_head,
        "current_revision": current_revision,
        "current_revision_known": known_revision,
        "at_head": at_head,
        "import_errors": import_errors,
        "db_error": db_error,
    }
    print(json.dumps(payload, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
