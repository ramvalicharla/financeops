from __future__ import annotations

import asyncio
import sys

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
    print("Environment validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
