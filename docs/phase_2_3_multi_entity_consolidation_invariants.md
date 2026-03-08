# Phase 2.3 Multi-Entity / Consolidation Invariants

1. Append-only on all Phase 2.3 tables.
2. No update-in-place for hierarchy/scope/rule/adjustment versions.
3. Supersession remains linear and cycle-free.
4. Hierarchy nodes reject cyclic parent chains.
5. RLS enabled and FORCE RLS on all new tables.
6. All API writes require control-plane + RBAC dependency.
7. Consolidation run token is deterministic from stable inputs.
8. Deterministic ordering for hierarchy traversal and result lines.
9. No writes to normalization/reconciliation/ratio/risk/anomaly/board-pack upstream outputs.
10. No journal generation and no accounting engine mutation.
11. Intercompany and adjustment are explicit analytical hooks only in v1.
12. Evidence links preserve drillable lineage to source refs and version tokens.
