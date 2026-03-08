# Phase 2.7 Equity / OCI / CTA Engine Design

## Audit Summary
- Consolidation source ledger used: `multi_entity_consolidation_metric_results` via `multi_entity_consolidation_runs`.
- FX source ledger used: `fx_translated_metric_results` via `fx_translation_runs`.
- Ownership source ledger used: `ownership_consolidation_metric_results` via `ownership_consolidation_runs`.
- No dedicated equity/OCI/CTA run/result ledger existed before this phase.
- Reporting-currency basis already existed in FX layer and is referenced, not mutated.

## Module Boundary
- New isolated module: `backend/financeops/modules/equity_engine/`.
- Additive API wiring under `/api/v1/equity`.
- No mutation path to consolidation, FX, ownership, cash flow, or accounting engine tables.

## Schema Added
- `equity_statement_definitions`
- `equity_line_definitions`
- `equity_rollforward_rule_definitions`
- `equity_source_mappings`
- `equity_runs`
- `equity_line_results`
- `equity_statement_results`
- `equity_evidence_links`

## Deterministic Engine Rules
- Run token includes period, org, definition/rule/mapping version tokens, and source run refs.
- Same inputs produce same `run_token` and idempotent run reuse.
- Rollforward computation is deterministic with fixed ordering (`presentation_order`, then `id`).
- Retained earnings bridge, CTA movement, and minority-interest contribution are explicit rule-driven calculations.

## Control Plane + Security
- Module code: `equity_engine`.
- Permissions enforced via control-plane dependency:
  - `equity_definition_manage`
  - `equity_rule_manage`
  - `equity_run`
  - `equity_view`
- RLS ENABLE + FORCE enabled on all new tables.
- Append-only triggers enabled on all new tables.

## Semantics Implemented in v1
- Opening/movement/closing rollforward at line level.
- Explicit retained-earnings bridge rule application.
- Explicit CTA derivation from FX translated minus source value.
- Explicit ownership/minority contribution path.
- Evidence links to mapping/rule version tokens and source run refs.

## Explicit Non-goals in v1
- No journal posting.
- No source restatement/mutation.
- No silent fallback when required source runs are missing.
