# Phase 2.4 DB Closure Checklist

## Migration
- [ ] Fresh Postgres migration reaches `0021_phase2_4_fx_translation`.
- [ ] New Phase 2.4 tables created.
- [ ] Expected constraints and indexes created.
- [ ] Supersession triggers compiled/attached.

## Security
- [ ] RLS enabled on all Phase 2.4 tables.
- [ ] FORCE RLS enabled on all Phase 2.4 tables.
- [ ] Cross-tenant read blocked in DB-level tests.

## Append-only
- [ ] Update rejection verified on definition tables.
- [ ] Update rejection verified on run/result/evidence tables.
- [ ] Central append-only registry includes all new Phase 2.4 tables.

## Determinism
- [ ] Deterministic run token stable across repeated inputs.
- [ ] Repeated execute path idempotent.
- [ ] Output ordering stable.

## Isolation
- [ ] Source consolidation counts unchanged by translation execution.
- [ ] No journal side effects.
- [ ] No accounting engine side effects.

## API / Governance
- [ ] Control-plane token required for Phase 2.4 endpoints.
- [ ] Module-specific enforcement uses `fx_translation_reporting`.

