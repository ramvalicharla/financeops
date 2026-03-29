from __future__ import annotations

import asyncio
import os
import socket
import ssl
import sys
from urllib.parse import unquote, urlparse

import asyncpg


def _parse_database_url() -> tuple[str, int, str, str, str]:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL is not set")
        sys.exit(1)

    if database_url.startswith("postgresql+asyncpg://"):
        database_url = "postgresql://" + database_url.split("://", 1)[1]

    parsed = urlparse(database_url)
    host = parsed.hostname
    port = parsed.port or 6543
    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    database = parsed.path.lstrip("/") or "postgres"

    if not host or not user or not password:
        print("DATABASE_URL is invalid")
        sys.exit(1)

    return host, port, user, password, database


async def test() -> None:
    host, port, user, password, database = _parse_database_url()

    print("Resolving host:", host)
    try:
        ip = socket.gethostbyname(host)
        print("Resolved IP:", ip)
    except Exception:
        print("Invalid Supabase pooler hostname - verify from dashboard")
        sys.exit(1)

    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        conn = await asyncpg.connect(
            user=user,
            password=password,
            database=database,
            host=host,
            port=port,
            ssl=ssl_context,
            statement_cache_size=0,
        )
        print("Connected successfully")
        await conn.close()
    except Exception as e:
        print("DB connection failed:", e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test())
