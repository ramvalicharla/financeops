# Phase 1F.1 MIS Manager Design

## Scope
Phase 1F.1 introduces an audit-grade MIS Manager layer above accounting engines. It ingests MIS artifacts (CSV/XLSX), detects template structure deterministically, versions template layouts append-only, detects drift explicitly, and stores immutable normalized snapshots for downstream reconciliation/reporting.

## Hard Boundaries
- No writes to revenue/lease/prepaid/fixed-assets tables.
- No journal generation.
- No schedule regeneration.
- No FX conversion logic inside MIS workflows.
- No in-place updates to template versions or snapshot records.
- No silent drift acceptance.

## Module Layout
Implemented under `backend/financeops/modules/mis_manager/` (repo package convention equivalent of requested `backend/src/modules/mis_manager/`).

- `domain/`: enums, value objects, entities, invariants.
- `application/`: ingest orchestration, template detection, drift detection, mapping, snapshot normalization, validation, canonical dictionary.
- `infrastructure/`: deterministic parsers, signature/token builders, DB repository.
- `api/`: request/response schemas and endpoints.
- `policies/`: control-plane policy dependency wrappers.

## Deterministic Processing
- `version_token` = SHA-256(canonical JSON of template id + structure/header/row/column hashes + detection summary).
- `snapshot_token` = SHA-256(canonical JSON of source hash + sheet + structure hash + mapping identity + rule set identity + period + template version + status).
- Same input artifact/rules/template version => same token and same normalized line output.

## Data Model
Phase 1F.1 introduces:
- `mis_template_versions`
- `mis_template_sections`
- `mis_template_columns`
- `mis_template_row_mappings`
- `mis_data_snapshots`
- `mis_normalized_lines`
- `mis_ingestion_exceptions`
- `mis_drift_events`
- `mis_canonical_metric_dictionary`
- `mis_canonical_dimension_dictionary`

And expands `mis_templates` with canonical parent fields (`organisation_id`, `template_code`, `template_name`, `template_type`, `status`) while retaining legacy fields for compatibility.

## Supersession Controls
`mis_template_versions` enforces:
- no self-supersession,
- no cross-template supersession,
- no branching children from one parent,
- no cycles.

Enforced via DB trigger `mis_template_versions_validate_supersession` plus unique/constraint checks.

## Drift Rules
- Minor drift (non-material): header-only shifts with stable row/column signatures.
- Major drift (material): row signature change, period-axis/column signature change, or structure hash mismatch.
- Material drift creates `mis_drift_events` with `pending_review`; candidate versions are not silently auto-activated.

## Validation Baseline
- Period-axis presence.
- Numeric block presence.
- P&L revenue/expense anchor checks.
- Duplicate metric+dimension grain checks.
- Mixed currency detection.
- Explicit append-only exception logging.

## Control Plane + Isolation
Every MIS endpoint now enforces:
- valid context token (`module_code=mis_manager`),
- authorizer checks (module enablement, RBAC action, quota, isolation route),
- tenant-scoped access via RLS.

## API Surface
Implemented endpoints:
- `POST /mis/templates/detect`
- `POST /mis/templates/commit-version`
- `POST /mis/snapshots/upload`
- `POST /mis/snapshots/{id}/validate`
- `POST /mis/snapshots/{id}/finalize`
- `GET /mis/templates`
- `GET /mis/templates/{id}/versions`
- `GET /mis/snapshots/{id}`
- `GET /mis/snapshots/{id}/exceptions`
- `GET /mis/drift-events/{id}`
- `GET /mis/snapshots/{id}/normalized-lines`
- `GET /mis/snapshots/{id}/summary`

## Replay and Explainability
Every output can be traced by:
- source artifact hash,
- selected sheet,
- template + template version,
- signature bundle,
- version/snapshot tokens,
- normalized lines + exception log.
