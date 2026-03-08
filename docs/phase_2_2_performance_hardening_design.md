# Phase 2.2 Performance Hardening Design

## Scope
- Non-functional optimization only.
- Preserved deterministic outputs, token values, ordering, API semantics, RLS/FORCE RLS, append-only, supersession.
- Touched only hot-path repository/service query patterns in:
  - Ratio & Variance Engine
  - Financial Risk Engine
  - Anomaly Pattern Engine
  - Board Pack Narrative Engine

## Profiling Baseline
Baseline artifact: `docs/phase_2_2_profile_baseline.json`.

Measured flows:
- ratio
- risk
- anomaly
- board_pack

Captured:
- query count
- DB time
- elapsed time

## Bottlenecks Identified
- Repeated run validation lookups (per-run-id DB fetch loops).
- Repeated prior-result lookups (per metric/risk/anomaly code loops).
- Multiple count queries in run summaries (4 separate queries per summary).
- Component-loading N+1 in ratio metric definition resolution.

## Optimizations Applied
1. Batched run validation lookups.
- Added batched repository methods and replaced per-id fetch loops:
  - metric runs
  - risk runs
  - anomaly runs
  - reconciliation sessions

2. Batched prior-series/prior-state retrieval.
- Ratio: fetch prior metric series for all metric codes in one query and partition in-memory.
- Risk: fetch latest prior risk rows for all risk codes in one query.
- Anomaly: fetch latest prior anomaly rows for all anomaly codes in one query.

3. Batched component fetch.
- Ratio: fetch all metric definition components for definition set in one query and group by definition id.

4. Consolidated summary count queries.
- Ratio/Risk/Anomaly/Board-Pack run summaries now use one statement with scalar subqueries instead of multiple round-trips.

5. Profiling harness hardening.
- Added stable SQL statement fingerprint aggregation and hotspot capture without nested event-loop runtime warnings.
- Added post-change artifact: `docs/phase_2_2_profile_after.json`.

## Safety Constraints
- No formula changes.
- No token builder changes.
- No ordering logic changes.
- No schema semantic changes.
- No permission/control-plane changes.
- No RLS/append-only/supersession logic changes.
