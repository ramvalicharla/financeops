# Phase 2.7 Equity Engine Commit / Tag Gate

## Hard Gate (all required)
- Fresh DB migration pass at `0024_phase2_7_equity_engine`.
- Equity integration suite pass:
  - migration
  - append-only
  - supersession
  - RLS
  - API control-plane
  - determinism
  - isolation
- Full pytest suite pass.
- No frozen-module drift evidence.

## Stop Conditions
- Any migration error.
- Any RLS leak.
- Any append-only bypass.
- Any supersession integrity failure.
- Any deterministic rerun mismatch.
- Any upstream mutation/journal side effect.

## Commit / Tag (only if hard gates pass)
- Commit message:
  `Phase 2.7 — Equity / OCI / CTA Engine DB-verified closure (deterministic, FX-aware, ownership-aware, isolated)`
- Tag:
  `PHASE_2_7_EQUITY_ENGINE_DB_VERIFIED_FROZEN`
