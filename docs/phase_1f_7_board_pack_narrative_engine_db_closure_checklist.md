# Phase 1F.7 — DB Closure Checklist

## Migration
- [ ] `0019_phase1f7_board_pack_narrative` applies cleanly on fresh Postgres.
- [ ] Alembic head resolves to `0019_phase1f7_board_pack_narrative`.

## Schema Objects
- [ ] All expected tables exist:
  - `board_pack_definitions`
  - `board_pack_section_definitions`
  - `narrative_templates`
  - `board_pack_inclusion_rules`
  - `board_pack_runs`
  - `board_pack_results`
  - `board_pack_section_results`
  - `board_pack_narrative_blocks`
  - `board_pack_evidence_links`
- [ ] Expected PK/FK/UNIQUE/CHECK constraints exist.
- [ ] Expected indexes exist.
- [ ] Supersession triggers exist on definition registries.
- [ ] Append-only triggers exist on all board-pack tables.

## RLS
- [ ] RLS enabled on all board-pack tables.
- [ ] FORCE RLS enabled on all board-pack tables.
- [ ] Cross-tenant read denied.
- [ ] Cross-tenant insert denied.

## Append-only
- [ ] UPDATE rejected on registries, runs, and output ledgers.
- [ ] DELETE rejected by append-only trigger policy.
- [ ] Append-only registry includes all board-pack tables.

## Determinism
- [ ] Same inputs create same run token and idempotent `run_id`.
- [ ] Re-execute is idempotent and does not duplicate outputs.
- [ ] Output ordering for sections/narratives/evidence is stable.

## API / Control Plane
- [ ] Missing context token denied.
- [ ] Module disabled denied.
- [ ] Missing RBAC denied.
- [ ] Wrong-tenant execution denied.
- [ ] Authorized tenant path succeeds for create/execute/read APIs.

## Isolation
- [ ] No accounting engine table mutation during board-pack flow.
- [ ] No journal side effects.
- [ ] No FX table side effects.
- [ ] No mutation of upstream ratio/risk/anomaly/reconciliation/normalization rows.

## Closure Rule
- Phase 1F.7 is DB-closed only when all checklist items pass under Postgres-backed integration tests plus full pytest.
