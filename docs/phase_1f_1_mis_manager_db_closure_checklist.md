# Phase 1F.1 MIS Manager DB Closure Checklist

## Scope Lock
- Phase: `1F.1` only.
- Accounting engine modules untouched: `revenue`, `lease`, `prepaid`, `fixed_assets`.
- No journal creation logic added in MIS Manager.
- No FX logic added in MIS Manager.
- No schedule regeneration paths added.

## Migration Checks
- `0012_phase1f1_mis_manager` upgrades cleanly on fresh Postgres.
- Alembic version in migrated DB is exactly `0012_phase1f1_mis_manager`.
- All required MIS tables exist.
- Supersession trigger function and trigger are present.
- Append-only triggers are present for MIS append-only tables.

## Schema Checks
- PK/FK/UNIQUE/CHECK constraints exist for MIS tables.
- Partial unique index for single active template version exists:
  `uq_mis_template_versions_one_active`.
- Deterministic lookup indexes exist for list/read paths.
- Model-to-migration compatibility verified for Phase 1F.1 fields.

## Append-Only Checks
- UPDATE is rejected on:
  - `mis_template_versions`
  - `mis_data_snapshots`
  - `mis_normalized_lines`
  - `mis_ingestion_exceptions`
  - `mis_drift_events`
- DELETE is rejected on append-only MIS tables.
- `APPEND_ONLY_TABLES` registry includes all Phase 1F.1 MIS tables.
- Repository paths do not bypass append-only DB protections.

## Supersession Checks
- Valid linear supersession chain is accepted.
- Rejected at DB level:
  - self-supersession
  - cross-template supersession
  - branching from same parent
  - cyclic supersession attempt
  - second active version for same template
  - malformed supersedes reference

## Idempotency Checks
- Identical upload inputs produce identical `snapshot_token`.
- Duplicate upload is idempotent and does not create invalid duplicate lines.
- Token changes when expected:
  - file content hash changes
  - reporting period changes
  - template version changes

## RLS Checks
- RLS is enabled and forced on all MIS tables in scope.
- Tenant A can read Tenant A data.
- Tenant A cannot read Tenant B data.
- Tenant A cannot insert Tenant B scoped snapshot data.
- Tenant A cannot read Tenant B normalized lines.

## Control-Plane API Checks
- Deny paths verified:
  - missing context token
  - invalid context token
  - module disabled
  - missing RBAC permission
  - quota exceeded
  - routing resolution failure
  - wrong-tenant finalize access
- Allow path verified for valid authorized tenant-scoped access.
- Normalized lines endpoint returns tenant-scoped results only.

## Determinism Checks
- Signature builder repeatability is stable.
- Version/snapshot token generation repeatability is stable.
- Detection pipeline output is stable for fixed fixture input.
- Validation output is stable for fixed fixture input.

## Isolation Checks
- MIS upload/validate/finalize does not mutate accounting engine tables.
- MIS finalize does not create journal rows.
- MIS pipeline does not write FX tables.

## Hard Gate Pass Condition
- Every hard-gate test in the Phase 1F.1 DB closure suite passes.
- No failing test masked, skipped, or mocked to bypass DB proof.
- No accounting engine side effects detected.

## Hard Gate Fail Condition
- Any migration/append-only/RLS/supersession/idempotency/control-plane/isolation test fails.
- Any non-deterministic replay behavior is observed on fixed input.
- Any cross-tenant leakage is detected.

