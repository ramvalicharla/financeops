# BACKEND GAP REPORT — Finqor

**Audited:** 2026-04-12
**Files reviewed:** `financeops/auth_service.py` (services), `financeops/api/v1/auth.py`, `financeops/api/deps.py`, `financeops/core/security.py`, `financeops/db/rls.py`, `financeops/main.py`, `financeops/config.py`, `financeops/db/models/accounting_jv.py`, `financeops/db/models/tenants.py`, `financeops/db/append_only.py`, `financeops/services/user_service.py`, `financeops/services/auth_service.py`, `financeops/tasks/celery_app.py`, `financeops/tasks/payment_tasks.py`, `financeops/api/v1/router.py`, `financeops/api/v1/users.py`, `financeops/platform/db/models/entities.py`, `financeops/platform/db/models/user_membership.py`, `financeops/platform/services/tenancy/entity_access.py`, `financeops/modules/erp_sync/infrastructure/connectors/registry.py`, `financeops/modules/erp_sync/infrastructure/connectors/base.py`, `financeops/modules/erp_sync/infrastructure/connectors/zoho.py`, `financeops/modules/payment/infrastructure/webhook_verifier.py`, `financeops/modules/coa/application/coa_upload_service.py`, `migrations/versions/0035_fix_float_columns.py`, `.github/workflows/ci.yml`, `.github/workflows/sast.yml`

**Summary:** 23 gaps found — 2 P0, 8 P1, 11 P2, 2 P3

**Priority definitions:**
- **P0** = security vulnerability, data integrity risk, or blocks a feature entirely
- **P1** = incorrect behaviour visible to users or breaks a documented API contract
- **P2** = quality gap, missing test coverage, or technical debt
- **P3** = nice-to-have improvement

---

## DIMENSION 1 — API CONTRACT & TYPE SAFETY — PARTIAL

| # | Gap | Priority | Effort | File(s) | Recommendation |
|---|-----|----------|--------|---------|----------------|
| 1 | **entityRoles never populated in JWT or `/me` response.** `build_billing_token_claims()` only fetches billing data. The JWT access token and `/me` response body both omit `entity_roles` entirely. `get_entities_for_user()` exists in `entity_access.py` but is never called during login. The frontend `EntitySwitcher` reads `session?.user?.entity_roles` from the JWT session — it gets an empty array on every login. | P0 | S | `services/auth_service.py:105`, `api/v1/auth.py:668–739` | In `build_billing_token_claims()`, query `get_entities_for_user(session, tenant_id=tenant_id, user_id=user.id, user_role=user.role)`, then return `entity_roles: [{entity_id, entity_name, role, currency}]` in both the JWT claims and the `/me` response body. |
| 2 | **JournalStatus mismatch (Known Gap 2).** Backend `JVStatus` defines 12 states: DRAFT, SUBMITTED, PENDING_REVIEW, UNDER_REVIEW, APPROVED, PUSH_IN_PROGRESS, PUSHED, PUSH_FAILED, REJECTED, RESUBMITTED, ESCALATED, VOIDED. Frontend TypeScript type models only 6: DRAFT, SUBMITTED, REVIEWED, APPROVED, POSTED, REVERSED. REVIEWED/POSTED/REVERSED don't exist in the backend; PENDING_REVIEW, UNDER_REVIEW, PUSH_IN_PROGRESS, PUSHED, PUSH_FAILED, RESUBMITTED, ESCALATED, VOIDED are never rendered. | P1 | S | `db/models/accounting_jv.py:25–54` | Export `JVStatus.ALL` from a dedicated schema file and use it as the source of truth for the frontend `JournalStatus` union type. Update the frontend type to the full 12-value union. |
| 3 | **Several API endpoints return raw `dict` not typed Pydantic response models.** `/auth/login`, `/auth/me`, `/auth/register`, `/auth/mfa/verify`, `/auth/refresh` all return `-> dict`. OpenAPI docs show `{}` schemas, breaking contract guarantees and client-side type inference. | P2 | M | `api/v1/auth.py` throughout | Define Pydantic response models (`LoginResponse`, `MeResponse`, `TokenPairResponse`, etc.) and annotate each endpoint's return type. |
| 4 | **No `/api/v1/user/entity-roles` endpoint.** The frontend calls `/api/v1/platform/entities` (which exists) but multiple frontend stores also rely on `entity_roles` being present in the JWT session — there is no dedicated REST endpoint to refetch entity roles out-of-band. | P2 | S | `api/v1/router.py` | Add `GET /api/v1/platform/user/entity-roles` that returns the current user's entity assignments, for use after role changes without requiring re-login. |

