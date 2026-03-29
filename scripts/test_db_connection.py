from __future__ import annotations

import asyncio

import asyncpg


async def test() -> None:
    conn = await asyncpg.connect(
        user="postgres",
        password="Nandas123!#",
        database="postgres",
        host="db.ojvqnonjcqnntwsimubd.supabase.co",
        port=6543,
        ssl=True,
        statement_cache_size=0,
    )
    print("✅ Connected successfully")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(test())
