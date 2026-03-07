# Phase 1F.3.1 Payroll ↔ GL Reconciliation Commit/Tag Gate

## Hard Gates (all required)
- Migration to head passes on fresh Postgres.
- New payroll-gl reconciliation schema objects are present and valid.
- RLS isolation passes with FORCE RLS verified.
- Append-only behavior passes on domain tables.
- Supersession trigger enforcement passes.
- Deterministic run token and repeat-run stability pass.
- Control-plane API enforcement pass.
- No accounting engine, journal, or FX side effects.
- No mutation of normalization source outputs.

## Soft Gates
- Design/invariants/checklist docs aligned to implementation.
- Error messages are explicit and fail-closed.
- Additive-only integration with reconciliation bridge is preserved.

## Stop Conditions
- Any hard gate failure.
- Any RLS leakage or append-only bypass.
- Any non-deterministic output drift for same inputs.
- Any disallowed side effects.

## Recommended Commit Message
`Phase 1F.3.1 — Payroll ↔ GL Reconciliation DB-verified closure (deterministic, append-only, evidence-linked, isolated)`

## Recommended Tag
`PHASE_1F3_1_PAYROLL_GL_RECONCILIATION_DB_VERIFIED_FROZEN`

