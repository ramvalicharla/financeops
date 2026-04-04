#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python -m financeops.migrations.run
echo "Migrations applied successfully"
