#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
echo "Running DB migrations..."
python -m financeops.migrations.run
echo "Migration completed successfully"
