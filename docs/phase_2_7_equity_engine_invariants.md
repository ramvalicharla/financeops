# Phase 2.7 Equity Engine Invariants

## Hard Invariants
- Append-only on all equity tables.
- RLS ENABLE + FORCE on all equity tables.
- Supersession is linear: no self-supersession, no branching, no cycles.
- One active definition per logical code family enforced by partial unique indexes.
- Deterministic run token for identical run inputs.
- Deterministic output ordering by stored sequence fields.
- Fail-closed if required source runs are missing for active rules/mappings.
- No upstream mutation of consolidation/FX/ownership/cash-flow/accounting-engine data.
- No journal creation side effects.

## Replay Invariants
- `create_run` is idempotent on `run_token`.
- `execute_run` is idempotent once line results exist.
- Historical results are immutable and explainable by:
  - statement/line/rule/mapping version tokens
  - source run refs
  - evidence links
