# Phase 2.6 Cash Flow Engine Invariants

1. Append-only only:
- No `UPDATE`/`DELETE` on Phase 2.6 ledgers.
- Corrections require superseding versions or new runs.

2. Deterministic run identity:
- Same inputs + same version tokens => same `run_token`.

3. Deterministic ordering:
- Mapping, line-result, and evidence ordering is stable and replay-safe.

4. Fail-closed source validation:
- Missing required source metrics fail execution explicitly.

5. Source isolation:
- No mutation of consolidation, FX translation, ownership, or accounting-engine outputs.

6. No posting side effects:
- No journal creation and no accounting engine invocation.

7. Tenant isolation:
- RLS + FORCE RLS on all Phase 2.6 tables, tenant-scoped access only.

8. Supersession integrity:
- No self-supersession, no branching, no cycles in definition chains.

9. Control-plane enforcement:
- Every endpoint requires valid context token + module enablement + RBAC.

10. Backward compatibility:
- Existing frozen module outputs and semantics remain unchanged.
