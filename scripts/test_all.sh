#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_root="${repo_root}/backend"
compose_file="${repo_root}/infra/docker-compose.test.yml"
python_exe="${backend_root}/.venv/bin/python"
if [[ ! -x "${python_exe}" ]]; then
  python_exe="python"
fi

export DEBUG="false"
export SECRET_KEY="test-secret-key"
export JWT_SECRET="test-jwt-secret"
export FIELD_ENCRYPTION_KEY="0123456789abcdef0123456789abcdef"
export DATABASE_URL="postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
export TEST_DATABASE_URL="postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
export REDIS_URL="redis://localhost:6380/0"
export TEST_REDIS_URL="redis://localhost:6380/0"

cleanup() {
  echo "Stopping test containers..."
  docker compose -f "${compose_file}" down || true
}
trap cleanup EXIT

cd "${repo_root}"
echo "Stopping test containers..."
docker compose -f "${compose_file}" down

echo "Removing stale lock files..."
rm -f "${repo_root}/.finos_prompt_engine.lock" "${backend_root}/.finos_prompt_engine.lock"

echo "Clearing pytest cache..."
(
  cd "${backend_root}"
  "${python_exe}" -m pytest --cache-clear --collect-only -q
)

echo "Starting test containers..."
docker compose -f "${compose_file}" up -d

echo "Waiting for database readiness..."
(
  cd "${backend_root}"
  "${python_exe}" tests/utils/wait_for_db.py --url "${TEST_DATABASE_URL}" --timeout 30
  echo "Applying migrations..."
  "${python_exe}" -m alembic upgrade head
  echo "Running parallel-safe pytest suite..."
  "${python_exe}" -m pytest -q -n auto -m "not serial_only"
  echo "Running serial-only pytest tail..."
  "${python_exe}" -m pytest -q -n 1 -m "serial_only"
)