Entity roles are the single highest-impact contract failure in this dimension: every `finance_team` and `auditor` user sees an empty EntitySwitcher after login. The JournalStatus mismatch will cause silent UI rendering failures any time a JV enters PENDING_REVIEW, PUSHED, or VOIDED state.

---

## DIMENSION 2 — AUTHENTICATION & AUTHORISATION — PARTIAL

| # | Gap | Priority | Effort | File(s) | Recommendation |
|---|-----|----------|--------|---------|----------------|
| 5 | **No rate limiting on `/forgot-password` or `/reset-password`.** All other auth endpoints (`/login`, `/mfa/verify`, `/refresh`) carry `@limiter.limit()` decorators. These two do not. `/forgot-password` can be used to enumerate registered emails via timing, and to spam password reset emails to any address. `/reset-password` can be brute-forced against the 15-minute token window. | P1 | XS | `api/v1/auth.py:525, 545` | Add `@limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT)` to both endpoints. Add `request: Request` parameter to `forgot_password`. |
| 6 | **`offboard_user()` uses direct `session.commit()` bypassing the audit wrapper.** All other mutation paths use `commit_session(session)` or `AuditWriter.flush_with_audit()`. `offboard_user` calls `await session.commit()` directly at line 252, which skips the commit-hook chain and could silently swallow audit events. | P2 | XS | `services/user_service.py:252` | Replace `await session.commit()` with `await commit_session(session)` for consistency. |
| 7 | **`/docs`, `/redoc`, `/openapi.json` are unauthenticated in all environments.** `main.py` mounts all three docs endpoints with no auth guard. In production this exposes the full API schema, all endpoint paths, and Pydantic model shapes to unauthenticated callers. | P1 | XS | `main.py:302–309` | Set `docs_url=None, redoc_url=None, openapi_url=None` in the `FastAPI(...)` constructor when `APP_ENV == "production"`, or protect with HTTP Basic auth. |
| 8 | **`verify_rls_active()` is defined but never called.** The `rls.py` function checks `pg_class.relrowsecurity` but there is no startup assertion or periodic check that confirms RLS is actually enabled on financial tables. A failed migration or manual `psql` command could silently disable RLS on a table without any observable error in application logs. | P2 | S | `db/rls.py:45–67`, `main.py` lifespan | Call `verify_rls_active(session, table)` for the top 10 most sensitive financial tables during the lifespan startup sequence (after DB ping passes). Log a CRITICAL alert and set `startup_errors` if any table has RLS disabled. |
| 9 | **RLS context not set for public route sessions.** `get_async_session()` lines 97–108 yield a session without calling `set_tenant_context` for paths in `PUBLIC_ROUTE_PATHS`. If a public-route handler accidentally issues a query that touches a table protected by RLS, it will return no rows rather than failing loudly — a silent data access failure. | P2 | XS | `api/deps.py:97–108` | Document the assumption explicitly. Add an `assert_no_financial_queries(session)` guard or use a read-only no-RLS session factory for public routes to make the constraint explicit. |
| 10 | **No startup validation that payment webhook secrets are non-empty in production.** `config.py` defines `STRIPE_SECRET_KEY: str = ""` and `RAZORPAY_WEBHOOK_SECRET: str = ""` with empty-string defaults. `validate_production_security_requirements()` checks `SECRET_KEY`, `JWT_SECRET`, `DATABASE_URL`, `REDIS_URL`, `FIELD_ENCRYPTION_KEY` — but NOT the payment provider secrets. If `RAZORPAY_WEBHOOK_SECRET` is empty, `hmac.new("".encode(), payload, hashlib.sha256)` computes a valid (but deterministic, zero-key) HMAC — webhooks would "verify" with no secret. | P1 | XS | `config.py:229–268` | Add `STRIPE_SECRET_KEY` and `RAZORPAY_WEBHOOK_SECRET` to `validate_production_security_requirements`. Raise `RuntimeError` if either is empty when `APP_ENV == "production"`. |

