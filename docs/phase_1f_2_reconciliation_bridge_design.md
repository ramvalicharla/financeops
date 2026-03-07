# Phase 1F.2 Reconciliation Bridge Design

## Scope
- Deterministic reconciliation control layer above MIS, GL, and TB.
- No writes to accounting engine tables.
- No journal creation.
- No FX side effects.

## Reconciliation Types (v1)
- `gl_vs_trial_balance`
- `mis_vs_trial_balance`

## Determinism
- Session identity via deterministic `session_token`.
- Stable line generation order by deterministic key material.
- Repeat run on same session is idempotent and returns existing output.

## Append-only
- Reconciliation tables are insert-only via DB triggers.
- Resolution and evidence are event-appended; no mutation paths.

## Security/Governance
- RLS ENABLE + FORCE on all reconciliation bridge tables.
- Tenant-scoped repository filters.
- Control plane guard per endpoint with module code `reconciliation_bridge`.
- Required permission set:
  - `reconciliation_session_create`
  - `reconciliation_run`
  - `reconciliation_view`
  - `reconciliation_exception_resolve`
  - `reconciliation_evidence_attach`
  - `reconciliation_review`

## API Surface
- `POST /reconciliation/sessions`
- `POST /reconciliation/sessions/{id}/run`
- `GET /reconciliation/sessions/{id}`
- `GET /reconciliation/sessions/{id}/summary`
- `GET /reconciliation/sessions/{id}/lines`
- `GET /reconciliation/sessions/{id}/exceptions`
- `POST /reconciliation/lines/{id}/explain`
- `POST /reconciliation/lines/{id}/attach-evidence`
- `POST /reconciliation/lines/{id}/resolve`
- `POST /reconciliation/lines/{id}/reopen`
