#!/usr/bin/env bash
set -euo pipefail

# Production migrations should run in Railway shell where runtime networking
# and secrets are available.
if [[ -z "${RAILWAY_ENVIRONMENT:-}" && -z "${RAILWAY_ENVIRONMENT_ID:-}" && -z "${RAILWAY_PROJECT_ID:-}" && "${MIGRATIONS_ALLOW_LOCAL:-0}" != "1" ]]; then
  echo "Refusing to run migrations outside Railway."
  echo "Open a Railway shell and rerun, or set MIGRATIONS_ALLOW_LOCAL=1 for non-production testing."
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}/backend"
python -m alembic -c alembic.ini upgrade head
