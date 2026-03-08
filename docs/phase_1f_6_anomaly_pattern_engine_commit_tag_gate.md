# Phase 1F.6 Commit/Tag Gate

## Hard Gates
1. Migration to head passes on fresh Postgres.
2. Integration suite passes with 1F.6 migration/append-only/RLS/supersession/determinism/isolation/API checks.
3. Full pytest suite passes.
4. No hard-stop condition observed (RLS leakage, append-only bypass, unstable tokens/outputs, upstream side effects, non-deterministic ordering).

## Soft Gates
1. Docs reflect implemented behavior.
2. Invariants match DB/runtime behavior.
3. Error paths are explicit and fail-closed.

## Stop Conditions
- Migration failure
- RLS leakage
- Append-only bypass
- Determinism instability
- Upstream mutation side effect
- Journal side effect
- FX side effect

## Commit
`Phase 1F.6 — Anomaly & Pattern Detection Engine DB-verified closure (deterministic, statistical-baseline-enabled, persistent, correlated, drillable, isolated)`

## Tag
`PHASE_1F6_ANOMALY_PATTERN_ENGINE_DB_VERIFIED_FROZEN`
