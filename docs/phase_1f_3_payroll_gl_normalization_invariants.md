# Phase 1F.3 Payroll / GL Normalization Invariants

1. Normalization does not mutate source artifacts or source rows.
2. Normalization does not mutate accounting engine tables or schedules.
3. Normalization does not mutate reconciliation bridge state.
4. Normalization does not create journals.
5. Source versions are append-only and supersession is linear only.
6. Mapping history is append-only and version-aware.
7. Runs are append-only and replay-safe by deterministic `run_token`.
8. Canonical normalized lines are append-only and drillable to source lineage.
9. Exceptions and evidence links are append-only.
10. RLS ENABLE + FORCE is mandatory for all normalization tables.
11. Control-plane enforcement is mandatory for all normalization endpoints.
12. Unmapped source data is explicit via exception flow; no silent drops.
