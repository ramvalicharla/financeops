# Phase 1F.3.1 Payroll ↔ GL Reconciliation Design

## Scope
- Add payroll-finance control module on top of:
  - `payroll_gl_normalization` (1F.3)
  - `reconciliation_bridge` (1F.2)
- Reconcile finalized payroll normalized runs vs finalized GL normalized runs.
- Keep deterministic, append-only, tenant-isolated behavior.

## Module Boundary
- New module: `backend/financeops/modules/payroll_gl_reconciliation/`.
- No payroll-specific business rules were injected into:
  - `reconciliation_bridge`
  - `payroll_gl_normalization`
  - accounting engines
  - MIS manager
- Only additive integration points:
  - API router registration
  - append-only table registry extension
  - test control-plane seeding and module routing.

## Database Additions
- `payroll_gl_reconciliation_mappings`
- `payroll_gl_reconciliation_rules`
- `payroll_gl_reconciliation_runs`
- `payroll_gl_reconciliation_run_scopes`

All new tables enforce:
- append-only trigger
- RLS ENABLE + FORCE
- tenant-isolation policy
- deterministic lookup indexes
- supersession checks (mappings/rules): self/cross-code/branch/cycle rejection

## Deterministic Run Model
- Run token inputs:
  - tenant
  - organisation
  - payroll_run_id
  - gl_run_id
  - mapping_version_token
  - rule_version_token
  - reporting_period
  - run status
- Same inputs produce same `run_token`.
- Run lifecycle is append-only (`created` → `completed`) using distinct rows.

## Matching and Classification
- Staged deterministic matching:
  - mapped payroll metric aggregate tie to selected GL accounts
  - dimension-sensitive checks (entity/department/cost center)
  - timing window check (`max_lag_days`)
  - explicit unmatched GL bucket capture
- Payroll-specific difference type is retained in line dimensions.
- Core reconciliation `difference_type` stays within frozen 1F.2 allowed values.

## Evidence and Workflow
- Uses 1F.2 core tables for lines/exceptions/events/evidence.
- On exception lines:
  - exception row appended
  - `exception_opened` event appended
  - evidence links appended (payroll run / GL run artifact refs)
- Manual actions:
  - attach evidence
  - resolve
  - reopen

## API Surface
- Mappings:
  - `POST /payroll-gl-reconciliation/mappings`
  - `GET /payroll-gl-reconciliation/mappings`
  - `GET /payroll-gl-reconciliation/mappings/{id}/versions`
- Rules:
  - `POST /payroll-gl-reconciliation/rules`
  - `GET /payroll-gl-reconciliation/rules`
  - `GET /payroll-gl-reconciliation/rules/{id}/versions`
- Runs:
  - `POST /payroll-gl-reconciliation/runs`
  - `POST /payroll-gl-reconciliation/runs/{id}/execute`
  - `GET /payroll-gl-reconciliation/runs/{id}`
  - `GET /payroll-gl-reconciliation/runs/{id}/summary`
  - `GET /payroll-gl-reconciliation/runs/{id}/lines`
  - `GET /payroll-gl-reconciliation/runs/{id}/exceptions`
- Actions:
  - `POST /payroll-gl-reconciliation/lines/{id}/attach-evidence`
  - `POST /payroll-gl-reconciliation/lines/{id}/resolve`
  - `POST /payroll-gl-reconciliation/lines/{id}/reopen`

## Control Plane
- Module code: `payroll_gl_reconciliation`
- Enforced per endpoint:
  - valid context token
  - module enablement
  - RBAC action + resource checks
  - quota + isolation routing (platform interceptors)

