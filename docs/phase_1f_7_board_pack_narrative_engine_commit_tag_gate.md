# Phase 1F.7 — Commit/Tag Gate

## Hard Gates (all required)
1. Migration applies on fresh Postgres.
2. Integration suite for Phase 1F.7 passes.
3. Full `pytest` passes.
4. Deterministic rerun behavior confirmed.
5. RLS isolation confirmed (including FORCE RLS).
6. Append-only enforcement confirmed.
7. Supersession enforcement confirmed.
8. No upstream mutation side effects.
9. No accounting engine/journal/FX side effects.

## Soft Gates
1. Design/invariants/checklist docs match implementation.
2. Error paths are explicit and stable.
3. API responses remain deterministic and tenant-scoped.

## Stop Conditions
- Migration failure.
- Cross-tenant leak.
- Append-only bypass.
- Supersession integrity break.
- Determinism instability.
- Upstream mutation detected.
- Journal or accounting-engine side effect detected.

## Commit Message
`Phase 1F.7 — Board Pack & Narrative Engine DB-verified closure (deterministic, versioned, risk-aware, drillable, isolated)`

## Tag
`PHASE_1F7_BOARD_PACK_NARRATIVE_ENGINE_DB_VERIFIED_FROZEN`

## Rule
- Commit and tag only if all hard gates pass.
