# Phase 2.4 Commit / Tag Gate

## Hard Gate Criteria
- Migration to head succeeds on fresh Postgres.
- Phase 2.4 integration tests pass (migration, RLS, append-only, determinism/API).
- Full integration suite passes.
- Full pytest suite passes.
- No drift in frozen module behavior.
- No upstream mutation side effects detected.

## Stop Conditions
- Migration failure.
- RLS leakage.
- Append-only bypass.
- Deterministic token/output drift.
- Silent FX fallback acceptance.
- Missing-rate fail-closed violation.
- Upstream mutation/journal side effects.

## Commit / Tag (only if all hard gates pass)
- Commit message:
  - `Phase 2.4 — FX Translation & Reporting Currency Layer DB-verified closure (deterministic, rule-versioned, drillable, isolated)`
- Tag:
  - `PHASE_2_4_FX_TRANSLATION_REPORTING_DB_VERIFIED_FROZEN`

