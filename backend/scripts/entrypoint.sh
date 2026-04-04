#!/usr/bin/env bash
set -euo pipefail

echo "Starting FinanceOps container..."

echo "========== MIGRATION START =========="
if ! PYTHONUNBUFFERED=1 python -m financeops.migrations.run; then
    echo "========== MIGRATION FAILED =========="
    exit 1
fi
echo "========== MIGRATION SUCCESS =========="

echo "Starting application..."
exec uvicorn financeops.main:app --host 0.0.0.0 --port ${PORT}
