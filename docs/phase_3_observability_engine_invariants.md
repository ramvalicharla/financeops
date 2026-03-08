# Phase 3 Observability Engine Invariants

## Hard Invariants
- Append-only storage for all observability tables.
- RLS enabled + FORCE RLS on all observability tables.
- Tenant-scoped access only.
- No writes to frozen financial tables.
- No journal generation.
- No mutation of upstream run tokens.
- No mutation of upstream evidence payloads.

## Determinism Invariants
- Same diff inputs produce identical diff summary and deterministic chain hash.
- Same graph root run with unchanged upstream state produces identical deterministic graph hash.
- Replay validation uses deterministic token recomputation and strict equality check.
- Dependency and output ordering is stable (sorted node/edge/material output order).

## Supersession Invariants
- `run_token_diff_definitions`:
  - No self-supersession.
  - No cross-comparison-type supersession.
  - No branching.
  - Single active definition per `(tenant_id, comparison_type)` by partial unique index.

## Fail-Closed Invariants
- Missing upstream run reference: hard failure.
- Unsupported replay module: hard failure.
- Invalid diff input (same run IDs): hard failure.

