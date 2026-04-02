# Migration Safety Guide (Phase 11D)

## Expand -> Migrate -> Contract
Use three-step migrations for production safety:
1. Expand: additive schema only (new nullable columns/tables/indexes).
2. Migrate: backfill/dual-write/read-switch once data is validated.
3. Contract: remove deprecated columns only after rollout stability window.

## Finance-Sensitive Tables
Use extra caution for:
- journal/GL and accounting lifecycle tables
- approval/governance/period-close records
- tenant identity/auth/session tables
- connector mappings and sync history

## Pre-Deploy Validation
Run before every deploy:

```bash
cd backend
python scripts/predeploy_migration_check.py
```

Pass conditions:
- single Alembic head
- DB current revision exists and is recognized
- current revision equals expected head
- migration files import cleanly

## Runtime Status Visibility
Use:
- `GET /api/v1/platform/ops/migrations/status`

This endpoint exposes:
- current revision
- expected head
- pending revisions
- divergent head detection

## Rollback Guidance
Safe rollback depends on migration class:
1. Additive-only migration: usually rollback-safe.
2. Data-transform migration: rollback may be unsafe if irreversible transform occurred.
3. Contract/destructive migration: rollback is often restore-based, not schema-downgrade based.

If rollback is unsafe:
1. Stop writes.
2. Restore from verified backup/snapshot.
3. Re-run migration chain to known-good revision.

## Deployment Ordering
1. Validate env and secrets.
2. Run predeploy migration check.
3. Run `alembic upgrade head`.
4. Start app/workers.
5. Run postdeploy smoke checks.

## Commands
```bash
# Run migrations
cd backend
alembic upgrade head

# Validate migration state and imports
python scripts/predeploy_migration_check.py
```
