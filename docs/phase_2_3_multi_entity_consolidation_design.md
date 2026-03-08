# Phase 2.3 Multi-Entity / Consolidation Extension Design

## Scope
- Adds a new isolated module: `financeops.modules.multi_entity_consolidation`.
- Preserves frozen module behavior and upstream immutability.
- Introduces hierarchy-aware, consolidation-aware deterministic analytical runs.

## New Schema
- Versioned hierarchy/config tables:
  - `entity_hierarchies`
  - `entity_hierarchy_nodes`
  - `consolidation_scopes`
  - `consolidation_rule_definitions`
  - `intercompany_mapping_rules`
  - `consolidation_adjustment_definitions`
- Run/result tables:
  - `multi_entity_consolidation_runs`
  - `multi_entity_consolidation_metric_results`
  - `multi_entity_consolidation_variance_results`
  - `multi_entity_consolidation_evidence_links`

## Determinism
- Run token includes reporting period, selected active version tokens, and ordered source references.
- Hierarchy traversal uses deterministic topological ordering.
- Result ordering uses stable sort keys and line numbers.

## Governance
- Append-only enforced on all new tables.
- RLS enabled and forced on all new tables.
- Control-plane dependency uses module code: `multi_entity_consolidation`.

## API Surface
- Configuration:
  - `POST/GET /consolidation/hierarchies`
  - `POST/GET /consolidation/scopes`
  - `POST/GET /consolidation/rules`
  - `POST/GET /consolidation/intercompany-rules`
  - `POST/GET /consolidation/adjustment-definitions`
- Runs:
  - `POST /consolidation/runs`
  - `POST /consolidation/runs/{id}/execute`
  - `GET /consolidation/runs/{id}`
  - `GET /consolidation/runs/{id}/summary`
  - `GET /consolidation/runs/{id}/metrics`
  - `GET /consolidation/runs/{id}/variances`
  - `GET /consolidation/runs/{id}/risks`
  - `GET /consolidation/runs/{id}/anomalies`
  - `GET /consolidation/runs/{id}/board-pack`
  - `GET /consolidation/runs/{id}/evidence`

## Explicit v1 Boundaries
- No journal creation.
- No accounting engine invocation.
- No implicit FX or ownership weighting.
- No silent intercompany elimination.
