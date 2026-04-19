# FINOS Testing Guide

## One-command test execution

Use the repository-level scripts to run backend tests in a clean, reproducible environment.

- Windows PowerShell:
  - `.\scripts\test_all.ps1`
- Linux/macOS:
  - `./scripts/test_all.sh`

Both scripts do the same sequence:

1. Stop existing test containers.
2. Remove stale prompt-engine lock files.
3. Clear pytest cache.
4. Start Docker test services from `infra/docker-compose.test.yml`.
5. Wait for Postgres readiness.
6. Apply migrations (`alembic upgrade head`).
7. Run the parallel-safe suite with `pytest -q -n auto -m "not serial_only"`.
8. Run the serial-only tail with `pytest -q -n 1 -m serial_only`.
9. Stop test containers on exit (success or failure).

## Prompt Engine governance flags

For `financeops.prompt_engine.cli run`:

- `--approve-high-risk`: allow HIGH risk prompt execution.
- `--approval-token <token>`: optional approval context token.
- `--allow-deps`: allow dependency-file modifications in generated patches.
- `--enable-review-gate`: enable deterministic rule-based patch review gate.
- `--allow-ledger-repair`: allow automatic ledger hash-chain repair if verification fails at startup.

Ledger commands:

- `python -m financeops.prompt_engine.cli ledger verify`
- `python -m financeops.prompt_engine.cli ledger repair --yes`

## Test environment variables

The scripts set deterministic values for each run:

- `DEBUG=false`
- `SECRET_KEY=test-secret-key`
- `JWT_SECRET=test-jwt-secret`
- `FIELD_ENCRYPTION_KEY=0123456789abcdef0123456789abcdef`
- `DATABASE_URL=postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test`
- `TEST_DATABASE_URL=postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test`
- `REDIS_URL=redis://localhost:6380/0`
- `TEST_REDIS_URL=redis://localhost:6380/0`

This avoids shell-specific drift during local and CI execution.

## Test groups

Backend tests are organized under:

- `backend/tests/unit`
- `backend/tests/integration`
- `backend/tests/prompt_engine`

Run specific groups from `backend/`:

- `python -m pytest tests/unit -q`
- `python -m pytest tests/integration -q`
- `python -m pytest tests/prompt_engine -q`

Recommended full-suite local command from `backend/`:

- `python -m pytest -q -n auto -m "not serial_only"`
- `python -m pytest -q -n 1 -m serial_only`

## Pytest defaults

Pytest is configured with:

- `--strict-markers`
- worker-isolated database handling for `pytest-xdist`
- `serial_only` markers for tests that must stay on a single worker

Declared markers:

- `unit`
- `integration`
- `slow`
- `serial_only`

## Docker services used for tests

The test environment is defined in:

- `infra/docker-compose.test.yml`

It provides:

- Postgres test database
- Redis test cache

## CI usage

Use `scripts/test_all.sh` directly in CI (including GitHub Actions Linux runners):

```bash
bash scripts/test_all.sh
```

No additional orchestration steps are required if Docker is available on the runner.
