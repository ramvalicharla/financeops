# Phase 2.3 Multi-Entity / Consolidation DB Closure Checklist

## Migration
- [ ] `alembic upgrade head` reaches `0020_phase2_3_multi_entity_consolidation`.
- [ ] Fresh DB creates all Phase 2.3 tables.
- [ ] All expected PK/FK/unique/check constraints exist.
- [ ] Supersession + hierarchy integrity triggers exist and compile.

## Security and Governance
- [ ] RLS enabled on every Phase 2.3 table.
- [ ] FORCE RLS enabled on every Phase 2.3 table.
- [ ] Tenant-isolation policy exists on every Phase 2.3 table.
- [ ] Append-only triggers attached to every Phase 2.3 table.

## Determinism
- [ ] Same inputs produce identical run token.
- [ ] Same inputs produce identical metric/variance output ordering.
- [ ] Repeated execute is idempotent and does not duplicate rows.

## Isolation
- [ ] No writes to accounting engine tables.
- [ ] No writes to normalization/reconciliation/ratio/risk/anomaly/board-pack result tables.
- [ ] No journal side effects.
- [ ] No FX side effects.

## API/Control Plane
- [ ] Context token required.
- [ ] Module enablement required for `multi_entity_consolidation`.
- [ ] RBAC permissions enforced per endpoint.
- [ ] Cross-tenant reads/writes denied.