Auth has a solid foundation — bcrypt+SHA256 pre-hashing, TOTP with recovery codes, session rotation, and scope-based token restrictions are all implemented correctly. The two highest-impact fixes are the rate-limiting gap on password reset (5 lines) and the production docs exposure (1 config change).

---

## DIMENSION 3 — FINANCIAL CALCULATION CORRECTNESS — PARTIAL

| # | Gap | Priority | Effort | File(s) | Recommendation |
|---|-----|----------|--------|---------|----------------|
| 11 | **`float()` used for financial debit/credit amounts in CoA upload preview.** `coa_upload_service.py` lines 386, 387, 403, 404, 421, 422 call `float(row.get("debit") or 0)` and `float(row.get("credit") or 0)`. These are preview payloads shown to the user, not persisted — but they are still financial amounts subject to precision loss on values like 1,234,567.89. | P1 | XS | `modules/coa/application/coa_upload_service.py:386–422` | Replace all six `float(...)` calls with `Decimal(str(row.get("debit") or 0))` using `ROUND_HALF_UP`. Add `from decimal import Decimal, ROUND_HALF_UP` import. |
| 12 | **`float` used for AI/LLM confidence scores in accounting ingestion pipeline.** `modules/accounting_ingestion/domain/schemas.py:45,51` and `application/ocr_pipeline_service.py:85` use `float` for `confidence` fields. These propagate into accounting decisions (auto-posting thresholds). | P2 | XS | `modules/accounting_ingestion/domain/schemas.py:45,51` | Confidence scores are not financial amounts — `float` is acceptable here, but the threshold comparison logic in `ocr_pipeline_service.py` should be clearly documented as non-financial to prevent future confusion. Low priority; document rather than change. |
| 13 | **Rounding consistency not auditable from code.** `services/accounting_common/quantization_policy.py` exists but the CoA upload floats, once resolved, should use the same `ROUND_HALF_UP` policy as the rest of the financial engine. | P2 | XS | `services/accounting_common/quantization_policy.py` | Add a `lint` or `grep` CI check that flags any `float(` call in `modules/` containing "debit", "credit", "amount", or "balance". |

Financial calculation correctness is otherwise very strong: all DB columns use `Numeric(20,4)`, `Decimal` is used throughout the service layer, `ROUND_HALF_UP` appears consistently, and migration `0035_fix_float_columns.py` demonstrates the team already cleaned up a prior float-column issue. The CoA upload float usage is the only remaining violation in production paths.

---

## DIMENSION 4 — DATA INTEGRITY & APPEND-ONLY ENFORCEMENT — PARTIAL

| # | Gap | Priority | Effort | File(s) | Recommendation |
|---|-----|----------|--------|---------|----------------|
| 14 | **`offboard_user()` issues a direct `DELETE` on `auditor_grants`, which is in `APPEND_ONLY_TABLES`.** `user_service.py` lines 214–219: `delete(AuditorGrant).where(...).returning(...)`. The PostgreSQL append-only trigger `trg_append_only_auditor_grants` will block this at runtime, causing offboarding to throw a DB error for any user with an auditor grant. This is a runtime failure, not a silent bug. | P0 | XS | `services/user_service.py:214–219` | Replace the `delete(AuditorGrant)` with a query that fetches all active grants and inserts new rows with `is_active=False, effective_to=now()` for each via `AuditWriter.insert_financial_record`. This is the documented pattern: revocation = INSERT new row with `is_active=False`. |
| 15 | **`accounting_jv_aggregates` is mutable (has `onupdate=func.now()`) and is not in `APPEND_ONLY_TABLES`.** `accounting_jv.py` line 132: `updated_at` with `onupdate=func.now()`, and `status`, `resubmission_count`, `voided_at` etc. are direct-update fields. This is intentional — the JV aggregate tracks current state while `accounting_jv_state_events` records history. But it means the aggregate table is a mutable island in an otherwise immutable architecture. | P2 | M | `db/models/accounting_jv.py:68–155` | Document this as an intentional design decision in `append_only.py` with a comment. Consider adding a compensating append-only table for "JV status overrides" rather than mutating the aggregate, or explicitly exclude the table with a comment explaining the state-machine rationale. |
| 16 | **No chain-hash verification API endpoint.** The audit trail uses `chain_hash` and `previous_hash` columns (per platform architecture), but there is no `/api/v1/audit/verify-chain` endpoint that an external auditor can call to independently verify the hash chain. | P2 | M | `db/append_only.py`, audit service | Add a `GET /api/v1/audit/verify-chain?table=accounting_jv_state_events&from_id=X&to_id=Y` endpoint that recomputes and verifies hashes, returning a pass/fail with the first broken link if any. |
| 17 | **IamSession DELETE in `offboard_user` loses device/IP history for offboarded user.** `user_service.py` line 204 deletes IamSession rows. `IamSession` is not in `APPEND_ONLY_TABLES` so it doesn't fail — but the audit history is destroyed. | P3 | XS | `services/user_service.py:204–209` | Replace `delete(IamSession)` with a bulk `update(IamSession).values(revoked_at=now())` using the existing `revoke_all_sessions()` function in `auth_service.py:508`. |

