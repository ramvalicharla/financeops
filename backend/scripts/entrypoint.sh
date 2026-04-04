#!/usr/bin/env bash
set -euo pipefail

echo "Starting FinanceOps container..."

echo "Running DB migrations..."
python -m financeops.migrations.run

echo "Migration completed successfully"

echo "Starting application..."
exec uvicorn financeops.main:app --host 0.0.0.0 --port ${PORT}
