# Phase 3 Observability & Governance Layer Design

## Scope
Phase 3 adds a read-oriented observability layer on top of frozen financial modules. It introduces deterministic introspection, token diffing, replay verification, lineage graph snapshots, governance event surfacing, and run performance telemetry.

## Architectural Boundaries
- New module: `backend/financeops/modules/observability_engine/`
- Financial modules are read-only dependencies.
- No mutation of financial run/result ledgers, no journal creation, no re-computation of financial meaning.
- Observability writes are append-only into observability-specific tables only.

## Data Model
- `observability_run_registry`: discovered upstream runs and token snapshots.
- `run_token_diff_definitions`: versioned diff definition registry (supersession guarded).
- `run_token_diff_results`: immutable diff outcomes.
- `lineage_graph_snapshots`: deterministic dependency graphs.
- `governance_events`: governance trace events.
- `run_performance_metrics`: per-operation telemetry.
- `observability_runs`: operation ledger (`diff`, `replay_validate`, `graph_snapshot`, etc.).
- `observability_results`: immutable operation payloads.
- `observability_evidence_links`: drillable evidence pointers.

## Deterministic Processing
- Token generation uses `shared_kernel.tokens.build_token`.
- Diff payload key ordering and dependency sorting are deterministic.
- Graph nodes/edges are sorted before hashing and persistence.
- Replay validation compares stored run token vs deterministic recomputation for supported modules (`equity_engine`, `cash_flow_engine`).

## API Surface
- `GET /observability/runs`
- `GET /observability/runs/{id}`
- `GET /observability/runs/{id}/dependencies`
- `POST /observability/diff`
- `GET /observability/diff/{id}`
- `POST /observability/replay-validate/{run_id}`
- `GET /observability/graph/{run_id}`
- `GET /observability/events/{run_id}`
- `GET /observability/performance/{run_id}`

## Governance Enforcement
- Module context: `observability_engine`
- Control-plane permissions:
  - `observability_view`
  - `observability_diff`
  - `observability_replay_validate`
  - `observability_graph_view`
- Tenant RLS isolation and FORCE RLS enabled for all new tables.

