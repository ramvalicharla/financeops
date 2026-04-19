# Final Todo Lists

This is the active implementation tracker pulled from the current platform
review. We can keep updating this file as work is completed or new priorities
are added.

---

## Tier 1 - Must Implement

### 1. Full-Suite Verification Blockers And Beta Readiness Cleanup

**Status:** Pending
**Priority:** Highest

### Scope

- fix the Redis-backed test/runtime mismatch around `localhost:6380`
- stabilize auth and MFA flows that failed in the full backend verification pass
- stabilize rate-limit coverage and any `slowapi` integration regressions surfaced by the full suite
- investigate and fix the remaining unrelated failures surfaced in:
  - auth / onboarding
  - board-pack routes
  - platform finance-route token enforcement
  - health / auditor portal / pagination
  - ERP integration edge tests
- rerun a clean full backend suite and record the new pass/fail/error counts
- define the minimum beta readiness gate after the suite is green enough

### Notes

The corrected stabilization plan has been executed through P3, but the latest
full backend verification is still not green. This item is the immediate gate
before real beta onboarding.

---

### 2. Billing Plan Enablement And Manual Access Control

**Status:** Pending  
**Priority:** High

### Scope

- allow `platform owner`, `admin`, `manager`, and `sales person` roles to enable any plan for a target user or tenant
- support explicit start date and end date, including limited-duration enablement
- define whether the action applies at user level, tenant level, or both
- enforce RBAC and audit logging for every manual plan change
- prevent ambiguous overlaps between manually enabled plans and normal subscription state
- add API and service-level validation for:
  - allowed actor roles
  - allowed target scope
  - date window validity
  - plan existence
  - duplicate or conflicting active assignments
- add integration tests proving authorized roles can grant access and unauthorized roles cannot

### Notes

This is a separate commercial and access-control feature. It should not be
mixed into webhook/idempotency stabilization work, but it is important for
beta onboarding, sales-assisted activation, and controlled plan trials.

---

### 3. Quality Signals Persistence

**Status:** Pending  
**Priority:** High if quality signals are part of trust, audit, compliance, or enterprise reporting

### Scope

- design a PostgreSQL table/model for quality signals
- replace compatibility DB usage in `backend/financeops/utils/quality_signals.py`
- implement async SQLAlchemy repository/service methods
- expose clear application-level read/write flows
- add integration tests for persistence and retrieval

### Notes

If quality signals remain a reference-only utility and are not part of the
live product, this item can be deferred.

---

### 4. Production ClamAV Enforcement

**Status:** Pending  
**Priority:** High

### Scope

- deploy a real ClamAV service for production environments
- set `CLAMAV_REQUIRED=true` in production
- add AV availability health checks
- add alerting for scan failures and unavailable scanner state
- document environment-specific scanning posture

### Notes

The platform code already supports ClamAV. The remaining work is production
hardening and operations enforcement.

---

### 5. R2 Storage Validation and Reliability

**Status:** Pending  
**Priority:** High

### Scope

- add startup or readiness validation for:
  - `R2_ENDPOINT_URL`
  - `R2_ACCESS_KEY_ID`
  - `R2_SECRET_ACCESS_KEY`
  - `R2_BUCKET_NAME`
- add storage health check that verifies credentials and bucket access
- add alerting/observability for upload/download/delete/presign failures
- define expected platform behavior when storage is unavailable

### Notes

R2 integration exists already. The remaining work is production readiness and
operational safety.

---

## Tier 2 - Should Implement

### 6. Remove or Quarantine Legacy Compatibility Helpers

**Status:** Pending  
**Priority:** Medium

### Scope

- identify all remaining compatibility-only helpers
- remove them where migration is complete
- isolate them clearly where temporary compatibility is still required
- document ownership and sunset plan for each compatibility layer

---

### 7. Security and Storage Runbooks

**Status:** Pending  
**Priority:** Medium

### Scope

- create operational runbooks for:
  - ClamAV unavailable
  - R2 unavailable
  - credential rotation
  - upload failure triage
  - presigned URL misuse or expiry issues

---

### 8. Environment Posture Checks

**Status:** Pending  
**Priority:** Medium

### Scope

- add checks preventing insecure defaults from reaching production
- validate required security and storage configuration per environment
- fail fast where production-critical settings are missing

---

## Tier 3 - Optional / Conditional

### 9. Stronger Local MIME Detection on Windows

**Status:** Optional  
**Priority:** Low

### Scope

- install or document native `libmagic` support for stricter local MIME checks

### Notes

Not required for normal platform operation because fallback detection already
exists.

---

## Tier 4 - Enterprise Scalability (WebSockets / Real-Time Sync)

### 10. Real-Time Collaborative Architecture
**Status:** Architecture Designed (Pending Build)  
**Priority:** Future Enterprise Phase

### Scope
- Deploy Redis Pub/Sub backplane for distributed messaging.
- Build WebSocket Gateway (Socket.io/FastAPI WebSockets) validating against NextAuth.
- Implement strictly scoped Rooms based on `tenant_id` and `entity_id`.
- Wire frontend `WebSocketProvider` to `React Query`'s `invalidateQueries` to automatically refresh UI states.
- See detailed design spec: `[docs/platform/REALTIME_SYNC_DESIGN.md](../docs/platform/REALTIME_SYNC_DESIGN.md)`

---

## Working Notes

### Already Addressed

- utility import-path issue
- `python-magic` missing dependency fallback path
- ClamAV integration in code
- R2 integration in code
- webhook idempotency stabilization plan through P3, with `GAP-17` completed as safe retention hot-path hardening instead of physical partitioning

### Current Recommended Execution Order

1. Full-suite verification blockers and beta readiness cleanup
2. Billing plan enablement and manual access control
3. R2 storage validation and health checks
4. Production ClamAV enforcement and alerting
5. Quality signals persistence, if product/compliance scope requires it
6. Environment posture checks
7. Legacy compatibility cleanup
8. Runbooks
