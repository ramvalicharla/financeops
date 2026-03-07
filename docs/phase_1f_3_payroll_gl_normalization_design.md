# Phase 1F.3 Payroll / GL Normalization Design

## Scope
- Deterministic canonical normalization layer for payroll and GL source families.
- Converts uploaded CSV/XLSX source artifacts into canonical append-only normalized lines.
- Supports downstream reconciliation, MIS alignment, and analytics extracts.
- No writes to accounting engine tables, MIS snapshots, or reconciliation outcomes.

## Canonical Outputs
- Payroll:
  - `payroll_normalized_lines`
  - Canonical employee/dimension fields and payroll metric facts.
- GL:
  - `gl_normalized_lines`
  - Canonical transaction/dimension fields with deterministic signed amount handling.

## Determinism
- Version identity:
  - `normalization_source_versions.version_token`
- Run identity:
  - `normalization_runs.run_token`
- Same `source + source_version + mapping_version + period + file_hash + run_status` yields same token.
- Stable output ordering by source row and deterministic repository ordering.

## Append-only
- Insert-only data path via `AuditWriter`.
- DB trigger-based update/delete blocking on normalization tables.
- No in-place overwrite for source versions, mappings, runs, normalized lines, exceptions, or evidence.

## Governance / Security
- RLS ENABLE + FORCE on all normalization tables.
- Tenant-scoped repository reads.
- Control-plane enforcement module code: `payroll_gl_normalization`.
- Endpoint-level permission checks:
  - `normalization_source_create`
  - `normalization_mapping_review`
  - `normalization_run_create`
  - `normalization_run_view`
  - `normalization_exception_resolve`
  - `normalization_extract_view`

## API Surface
- Sources:
  - `POST /normalization/sources/detect`
  - `POST /normalization/sources/commit-version`
  - `GET /normalization/sources`
  - `GET /normalization/sources/{id}/versions`
- Runs:
  - `POST /normalization/runs/upload`
  - `POST /normalization/runs/{id}/validate`
  - `POST /normalization/runs/{id}/finalize`
  - `GET /normalization/runs/{id}`
  - `GET /normalization/runs/{id}/exceptions`
- Extracts:
  - `GET /normalization/runs/{id}/payroll-lines`
  - `GET /normalization/runs/{id}/gl-lines`
  - `GET /normalization/runs/{id}/summary`
