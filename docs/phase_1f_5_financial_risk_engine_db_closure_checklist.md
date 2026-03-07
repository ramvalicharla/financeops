# Phase 1F.5 DB Closure Checklist

## Migration
- [ ] `alembic upgrade head` reaches `0017_phase1f5_financial_risk`
- [ ] all 1F.5 tables exist
- [ ] expected constraints/indexes/triggers exist

## Governance
- [ ] RLS ENABLE + FORCE verified on all 1F.5 tables
- [ ] append-only update/delete rejection verified live
- [ ] supersession trigger rejection verified live
- [ ] dependency-cycle trigger rejection verified live

## Determinism
- [ ] duplicate create input returns same run token and run id
- [ ] duplicate execute is idempotent (no duplicate result rows)
- [ ] changed source set changes run token
- [ ] results/signals/rollforwards stable across repeated reads

## Control Plane
- [ ] missing context token denied
- [ ] module disabled denied
- [ ] missing RBAC denied
- [ ] tenant-cross execution denied
- [ ] valid allow-path succeeds

## Isolation
- [ ] no accounting engine schedule mutation
- [ ] no journal table side effect
- [ ] no normalization/reconciliation/ratio upstream mutation
- [ ] no FX side effect

## Closure Gate
Hard gate pass requires all sections above green in Postgres-backed integration and full pytest.
