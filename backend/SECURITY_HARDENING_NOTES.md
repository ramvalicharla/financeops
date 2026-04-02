# Security Hardening Notes (Phase 11A)

Date: 2026-04-02

## Implemented

1. Authorization dependency hardening
- Removed unsafe `OPTIONS` behavior that raised 204 from auth dependencies.
- Reduced noisy debug logs in auth/tenant resolution path.
- Tightened session tenant derivation by removing non-JWT auditor token fallback.
- Added standardized role helpers in `financeops/api/deps.py`:
  - `require_platform_admin`
  - `require_support_or_admin`
  - strengthened `require_finance_leader` and `require_finance_team`.

2. API abuse hardening
- Added request size limit middleware (`RequestSizeLimitMiddleware`) using `MAX_UPLOAD_SIZE_MB`.
- Integrated middleware globally in app startup stack.
- Added rate limits:
  - AI streaming endpoint (`AI_STREAM_RATE_LIMIT`)
  - ERP sync mutating endpoints (`ERP_SYNC_WRITE_RATE_LIMIT`)
  - CoA upload/validate/apply endpoints (`UPLOAD_RATE_LIMIT`).

3. Upload hardening
- Added strict CoA upload file validation at API edge:
  - extension/mime/path traversal checks
  - explicit CoA 5 MB cap
  - structured validation error path (`file_validation_failed:*`).

4. Session hardening
- Added `POST /api/v1/auth/sessions/revoke-all` to revoke active refresh sessions.
- Added audit logging for session revoke-all action.

5. Admin control auditability
- Added audit events for platform user admin actions:
  - create platform user
  - update platform user role
  - deactivate platform user.

6. Security tests added
- `tests/test_phase11a_security_hardening.py` covers:
  - CoA upload filename traversal rejection
  - ERP sync denial for read-only role
  - ERP sync replay endpoint requires auth
  - role-downgrade enforcement (token claims do not bypass DB role checks)
  - revoke-all sessions blocks refresh reuse
  - invalid/expired token handling
  - tenant mismatch token denial.

## Remaining Known Risks

1. Access token revocation granularity
- Current access tokens remain valid until expiry (stateless JWT model).
- Refresh sessions are revoked immediately; full immediate access-token revocation would require jti/session-bound access-token deny-list.

2. Legacy endpoints
- Some legacy read-only endpoints still rely on existing auth + control-plane guards rather than per-endpoint role helper wrappers; these remain functional but should be progressively normalized.

3. Content-Length dependence for size middleware
- Request-size middleware enforces using `Content-Length`; chunked uploads without this header are not pre-rejected there (endpoint-level validation still applies to upload paths).
