from __future__ import annotations

import asyncio
import socket
import os

import asyncpg


async def test() -> None:
    host = os.getenv("SUPABASE_POOLER_HOST", "aws-0-ap-southeast-1.pooler.supabase.com")

    try:
        print("Resolving host:", host)
        print(socket.gethostbyname(host))
    except Exception as e:
        print("DNS resolution failed:", e)
        print("Invalid Supabase pooler hostname — verify from dashboard")
        raise

    conn = await asyncpg.connect(
        user="postgres",
        password="Nandas123!#",
        database="postgres",
        host=host,
        port=6543,
        ssl=True,
        statement_cache_size=0,
    )
    print("✅ Connected successfully")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(test())
