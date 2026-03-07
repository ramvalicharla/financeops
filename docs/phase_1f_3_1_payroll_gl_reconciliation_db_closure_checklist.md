# Phase 1F.3.1 Payroll ↔ GL Reconciliation DB Closure Checklist

## Migration
- [ ] Fresh Postgres migration to head succeeds (`0015_phase1f3_1_pg_gl_recon`).
- [ ] New payroll-gl reconciliation tables exist.
- [ ] Supersession triggers exist and are attached.
- [ ] Required indexes and constraints exist.

## RLS
- [ ] RLS ENABLE + FORCE confirmed on all new payroll-gl reconciliation tables.
- [ ] Cross-tenant read and insert are denied in DB-backed tests.

## Append-only
- [ ] Update attempts on mappings/rules/runs/run_scopes are rejected by DB.
- [ ] Append-only registry includes all new payroll-gl reconciliation tables.

## Supersession
- [ ] Valid linear supersession accepted.
- [ ] Self supersession rejected.
- [ ] Cross-code supersession rejected.
- [ ] Branching supersession rejected.
- [ ] Cyclic supersession rejected.
- [ ] Single active version per mapping/rule code enforced.

## Determinism
- [ ] Same inputs create same run token.
- [ ] Repeated execute path is idempotent.
- [ ] Line ordering and contents are stable across repeats.
- [ ] Mapping/rule input changes alter token as expected.

## Control Plane
- [ ] Context token required.
- [ ] Module enablement enforced (`payroll_gl_reconciliation`).
- [ ] RBAC action checks enforced.
- [ ] Wrong-tenant access denied.

## Isolation
- [ ] No writes to accounting engine schedule tables.
- [ ] No writes to journal tables.
- [ ] No mutation of normalization output tables.
- [ ] No FX side effects.

## Freeze Gate
- [ ] Integration suite green.
- [ ] Full pytest suite green.
- [ ] All hard gates pass.

