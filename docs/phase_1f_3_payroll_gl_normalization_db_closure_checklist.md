# Phase 1F.3 Payroll / GL Normalization DB Closure Checklist

## Migration
- [x] Fresh Postgres migration to head succeeds (`0014_phase1f3_pglnorm`).
- [x] Normalization tables, constraints, indexes, triggers, and policies are present.

## RLS
- [x] RLS ENABLE + FORCE on all normalization tables.
- [x] Cross-tenant read/insert denied in DB-backed tests.

## Append-only
- [x] Update attempts rejected on source versions, mappings, runs, lines, exceptions, and evidence.
- [x] Append-only registry includes all normalization tables.

## Supersession
- [x] Linear supersession allowed.
- [x] Self / cross-source / branch / cycle / malformed supersession rejected.
- [x] Single-active-version constraint enforced.

## Determinism / Idempotency
- [x] Token builders deterministic.
- [x] Same upload input returns same run token and same run id.
- [x] Changed file hash or period changes run token.
- [x] Detection/validation outputs stable for fixed fixture input.

## Control Plane
- [x] Context token required.
- [x] Module enablement enforced (`payroll_gl_normalization`).
- [x] RBAC permission checks enforced.
- [x] Tenant-scoped endpoint behavior verified.

## Isolation
- [x] No writes to accounting engine schedule tables.
- [x] No writes to journal tables.
- [x] No writes to reconciliation bridge tables.
- [x] No FX side effects.
