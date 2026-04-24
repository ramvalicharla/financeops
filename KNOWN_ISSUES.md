# Known Issues - FinanceOps Current State

This file replaces the older "Phase 0" issue snapshot with the platform's
current status.

The goal here is to separate:

- issues already addressed in code
- issues that are still optional/legacy
- issues that still need implementation or production hardening

---

## KI-001: Utility File Import Paths

**Current Status:** Resolved  
**Priority:** None  
**Affects:** `backend/financeops/utils/findings.py`, `backend/financeops/utils/quality_signals.py`

### Current State

The original legacy import-path problem is no longer present.

Current implementation:

- `findings.py` imports `determinism` through `financeops.utils.erp_compat`
- `quality_signals.py` imports `db` and `determinism` through `financeops.utils.erp_compat`
- `erp_compat.py` exists as the compatibility layer

### Required Work

Not required.

### Notes

This item should not be treated as an active platform risk anymore.

---

## KI-002: quality_signals.py Still Uses Legacy Compatibility DB Pattern

**Current Status:** Partially addressed  
**Priority:** Medium if quality-signal persistence is a roadmap feature  
**Affects:** `backend/financeops/utils/quality_signals.py`

### Current State

The import problem has been fixed, so the module is importable.

However:

- `build_quality_signal()` is usable as a pure transformation helper
- `record_quality_signal()` still depends on `db.get_conn()`
- `list_quality_signals()` still depends on `db.get_conn()`
- the compatibility DB shim intentionally raises at runtime in FinanceOps

This means the module is currently suitable as a reference/helper module,
but not as a production-ready persistence implementation.

### What Still Needs Implementation

If FinanceOps wants quality-signal persistence as a real platform capability:

1. Define a proper PostgreSQL table/model for quality signals.
2. Replace compatibility DB calls with async SQLAlchemy repository/service code.
3. Expose clear application-level APIs for write/read/query behavior.
4. Add integration tests covering persistence and retrieval.

### Required Work

Required only if quality-signal storage/querying is an active product or
operations requirement.

If this utility is not part of the live platform roadmap, this can remain
deferred.

---

## KI-003: python-magic / libmagic Native Dependency

**Current Status:** Addressed with fallback behavior  
**Priority:** Low  
**Affects:** `backend/financeops/storage/airlock.py`

### Current State

The platform already handles missing `python-magic` gracefully:

- if `magic` is available, MIME detection uses file content
- if it is unavailable, the code falls back to filename extension detection

This makes local development workable even without native `libmagic`
installed.

### Required Work

Not required for normal development.

Optional hardening only:

- install native `libmagic` or Windows equivalent where strict MIME detection
  is desired

### Notes

This is now an environment-quality issue, not a core code defect.

---

## KI-004: ClamAV Scanning Was Previously Stubbed

**Current Status:** Implemented, but production hardening still matters  
**Priority:** High for enterprise production environments  
**Affects:** `backend/financeops/security/antivirus.py`, `backend/financeops/storage/airlock.py`

### Current State

The old "scan skipped only" Phase 0 state is no longer accurate.

Current implementation includes:

- actual ClamAV client integration
- unix socket and TCP connection attempts
- explicit `AntivirusUnavailableError`
- fail-open behavior when `CLAMAV_REQUIRED=false`
- fail-closed behavior when `CLAMAV_REQUIRED=true`

### What Still Needs Implementation / Hardening

For production-grade security posture:

1. Ensure a real ClamAV service is deployed and monitored in production.
2. Set `CLAMAV_REQUIRED=true` in production environments handling untrusted uploads.
3. Add explicit health/alerting for AV availability and scan failures.
4. Document the expected security mode per environment.

### Required Work

Platform code changes are not strictly required.

Operational hardening is required for serious production deployments.

---

## KI-005: R2 Storage Requires Real Configuration and Stronger Operational Validation

**Current Status:** Implemented in code, but configuration-dependent  
**Priority:** High if R2 is used for customer-facing artifacts  
**Affects:** `backend/financeops/storage/r2.py`, `backend/financeops/storage/provider.py`

### Current State

R2 support is implemented and actively used through the storage abstraction.

However, it depends on valid configuration:

- `R2_ENDPOINT_URL`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME`

If these are absent or wrong, runtime operations can fail.

### What Still Needs Implementation / Hardening

For production-grade storage reliability:

1. Add explicit startup or health validation for required R2 configuration.
2. Add a storage readiness/health check that verifies credentials and bucket access.
3. Add alerting/observability for failed upload/download/delete/presign operations.
4. Define environment-specific behavior when storage is unavailable.

### Required Work

Configuration is required immediately for real usage.

Additional validation/health tooling is recommended for production maturity.

---

## Executive Summary

### Already Addressed

- KI-001 import-path issue
- KI-003 native `libmagic` absence is handled with fallback behavior
- KI-004 ClamAV integration exists in platform code
- KI-005 R2 integration exists in platform code

### Still Worth Implementing

- KI-002 only if quality-signal persistence is actually needed
- KI-004 production AV hardening and monitoring
- KI-005 storage configuration validation and readiness checks

### Not Required Right Now

- any additional work for KI-001
- mandatory code changes for KI-003

---

## If the Goal Is a $1B-Scale Company

From the issues in this file, the truly important remaining work is not the
legacy import cleanup. It is production hardening.

### Must-Have

1. Real async persistence for quality signals if that data is part of
   trust/compliance/enterprise reporting.
2. Production ClamAV enforcement with `CLAMAV_REQUIRED=true` plus monitoring.
3. R2 configuration validation, readiness checks, and operational alerting.

### Should-Have

1. Remove or clearly quarantine legacy compatibility helpers once migrations are complete.
2. Add stronger security and storage runbooks for ops teams.
3. Add explicit environment posture checks so insecure defaults cannot silently reach production.

### Not a Meaningful Growth Blocker

- the old utility import-path issue by itself
- Windows `libmagic` convenience gaps for local development


---

## KI-FE-001: Unify tenant-coa-accounts query keys

**Title:** refactor(coa): unify tenant-coa-accounts query keys  
**Priority:** Low — no functional impact, cache isolation is intentional today  
**Affects:** `frontend/lib/query/keys/coa.ts`, `frontend/lib/query/keys/orgSetup.ts`

### Current State

Four separate query keys all resolve the same `/api/v1/coa/accounts` resource:

| Key | Caller |
|-----|--------|
| `["tenant-coa-accounts"]` | settings/chart-of-accounts, journals/new |
| `["tenant-coa-accounts-for-erp-mapping"]` | erp/mappings |
| `["tenant-coa-accounts-for-mapping"]` | settings/erp-mapping |
| `["org-setup-tenant-coa-accounts"]` | org-setup Step6ErpMapping |

These were preserved as-is during the query-key factory migration (feat/phase0-query-keys)
because unifying them could cause cross-page cache sharing with unintended staleTime
interactions. They are factored in the factory as four named methods.

### Remediation

Audit whether callers share the same staleTime and enabled conditions.
If they do, collapse to a single `queryKeys.coa.tenantAccounts()` key.
If they don't, document why each key needs isolation.
