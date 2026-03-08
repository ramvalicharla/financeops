# Phase 2.2 Performance Hardening Invariants

## Locked Invariants
- Token equivalence: unchanged.
- Deterministic ordering: unchanged.
- Output payload semantics: unchanged.
- API contract semantics: unchanged.
- RLS + FORCE RLS behavior: unchanged.
- Append-only enforcement: unchanged.
- Supersession behavior: unchanged.
- Cross-module isolation: unchanged.

## Explicit Non-Changes
- No accounting/business formula edits.
- No risk severity/materiality semantic edits.
- No anomaly classification semantic edits.
- No narrative semantic edits.
- No DB constraint weakening.
- No control-plane widening.

## Equivalence Proof Sources
- Token equivalence: `tests/unit/test_phase2_1_shared_kernel_token_equivalence.py`.
- Determinism suites:
  - 1F.1 MIS
  - 1F.2 reconciliation bridge
  - 1F.3 normalization
  - 1F.3.1 payroll-GL reconciliation
  - 1F.4 ratio/variance
  - 1F.5 risk
  - 1F.6 anomaly
  - 1F.7 board-pack
- Full integration and full pytest runs passed after optimization changes.
