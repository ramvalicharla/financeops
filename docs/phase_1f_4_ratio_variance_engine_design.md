# Phase 1F.4 Ratio & Variance Engine Design

## Scope
Phase 1F.4 adds a separate deterministic module at `backend/financeops/modules/ratio_variance_engine/`.

The module computes metric, variance, and trend outputs from normalized/reconciled inputs while preserving append-only, RLS, control-plane, and engine isolation requirements.

## Boundaries
Allowed:
- versioned definition intake (metric/variance/trend/materiality)
- deterministic run creation and execution
- immutable metric/variance/trend/evidence result writes
- deterministic API reads

Forbidden:
- accounting engine table mutation
- journal generation
- upstream normalization mutation
- reconciliation history mutation
- in-place updates/deletes

## Database Objects
Migration: `0016_phase1f4_ratio_variance.py`

Tables:
- `metric_definitions`
- `metric_definition_components`
- `variance_definitions`
- `trend_definitions`
- `materiality_rules`
- `metric_runs`
- `metric_results`
- `variance_results`
- `trend_results`
- `metric_evidence_links`

Schema guarantees:
- append-only triggers on all tables
- RLS ENABLE + FORCE on all tables
- tenant isolation policies on all tables
- supersession triggers for definition tables
- partial unique single-active indexes per definition code

## Deterministic Pipeline
1. Validate tenant-scoped source references and active definition sets.
2. Build deterministic definition tokens and input signature hash.
3. Build deterministic `run_token` for `created` status.
4. Idempotent create by `tenant_id + run_token`.
5. Execute into deterministic `completed` status run row.
6. Aggregate upstream values deterministically.
7. Compute metrics from versioned components.
8. Compute variances from definition types and deterministic baselines.
9. Compute trends (rolling/trailing/directional) deterministically.
10. Persist results in stable ordering and append evidence links.

## API Surface
- `POST /ratio-variance/metric-definitions`
- `GET /ratio-variance/metric-definitions`
- `GET /ratio-variance/metric-definitions/{id}/versions`
- `POST /ratio-variance/variance-definitions`
- `GET /ratio-variance/variance-definitions`
- `GET /ratio-variance/variance-definitions/{id}/versions`
- `POST /ratio-variance/trend-definitions`
- `GET /ratio-variance/trend-definitions`
- `GET /ratio-variance/trend-definitions/{id}/versions`
- `POST /ratio-variance/materiality-rules`
- `GET /ratio-variance/materiality-rules`
- `GET /ratio-variance/materiality-rules/{id}/versions`
- `POST /ratio-variance/runs`
- `POST /ratio-variance/runs/{id}/execute`
- `GET /ratio-variance/runs/{id}`
- `GET /ratio-variance/runs/{id}/summary`
- `GET /ratio-variance/runs/{id}/metrics`
- `GET /ratio-variance/runs/{id}/variances`
- `GET /ratio-variance/runs/{id}/trends`
- `GET /ratio-variance/runs/{id}/evidence`

## Control Plane
Module code: `ratio_variance_engine`

Permissions:
- `ratio_variance_run`
- `ratio_variance_view`
- `metric_definition_manage`
- `variance_definition_manage`
- `trend_definition_manage`
- `materiality_rule_manage`
- `ratio_variance_evidence_view`
