#!/usr/bin/env bash
set -euo pipefail

echo "Starting FinanceOps container..."

echo "Waiting for database to be ready..."

for i in {1..10}; do
  if PYTHONUNBUFFERED=1 python -c "
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = os.environ['DATABASE_URL']

engine = create_async_engine(
    DATABASE_URL,
    connect_args={'statement_cache_size': 0, 'timeout': 10},
    pool_pre_ping=True
)

async def main():
    async with engine.connect() as conn:
        await conn.execute(text('SELECT 1'))
    await engine.dispose()

asyncio.run(main())
"; then
    echo "Database is ready!"
    break
  fi

  echo "DB not ready, retrying in 3 seconds... ($i/10)"
  sleep 3

  if [ $i -eq 10 ]; then
    echo "Database not reachable after retries. Exiting."
    exit 1
  fi
done

echo "========== MIGRATION START =========="
if ! PYTHONUNBUFFERED=1 python -m financeops.migrations.run; then
    echo "========== MIGRATION FAILED =========="
    exit 1
fi
echo "========== MIGRATION SUCCESS =========="

echo "Starting application..."
exec uvicorn financeops.main:app --host 0.0.0.0 --port ${PORT}
