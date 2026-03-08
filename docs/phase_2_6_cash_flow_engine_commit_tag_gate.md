# Phase 2.6 Commit / Tag Gate

## Hard gate requirements
- Fresh DB migration success at `0023_phase2_6_cash_flow`.
- Integration suite green, including:
  - migration
  - append-only
  - supersession
  - RLS
  - determinism
  - isolation
  - API control-plane checks
- Full pytest green.
- No drift in frozen module outputs/tokens/order.
- No upstream mutation and no posting side effects.

## Commit message
`Phase 2.6 — Cash Flow Engine (Ownership + FX aware) DB-verified closure (deterministic, drillable, isolated)`

## Tag
`PHASE_2_6_CASH_FLOW_ENGINE_DB_VERIFIED_FROZEN`

## Stop conditions
- Migration error.
- RLS leak.
- Append-only bypass.
- Supersession drift.
- Frozen-module token/output drift.
- Upstream mutation or journal side effect.
