# Phase 1F.5 Financial Risk Engine Invariants

1. All 1F.5 tables are append-only; update/delete is blocked by trigger.
2. All 1F.5 tables enforce RLS ENABLE + FORCE with tenant policy.
3. Supersession chains are linear-only: no self/cross/branch/cycle.
4. Dependency graph cycles are rejected at insert time.
5. Same run inputs + same version tokens + same status => same run token.
6. Same completed run inputs produce stable risk/signal/rollforward/evidence outputs.
7. Result ordering is deterministic by risk code/topological order and line number.
8. Severity, confidence, materiality, and board-attention outcomes are deterministic.
9. Rollforward events are append-only and derive deterministically from persistence/confidence state.
10. Evidence links are append-only and tie every result to source/version lineage.
11. No writes to accounting engine/journal/fx tables in 1F.5 flow.
12. No mutation of normalization, reconciliation, or ratio/variance upstream outputs.
