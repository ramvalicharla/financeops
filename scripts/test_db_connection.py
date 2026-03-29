from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

_SSL_REQUIRED_MODES = {"require", "verify-ca", "verify-full"}


def _build_connection_config(database_url: str) -> tuple[str, dict[str, Any]]:
    """
    Build asyncpg kwargs from SQLAlchemy DATABASE_URL.

    Strips sslmode from URL query and maps TLS requirement to `ssl=True`
    for asyncpg.
    """
    from sqlalchemy.engine import make_url

    url_obj = make_url(database_url)
    query = dict(url_obj.query)
    sslmode = str(query.pop("sslmode", "")).lower()
    host = (url_obj.host or "").lower()
    ssl_enabled = sslmode in _SSL_REQUIRED_MODES or host.endswith(".supabase.co")

    normalized_url = str(url_obj.set(query=query))
    kwargs: dict[str, Any] = {
        "host": url_obj.host,
        "port": int(url_obj.port or 5432),
        "user": url_obj.username,
        "password": url_obj.password,
        "database": url_obj.database,
        "timeout": 10,
        "ssl": ssl_enabled,
    }
    return normalized_url, kwargs


async def _run_check() -> int:
    try:
        import asyncpg
    except ModuleNotFoundError:
        print(
            "ERROR: asyncpg is not installed in this Python environment.\n"
            "Run from backend env/container where dependencies are installed."
        )
        return 3

    try:
        # Import here so script still prints friendly guidance if missing.
        from sqlalchemy.engine import make_url as _  # noqa: F401
    except ModuleNotFoundError:
        print(
            "ERROR: SQLAlchemy is not installed in this Python environment.\n"
            "Run from backend env/container where dependencies are installed."
        )
        return 4

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("ERROR: DATABASE_URL is not set.")
        return 1

    normalized_url, connect_kwargs = _build_connection_config(database_url)
    print(f"Host: {connect_kwargs['host']}")
    print(f"Port: {connect_kwargs['port']}")
    print(f"Database: {connect_kwargs['database']}")
    print(f"SSL Enabled: {connect_kwargs['ssl']}")
    print(f"Normalized URL: {normalized_url}")

    conn: asyncpg.Connection | None = None
    try:
        conn = await asyncpg.connect(**connect_kwargs)
        value = await conn.fetchval("SELECT 1")
        print(f"SUCCESS: Connectivity verified. SELECT 1 -> {value}")
        return 0
    except Exception as exc:
        print(f"ERROR: Database connectivity check failed: {exc!r}")
        return 2
    finally:
        if conn is not None:
            await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run_check()))