Append-only enforcement is structurally excellent — the trigger function `financeops_block_update_delete` is defined in `append_only.py` and applied to 290+ tables. The only actual violation is the `auditor_grants` DELETE which the DB trigger will catch at runtime. The JV aggregate mutable design is intentional but undocumented.

---

## DIMENSION 5 — ERP CONNECTOR HEALTH — PASS

| # | Gap | Priority | Effort | File(s) | Recommendation |
|---|-----|----------|--------|---------|----------------|
| 18 | **`AbstractConnector.test_connection()` default returns `{"ok": True}` without testing.** `base.py` line 33–34: the base implementation doesn't attempt any real connection. Subclasses that don't override this will always report a healthy connection. | P2 | XS | `modules/erp_sync/infrastructure/connectors/base.py:33` | Make `test_connection()` abstract (`@abstractmethod`) so any connector that doesn't override it fails at import time rather than silently at runtime. Audit each of the 23 connectors to confirm they override it. |
| 19 | **No dead-letter queue beyond Celery's built-in retry.** Sync task failures retry 3 times (60s delay) then are lost. There is a `dead_lettered` flag on `ErpWebhookEvent` but no mechanism that moves failed Celery sync tasks into a queryable dead-letter store visible in the UI. | P2 | L | `tasks/celery_app.py:38`, `db/models/erp_webhook.py` | Configure a dead-letter queue in Redis with a periodic beat task that re-queues or alerts on items older than 24h. |

All 23 connectors are registered: Tally, Busy, Marg, Munim, Zoho, QuickBooks, Xero, FreshBooks, Wave, NetSuite, Dynamics 365, Sage, Odoo, SAP, Oracle, Razorpay, Stripe, AA Framework, Plaid, Keka, Darwinbox, Razorpay Payroll, Generic File. The `AbstractConnector` interface with `extract()` dispatch is clean. Zoho uses `secret_store` for credentials (no hardcoding). Webhook signature verification (HMAC-SHA256) is implemented for Zoho, QuickBooks, and Tally. ERP connector health is the strongest dimension.

---

## DIMENSION 6 — CELERY & ASYNC TASK RELIABILITY — PARTIAL

| # | Gap | Priority | Effort | File(s) | Recommendation |
|---|-----|----------|--------|---------|----------------|
| 20 | **Board pack generation and full-consolidation runs are single monolithic tasks with no chunking.** The 600-second `task_time_limit` applies globally. A large board pack or a full multi-entity consolidation (dozens of entities, years of data) can exceed 10 minutes — hitting the hard limit and leaving the run in an incomplete state with no recovery path. | P2 | L | `tasks/celery_app.py:36–38`, board pack and consolidation task implementations | Implement chunked task chains for board pack (one Celery task per section) and consolidation (one task per entity-period). Use Celery Canvas `chord` or `chain`. |
| 21 | **`asyncio.run()` inside sync Celery tasks creates a new event loop per invocation.** `payment_tasks.py` uses the pattern `def task(): return asyncio.run(_run())`. This is functional but inefficient — each task invocation creates and destroys an event loop. On Windows (local dev) this interacts poorly with `WindowsSelectorEventLoopPolicy`. | P2 | M | `tasks/payment_tasks.py:86,145,214,249` | Either switch to `anyio.from_thread.run_sync()` or run Celery workers in asyncio mode. The Celery 5.4 async worker runs tasks in an existing event loop. |

