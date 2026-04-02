# Deployment Checklist (Phase 11D)

## 1. Pre-Deploy
1. Confirm `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `FIELD_ENCRYPTION_KEY`, `SECRET_KEY` are set.
2. Confirm migration URL strategy (`MIGRATION_DATABASE_URL` optional for direct DB migrations).
3. Run:
   ```bash
   cd backend
   python scripts/predeploy_migration_check.py
   ```
4. Validate no unexpected git changes in deployment branch.

## 2. Migration Execution
1. Run:
   ```bash
   cd backend
   alembic upgrade head
   ```
2. Verify:
   - `GET /api/v1/platform/ops/migrations/status` reports no pending revisions.

## 3. App/Worker Startup
1. Start backend API.
2. Start worker and beat.
3. Verify startup logs show no auth/env validation errors.

## 4. Post-Deploy Smoke
Run:
```bash
cd backend
BASE_URL="https://<your-backend-host>" ACCESS_TOKEN="<token>" python scripts/postdeploy_smoke_check.py
```

Critical checks:
- `/health`, `/ready`, `/live`
- auth route availability
- onboarding summary
- journal list and create validation path
- trial balance and P&L route availability
- consolidation summary route availability
- ERP sync health
- AI anomaly route

## 5. Operational Verification
1. `GET /api/v1/platform/ops/dependencies`
2. `GET /api/v1/platform/ops/jobs/status`
3. `GET /api/v1/platform/ops/sessions/status`
4. Ensure no abnormal failure spikes in logs/metrics.

## 6. Rollback Trigger Conditions
Rollback or halt rollout if:
- migrations fail or drift from expected head
- readiness remains failed after stabilization window
- auth/session failures spike
- journal/GL read/write path returns unexpected 5xx
