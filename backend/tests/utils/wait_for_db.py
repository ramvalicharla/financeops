from __future__ import annotations

import argparse
import asyncio
import os
import time

import asyncpg


def _normalize_dsn(raw_dsn: str) -> str:
    return raw_dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


async def _wait_for_db(dsn: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            conn = await asyncpg.connect(dsn)
            await conn.close()
            return
        except Exception as exc:  # pragma: no cover - depends on runtime availability
            last_error = exc
            await asyncio.sleep(1)

    if last_error is None:
        raise TimeoutError("Database readiness check timed out.")
    raise TimeoutError(f"Database readiness check timed out: {last_error}")


def _resolve_default_dsn() -> str:
    return (
        os.getenv("TEST_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait for Postgres readiness.")
    parser.add_argument("--url", default=_resolve_default_dsn(), help="Database DSN.")
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds (default: 30).",
    )
    args = parser.parse_args()

    dsn = _normalize_dsn(args.url)
    asyncio.run(_wait_for_db(dsn=dsn, timeout_seconds=args.timeout))
    print(f"Database is ready: {dsn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
