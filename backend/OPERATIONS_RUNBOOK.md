# FinanceOps Operations Runbook (Phase 11D)

## Scope
This runbook covers safe operations for FinanceOps backend in production:
- deployment flow
- migration execution safety
- job/workflow recovery
- dependency diagnostics
- incident handling entry points

## Golden Rules
1. Treat accounting and GL tables as append-only truth.
2. Use `DATABASE_URL` as runtime source of truth.
3. Run schema migrations before app startup (`alembic upgrade head`).
4. Never run destructive schema changes without a tested rollback/restore path.
5. Fail closed on critical dependency errors (DB/auth), degrade gracefully on non-critical workers.

## Operator Endpoints
- Migration status: `GET /api/v1/platform/ops/migrations/status`
- Dependency diagnostics: `GET /api/v1/platform/ops/dependencies`
- Job status summary: `GET /api/v1/platform/ops/jobs/status`
- Safe ERP retry (paused+resumable only): `POST /api/v1/platform/ops/jobs/erp-sync/{run_id}/retry`
- Session visibility: `GET /api/v1/platform/ops/sessions/status`
- Ops summary: `GET /api/v1/platform/ops/summary`
- Public health:
  - `GET /live`
  - `GET /ready`
  - `GET /health`

## Long-Running Workflows
- ERP sync runs: inspect status/counts from `/api/v1/platform/ops/jobs/status`.
- Consolidation/translation/revaluation/audit-export runs: inspect from `/api/v1/platform/ops/jobs/status` and module-specific APIs.
- Retry policy:
  - ERP sync: only paused and resumable runs are retried by ops endpoint.
  - Failed/non-resumable runs require a fresh sync run with a new idempotency key.

## Backup/Restore Readiness
- Source-of-truth classes:
  - journals, GL/ledger truth, approvals/governance events, tenant/core auth and role tables.
- Derived/regenerable classes:
  - analytics snapshots/variance/trend outputs, AI narrative artifacts, some operational dashboards.
- Strictly back up:
  - transactional accounting data, tenant identity/auth/session state, connector definitions, migration state.
- Validate restore by:
  - migration head check
  - `/ready` and `/health`
  - smoke script (`scripts/postdeploy_smoke_check.py`)

## Remaining Operational Risks
1. Cross-region DB latency can increase readiness time during peak windows.
2. ERP connector provider-side outages can cause repeated failed sync attempts.
3. Large tenant data growth can pressure slow query paths if index hygiene regresses.
4. AI/analytics features can degrade independently of core finance correctness.
5. Manual operator retries must still follow idempotency expectations for external systems.
