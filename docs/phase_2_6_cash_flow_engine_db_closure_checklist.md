# Phase 2.6 DB Closure Checklist

## Migration checks
- [ ] Alembic head reaches `0023_phase2_6_cash_flow` on fresh DB.
- [ ] All six cash-flow tables created.
- [ ] Required PK/FK/UNIQUE/CHECK constraints present.
- [ ] Supersession triggers attached and working.

## Governance checks
- [ ] RLS enabled on every cash-flow table.
- [ ] FORCE RLS enabled on every cash-flow table.
- [ ] Append-only triggers attached to every cash-flow table.

## Determinism checks
- [ ] Same run inputs produce identical `run_token`.
- [ ] Re-execution is idempotent.
- [ ] Line and evidence ordering remains stable.
- [ ] Missing source metric fails closed.

## Isolation checks
- [ ] No mutation of source consolidation rows.
- [ ] No mutation of FX translated rows.
- [ ] No mutation of ownership consolidated rows.
- [ ] No journal side effects.
- [ ] No accounting engine side effects.

## API/control-plane checks
- [ ] Context token required.
- [ ] Module/RBAC deny paths enforced.
- [ ] Tenant scoping enforced end-to-end.
