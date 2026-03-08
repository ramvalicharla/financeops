# Phase 1F.6 Anomaly & Pattern Detection Engine Design

## Scope
Phase 1F.6 adds a separate deterministic module at `backend/financeops/modules/anomaly_pattern_engine/`.

The module computes point, persistent, correlated, and statistical-baseline anomaly outputs from frozen upstream ratio/variance/trend/risk/reconciliation datasets while preserving append-only, RLS, control-plane, and upstream isolation guarantees.

## Boundaries
Allowed:
- versioned anomaly definition/rule intake
- deterministic anomaly run creation and execution
- immutable anomaly result/signal/rollforward/evidence writes
- deterministic API reads

Forbidden:
- accounting engine mutations
- journal creation
- mutation of normalization outputs
- mutation of reconciliation outcomes
- mutation of ratio/variance/risk outputs
- in-place updates/deletes of anomaly history

## Database Objects
Migration: `0018_phase1f6_anomaly_pattern.py`

Tables:
- `anomaly_definitions`
- `anomaly_pattern_rules`
- `anomaly_persistence_rules`
- `anomaly_correlation_rules`
- `anomaly_statistical_rules`
- `anomaly_runs`
- `anomaly_results`
- `anomaly_contributing_signals`
- `anomaly_rollforward_events`
- `anomaly_evidence_links`

Schema guarantees:
- append-only triggers on all 1F.6 tables
- RLS ENABLE + FORCE on all 1F.6 tables
- tenant isolation policies on all 1F.6 tables
- supersession triggers for definitions and rule registries
- partial unique single-active indexes for versioned registries

## Deterministic Pipeline
1. Validate source run/session references and completed-state availability.
2. Resolve active definitions and active pattern/persistence/correlation/statistical rule sets.
3. Build deterministic version tokens and deterministic `run_token`.
4. Idempotent create by `tenant_id + run_token`.
5. Execute into deterministic `completed` status row.
6. Build deterministic metric/variance/trend/risk/reconciliation signal maps.
7. Compute rolling baseline, z-score, and severity/materiality/risk elevation deterministically.
8. Compute persistence/correlation classification deterministically.
9. Persist deterministic result ordering with append-only signals, rollforwards, evidence.

## API Surface
- `POST /anomaly-engine/anomaly-definitions`
- `GET /anomaly-engine/anomaly-definitions`
- `GET /anomaly-engine/anomaly-definitions/{id}/versions`
- `POST /anomaly-engine/pattern-rules`
- `GET /anomaly-engine/pattern-rules`
- `POST /anomaly-engine/persistence-rules`
- `GET /anomaly-engine/persistence-rules`
- `POST /anomaly-engine/correlation-rules`
- `GET /anomaly-engine/correlation-rules`
- `POST /anomaly-engine/statistical-rules`
- `GET /anomaly-engine/statistical-rules`
- `POST /anomaly-engine/runs`
- `POST /anomaly-engine/runs/{id}/execute`
- `GET /anomaly-engine/runs/{id}`
- `GET /anomaly-engine/runs/{id}/results`
- `GET /anomaly-engine/runs/{id}/signals`
- `GET /anomaly-engine/runs/{id}/rollforwards`
- `GET /anomaly-engine/runs/{id}/evidence`

## Control Plane
Module code: `anomaly_pattern_engine`

Permissions:
- `anomaly_engine_run`
- `anomaly_engine_view`
- `anomaly_definition_manage`
- `anomaly_pattern_rule_manage`
- `anomaly_persistence_rule_manage`
- `anomaly_correlation_rule_manage`
- `anomaly_statistical_rule_manage`
- `anomaly_engine_evidence_view`
