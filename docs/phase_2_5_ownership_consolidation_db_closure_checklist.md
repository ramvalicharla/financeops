# Phase 2.5 DB Closure Checklist

## Migration checks
- [ ] Alembic head reaches `0022_phase2_5_ownership_consol` on fresh DB.
- [ ] All eight ownership tables created.
- [ ] All expected PK/FK/UNIQUE/CHECK constraints present.
- [ ] Supersession and ownership integrity triggers present.

## Governance checks
- [ ] RLS enabled on every ownership table.
- [ ] FORCE RLS enabled on every ownership table.
- [ ] Append-only triggers attached to every ownership table.

## Determinism checks
- [ ] Same ownership run inputs produce identical `run_token`.
- [ ] Re-execution is idempotent.
- [ ] Result and evidence ordering remains stable.

## Isolation checks
- [ ] No mutation of source consolidation rows during ownership runs.
- [ ] No mutation of Phase 2.4 translated rows.
- [ ] No journal side effects.
- [ ] No accounting engine side effects.

## API/control-plane checks
- [ ] Ownership endpoints fail closed without valid context token.
- [ ] Tenant scoping enforced through RLS and control-plane module code.
