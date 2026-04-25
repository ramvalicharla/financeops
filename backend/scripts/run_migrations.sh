#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
echo "Running DB migrations..."
PYTHONUNBUFFERED=1 python -m financeops.migrations.run 2>&1
echo "Migration completed successfully"
