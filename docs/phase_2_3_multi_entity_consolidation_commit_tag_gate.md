# Phase 2.3 Multi-Entity / Consolidation Commit + Tag Gate

## Hard Gates
- Fresh Postgres migration passes to `0020_phase2_3_multi_entity_consolidation`.
- Integration tests for migration/RLS/append-only/determinism/isolation pass.
- Full pytest passes.
- No frozen-module drift detected.
- No upstream mutation side effects detected.

## Soft Gates
- Phase docs align with implementation.
- Error messages are explicit and fail-closed.
- Deterministic ordering and token behavior are documented.

## Stop Conditions
- Migration failure.
- RLS leakage.
- Append-only bypass.
- Supersession/hierarchy cycle protection failure.
- Run token drift.
- Evidence/linkage loss.
- Any upstream mutation side effect.

## Commit
`Phase 2.3 — Multi-Entity / Consolidation Extension DB-verified closure (deterministic, hierarchy-aware, drillable, isolated)`

## Tag
`PHASE_2_3_MULTI_ENTITY_CONSOLIDATION_DB_VERIFIED_FROZEN`

Tag only if all hard gates pass.
