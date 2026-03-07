# Phase 1F.3 Payroll / GL Normalization Commit/Tag Gate

## Hard Gates
- Migration applies cleanly on fresh Postgres.
- Integration suite passes with Phase 1F.3 tests.
- Full pytest suite passes.
- RLS and append-only checks pass.
- Supersession checks pass.
- Determinism and idempotency checks pass.
- No accounting engine/reconciliation/journal/FX side effects.

## Soft Gates
- Design and invariant docs match implementation.
- API permissions are explicit and control-plane enforced.
- Error responses remain deterministic and fail-closed.

## Freeze Tag
- `PHASE_1F3_PAYROLL_GL_NORMALIZATION_DB_VERIFIED_FROZEN`
