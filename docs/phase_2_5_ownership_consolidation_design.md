# Phase 2.5 Ownership / Minority Interest / Proportionate Consolidation Design

## Audit alignment
- Reused Phase 2.3 source outputs from `multi_entity_consolidation_*` tables.
- Reused Phase 2.4 optional FX run linkage through `fx_translation_runs`.
- No existing ownership/minority implementation was present; this phase is additive.

## Module boundary
- New module: `backend/financeops/modules/ownership_consolidation/`.
- No mutations to accounting engines, normalization, reconciliation, Phase 2.3, or Phase 2.4 outputs.
- Ownership-aware flows are explicit via `/api/v1/ownership/...` endpoints.

## Schema added
- `ownership_structure_definitions`
- `ownership_relationships`
- `ownership_consolidation_rule_definitions`
- `minority_interest_rule_definitions`
- `ownership_consolidation_runs`
- `ownership_consolidation_metric_results`
- `ownership_consolidation_variance_results`
- `ownership_consolidation_evidence_links`

## Deterministic behavior
- Version tokens are deterministic from canonical row payloads.
- Run token is deterministic from period + version tokens + source refs + optional FX run ref.
- Stable sorting is used for source refs, source rows, result rows, and evidence rows.
- Idempotent create/execute semantics are preserved.

## Ownership semantics implemented in v1
- Explicit ownership relationships with effective dating and status.
- Explicit proportionate vs full application via relationship flag.
- Explicit minority-interest attribution via relationship flag + percentage.
- No implicit ownership inference from hierarchy.
- No hidden minority-interest deduction in legacy/non-ownership paths.

## Future placeholders (not implemented in v1)
- Equity-method accounting treatment logic.
- Journal posting for NCI/equity entries.
- Complex mixed-rule attribution per metric family beyond explicit rule payloads.