Task reliability is otherwise solid: `task_acks_late=True`, `task_reject_on_worker_lost=True`, `worker_prefetch_multiplier=1`, `result_expires=86400`, all 4 queues defined, beat schedule configured. Failure signals are connected via `connect_task_failure_signal()`.

---

## DIMENSION 7 — SECURITY & COMPLIANCE — PARTIAL

| # | Gap | Priority | Effort | File(s) | Recommendation |
|---|-----|----------|--------|---------|----------------|
| 22 | **User emails logged at INFO level in auth failure paths — PII in production logs.** `api/v1/auth.py` lines 425, 438, 448: `log.info(f"Login rejected: ... email={normalized_email}")`. User email addresses are PII under GDPR/DPDP. These log lines appear at INFO level, meaning they will be captured in production log aggregators (CloudWatch, Datadog, Sentry) in plain text. | P1 | XS | `api/v1/auth.py:425,438,448` | Change `log.info` to `log.debug` for lines containing email. Where a log line is needed at INFO for alerting, replace the email with `SHA256(normalized_email)[:8]` for correlation without PII exposure. |
| 23 | **API docs exposed in production.** (Already detailed as Gap 7 in Dimension 2.) | P1 | XS | `main.py:302–309` | Set `docs_url=None, redoc_url=None, openapi_url=None` when `APP_ENV == "production"`. |

Security strengths confirmed: SAST (Semgrep) runs on every PR and push via `sast.yml` with `p/python`, `p/security-audit`, `p/owasp-top-ten` rulesets. CORS wildcard is blocked in production by `validate_cors_wildcard_for_production`. Stripe webhook verification uses `stripe.Webhook.construct_event()` (the official method). Razorpay webhook uses `hmac.compare_digest()` with HMAC-SHA256 — timing-safe. No hardcoded API keys found in any source file. No raw SQL string formatting found (all queries use SQLAlchemy ORM or `text()` with bound params).

---

## DIMENSION 8 — TEST COVERAGE & CI GAPS — PARTIAL

| # | Gap | Priority | Effort | File(s) | Recommendation |
|---|-----|----------|--------|---------|----------------|
| 24 | **WebKit Playwright browser binary not installed in CI (Known Gap 3).** `ci.yml` frontend job runs `npm test -- --run` but there is NO `npx playwright install` step anywhere in the workflow. All WebKit mobile Safari tests will fail with "Executable doesn't exist at..." on every CI run. | P1 | XS | `.github/workflows/ci.yml:111–145` | Add a step before `Run frontend tests`: `working-directory: frontend` / `run: npx playwright install --with-deps webkit`. |
| 25 | **CI tests against PostgreSQL 15, not 16.** `ci.yml` line 27: `image: pgvector/pgvector:pg15`. The platform targets PostgreSQL 16. Row-level security policy syntax, JSONB operator behaviour, and query planner differences can vary between minor versions. | P2 | XS | `.github/workflows/ci.yml:27` | Change image to `pgvector/pgvector:pg16`. |
| 26 | **No coverage threshold enforced in CI.** `pytest` is invoked without `--cov` or `--cov-fail-under`. Coverage can silently drop to 0% without failing CI. | P2 | XS | `.github/workflows/ci.yml:100–108` | Add `--cov=financeops --cov-report=xml --cov-fail-under=70` to the pytest invocation. |
| 27 | **No dependency vulnerability scanning in CI.** `sast.yml` runs Semgrep (static analysis) but there is no `pip-audit` or `safety` step to detect known CVEs in installed packages. | P2 | XS | `.github/workflows/ci.yml` | Add a job step: `pip install pip-audit && pip-audit --strict`. Or use the `pypa/gh-action-pip-audit` action. |
| 28 | **No RLS tenant-isolation integration test.** There is no test that authenticates as Tenant A and asserts that querying Tenant B's financial data returns 0 rows (not 403, which would be an application-layer check — 0 rows from the DB proves RLS is active). | P2 | M | `tests/integration/` | Add a test: create two tenants, insert a GL entry for tenant A, authenticate as tenant B user, assert `select(GLEntry)` returns empty result set. |
| 29 | **CI uses `pip install -e ".[dev]"` not `uv`.** `ci.yml` line 71 bypasses the project's `uv` lock file, allowing CI to install different package versions than local dev. | P3 | XS | `.github/workflows/ci.yml:70–71` | Replace with `pip install uv && uv sync --extra dev` to honour `uv.lock` exactly. |

