# Phase 2.2 Performance Hardening Commit/Tag Gate

## Hard Gates
All must pass:
1. Full integration suite green.
2. Full pytest suite green.
3. Token equivalence green.
4. Determinism suites (1F.1–1F.7) green.
5. No RLS/append-only/supersession regression.
6. Fresh migration path valid.
7. Profiling before/after artifacts present.
8. No business semantic drift.

## Soft Gates
- Profiling hotspots documented.
- Optimization rationale documented.
- Before/after metrics documented.

## Stop Conditions
Do not commit/tag if any of the following fail:
- token drift
- ordering drift
- output drift
- RLS drift
- append-only drift
- supersession drift
- migration failure

## Recommended Commit Message
`Phase 2.2 — Performance Optimization Hardening (non-functional, profiling-guided, no-drift)`

## Recommended Tag
`PHASE_2_2_PERFORMANCE_HARDENING_DB_VERIFIED_FROZEN`
