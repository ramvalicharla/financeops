# Phase 2.6 Cash Flow Engine Design

## Audit summary
- Authoritative source result ledgers found:
  - `multi_entity_consolidation_metric_results`
  - `fx_translated_metric_results`
  - `ownership_consolidation_metric_results`
- Consolidation/FX/ownership run ledgers used as source references:
  - `multi_entity_consolidation_runs`
  - `fx_translation_runs`
  - `ownership_consolidation_runs`
- Existing board-pack dependency path remains read-only and unchanged.
- No accounting engine mutation path is introduced.

## Scope implemented in v1
- Deterministic cash-flow statement definitions (versioned, supersession-only).
- Deterministic cash-flow line mappings (versioned, supersession-only).
- Deterministic bridge rule definitions for indirect-method derived lines.
- Immutable cash-flow run ledger with deterministic run token.
- Immutable line result ledger and evidence linkage ledger.
- Ownership-aware and FX-aware source selection:
  - ownership source takes precedence if provided
  - otherwise FX source if provided
  - otherwise consolidation source

## Deterministic processing
- Run token input includes:
  - tenant/org/reporting period
  - statement definition version token
  - line mapping version token
  - bridge rule version token
  - source run references (consolidation required, FX/ownership optional)
  - run status (`created`)
- Stable ordering:
  - mappings ordered by `(mapping_code, line_order, id)`
  - line results ordered by `line_no`
  - evidence ordered by creation sequence and id

## Cash-flow semantics (v1)
- Indirect-method bridge supported through `bridge_logic_json.derived_lines`.
- Mappings reference source metrics directly or derived bridge keys (`derived:<key>`).
- Missing required source metrics fail closed.
- No silent classification, no implicit ownership weighting in old paths, no implicit FX plug.

## Governance controls
- Append-only on all Phase 2.6 tables.
- RLS + FORCE RLS enabled on all Phase 2.6 tables.
- Supersession validation triggers on definition tables.
- Control-plane module code: `cash_flow_engine`.

## Future placeholders
- Direct-method specialized bridges.
- Dedicated board-pack cash-flow section renderer.
- Additional statement templates and richer working-capital bridge conventions.