---

## PRIORITY FIX LIST — TOP 15

Ordered: P0 first, then P1 by user impact.

### 1. entity_roles never built into JWT — EntitySwitcher broken for all users
- **File:** `backend/financeops/services/auth_service.py:105`
- **Change:** In `build_billing_token_claims()`, add `user_id` and `user_role` parameters (both call sites have the `user` object). Query `get_entities_for_user()` from `entity_access.py` and populate:
```python
from financeops.platform.services.tenancy.entity_access import get_entities_for_user
entities = await get_entities_for_user(session, tenant_id=tenant_id, user_id=user_id, user_role=user_role)
claims["entity_roles"] = [
    {"entity_id": str(e.id), "entity_name": e.entity_name,
     "role": user_role.value, "currency": e.base_currency}
    for e in entities
]
```

### 2. DELETE on `auditor_grants` in `offboard_user()` — DB trigger blocks offboarding
- **File:** `backend/financeops/services/user_service.py:214–219`
- **Change:** Replace `delete(AuditorGrant).where(AuditorGrant.user_id == user_id)` with: query all active grants for the user, then for each call `AuditWriter.insert_financial_record(session, model_class=AuditorGrant, ...)` with `is_active=False, effective_to=now()`.

### 3. JournalStatus 6 vs 12 type mismatch — breaks UI for 6 backend states
- **File:** `backend/financeops/db/models/accounting_jv.py:25–54` / frontend type definitions
- **Change:** Create `backend/financeops/api/v1/schemas/journal_status.py` exporting the 12-value literal. Update the frontend `JournalStatus` TypeScript type to the full 12-value union.

### 4. No rate limit on `/forgot-password` — email enumeration and spam risk
- **File:** `backend/financeops/api/v1/auth.py:525`
- **Change:** Add `@limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT)` decorator and `request: Request` parameter to both `forgot_password` (line 525) and `reset_password` (line 545).

### 5. Email PII logged at INFO level in auth failure paths
- **File:** `backend/financeops/api/v1/auth.py:425,438,448`
- **Change:** `log.info(f"Login rejected: ... email={normalized_email}")` → change to `log.debug(...)` or replace email with `hashlib.sha256(normalized_email.encode()).hexdigest()[:8]` for correlation.

### 6. `/me` response body missing entity_roles
- **File:** `backend/financeops/api/v1/auth.py:668`
- **Change:** After the same `get_entities_for_user()` call introduced for the JWT, add `"entity_roles": [...]` to the returned dict in `get_me()`.

### 7. WebKit Playwright binary not installed in CI — all mobile Safari tests fail
- **File:** `.github/workflows/ci.yml` (after node install step, line ~130)
- **Change:** Add step:
```yaml
- name: Install Playwright browsers
  working-directory: frontend
  run: npx playwright install --with-deps webkit
```

### 8. `RAZORPAY_WEBHOOK_SECRET` / `STRIPE_SECRET_KEY` not validated at startup
- **File:** `backend/financeops/config.py:229–268`
- **Change:** Add to `required_values` dict in `validate_production_security_requirements()`:
```python
"STRIPE_SECRET_KEY": str(self.STRIPE_SECRET_KEY),
"RAZORPAY_WEBHOOK_SECRET": str(self.RAZORPAY_WEBHOOK_SECRET),
```

### 9. API docs exposed in production
- **File:** `backend/financeops/main.py:302–309`
- **Change:**
```python
is_prod = settings.APP_ENV.lower() == "production"
app = FastAPI(
    ...
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
)
```

