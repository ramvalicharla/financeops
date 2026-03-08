# Phase 2.5 Commit / Tag Gate

## Hard gate requirements
- Fresh DB migration success at `0022_phase2_5_ownership_consol`.
- Integration suite green (including ownership migration/append-only/RLS/determinism/API tests).
- Full pytest green.
- No drift in frozen module behavior.
- No upstream mutation and no journal side effects.
- Ownership cycle rejection verified.

## Commit message
`Phase 2.5 — Ownership / Minority Interest / Proportionate Consolidation Layer DB-verified closure (deterministic, attribution-aware, drillable, isolated)`

## Tag
`PHASE_2_5_OWNERSHIP_CONSOLIDATION_DB_VERIFIED_FROZEN`

## Stop conditions
- Any migration error.
- Any RLS leak.
- Any append-only bypass.
- Any deterministic/token drift in frozen modules.
- Any detected upstream mutation or posting side effect.
