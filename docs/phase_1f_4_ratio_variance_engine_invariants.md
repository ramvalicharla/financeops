# Phase 1F.4 Ratio & Variance Engine Invariants

1. All 1F.4 tables are append-only; update/delete is blocked by trigger.
2. All 1F.4 tables enforce RLS ENABLE + FORCE with tenant policy.
3. Definition supersession is linear-only, no self/cross/branch/cycle.
4. Only one active definition per `(tenant, organisation, definition_code)`.
5. Same inputs + same definition versions + same status => same run token.
6. Same completed run inputs produce stable metric/variance/trend outputs.
7. Result ordering is deterministic by metric/comparison/trend keys.
8. Materiality and favorable/unfavorable classification are deterministic.
9. Evidence links are append-only and tied to run/result lineage.
10. No writes to accounting engine/journal tables in 1F.4 flow.
11. No mutation of normalization outputs or reconciliation core outcomes.
