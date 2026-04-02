# Incident Response Guide (Phase 11D)

## Incident Workflow
1. Identify symptom and severity.
2. Capture correlation IDs and tenant scope.
3. Verify dependency state (`/api/v1/platform/ops/dependencies`).
4. Mitigate using safe actions only.
5. Document timeline, root cause, and follow-up actions.

## 1) Auth Failure / MFA Incident
- Symptoms: login failures, MFA verify failures, 401/403 spikes.
- Diagnose:
  - check auth endpoints and token expiry behavior
  - inspect recent session status via `/api/v1/platform/ops/sessions/status`
- Safe actions:
  - revoke compromised sessions
  - reset MFA for impacted users through admin flow

## 2) Database Unavailable
- Symptoms: `/ready` fails DB check, 5xx on protected endpoints.
- Diagnose:
  - DB connectivity, credentials, network, pool saturation
- Safe actions:
  - fail closed for writes
  - restore DB connectivity before reopening traffic

## 3) Redis Unavailable
- Symptoms: degraded queue behavior, cache misses, worker issues.
- Diagnose:
  - Redis ping and connection errors
- Safe actions:
  - keep core DB-backed finance flows available if possible
  - restore Redis before re-enabling dependent async workloads

## 4) ERP Sync Stuck/Failing
- Symptoms: `failed/halted/paused` sync runs, rising sync alerts.
- Diagnose:
  - `/api/v1/platform/ops/jobs/status`
  - `/api/v1/erp-sync/health`
- Safe actions:
  - use safe retry only for paused+resumable runs:
    `POST /api/v1/platform/ops/jobs/erp-sync/{run_id}/retry`
  - start fresh run for non-resumable failures

## 5) Consolidation Run Failure
- Symptoms: missing or failed consolidated outputs.
- Diagnose:
  - consolidation run APIs and logs with correlation ID
- Safe actions:
  - rerun with same validated period inputs
  - verify no locked-period conflicts

## 6) Revaluation/Translation Failure
- Symptoms: FX run failures, inconsistent reporting output.
- Diagnose:
  - run status in `/api/v1/platform/ops/jobs/status`
  - latest FX rate availability
- Safe actions:
  - rerun after fixing rate availability or period lock constraints

## 7) Period Close Blocked
- Symptoms: readiness/checklist blockers prevent close.
- Diagnose:
  - close readiness endpoint and blockers list
- Safe actions:
  - resolve open drafts/imbalances
  - do not bypass governance chain

## 8) AI/Analytics Degradation
- Symptoms: slow/failing AI/analytics routes, narrative generation delays.
- Diagnose:
  - AI health and observability metrics/logs
- Safe actions:
  - degrade AI features while keeping deterministic finance paths online

## 9) Large Upload Failure
- Symptoms: 4xx/5xx on upload routes, parser/rejection errors.
- Diagnose:
  - request size/content validation logs
  - antivirus/format validation outcomes
- Safe actions:
  - enforce size/type constraints
  - reattempt with validated files only

## 10) Migration Failure
- Symptoms: app startup mismatch, migration head drift, Alembic errors.
- Diagnose:
  - `python scripts/predeploy_migration_check.py`
  - `/api/v1/platform/ops/migrations/status`
- Safe actions:
  - stop rollout
  - restore from backup if destructive step failed
  - re-run migration from known-safe point

## Escalation
- Escalate immediately for:
  - data integrity risk
  - cross-tenant data exposure risk
  - prolonged DB unavailability
  - migration corruption scenarios
