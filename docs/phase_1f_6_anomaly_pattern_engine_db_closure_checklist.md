# Phase 1F.6 DB Closure Checklist

## Migration
- [ ] `alembic upgrade head` reaches `0018_phase1f6_anomaly_pattern`
- [ ] all 1F.6 tables exist
- [ ] expected constraints/indexes/triggers exist

## Governance
- [ ] RLS ENABLE + FORCE verified on all 1F.6 tables
- [ ] append-only update/delete rejection verified live
- [ ] supersession trigger rejection verified live

## Determinism
- [ ] duplicate create input returns same run token and run id
- [ ] duplicate execute is idempotent (no duplicate result rows)
- [ ] changed source set changes run token
- [ ] results/signals/rollforwards/evidence stable across repeated reads
- [ ] z-score and baseline outputs are stable across reruns

## Control Plane
- [ ] missing context token denied
- [ ] module disabled denied
- [ ] missing RBAC denied
- [ ] tenant-cross execution denied
- [ ] valid allow-path succeeds

## Isolation
- [ ] no accounting engine schedule mutation
- [ ] no journal table side effect
- [ ] no normalization/reconciliation/ratio/risk upstream mutation
- [ ] no FX side effect

## Closure Gate
Hard gate pass requires all sections above green in Postgres-backed integration and full pytest.
