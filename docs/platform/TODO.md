# FinanceOps Platform — TODO & Improvement Plan
*Generated: 2026-04-05*
*Based on: codebase audit, git log, KNOWN_ISSUES.md, commit history*

---

## IMMEDIATE (fix before any user login)

### I-001: Verify pytest-asyncio version
**What:** `pyproject.toml` pins `pytest-asyncio==0.24.0` but MEMORY.md states `>=1.0.0` is required to prevent loop teardown issues.
**Why:** 0.24.0 has a known teardown loop bug. Running tests with the wrong version may cause indefinite hangs or flaky teardown.
**How:** Update `pyproject.toml`: `pytest-asyncio>=1.0.0`; also add `asyncio_default_test_loop_scope = "session"` to `[tool.pytest.ini_options]` if not already present.
**Files:** `backend/pyproject.toml`
**Effort:** 30 minutes

### I-002: Set NEXTAUTH_SECRET / AUTH_SECRET in all environments
**What:** NextAuth requires `NEXTAUTH_SECRET` (or `AUTH_SECRET`) to sign session JWTs. If not set, the app will throw a runtime error on first login.
**Why:** Without this, no user can log in.
**How:** Generate: `python -c "import secrets; print(secrets.token_hex(32))"`. Set `NEXTAUTH_SECRET` in Vercel environment variables.
**Files:** `frontend/.env.local` (dev), Vercel dashboard (prod)
**Effort:** 15 minutes

### I-003: Configure CORS_ALLOWED_ORIGINS for production
**What:** The backend requires `CORS_ALLOWED_ORIGINS` to include the Vercel frontend URL. Without it, all browser requests from the frontend will fail with CORS errors.
**Why:** The production safety validator rejects `*` as CORS origin in production mode.
**How:** Set `CORS_ALLOWED_ORIGINS=https://your-app.vercel.app` in Render environment variables (or `CORS_ORIGINS` as priority override).
**Files:** Render dashboard env vars, `backend/financeops/config.py`
**Effort:** 10 minutes

### I-004: Seed platform owner before first login
**What:** Without a platform owner user, there is no way to log in to the system for the first time.
**Why:** The application requires at least one user to exist to authenticate.
**How:** Set `SEED_ON_STARTUP=true` and configure `PLATFORM_OWNER_EMAIL`, `PLATFORM_OWNER_PASSWORD`, `PLATFORM_OWNER_NAME` in the backend environment. Deploy and let the startup seed run.
**Files:** Render env vars, `backend/financeops/seed/platform_owner.py`
**Effort:** 15 minutes (configuration only)

### I-005: Configure R2 or acknowledge file upload unavailability
**What:** R2 credentials (`R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`) are empty by default. File upload and storage features will fail silently or return errors.
**Why:** KI-005. Any feature using file upload (board pack attachments, audit evidence, accounting ingestion) will error until R2 is configured.
**How:** Either configure Cloudflare R2 credentials, or explicitly document which features are unavailable and add UI-level guards.
**Files:** Render env vars, `.env.example`
**Effort:** 1-2 hours (R2 bucket setup + key generation)

---

## CRITICAL (fix within first week)

### C-001: Fix broken utility imports (KI-001, KI-002)
**What:** `backend/financeops/utils/findings.py` and `backend/financeops/utils/quality_signals.py` import from `workbench.backend` (old package) instead of `financeops.utils`.
**Why:** If any code path imports these files, Python will throw `ModuleNotFoundError` at runtime. Currently non-blocking only if these files are never imported.
**How:**
- `findings.py` line 7: change `from workbench.backend import determinism` → `from financeops.utils import determinism`
- `quality_signals.py` lines 8-9: change `from workbench.backend import db, determinism` → `from financeops.utils import determinism` and replace `db.utc_now_iso()` with `from financeops.utils.formatting import utc_now_iso`; replace `db.get_conn()` with proper async session usage
**Files:** `backend/financeops/utils/findings.py`, `backend/financeops/utils/quality_signals.py`
**Effort:** 2-4 hours

### C-002: Add Temporal worker to production deployment
**What:** `render.yaml` has 3 services (web, worker, beat) but no Temporal workflow worker. Long-running financial computation runs (FX translation, consolidation, fixed asset depreciation, etc.) will not execute.
**Why:** Without the Temporal worker, all workflows submitted to Temporal's task queue will queue indefinitely.
**How:** Add a 4th service to `render.yaml`:
```yaml
- type: worker
  name: financeops-temporal-worker
  runtime: docker
  region: singapore
  plan: starter
  dockerfilePath: backend/Dockerfile
  dockerCommand: python -m financeops.temporal.worker
  envVars:
    - key: DATABASE_URL
      sync: false
    - key: REDIS_URL
      sync: false
    - key: TEMPORAL_ADDRESS
      sync: false
```
**Files:** `render.yaml`
**Effort:** 1 hour (config + deploy)

