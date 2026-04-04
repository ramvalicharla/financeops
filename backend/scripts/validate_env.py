from __future__ import annotations

import asyncio
import os
import sys

import httpx
from sqlalchemy import text


async def _check_database_connection() -> tuple[bool, str]:
    from financeops.db.session import engine

    try:
        async with engine.connect() as connection:
            await asyncio.wait_for(connection.execute(text("SELECT 1")), timeout=5.0)
        return True, "connected"
    except Exception as exc:
        return False, str(exc).strip() or exc.__class__.__name__
    finally:
        await engine.dispose()


async def _check_migration_state() -> tuple[bool, str, str | None, str | None]:
    from financeops.core.migration_checker import check_migration_state

    try:
        result = await check_migration_state()
    except Exception as exc:
        return False, str(exc).strip() or exc.__class__.__name__, None, None

    if result.current_revision != result.head_revision:
        detail = (
            f"Migration mismatch: current={result.current_revision}, "
            f"head={result.head_revision}. Run migrations before starting the app."
        )
        return False, detail, result.current_revision, result.head_revision

    return True, "current == head", result.current_revision, result.head_revision


async def _check_migration_status_endpoint(
    current_revision: str | None,
    head_revision: str | None,
) -> tuple[bool, str]:
    endpoint = os.getenv("MIGRATION_STATUS_URL", "").strip()
    if not endpoint:
        return True, "skipped (MIGRATION_STATUS_URL not set)"

    token = os.getenv("MIGRATION_STATUS_BEARER_TOKEN", "").strip()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint, headers=headers)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return False, f"endpoint check failed: {str(exc).strip() or exc.__class__.__name__}"

    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    endpoint_current = data.get("current_revision")
    endpoint_head = data.get("expected_head") or data.get("head_revision")
    if endpoint_current is None or endpoint_head is None:
        return False, "endpoint response missing revision fields"
    if str(endpoint_current) != str(current_revision) or str(endpoint_head) != str(head_revision):
        return (
            False,
            "endpoint mismatch: "
            f"endpoint_current={endpoint_current}, endpoint_head={endpoint_head}, "
            f"local_current={current_revision}, local_head={head_revision}",
        )
    return True, "endpoint revisions match local migration state"


def main() -> int:
    try:
        from financeops.config import Settings, get_settings

        get_settings.cache_clear()
        Settings()
    except Exception as exc:
        print(f"Environment validation failed: {exc}", file=sys.stderr)
        return 1

    ok, detail = asyncio.run(_check_database_connection())
    if not ok:
        print("Database connectivity: FAIL", file=sys.stderr)
        print(f"Reason: {detail}", file=sys.stderr)
        return 1
    print("Database connectivity: SUCCESS (connected)")

    migration_ok, migration_detail, current_revision, head_revision = asyncio.run(_check_migration_state())
    if not migration_ok:
        print("Migration status: FAIL", file=sys.stderr)
        print(f"Reason: {migration_detail}", file=sys.stderr)
        return 1
    print(
        f"Migration status: SUCCESS (current={current_revision}, head={head_revision})"
    )

    endpoint_ok, endpoint_detail = asyncio.run(
        _check_migration_status_endpoint(current_revision, head_revision)
    )
    if not endpoint_ok:
        print("Migration status endpoint: FAIL", file=sys.stderr)
        print(f"Reason: {endpoint_detail}", file=sys.stderr)
        return 1
    print(f"Migration status endpoint: SUCCESS ({endpoint_detail})")

    print("Environment validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
