# Phase 2.7 Equity Engine DB Closure Checklist

## Migration
- [ ] `0024_phase2_7_equity_engine` upgrades cleanly on fresh Postgres.
- [ ] New tables exist.
- [ ] Expected constraints and indexes exist.
- [ ] Supersession triggers exist.
- [ ] Append-only triggers exist.

## Security
- [ ] RLS enabled on all equity tables.
- [ ] FORCE RLS enabled on all equity tables.
- [ ] Cross-tenant read denied in probe tests.

## Determinism
- [ ] Unit token stability test passes.
- [ ] Integration idempotent create/execute path passes.
- [ ] Ordered line results stable across reruns.

## Isolation
- [ ] No mutation detected in accounting engine journal tables.
- [ ] No mutation detected in upstream consolidation source rows.
- [ ] No journal side effects.

## API / Control Plane
- [ ] Missing context token denied.
- [ ] Missing RBAC denied.
- [ ] Authorized tenant-scoped access allowed.

## Regression
- [ ] Full integration suite green.
- [ ] Full pytest suite green.
- [ ] Frozen module migration head assertions updated and passing.
