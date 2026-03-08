# Phase 2.4 FX Translation & Reporting Currency Layer Design

## Scope
- Additive module: `backend/financeops/modules/fx_translation_reporting/`
- Purpose: deterministic, append-only reporting-currency translation on top of frozen source-currency consolidation outputs.
- No mutation of upstream engines, normalization, reconciliation, ratio/risk/anomaly/board-pack histories.

## Audit Alignment
- Reused existing authoritative FX sources:
  - `fx_manual_monthly_rates`
  - `fx_rate_quotes`
  - `fx_rate_fetch_runs` (provider lineage context)
- Reused month-end lock semantics from existing FX service model (`is_month_end_locked`).
- Translation consumes:
  - `multi_entity_consolidation_metric_results`
  - `multi_entity_consolidation_variance_results`

## Schema Additions
- `reporting_currency_definitions`
- `fx_translation_rule_definitions`
- `fx_rate_selection_policies`
- `fx_translation_runs`
- `fx_translated_metric_results`
- `fx_translated_variance_results`
- `fx_translation_evidence_links`

All new tables are append-only, RLS enabled + force RLS, tenant-isolated.

## Deterministic Execution
- Deterministic run token includes period/org/reporting currency/version tokens/source refs/status.
- Stable source ordering:
  - metrics: `(run_id, line_no, id)`
  - variances: `(run_id, line_no, id)`
- Stable output ordering:
  - translated metrics/variances by `(line_no, id)`
  - evidence by `(created_at, id)`

## Rate Selection
- Identity multiplier for same source/reporting currency.
- Locked policy path:
  - requires month-end locked manual monthly rate (direct or inverse)
  - fail-closed if missing unless explicit configured unlocked-manual fallback
- Non-locked policy path:
  - manual monthly precedence (direct/inverse)
  - quote-based selection by `rate_type` (`closing`, `average`, `historical`)
  - optional configured fallback from average to closing
  - otherwise fail-closed
- Inverse rates use deterministic reciprocal conversion.

## API Surface
- `/api/v1/fx/reporting-currencies*`
- `/api/v1/fx/translation-rules*`
- `/api/v1/fx/rate-policies*`
- `/api/v1/fx/runs*` (+ summary/metrics/variances/risks/anomalies/board-pack/evidence)

## Control Plane
- Module code: `fx_translation_reporting`
- Permissions:
  - `fx_translation_run`
  - `fx_translation_view`
  - `reporting_currency_manage`
  - `fx_translation_rule_manage`
  - `fx_rate_policy_manage`
  - `fx_translation_evidence_view`

