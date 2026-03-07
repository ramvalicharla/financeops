# Phase 1F.1 MIS Manager Commit/Tag Gate

## Hard Gate Criteria (Must Pass)
1. `0012_phase1f1_mis_manager` applies cleanly on fresh Postgres.
2. All expected MIS DB objects exist:
   - tables
   - constraints
   - indexes
   - triggers
3. RLS is verified end-to-end and `FORCE RLS` is active on all MIS tables in scope.
4. Append-only enforcement is verified in live DB.
5. Supersession trigger rules are verified in live DB.
6. Snapshot idempotency is verified in live DB.
7. Control-plane API enforcement is verified for deny and allow paths.
8. No accounting engine side effects are detected from MIS flows.
9. Deterministic outputs are stable across repeated runs.

## Soft Gate Criteria (Should Pass)
1. Closure docs match implemented behavior and test evidence.
2. Invariant docs match actual DB/runtime behavior.
3. Error messages and reason codes are clear and stable.
4. Any intentionally allowed mutation path is explicitly documented.

## Stop Conditions (Do Not Freeze)
1. Any hard-gate test fails.
2. Any test is replaced by mocked proof where DB-backed proof is required.
3. Any cross-tenant or control-plane bypass is detected.
4. Any append-only or RLS weakening is introduced.
5. Any accounting engine mutation occurs during MIS flows.

## Recommended Commit Message
`phase(1f1): db-backed closure verification for mis manager (migration/append-only/rls/idempotency/control-plane/isolation)`

## Recommended Tag
`PHASE_1F1_MIS_MANAGER_DB_VERIFIED_FROZEN`

## Release Decision Rule
- Apply the recommended tag only when all hard gates are green.
- If any hard gate is red, mark Phase 1F.1 as `NOT DB-CLOSED` and publish blocker details.

