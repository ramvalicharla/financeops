# Phase 1F.2 Reconciliation Bridge Commit/Tag Gate

## Hard Gates
- Migration applies cleanly on fresh Postgres.
- Integration suite passes with reconciliation bridge tests included.
- Full pytest passes.
- RLS and append-only checks pass.
- Determinism checks pass for GL vs TB and MIS vs TB.
- No accounting engine/journal side effects.

## Soft Gates
- Design and invariant docs reflect implementation.
- API contracts and permissions are explicit.
- Error responses are deterministic/fail-closed.

## Freeze Tag
- `PHASE_1F2_RECONCILIATION_BRIDGE_DB_VERIFIED_FROZEN`
