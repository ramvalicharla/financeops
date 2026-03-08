# Phase 2.4 Invariants

## Hard Invariants
- Append-only on all Phase 2.4 tables.
- RLS ENABLE + FORCE on all Phase 2.4 tables.
- Deterministic run token for identical inputs.
- Deterministic ordering for translated rows and evidence rows.
- Fail-closed rate selection when required rate is missing.
- No implicit rate-type selection.
- No mixed reporting currencies within one translation run.
- No mutation of source consolidation outputs.
- No journal creation / accounting engine mutation.

## Supersession Invariants
- Definitions are append-only via supersedes chain.
- Self-supersession rejected.
- Cross-code supersession rejected.
- Branching supersession rejected.
- Cycles rejected.
- One active definition per constrained scope/code via partial unique index.

## Replay Invariants
- Executed run with existing translated rows is idempotent.
- Repeated run creation with same deterministic payload resolves to same token and same run row.
- Snapshot mismatch between run-stored definition tokens and active snapshot blocks execution.