### C-003: Deploy ClamAV or gate file uploads behind CLAMAV_REQUIRED=False
**What:** `Dockerfile` sets `CLAMAV_REQUIRED=True` but there is no ClamAV service in `render.yaml`. Files will fail the airlock scan or get stuck.
**Why:** KI-004. All file uploads go through the airlock pipeline. If ClamAV is required but unavailable, upload features are broken in production.
**How:** Either:
  a) Add ClamAV as a sidecar service (complex on Render; better with Docker Compose or k8s)
  b) Set `CLAMAV_REQUIRED=False` in production until ClamAV is properly deployed — files get `SCAN_SKIPPED` with a warning log
**Files:** `backend/Dockerfile`, `render.yaml`, Render env vars
**Effort:** 2 hours (option b) or 1 day (option a)

### C-004: Configure SMTP for email features
**What:** `SMTP_REQUIRED=false` by default but the following features depend on email: registration welcome email, password reset, MFA setup notification, scheduled report delivery.
**Why:** Password reset in particular is a critical user journey. Without email, users who forget their password cannot recover their account.
**How:** Configure an email provider (SendGrid, AWS SES, Mailgun, or standard SMTP). Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` in Render environment.
**Files:** Render env vars, `backend/financeops/modules/notifications/channels/email_channel.py`
**Effort:** 2-4 hours (email provider setup)

### C-005: Configure SENTRY_DSN for production error tracking
**What:** `SENTRY_DSN` is empty by default. Production errors will not be tracked or alerted.
**Why:** Without Sentry, production incidents will be invisible until users report them.
**How:** Create a Sentry project, get the DSN, set it in Render env vars (backend) and Vercel env vars (frontend: `SENTRY_DSN` and `NEXT_PUBLIC_SENTRY_DSN`).
**Files:** Render + Vercel env vars
**Effort:** 1 hour

### C-006: Verify MFA recovery codes single-use enforcement
**What:** The `MfaRecoveryCode` model has a `used_at` field. Verify that the auth service marks codes as used immediately and prevents reuse.
**Why:** If recovery codes can be reused, they provide no security benefit and enable replay attacks.
**How:** Audit `backend/financeops/api/v1/auth.py` MFA verify handler; ensure it queries `used_at IS NULL` and immediately sets `used_at = now()` in an atomic transaction.
**Files:** `backend/financeops/api/v1/auth.py`, `backend/financeops/db/models/auth_tokens.py`
**Effort:** 2 hours (audit + test)

### C-007: Confirm session revocation on password change
**What:** When a user changes their password (forced or voluntary), all existing sessions should be revoked to prevent session fixation attacks.
**Why:** If sessions survive a password change, a stolen session token remains valid indefinitely.
**How:** Audit `backend/financeops/services/auth_service.py` `change_password` flow; ensure it calls `revoke_all_sessions(user_id)` or equivalent.
**Files:** `backend/financeops/services/auth_service.py`, `backend/financeops/api/v1/auth.py`
**Effort:** 2 hours (audit + test)

---

## HIGH (fix within first sprint)

### H-001: Protect the /metrics endpoint
**What:** Prometheus `/metrics` endpoint is mounted without authentication. It exposes internal application metrics publicly.
**Why:** Metrics can reveal business data (active tenants, task depths, error rates) and internal service information useful for attackers.
**How:** Add IP allowlist, basic auth, or bearer token check on the `/metrics` route.
**Files:** `backend/financeops/main.py`
**Effort:** 2-4 hours

### H-002: Upgrade OpenTelemetry to latest
**What:** All OpenTelemetry packages are at 1.27.0 / 0.48b0; latest is 1.40.0 / 0.61b0.
**Why:** Security fixes, performance improvements, and compatibility updates in newer versions.
**How:** Update `pyproject.toml` versions and retest with OTEL collector.
**Files:** `backend/pyproject.toml`
**Effort:** 4-8 hours (update + regression test)

### H-003: Upgrade Anthropic SDK from 0.34.0 to latest (0.86.0+)
**What:** Anthropic SDK is at 0.34.0; latest is 0.86.0. Significant API surface changes and new model support.
**Why:** Newer Claude models (3.5 Sonnet, 3.5 Haiku, Claude 3.7) are not supported in 0.34.0.
**How:** Update `pyproject.toml`, review breaking changes in Anthropic changelog, update any API call patterns.
**Files:** `backend/pyproject.toml`, `backend/financeops/llm/providers/`
**Effort:** 1-2 days

### H-004: Upgrade FastAPI from 0.115.0 to latest (0.135.x)
**What:** FastAPI is at 0.115.0; latest is 0.135.2.
**Why:** Bug fixes, performance improvements. Some security patches may apply.
**How:** Review FastAPI changelog, update pyproject.toml, test all endpoints.
**Files:** `backend/pyproject.toml`
**Effort:** 1 day (update + regression)

### H-005: Add dead letter queue for Celery failed tasks
**What:** Tasks that exhaust their 3 retries are silently dropped. There is no dead letter queue (DLQ) configured.
**Why:** Failed financial tasks (payment processing, ERP sync, report delivery) are lost without any alert or recovery mechanism.
**How:** Configure Celery to route failed tasks to a `dead_letter_q`; add a monitor that alerts when tasks land in the DLQ.
**Files:** `backend/financeops/tasks/celery_app.py`
**Effort:** 4 hours

### H-006: Deploy Flower to production
**What:** Flower (Celery monitor) is only configured for local Docker Compose, not for production Render deployment.
**Why:** Without Flower, there is no visibility into Celery task queues, worker health, or task failure rates in production.
**How:** Add Flower as a web service in `render.yaml`, protected behind basic auth or IP allowlist.
**Files:** `render.yaml`
**Effort:** 2-4 hours

### H-007: Set up OTEL collector endpoint
**What:** `OTEL_EXPORTER_OTLP_ENDPOINT` is empty by default. Distributed tracing is instrumented but traces are not exported.
**Why:** Without an OTEL backend (Jaeger, Honeycomb, Datadog, etc.), tracing data is discarded.
**How:** Deploy or subscribe to an OTEL-compatible backend; set `OTEL_EXPORTER_OTLP_ENDPOINT` in Render env.
**Files:** Render env vars
**Effort:** 2-4 hours (backend setup) + 30 min (config)

### H-008: Fix trust page role restriction (too narrow)
**What:** In `frontend/middleware.ts`, the `/trust/*` route requires `role === "finance_leader"` only. Platform owners and platform admins cannot access the trust center.
**Why:** Platform owners should be able to view compliance/trust pages for their tenants.
**How:** Expand the role check to include `platform_owner`, `platform_admin`, `super_admin`, and `finance_leader`.
**Files:** `frontend/middleware.ts`
**Effort:** 30 minutes

### H-009: Add rate limiting to registration endpoint
**What:** The `/api/v1/auth/register` endpoint does not appear to be rate-limited (unlike login which has 5/min).
**Why:** Without rate limiting, an attacker can enumerate email addresses or create unlimited spam tenants.
**How:** Add `@limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT)` decorator to the register endpoint.
**Files:** `backend/financeops/api/v1/auth.py`
**Effort:** 1 hour

### H-010: Add E2E tests for critical auth flows
**What:** Playwright E2E tests are configured (`@playwright/test` in devDependencies) but no E2E test files are visible in the codebase.
**Why:** Auth flows (login → MFA → dashboard) and org setup flows are critical and not covered by backend integration tests alone.
**How:** Create `frontend/e2e/` directory with Playwright tests for: login, MFA setup, password reset, org setup wizard, dashboard access.
**Files:** `frontend/e2e/` (new)
**Effort:** 2-3 days

---

## MEDIUM (fix within first month)

### M-001: Resolve quality_signals.py sync DB dependency (KI-002)
**What:** `utils/quality_signals.py` calls `db.get_conn()` (synchronous SQLite). The data model needs rewriting for async PostgreSQL.
**Why:** `build_quality_signal()` pure function is usable but `record_quality_signal()` and `list_quality_signals()` need complete rewrites.
**How:** Rewrite DB-touching functions in `quality_signals.py` to use `AsyncSession` pattern from the project.
**Files:** `backend/financeops/utils/quality_signals.py`
**Effort:** 4-8 hours

### M-002: Implement ClamAV in production (KI-004)
**What:** ClamAV antivirus scanning is stubbed. All file uploads get `SCAN_SKIPPED` status.
**Why:** Production file uploads (accounting ingestion, audit evidence, board pack attachments) are not virus-scanned.
**How:** Options: (a) Use ClamAV REST API via a sidecar service; (b) Use a cloud antivirus API; (c) Integrate with a managed file scanning service.
**Files:** `backend/financeops/storage/airlock.py`
**Effort:** 1-2 days

### M-003: Upgrade SQLAlchemy, asyncpg, and Alembic
**What:** SQLAlchemy 2.0.35 → latest, asyncpg 0.30.0 → 0.31.0, Alembic 1.13.0 → 1.18.4
**Why:** Bug fixes and performance improvements. asyncpg 0.31.0 has improved PgBouncer compatibility.
**Files:** `backend/pyproject.toml`
**Effort:** 1 day

### M-004: Upgrade Celery from 5.4.0 to 5.6.2
**What:** Celery is at 5.4.0; latest is 5.6.2.
**Why:** Bug fixes, performance improvements, better Redis 7 compatibility.
**Files:** `backend/pyproject.toml`
**Effort:** 4 hours (update + test)

### M-005: Set up database connection pooling (PgBouncer)
**What:** The app connects directly to PostgreSQL with a pool of 20+10 connections. On Supabase/Render, this may exhaust connection limits, especially with Celery workers.
**Why:** Each Render service (API + 2 workers) * pool_size can exceed database connection limits quickly.
**How:** Use Supabase's PgBouncer transaction mode pooler. Update `DATABASE_URL` to point to pooler URL. Use `MIGRATION_DATABASE_URL` for direct connections (Alembic requires direct connection).
**Files:** Render env vars, `backend/alembic.ini`, `backend/financeops/db/session.py`
**Effort:** 4-8 hours

### M-006: Add frontend error boundaries
**What:** The Next.js app does not appear to have React error boundaries on key pages. An uncaught render error will show a blank page to users.
**Why:** Financial data pages can throw render errors if API data is malformed. Error boundaries provide graceful degradation.
**How:** Add `error.tsx` files in key app router directories; implement `global-error.tsx`.
**Files:** `frontend/app/(dashboard)/error.tsx`, `frontend/app/global-error.tsx` (new)
**Effort:** 4-8 hours

### M-007: Add pagination to all list endpoints
**What:** Several API list endpoints may not be paginated. Large tenants with many records could cause slow responses or OOMs.
**Why:** Without pagination, list endpoints become unusable at scale.
**How:** Use `backend/financeops/utils/pagination.py` consistently. Verify all list endpoints have `limit`/`offset` or cursor-based pagination.
**Files:** Various `backend/financeops/api/v1/*.py`, `backend/financeops/modules/*/api/routes.py`
**Effort:** 2-3 days (audit all endpoints)

### M-008: Implement refresh token rotation
**What:** The current refresh token flow reuses the same refresh token on every refresh call. Refresh token rotation (issue a new refresh token on each use) prevents token replay attacks.
**Why:** If a refresh token is stolen, the attacker has a 7-day window to generate access tokens.
**How:** On `/auth/refresh`, issue a new refresh token, revoke the old one in `iam_sessions`, return both tokens.
**Files:** `backend/financeops/services/auth_service.py`, `backend/financeops/api/v1/auth.py`
**Effort:** 4-8 hours

### M-009: Add database indexes for frequent query patterns
**What:** Verify all frequently-queried columns have indexes. Common patterns: `tenant_id + created_at` DESC ranges, `tenant_id + status`, `user_id` on session tables.
**Why:** Without proper indexes, queries degrade from O(1) to O(n) as data grows.
**How:** Use `EXPLAIN ANALYZE` on key queries in staging; add indexes via Alembic migration.
**Files:** New migration file
**Effort:** 1 day (analysis) + 4 hours (migration)

### M-010: Configure Redis persistence for production
**What:** The local Docker Redis is configured with AOF + RDB persistence. Verify the production managed Redis has equivalent persistence settings.
**Why:** Celery tasks and rate limit counters live in Redis. Without persistence, a Redis restart loses all queued tasks.
**How:** Configure Redis persistence settings in your managed Redis provider; set `appendonly yes`, `appendfsync everysec`.
**Files:** Managed Redis configuration, `infra/docker-compose.yml` (reference)
**Effort:** 2 hours

### M-011: Add API versioning strategy
**What:** All routes are under `/api/v1/`. There is no plan documented for `/api/v2/` when breaking changes are needed.
**Why:** Without a versioning strategy, breaking API changes will break frontend/integrations without warning.
**How:** Document the versioning policy; add API version headers (`X-API-Version`) to responses; plan deprecation notices.
**Files:** New `docs/api/VERSIONING.md`
**Effort:** 4 hours (documentation)

### M-012: Add frontend loading states and skeleton screens
**What:** Many dashboard pages likely fetch data on mount with no loading skeleton. Users see blank pages briefly.
**Why:** Perceived performance impacts user satisfaction, especially for financial dashboards with multiple data fetches.
**How:** Add skeleton components (shadcn has `<Skeleton>`) to all data-heavy pages.
**Files:** `frontend/components/` (various), `frontend/app/(dashboard)/*/page.tsx`
**Effort:** 3-5 days

---

## LOW (backlog)

### L-001: Upgrade to Next.js 15
**What:** Next.js is at 14.2.35; Next.js 15 is released with improved performance and React 19 support.
**Why:** Better performance, security patches, React 19 concurrent features.
**Files:** `frontend/package.json`
**Effort:** 1-2 days (migration + testing)

### L-002: Replace `next-auth` beta with stable release
**What:** `next-auth` is at `5.0.0-beta.30`. The Auth.js v5 stable release should be used for production.
**Why:** Beta software may have breaking changes or security issues.
**Files:** `frontend/package.json`
**Effort:** 4 hours (when stable released)

### L-003: Implement request deduplication for financial reads
**What:** Multiple simultaneous identical GET requests to the same endpoint may result in duplicate DB reads.
**Why:** Dashboard pages with multiple widgets fetching the same data create unnecessary DB load.
**How:** Use TanStack Query's built-in deduplication (it deduplicates by query key automatically). Verify all dashboard pages use consistent query keys.
**Files:** `frontend/lib/api/` (various)
**Effort:** 1-2 days

### L-004: Add OpenAPI response schemas
**What:** Many FastAPI endpoints return `dict` or `Any` response type instead of typed Pydantic response schemas.
**Why:** Without typed responses, the OpenAPI spec at `/docs` is incomplete and client code generation is impossible.
**How:** Add `response_model=...` to all route decorators.
**Files:** Various `backend/financeops/api/v1/*.py`
**Effort:** 3-5 days

### L-005: Set up staging environment
**What:** There is no staging environment configured (only local dev and production).
**Why:** Without a staging environment, production deployments cannot be tested before going live.
**How:** Create separate Render services with `APP_ENV=staging`, separate DB and Redis instances, separate Vercel preview deployments.
**Effort:** 1 day

### L-006: Add multi-language (i18n) support
**What:** The frontend uses hardcoded English strings. No i18n framework is configured.
**Why:** International financial SaaS needs localization for key markets (India: Hindi/regional, Europe: German/French, etc.).
**How:** Add `next-intl` or `react-i18next`; extract all UI strings to locale files.
**Files:** `frontend/` (global change)
**Effort:** 1-2 weeks

### L-007: Implement proper chart of accounts validation
**What:** CoA framework exists (migration 0075) but CoA account number format validation rules may not be enforced at the API layer.
**Why:** Invalid CoA entries can corrupt financial reporting.
**Files:** `backend/financeops/modules/coa/`
**Effort:** 1-2 days

### L-008: Add API key authentication for external integrations
**What:** The platform currently only supports JWT bearer tokens. External system integrations (ERP webhooks, partner portals) need API key authentication.
**Why:** ERP systems cannot use browser-based JWT flows.
**How:** Add `api_keys` table, API key generation endpoint, API key auth dependency in FastAPI.
**Effort:** 1-2 days

### L-009: Implement webhook signature validation for ERP events
**What:** ERP webhook events arrive at `/api/v1/erp-push/webhook`. Verify HMAC signature validation is implemented for all supported ERPs.
**Why:** Without signature validation, any party can send fake webhook events.
**Files:** `backend/financeops/modules/erp_push/application/webhook_task.py`, `backend/financeops/api/v1/erp_push.py`
**Effort:** 2-4 hours (audit + implement)

### L-010: Document all Temporal workflow SLAs
**What:** Temporal workflows for long-running financial runs (consolidation, FX translation, FA depreciation) have no documented SLA or timeout configuration.
**Why:** A stuck workflow with no timeout can block downstream processes indefinitely.
**Files:** `backend/financeops/temporal/` (various workflows)
**Effort:** 4 hours (documentation + timeout config)

---

## PHASE COMPLETION STATUS

| Phase | Status | Description | Test Coverage |
|---|---|---|---|
| Phase 0 | COMPLETE | Foundation (IAM, credits, audit, LLM, storage) | ~100% |
| Phase 1 | COMPLETE | Core finance (MIS, recon, bank recon, WC, GST, monthend, auditor) | ~100% |
| Phase 1a | COMPLETE | Architecture controls (recon bridge, normalization, ratio variance, risk, anomaly, board pack) | ~100% |
| Phase 1b | COMPLETE | FX rate engine | ~100% |
| Phase 1c | COMPLETE | Multi-currency consolidation | ~100% |
| Phase 1d | COMPLETE | Revenue, Lease, Prepaid, Fixed Assets | ~100% |
| Phase 1e | COMPLETE | Platform control plane (RBAC, quota, isolation, workflow) | ~100% |
| Phase 1f | COMPLETE | Advanced finance modules (MIS, recon bridge, payroll, ratio, risk, anomaly, board pack) | ~100% |
| Phase 2 | COMPLETE | Multi-entity consolidation, FX translation, ownership, cash flow, equity | ~100% |
| Phase 3 | COMPLETE | Observability engine | ~100% |
| Phase 4 | COMPLETE | ERP integration (20+ connectors, sync kernel, push, webhooks) | ~100% |
| Phases 5-12 | COMPLETE | All additional modules (billing, advisory, compliance, marketplace, etc.) | ~100% |
| Phase 6 | PARTIAL | ClamAV integration (stubbed — KI-004) | Partial |
| Production Hardening | IN PROGRESS | Auth hardening done; ClamAV/monitoring gaps remain | — |

---

## FEATURE DEVELOPMENT BACKLOG

### Core Financial Features

| Feature | Priority | Status | Notes |
|---|---|---|---|
| Real-time dashboard KPI refresh | High | Not started | WebSocket or SSE |
| AI-powered journal entry suggestions | High | Partial | AI CFO layer exists |
| Automated bank statement parsing | High | Partial | Bank parsers in test |
| Period-close lockout enforcement | High | Partial | Period close governance in 0104 |
| Multi-currency GL posting | Medium | Partial | FX/IAS21 migration in 0103 |
| Intercompany elimination automation | Medium | Partial | Multi-entity consolidation exists |
| Tax computation engine (GST, TDS, VAT) | Medium | Partial | GST/TDS rules in 0093 |
| Payroll integration (full cycle) | Medium | Partial | Payroll GL normalization + recon |
| XBRL/iXBRL filing generation | Low | Not started | Statutory module exists |
| IFRS 17 insurance contracts | Low | Not started | — |

### Platform Features

| Feature | Priority | Status | Notes |
|---|---|---|---|
| Two-factor authentication via SMS | Medium | Not started | TOTP only currently |
| SSO / SAML 2.0 / OIDC | High | Not started | Enterprise requirement |
| Self-service tenant onboarding | High | Partial | Org setup wizard exists |
| Custom field / metadata extension | Medium | Not started | — |
| Data export (CSV, Excel, PDF) | High | Partial | Board pack has export; need global export |
| Audit log export (compliance) | High | Partial | Audit trail exists; export API TBD |
| API webhook subscriptions (outbound) | Medium | Not started | ERP push exists; generic webhooks TBD |
| White-label domain (custom DNS) | Medium | Partial | White-label config exists; DNS management TBD |
| Usage analytics for platform admin | Medium | Not started | — |
| Tenant data migration tool | Low | Not started | — |

### Integration Features

| Feature | Priority | Status | Notes |
|---|---|---|---|
| Stripe Connect for marketplace payouts | Medium | Not started | Partner commissions exist |
| Direct bank feeds (Open Banking) | High | Partial | Account Aggregator connector exists |
| GST portal API integration (India) | High | Partial | GST recon module exists |
| TDS returns filing (India) | Medium | Not started | TDS rules exist |
| ROC filings (MCA21) | Low | Not started | Statutory module exists |
| VAT filing (EU/UK) | Low | Not started | Multi-GAAP exists |
| Payroll HRMS connectors (ADP, Workday) | Medium | Not started | Keka/Darwinbox connectors exist |
| Document management (SharePoint/GDrive) | Low | Not started | — |

---

## TECHNICAL DEBT REGISTER

| ID | Area | Description | Severity | Effort |
|---|---|---|---|---|
| TD-001 | Utils | `findings.py`, `quality_signals.py` broken imports (KI-001, KI-002) | High | 4h |
| TD-002 | Tests | `pytest-asyncio==0.24.0` should be `>=1.0.0` | High | 30m |
| TD-003 | Dependencies | Multiple packages 2+ major versions behind (anthropic, fastapi, openai, OTEL) | Medium | 2-3 days |
| TD-004 | Frontend | `next-auth@5.0.0-beta.30` — beta dependency in production | Medium | 4h (when stable) |
| TD-005 | Backend | Mixed module patterns (some in `api/v1/`, some in `modules/*/api/`) | Low | — |
| TD-006 | Backend | No typed response models on many endpoints (missing `response_model=`) | Medium | 3-5 days |
| TD-007 | Security | Refresh token rotation not implemented | High | 8h |
| TD-008 | Security | `/metrics` endpoint unauthenticated | High | 2h |
| TD-009 | Security | Registration endpoint not rate-limited | High | 1h |
| TD-010 | Ops | No DLQ for Celery failed tasks | Medium | 4h |
| TD-011 | Ops | Flower not deployed to production | Medium | 2h |
| TD-012 | Ops | OTEL exporter not configured | Medium | 2h |
| TD-013 | Ops | Temporal worker not in render.yaml | Critical | 1h |
| TD-014 | Storage | ClamAV stubbed in production | High | 1-2 days |
| TD-015 | DB | No PgBouncer pooler in front of PostgreSQL | Medium | 4-8h |
| [TD-016](../tech-debt/TD-016-phase2-consolidation-tax-tabs.md) | Frontend / Phase 2 | No standalone consolidation or tax workspace tabs — Phase 2 Deliverables 5 & 6 (consolidation tab disable, Tax/GST relabel) cannot be implemented as specified | High | 2–3 days (Option A) or 1 day (Option B) |
| [TD-017](../tech-debt/TD-017-user-orgs-endpoint-duplication.md) | Frontend / API duplication | Two endpoints (`/user/tenants` legacy and `/users/me/orgs` BE-001) returning org-membership-shaped data with different shapes; `PageClient.tsx` uses the legacy one, `OrgSwitcher.tsx` (SP-2A) uses the new one. Resolve by deciding whether to migrate or formalize the split. | Medium | 1d |

---

## ARCHITECTURE DECISIONS NEEDED

### AD-001: Temporal vs Celery for long-running runs
**Question:** Should all long-running financial computation runs (consolidation, FX, FA depreciation) migrate to Temporal, or stay as Celery tasks?
**Context:** Temporal provides durable execution, workflow history, and retry semantics. Current implementation uses Temporal but the worker is not deployed to production.
**Options:**
  a) Commit to Temporal: deploy worker, migrate all complex tasks
  b) Simplify: use Celery for everything, remove Temporal dependency
**Deadline:** Before first production load

### AD-002: Multi-region strategy
**Question:** Should the platform support data residency in specific regions?
**Context:** Currently deployed in Singapore (Render). EU/US customers may require data residency.
**Options:**
  a) Single region with data export compliance
  b) Multi-region with data residency (high complexity)

### AD-003: Frontend state management consolidation
**Question:** Both Zustand and TanStack Query are used. Should there be a unified state management strategy?
**Context:** Zustand for global UI state, TanStack Query for server state is a clean separation.
**Recommendation:** Keep this separation; document the boundary clearly.

### AD-004: API versioning mechanism
**Question:** When breaking API changes are needed, how will `v2` routes be introduced?
**Context:** All routes are `/api/v1/*`. Frontend and any external integrations depend on these paths.
**Options:**
  a) New route prefix `/api/v2/*`
  b) Content negotiation (`Accept: application/vnd.financeops.v2+json`)
  c) Feature flags per tenant

### AD-005: Search implementation
**Question:** The `search` module has a `SearchIndexEntry` table. Should this remain in PostgreSQL full-text search or migrate to a dedicated search engine (Elasticsearch, Typesense, Meilisearch)?
**Context:** pgvector is already installed for vector similarity. PostgreSQL FTS is sufficient for initial scale.
**Recommendation:** Keep PostgreSQL FTS + pgvector for now; re-evaluate at 1M+ records per tenant.

---

## DEPLOYMENT READINESS CHECKLIST

### Before First User Login
- [ ] All required env vars set: `SECRET_KEY`, `JWT_SECRET`, `FIELD_ENCRYPTION_KEY`, `NEXTAUTH_SECRET`, `DATABASE_URL`, `REDIS_URL`
- [ ] `CORS_ALLOWED_ORIGINS` set to frontend URL
- [ ] `APP_ENV=production` on backend
- [ ] Platform owner seeded (`SEED_ON_STARTUP=true` or manual seed script)
- [ ] `alembic upgrade head` run on production DB
- [ ] Database health check passing (`GET /ready` returns 200)
- [ ] Frontend can authenticate (GET `/api/v1/auth/login` returns tokens)

### Before First External User
- [ ] SMTP email configured (password reset must work)
- [ ] Sentry DSN configured (error tracking active)
- [ ] R2 storage configured (file uploads work)
- [ ] ClamAV deployed or `CLAMAV_REQUIRED=false` explicitly set
- [ ] Rate limits tested and tuned for expected traffic
- [ ] All legal pages live (`/legal/terms`, `/legal/privacy`, `/legal/dpa`, `/legal/sla`)
- [ ] Temporal worker deployed (if using workflow-based features)
- [ ] Celery workers healthy (Flower or equivalent monitoring)

### Before Public Launch
- [ ] Penetration test or security audit
- [ ] Load test (simulate 100+ concurrent users)
- [ ] Database indexes reviewed and optimized
- [ ] PgBouncer connection pooler configured
- [ ] Redis persistence confirmed for production Redis
- [ ] Backup/DR tested (restore from backup)
- [ ] OTEL distributed tracing configured
- [ ] SOC2 / ISO27001 controls documented and implemented
- [ ] Privacy policy and DPA reviewed by legal
- [ ] Cookie consent banner functional
- [ ] GDPR data export/deletion tested

### Before Enterprise Customers
- [ ] SSO / SAML 2.0 support
- [ ] Custom data residency options
- [ ] SLA monitoring and uptime reporting
- [ ] Enterprise RBAC (custom roles + granular permissions)
- [ ] Dedicated tenant environment option
- [ ] Audit log API (downloadable audit trail)
- [ ] Advanced security: IP allowlisting, MFA enforcement policies

---

## MONITORING & ALERTING SETUP NEEDED

| Alert | Condition | Severity | Tool |
|---|---|---|---|
| API error rate spike | 5xx rate > 1% over 5m | Critical | Sentry + OTEL |
| Database connectivity failure | `/ready` returns non-200 | Critical | Render health check |
| Migration mismatch | `/ready` returns `out_of_sync` | Critical | Custom alert |
| Celery queue depth spike | Any queue > 1000 tasks | High | Prometheus gauge |
| Redis connectivity failure | Redis ping fails | Critical | Celery heartbeat |
| JWT errors spike | Auth failures > 10/min per tenant | High | Prometheus counter |
| AI provider failures | All AI models circuit-open | High | Custom metric |
| File upload validation failures | > 5/min | Medium | Prometheus counter |
| Payment webhook processing failure | Stripe/Razorpay webhook error | Critical | Sentry |
| Active tenant count drop | Active tenants < expected baseline | High | Prometheus gauge |
| Temporal workflow stuck | Workflow running > max expected duration | High | Temporal UI / API |

---

## BACKUP & DISASTER RECOVERY

### Current State
- `backup` module exists (`modules/backup/`) with `BackupRunLog` table
- No backup service is configured in `render.yaml`
- No documented RTO (Recovery Time Objective) or RPO (Recovery Point Objective)

### Required Actions

| Action | Priority | Notes |
|---|---|---|
| Configure automated PostgreSQL backups | Critical | Use Supabase daily backups or pg_dump to R2 |
| Document RTO/RPO targets | High | e.g., RTO=4h, RPO=24h for starter; RTO=1h, RPO=1h for enterprise |
| Configure Redis backup | High | AOF + snapshot to R2 |
| Test DB restore from backup | High | Verify restore process works before incident |
| Document disaster recovery runbook | Medium | Step-by-step for: DB failure, Redis failure, Render outage, Vercel outage |
| Configure R2 versioning | Medium | Enable object versioning on R2 bucket for file recovery |
| Set up cross-region backup | Low | For enterprise data residency |
| Implement point-in-time recovery | Low | PostgreSQL WAL archiving |

---

## COMPLIANCE & LEGAL

### GDPR (EU / UK)
| Requirement | Status | Action Needed |
|---|---|---|
| Data processing agreement | Partial | `/legal/dpa` page exists; verify legal review |
| Right to erasure | Partial | `gdpr_erasure` migration + `ErasureLog` model exist; verify API completeness |
| Right to access | Partial | `/settings/privacy/my-data` page exists; verify data export completeness |
| Consent management | Partial | `GDPRConsentRecord` model exists; verify consent capture on registration |
| Breach notification | Partial | `GDPRBreachRecord` model exists; verify 72h notification workflow |
| Data retention policies | Not started | Define retention periods per data category |
| DPA with sub-processors | Not started | Anthropic, OpenAI, Sentry, Render, Vercel, Cloudflare |
| Cookie consent | Partial | `CookieConsent` component exists; verify GDPR-compliant implementation |

### India Data Protection (DPDPA 2023)
| Requirement | Status | Action Needed |
|---|---|---|
| Data fiduciary registration | Not started | Required for processing Indian user data |
| Consent framework | Partial | Consent records exist; adapt for DPDPA requirements |
| Data localisation | Not started | Indian user data may need to stay in India |
| Grievance officer | Not started | Must designate and publish contact |

### Financial Regulations
| Regulation | Status | Action Needed |
|---|---|---|
| Audit trail integrity | Complete | Chain hash + insert-only enforced |
| Segregation of duties | Partial | RBAC exists; specific SoD rules per regulation TBD |
| Financial data retention | Not started | Define and implement retention periods |
| PCI-DSS (payments) | Not started | If storing payment card data; Stripe/Razorpay handle card data |
| SOC2 Type I | Partial | Compliance controls in place; formal audit needed |
| SOC2 Type II | Not started | Requires 6-12 months operating evidence |
| ISO 27001 | Partial | ISO 27001 controls module exists; formal certification TBD |
