# Phase 2.1 — Commit/Tag Gate

## Hard Gates
1. Token equivalence test passes against baseline artifact.
2. Determinism integration suites (1F.1–1F.7) pass.
3. Migration verification suites pass on fresh DB.
4. Full integration suite passes.
5. Full pytest suite passes.
6. No RLS, append-only, or supersession drift detected.
7. No API semantic drift detected.
8. No output ordering drift detected.

## Soft Gates
1. Shared-kernel extraction remains domain-neutral.
2. Domain semantics intentionally remain local.
3. Refactor docs reflect final implementation and evidence.

## Commit Message
`Phase 2.1 — Architectural Refactoring & Shared Kernel Hardening (non-functional, no-drift, regression-safe)`

## Tag
`PHASE_2_1_SHARED_KERNEL_REFACTOR_DB_VERIFIED_FROZEN`

## Rule
- Do not commit/tag if any hard gate fails.
