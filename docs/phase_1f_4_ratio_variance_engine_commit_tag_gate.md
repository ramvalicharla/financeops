# Phase 1F.4 Commit/Tag Gate

## Hard Gates
1. Migration to head passes on fresh Postgres.
2. Integration suite passes with 1F.4 migration/append-only/RLS/supersession/determinism/isolation/API checks.
3. Full pytest suite passes.
4. No hard-stop condition observed (RLS leakage, append-only bypass, unstable tokens, side effects).

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

## Commit
`Phase 1F.4 — Ratio & Variance Engine DB-verified closure (deterministic, versioned, materiality-aware, drillable, isolated)`

## Tag
`PHASE_1F4_RATIO_VARIANCE_ENGINE_DB_VERIFIED_FROZEN`
