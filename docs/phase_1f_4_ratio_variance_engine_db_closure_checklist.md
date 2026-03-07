# Phase 1F.4 DB Closure Checklist

## Migration
- [ ] `alembic upgrade head` reaches `0016_phase1f4_ratio_variance`
- [ ] all 1F.4 tables exist
- [ ] expected constraints/indexes/triggers exist

## Governance
- [ ] RLS ENABLE + FORCE verified on all 1F.4 tables
- [ ] append-only update/delete rejection verified live
- [ ] supersession trigger rejection verified live

## Determinism
- [ ] duplicate create input returns same run token and run id
- [ ] duplicate execute is idempotent (no duplicate result rows)
- [ ] changed input scope/reference changes run token
- [ ] metrics/variances/trends stable across repeated reads

## Control Plane
- [ ] missing context token denied
- [ ] module disabled denied
- [ ] missing RBAC denied
- [ ] tenant-cross execution denied
- [ ] valid allow-path succeeds

## Isolation
- [ ] no accounting engine schedule mutation
- [ ] no journal table side effect
- [ ] no normalization output mutation
- [ ] no reconciliation core mutation

## Closure Gate
Hard gate pass requires all sections above green in Postgres-backed integration and full pytest.
