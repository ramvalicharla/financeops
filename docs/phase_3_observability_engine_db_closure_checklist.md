# Phase 3 Observability Engine DB Closure Checklist

## Migration
- [ ] Fresh Postgres migration to head succeeds.
- [ ] Alembic head is `0025_phase3_observability_engine`.
- [ ] All observability tables exist.
- [ ] Expected indexes, constraints, and supersession trigger exist.

## RLS / Isolation
- [ ] RLS enabled on all observability tables.
- [ ] FORCE RLS enabled on all observability tables.
- [ ] Tenant A cannot read tenant B rows.
- [ ] Tenant A cannot insert tenant B-scoped rows under probe role.

## Append-Only
- [ ] Update blocked for observability run/result tables.
- [ ] Update blocked for diff/graph/event/perf ledgers.
- [ ] Observability tables included in central append-only registry.

## Determinism
- [ ] Diff output deterministic across repeat calls.
- [ ] Replay validation deterministic for supported modules.
- [ ] Graph snapshot hash stable for unchanged inputs.

## Governance / API
- [ ] Missing context token denied.
- [ ] Missing RBAC permission denied.
- [ ] Authorized tenant path allowed.

## Upstream Safety
- [ ] No changes to upstream financial run counts.
- [ ] No journal side effects.
- [ ] No token drift in frozen modules.

