# Phase 2.1 — Shared Kernel Refactor Design

## Scope
- Non-functional refactor only.
- No schema semantic changes.
- No API semantic changes.
- No domain-business logic movement.

## Extracted Shared Kernel
- New package:
  - `backend/financeops/shared_kernel/`
  - `backend/financeops/shared_kernel/tokens/`
- New shared token primitives:
  - `build_token(payload, sorted_list_fields=...)`
  - `build_version_rows_token(rows)`
- File:
  - `backend/financeops/shared_kernel/tokens/token_hashing.py`

## Refactored Callers (behavior-preserving)
- `mis_manager` token builder
- `reconciliation_bridge` token builder
- `payroll_gl_normalization` token builder
- `payroll_gl_reconciliation` token builder
- `ratio_variance_engine` token builder
- `financial_risk_engine` token builder
- `anomaly_pattern_engine` token builder
- `board_pack_narrative_engine` token builder

All retain identical payload fields, identical canonical serialization, identical hash algorithm, and identical list-sorting semantics where applicable.

## Baseline/Equivalence Artifacts
- Baseline token snapshot captured:
  - `docs/phase_2_1_baseline_token_artifacts.json`
- Enforced by test:
  - `backend/tests/unit/test_phase2_1_shared_kernel_token_equivalence.py`

## No-Drift Validation Strategy
- Token equality:
  - baseline artifact vs post-refactor computed output.
- Ordering/output stability:
  - deterministic integration suites for 1F.1–1F.7.
- API/DB behavior:
  - full integration suite.
- Global regression:
  - full pytest suite.

## Intentionally Left Local
- Ratio formulas, variance formulas, risk scoring semantics.
- Anomaly scoring/persistence semantics.
- Narrative phrasing and board-pack inclusion business rules.
- Payroll/reconciliation domain classification logic.

These remain module-local to avoid semantic drift.