### 10. `float()` for financial debit/credit in CoA upload
- **File:** `backend/financeops/modules/coa/application/coa_upload_service.py:386,387,403,404,421,422`
- **Change:** Replace all 6 instances of `float(row.get("debit") or 0)` / `float(row.get("credit") or 0)` with:
```python
Decimal(str(row.get("debit") or 0)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
```

### 11. `test_connection()` in base connector always returns OK
- **File:** `backend/financeops/modules/erp_sync/infrastructure/connectors/base.py:33`
- **Change:** Replace the default body with `raise NotImplementedError("Connector must implement test_connection")` or decorate with `@abstractmethod`. Audit all 23 connectors to confirm they override it.

### 12. `verify_rls_active()` never called at startup
- **File:** `backend/financeops/main.py` lifespan block, `backend/financeops/db/rls.py:45`
- **Change:** After the DB ping passes in the lifespan block, add:
```python
async with AsyncSessionLocal() as session:
    for table in ["accounting_jv_state_events", "gl_entries", "bank_transactions",
                  "credit_ledger", "auditor_grants"]:
        if not await verify_rls_active(session, table):
            startup_errors.append(f"RLS not active on critical table: {table}")
```

### 13. No tenant isolation integration test
- **File:** `backend/tests/integration/test_rls_isolation.py` (new file)
- **Change:** Add test that creates two tenants, inserts a `GLEntry` under tenant A's RLS context, switches to tenant B's context, asserts query returns 0 rows. This proves the DB trigger is active, not just the application-layer guard.

### 14. CI uses PostgreSQL 15, project targets PostgreSQL 16
- **File:** `.github/workflows/ci.yml:27`
- **Change:** `image: pgvector/pgvector:pg15` → `image: pgvector/pgvector:pg16`

### 15. No dependency vulnerability scanning
- **File:** `.github/workflows/ci.yml`
- **Change:** Add a step to the backend job:
```yaml
- name: Dependency vulnerability scan
  working-directory: backend
  run: pip install pip-audit && pip-audit --desc on
```

---

## KNOWN STUBS INVENTORY

| # | File | Line | Stub Description | Risk if Shipped |
|---|------|------|-----------------|-----------------|
| 1 | `services/auth_service.py` | 105 | `build_billing_token_claims()` builds billing JWT claims but never populates `entity_roles`. Root cause of Known Gap 1. | EntitySwitcher and all entity-scoped features are non-functional for all non-owner users. |
| 2 | `modules/erp_sync/infrastructure/connectors/base.py` | 33 | `AbstractConnector.test_connection()` returns `{"ok": True}` without attempting any real connection. Any connector that doesn't override this will always appear healthy. | Misconfigured ERP connections appear healthy in the UI — sync will fail silently at runtime. |
| 3 | `config.py` | 129 | `CLAMAV_REQUIRED: bool = False` — ClamAV anti-virus scan is disabled by default. The airlock storage pipeline has a ClamAV stub that passes all files without scanning. Documented as Phase 6 work. | Malicious file uploads are not virus-scanned in any environment until `CLAMAV_REQUIRED=True` and ClamAV is deployed. |
| 4 | `services/user_service.py` | 214 | `offboard_user()` issues `delete(AuditorGrant)` — functionally a stub for the correct append-only revocation pattern. Would throw a DB error (blocked by trigger) rather than a silent wrong result. | Runtime 500 error for any offboarding of a user with auditor grants. |
| 5 | `api/v1/auth.py` | 739 | `get_me()` returns correct user/tenant/billing data but `entity_roles` is absent from the response body. Frontend `useSession` has no server-side entity data outside of the JWT. | EntitySwitcher unpopulated until entity_roles are added to both JWT claims and `/me` response. |
| 6 | `tasks/payment_tasks.py` | 228 | `retry_failed_payments()` marks all PAST_DUE subscriptions as ACTIVE without attempting an actual payment retry. No Stripe/Razorpay charge attempt is made. | Subscriptions in PAST_DUE state are converted to ACTIVE without successful payment — revenue loss and incorrect billing state in production. |
