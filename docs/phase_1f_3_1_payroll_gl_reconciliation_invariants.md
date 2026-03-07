# Phase 1F.3.1 Payroll ↔ GL Reconciliation Invariants

1. Payroll-GL reconciliation never mutates payroll/GL normalization source outputs.
2. Payroll-GL reconciliation never mutates accounting engine tables or schedules.
3. Payroll-GL reconciliation never creates journals.
4. Payroll-GL reconciliation never invokes FX side-effect flows.
5. Mapping and rule histories are append-only and supersession-linear.
6. Run history is append-only; no update-in-place lifecycle mutation.
7. Reconciliation core writes are additive only (sessions/lines/exceptions/events/evidence).
8. Deterministic token identity is mandatory for run reproducibility.
9. Same inputs produce same reconciliation run token and same output set.
10. Exception and evidence workflow is append-only.
11. RLS ENABLE + FORCE applies to all payroll-gl reconciliation domain tables.
12. Control-plane enforcement is mandatory for all payroll-gl reconciliation APIs.
13. Tenant and organisation scoping must be validated before execution.
14. Missing required mapping/rule state fails closed; no best-effort run.

