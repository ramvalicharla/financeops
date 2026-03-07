# Phase 1F.2 Reconciliation Bridge Invariants

1. Reconciliation bridge does not mutate source datasets (GL, TB, MIS, engine outputs).
2. Session creation is deterministic by `session_token`.
3. Same session run is idempotent and replay-safe.
4. Reconciliation line math invariant:
   - `variance_value = source_a_value - source_b_value`
5. Resolution and evidence history are append-only.
6. RLS ENABLE + FORCE enforced on all bridge tables.
7. Control plane enforcement required for all bridge endpoints.
8. No reconciliation bridge path writes journals or regenerates schedules.
