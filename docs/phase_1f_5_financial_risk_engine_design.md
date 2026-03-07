# Phase 1F.5 Financial Risk & Materiality Propagation Engine Design

## Scope
Phase 1F.5 adds a separate deterministic module at `backend/financeops/modules/financial_risk_engine/`.

The module computes versioned, dependency-aware financial risk outputs from frozen upstream metric/variance/trend/reconciliation artifacts while preserving append-only, RLS, control-plane, and upstream isolation guarantees.

## Boundaries
Allowed:
- versioned risk definition intake
- versioned dependency, weight, and materiality configuration intake
- deterministic risk run creation and execution
- immutable risk results/signal/rollforward/evidence writes
- deterministic API reads

Forbidden:
- accounting engine mutations
- journal creation
- mutation of normalization outputs
- mutation of reconciliation outcomes
- mutation of ratio/variance outputs
- in-place updates/deletes of risk history

## Database Objects
Migration: `0017_phase1f5_financial_risk.py`

Tables:
- `risk_definitions`
- `risk_definition_dependencies`
- `risk_weight_configurations`
- `risk_materiality_rules`
- `risk_runs`
- `risk_results`
- `risk_contributing_signals`
- `risk_rollforward_events`
- `risk_evidence_links`

Schema guarantees:
- append-only triggers on all 1F.5 tables
- RLS ENABLE + FORCE on all 1F.5 tables
- tenant isolation policies on all 1F.5 tables
- supersession triggers for definitions/weights/materiality
- cycle-rejection trigger for risk dependency graph
- partial unique single-active indexes for versioned registries

## Deterministic Pipeline
1. Validate source run/session references and completed-state availability.
2. Resolve active risk definitions, dependencies, weights, and materiality rules.
3. Build deterministic version tokens and deterministic `run_token`.
4. Idempotent create by `tenant_id + run_token`.
5. Execute into deterministic `completed` status row.
6. Aggregate source signals from metric/variance/trend/reconciliation inputs.
7. Execute deterministic topological order for dependency-aware scoring.
8. Compute score, confidence, severity, materiality, board flag, persistence state.
9. Persist deterministic result ordering with append-only signals, rollforwards, evidence.

## API Surface
- `POST /financial-risk/risk-definitions`
- `GET /financial-risk/risk-definitions`
- `GET /financial-risk/risk-definitions/{id}/versions`
- `POST /financial-risk/risk-weights`
- `GET /financial-risk/risk-weights`
- `GET /financial-risk/risk-weights/{id}/versions`
- `POST /financial-risk/materiality-rules`
- `GET /financial-risk/materiality-rules`
- `GET /financial-risk/materiality-rules/{id}/versions`
- `POST /financial-risk/runs`
- `POST /financial-risk/runs/{id}/execute`
- `GET /financial-risk/runs/{id}`
- `GET /financial-risk/runs/{id}/summary`
- `GET /financial-risk/runs/{id}/results`
- `GET /financial-risk/runs/{id}/signals`
- `GET /financial-risk/runs/{id}/rollforwards`
- `GET /financial-risk/runs/{id}/evidence`

## Control Plane
Module code: `financial_risk_engine`

Permissions:
- `financial_risk_run`
- `financial_risk_view`
- `risk_definition_manage`
- `risk_weight_manage`
- `risk_materiality_manage`
- `financial_risk_evidence_view`
