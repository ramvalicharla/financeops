# Phase 2.1 — Shared Kernel Refactor Invariants

## Refactor Invariants
1. Token outputs remain byte-identical for same inputs.
2. Canonical serialization and SHA-256 hashing remain unchanged.
3. List ordering normalization in token payloads remains unchanged.
4. No business-logic movement across module boundaries.
5. No changes to API contracts or semantic meanings.
6. No schema-meaning drift.
7. RLS and FORCE RLS behavior remains unchanged.
8. Append-only trigger/registry behavior remains unchanged.
9. Supersession trigger behavior remains unchanged.
10. Deterministic ordering of results/sections/evidence remains unchanged.

## Verified by
- Token equivalence test against frozen baseline:
  - `backend/tests/unit/test_phase2_1_shared_kernel_token_equivalence.py`
- Determinism integration suites:
  - `test_*_determinism_phase1f*.py` (all frozen modules)
- Migration verification suites:
  - `test_*_migration_phase1f*.py`
- Full integration and full pytest regressions.

## Non-Goals (unchanged)
- No new financial formulas.
- No new risk/anomaly/narrative semantics.
- No permission widening.
- No control-plane policy weakening.
