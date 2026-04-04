from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

from _phase1_validation_lib import (
    ValidationRun,
    base_url,
    build_auth_headers,
    env,
    extract_enveloped_data,
    get_auth_context,
    request_json,
    write_artifact,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _backend_dir() -> Path:
    return _repo_root() / "backend"


def _run_lock_safe_migration() -> dict[str, Any]:
    backend = _backend_dir()
    command = [sys.executable, "-m", "financeops.migrations.run"]
    env_map = os.environ.copy()
    pythonpath = env_map.get("PYTHONPATH", "").strip()
    backend_path = str(backend)
    env_map["PYTHONPATH"] = f"{backend_path}{os.pathsep}{pythonpath}" if pythonpath else backend_path

    proc = subprocess.run(
        command,
        cwd=str(backend),
        capture_output=True,
        text=True,
        check=False,
        env=env_map,
    )
    return {
        "command": " ".join(command),
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
        "success": proc.returncode == 0,
    }


def _alembic_head_revision() -> str | None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
    except Exception:
        return None

    backend = _backend_dir()
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "migrations"))
    script = ScriptDirectory.from_config(cfg)
    return script.get_current_head()


async def _db_current_revision(database_url: str) -> dict[str, Any]:
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.pool import NullPool
    except Exception as exc:
        return {"success": False, "error": f"sqlalchemy import failed: {exc}"}

    engine = create_async_engine(
        database_url,
        poolclass=NullPool,
        connect_args={
            "ssl": True,
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "timeout": 15,
        },
    )
    try:
        async with engine.connect() as conn:
            revision = (
                await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            ).scalar_one_or_none()
            return {"success": True, "current_revision": revision}
    except Exception as exc:
        return {"success": False, "error": str(exc) or exc.__class__.__name__}
    finally:
        await engine.dispose()


async def main() -> int:
    run = ValidationRun("migration_execution_validation")

    migration_run = _run_lock_safe_migration()
    run.add("lock_safe_migration_run", "pass" if migration_run["success"] else "fail", **migration_run)

    head_revision = _alembic_head_revision()
    if head_revision:
        run.add("read_alembic_head", "pass", head_revision=head_revision)
    else:
        run.add("read_alembic_head", "fail", error="unable to read Alembic head revision")

    database_url = env("MIGRATION_DATABASE_URL") or env("DATABASE_URL")
    if not database_url:
        run.add("read_db_revision", "fail", error="MIGRATION_DATABASE_URL or DATABASE_URL is required")
        db_revision = {"success": False, "error": "missing_database_url"}
    else:
        db_revision = await _db_current_revision(database_url)
        run.add(
            "read_db_revision",
            "pass" if db_revision.get("success") else "fail",
            **db_revision,
        )

    ops_status_payload: dict[str, Any] | None = None
    ops_status_code: int | None = None
    ops_error: str | None = None

    try:
        api_base = base_url()
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            auth = await get_auth_context(
                client,
                api_base=api_base,
                access_token_env="ADMIN_ACCESS_TOKEN",
                email_env="ADMIN_AUTH_EMAIL",
                password_env="ADMIN_AUTH_PASSWORD",
            )
            ops_resp = await request_json(
                client,
                "GET",
                f"{api_base}api/v1/platform/ops/migrations/status",
                headers=build_auth_headers(access_token=auth["access_token"]),
            )
            ops_status_code = ops_resp.get("status_code")
            ops_status_payload = ops_resp.get("payload")
            if not ops_resp.get("ok"):
                ops_error = ops_resp.get("error")
            elif ops_status_code != 200:
                ops_error = f"unexpected_status:{ops_status_code}"
            elif isinstance(ops_status_payload, dict):
                try:
                    extract_enveloped_data(ops_status_payload)
                except Exception as exc:
                    ops_error = str(exc)
            else:
                ops_error = "non_json_payload"
    except Exception as exc:
        ops_error = str(exc) or exc.__class__.__name__

    run.add(
        "ops_migration_status_api",
        "pass" if ops_error is None else "fail",
        status_code=ops_status_code,
        response=ops_status_payload,
        error=ops_error,
    )

    db_current = db_revision.get("current_revision") if db_revision.get("success") else None
    api_current = None
    api_head = None
    if isinstance(ops_status_payload, dict):
        try:
            ops_data = extract_enveloped_data(ops_status_payload)
            if isinstance(ops_data, dict):
                api_current = ops_data.get("current_revision")
                api_head = ops_data.get("expected_head")
        except Exception:
            pass

    revision_match = (
        bool(head_revision)
        and bool(db_current)
        and str(head_revision) == str(db_current)
        and (api_current is None or str(api_current) == str(db_current))
        and (api_head is None or str(api_head) == str(head_revision))
    )
    run.add(
        "revision_match_status",
        "pass" if revision_match else "fail",
        alembic_head=head_revision,
        db_current_revision=db_current,
        api_current_revision=api_current,
        api_expected_head=api_head,
        matched=revision_match,
    )

    payload = run.to_dict()
    payload["summary"] = {
        "migration_head": head_revision,
        "current_revision": db_current,
        "match_status": revision_match,
    }
    artifact_path = write_artifact("migration_validation.json", payload)
    print(json.dumps({"artifact": str(artifact_path), "passed": payload["passed"]}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
