# Phase 1F.7 — Board Pack & Narrative Engine Invariants

## Hard Invariants
1. Append-only persistence for all board-pack tables.
2. No in-place update/delete allowed after insert.
3. RLS enabled and forced on all board-pack tables.
4. Tenant context is mandatory for every read/write path.
5. Supersession chains are linear (no self, no branch, no cycle intent).
6. At most one active version per code per tenant/org for registries.
7. Same run inputs yield identical `run_token`.
8. Same run inputs yield identical ordered outputs.
9. Section and narrative ordering is deterministic.
10. Evidence linkage is append-only and drillable.
11. No mutation of upstream ratio/risk/anomaly/reconciliation/normalization outputs.
12. No accounting engine writes.
13. No journal creation.
14. No FX side effects.
15. Control-plane enforcement is fail-closed.

## Deterministic Construction Inputs
- `reporting_period`
- `organisation_id`
- definition version token aggregate
- section version token aggregate
- narrative template version token aggregate
- inclusion rule version token aggregate
- source metric run IDs
- source risk run IDs
- source anomaly run IDs
- status marker

## Required Failure Behavior
- Missing upstream runs => reject run creation.
- Missing active definition sets => reject run creation/execution.
- Duplicate source run IDs => reject.
- Wrong-tenant access => deny (403/404).
- Invalid supersession insert => database error (trigger/constraint).
