# FinanceOps Platform — Complete State Document
*Generated: 2026-04-05*
*Migration head: 0120_normalize_iam_user_emails.py (120 migrations total)*
*Last commit: ee2fd70 — ARCH: enforce multi-layer auth model*

---

## 1. PLATFORM OVERVIEW

### 1.1 What This Platform Is

FinanceOps is a production-grade, multi-tenant financial SaaS platform serving CFOs, finance teams, and directors. It provides a comprehensive suite of financial operations modules including general ledger, reconciliation, payroll GL, bank reconciliation, revenue recognition (ASC 606 / IFRS 15), lease accounting (IFRS 16 / ASC 842), fixed assets, consolidation (multi-entity, multi-currency, FX translation), working capital, forecasting, budgeting, scenario modelling, tax provision, debt covenants, transfer pricing, board pack generation, anomaly detection, AI-powered CFO analysis, and an ERP integration layer with 20+ connector implementations.

The platform enforces strict financial integrity guarantees: insert-only financial tables with cryptographic chain hashes (SHA-256), row-level security at the PostgreSQL level, AES-256-GCM field encryption for secrets, Decimal arithmetic throughout, and full audit trails. Multi-tenancy is enforced at the DB layer using PostgreSQL `set_config('app.current_tenant_id', ...)` via RLS policies.

The frontend is a Next.js 14 application deployed on Vercel with NextAuth v5 (Auth.js) for session management. The backend is FastAPI 0.115 deployed on Render.com (Docker). Background jobs run via Celery 5 + Redis 7 with four priority queues. Temporal.io is available for long-running financial workflows (consolidation, FX translation, fixed asset depreciation runs, etc.). Storage uses Cloudflare R2 (S3-compatible). AI integrations support Anthropic, OpenAI, Gemini, and Ollama with fallback chains and circuit breakers.

### 1.2 Technology Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Frontend Framework | Next.js | 14.2.35 | App Router |
| Frontend Auth | NextAuth / Auth.js | 5.0.0-beta.30 | JWT session strategy |
| Frontend State | Zustand | 5.0.11 | |
| Frontend Data Fetching | TanStack Query | 5.x | |
| Frontend UI | Radix UI + Tailwind + shadcn | Latest | |
| Frontend Charts | Recharts | 3.x | |
| Backend Framework | FastAPI | 0.115.0 | Python 3.11 |
| Backend ASGI | Uvicorn + Gunicorn | 0.30.0 / 22.0.0 | |
| ORM | SQLAlchemy | 2.0.35 | Async |
| DB Driver | asyncpg | 0.30.0 | |
| Database | PostgreSQL | 16 + pgvector | |
| Migrations | Alembic | 1.13.0 | 120 migrations |
| Cache / Queue Broker | Redis | 7 | |
| Task Queue | Celery | 5.4.0 | 4 priority queues |
| Task Monitor | Flower | 2.0.1 | |
| Workflow Engine | Temporal.io | 1.7.0 | |
| Auth (backend) | JWT (python-jose) + bcrypt | 3.3.0 / 1.7.4 | HS256 |
| MFA | pyotp TOTP | 2.9.0 | |
| Field Encryption | AES-256-GCM (cryptography) | 43.0.0 | |
| Rate Limiting | slowapi | 0.1.9 | |
| CSRF | starlette-csrf | 3.0.0 | |
| AI Providers | Anthropic / OpenAI / Gemini / Ollama | Various | |
| Storage | Cloudflare R2 (boto3 S3) | 1.35.0 | |
| Telemetry | OpenTelemetry + Sentry | 1.27.0 / 2.14.0 | |
| Metrics | Prometheus | 0.21.0 | |
| Payments | Stripe + Razorpay | 11.6.0 / 1.4.2 | |
| Package Manager | uv (backend) / npm (frontend) | Latest | |
| CI/CD | GitHub Actions | — | |
| Backend Deploy | Render.com | — | Docker |
| Frontend Deploy | Vercel | — | Next.js |
| DB Host | Supabase or self-hosted | — | PostgreSQL 16 |

### 1.3 High-Level Architecture

```
                        ┌─────────────────────────────────┐
                        │       Vercel (Frontend)         │
                        │  Next.js 14 + NextAuth v5       │
                        │  JWT session, SSR+CSR            │
                        └──────────────┬──────────────────┘
                                       │ HTTPS API calls
                                       │ Bearer token
                        ┌──────────────▼──────────────────┐
                        │     Render.com (Backend)        │
                        │  FastAPI 0.115 (uvicorn)        │
                        │  /api/v1/* routes               │
                        │  Middleware stack:              │
                        │  CORS → CSRF → RLS →           │
                        │  CorrelationId → Idempotency   │
                        │  → Envelope → RequestLogging   │
                        └────┬──────────────┬────────────┘
                             │              │
              ┌──────────────▼──┐    ┌──────▼──────────┐
              │  PostgreSQL 16  │    │   Redis 7        │
              │  + pgvector     │    │   Cache + Broker │
              │  120 migrations │    │   Sessions       │
              │  RLS policies   │    └──────┬───────────┘
              │  Chain hashes   │           │
              └─────────────────┘    ┌──────▼───────────┐
                                     │  Celery Workers  │
                                     │  4 priority queues│
                                     │  + Beat Scheduler│
                                     └──────────────────┘
                        ┌────────────────────────────────┐
                        │     Temporal.io (optional)     │
                        │  Long-running financial runs   │
                        │  FX, consolidation, FA, etc.   │
                        └────────────────────────────────┘
                        ┌────────────────────────────────┐
                        │  External Integrations         │
                        │  Anthropic / OpenAI / Gemini   │
                        │  Cloudflare R2 storage         │
                        │  Stripe + Razorpay payments    │
                        │  20+ ERP connectors            │
                        │  ClamAV (antivirus)            │
                        └────────────────────────────────┘
```

---

## 2. REPOSITORY STRUCTURE

### 2.1 Full Repo Tree (Grouped)

```
D:/finos/
├── .env                          # Local dev environment vars
├── .env.example                  # Template for all env vars
├── .env.prod                     # Production env template
├── .env.production.example       # Production env example
├── .github/
│   └── workflows/
│       ├── ci.yml                # Main CI: tests + build + alembic check
│       ├── dependency_matrix.yml # Dependency matrix automation
│       ├── sast.yml              # Static analysis security testing
│       └── schema_check.yml      # Schema validation
├── .semgrep.yml                  # Semgrep SAST rules
├── DEPENDENCY_MATRIX.md          # Generated dependency matrix
├── KNOWN_ISSUES.md               # Open issues register
├── _audit_ge300.md               # Internal audit artifact
├── _audit_ge300.tsv              # Internal audit artifact
├── artifacts/
│   ├── migration_validation.json
│   └── phase1_validation_report.json
├── backend/
│   ├── .env                      # Backend env overrides
│   ├── .env.example              # Backend env template
│   ├── Dockerfile                # API container (python:3.11-slim)
│   ├── Dockerfile.beat           # Celery beat container
│   ├── Dockerfile.worker         # Celery worker container
│   ├── alembic.ini               # Alembic config
│   ├── pyproject.toml            # Python deps + tool config
│   ├── uv.lock                   # Locked dependencies
│   ├── financeops/               # Main application package
│   │   ├── api/
│   │   │   ├── deps.py           # All FastAPI dependencies
│   │   │   └── v1/               # 45+ route modules
│   │   ├── config.py             # Settings (pydantic-settings)
│   │   ├── core/
│   │   │   ├── auth.py           # Auth dependencies
│   │   │   ├── exceptions.py     # Exception hierarchy
│   │   │   ├── middleware.py     # Custom middleware stack
│   │   │   ├── migration_checker.py
│   │   │   └── security.py       # JWT, bcrypt, AES, TOTP
│   │   ├── db/
│   │   │   ├── base.py           # Base, UUIDBase, FinancialBase
│   │   │   ├── models/           # 50+ SQLAlchemy model files
│   │   │   ├── rls.py            # RLS context helpers
│   │   │   ├── session.py        # Engine + session factory
│   │   │   └── transaction.py    # commit_session helper
│   │   ├── llm/                  # LLM gateway + circuit breaker
│   │   ├── main.py               # FastAPI app factory + lifespan
│   │   ├── migrations/
│   │   │   └── run.py            # run_migrations_to_head
│   │   ├── modules/              # 65+ feature modules
│   │   ├── observability/        # Sentry, OTEL, Prometheus, logging
│   │   ├── platform/             # Control plane (RBAC, quota, isolation)
│   │   ├── prompt_engine/        # AI prompt governance
│   │   ├── seed/                 # Seed scripts (CoA, platform owner)
│   │   ├── services/             # Core services (auth, user, tenant, credit, audit)
│   │   ├── shared_kernel/        # Response envelopes, idempotency
│   │   ├── storage/              # R2 provider, airlock file validation
│   │   ├── tasks/                # Celery app + beat tasks
│   │   ├── temporal/             # Temporal worker
│   │   └── utils/                # chain_hash, pagination, formatting, etc.
│   ├── migrations/
│   │   ├── env.py                # Async Alembic env
│   │   └── versions/             # 120 migration files
│   ├── scripts/
│   │   ├── entrypoint.sh         # Docker entrypoint (migrations + start)
│   │   └── start.sh              # App start script
│   └── tests/
│       ├── conftest.py           # Test fixtures (engine, session, client)
│       ├── integration/          # Integration test suites
│       ├── prompt_engine/        # Prompt engine tests
│       ├── unit/                 # Unit test suites
│       └── utils/                # Test utilities
├── docker-compose.prod.yml       # Production docker-compose
├── frontend/
│   ├── Dockerfile                # Frontend container
│   ├── app/                      # Next.js App Router pages
│   │   ├── (admin)/              # Admin route group
│   │   ├── (auth)/               # Auth route group
│   │   ├── (dashboard)/          # Main dashboard route group
│   │   ├── (org-setup)/          # Org setup route group
│   │   ├── legal/                # Legal pages
│   │   └── page.tsx              # Root page
│   ├── components/               # React components
│   ├── hooks/                    # Custom React hooks
│   ├── lib/                      # Auth, API client, utilities
│   ├── middleware.ts              # NextAuth middleware + security headers
│   ├── next.config.mjs           # Next.js config + Sentry
│   ├── package.json              # Frontend dependencies
│   └── vercel.json               # Vercel deployment config
├── infra/
│   ├── docker-compose.yml        # Local dev compose (full stack)
│   └── docker-compose.test.yml   # Test compose (pgvector)
├── railway.toml                  # Railway deploy config (alternative)
└── render.yaml                   # Render.com deploy config (primary)
```

### 2.2 Key Directories

| Path | Purpose | Key Files |
|---|---|---|
| `backend/financeops/api/v1/` | All REST API route handlers | 45+ .py files per module |
| `backend/financeops/core/` | Security, middleware, exceptions | security.py, middleware.py, exceptions.py |
| `backend/financeops/db/` | Database layer | base.py, session.py, rls.py, models/ |
| `backend/financeops/modules/` | Feature modules (self-contained) | 65+ subdirectories |
| `backend/financeops/platform/` | Control plane (RBAC, quota, isolation) | services/, db/models/, api/ |
| `backend/financeops/services/` | Core business services | auth_service.py, user_service.py, tenant_service.py, credit_service.py, audit_service.py |
| `backend/financeops/tasks/` | Celery configuration | celery_app.py, payment_tasks.py |
| `backend/financeops/llm/` | AI gateway | gateway.py, circuit_breaker.py, fallback.py |
| `backend/financeops/storage/` | File operations | r2.py, airlock.py, provider.py |
| `backend/migrations/versions/` | Alembic migration files | 120 files (0001–0120) |
| `backend/tests/` | Test suite | conftest.py, integration/, unit/ |
| `frontend/app/` | Next.js pages (App Router) | 150+ page.tsx files |
| `frontend/components/` | Reusable React components | 90+ .tsx files |
| `frontend/lib/` | Auth, API client, utilities | auth.ts, api/client.ts |

### 2.3 Frontend Architecture

**Framework:** Next.js 14 with App Router

**Route Groups:**
- `(auth)` — unauthenticated pages: login, register, forgot/reset password, MFA, accept invite, change password
- `(dashboard)` — authenticated pages: all finance modules
- `(admin)` — platform admin pages (requires platform_owner/platform_admin role)
- `(org-setup)` — org setup wizard (required before accessing dashboard)
- `legal/` — public legal pages (terms, privacy, DPA, SLA, cookies)

**Auth:** NextAuth v5 with `Credentials` provider. Session strategy: JWT. Token refresh handled automatically in `jwt` callback when `access_token_expires_at` passes. Three special error codes drive redirects: `mfa_required`, `password_change_required`, `mfa_setup_required`.

**State management:** Zustand for global state, TanStack Query for server state / data fetching.

**Key files:**
- `frontend/middleware.ts` — Route protection, org-setup redirect, admin role guard, security headers (HSTS, CSP, X-Frame-Options, etc.)
- `frontend/lib/auth.ts` — NextAuth config, JWT/session callbacks, token refresh
- `frontend/lib/auth-handoff.ts` — MFA/password-change handoff between pages
- `frontend/lib/api/client.ts` — Typed API client with bearer token injection
- `frontend/next.config.mjs` — Sentry integration (conditional on SENTRY_DSN)

### 2.4 Backend Architecture

**App factory pattern:** `create_app()` in `main.py` returns a configured FastAPI app. Lifespan context manages startup (DB connectivity check, optional AUTO_MIGRATE, migration state verification, CoA seed, platform user seed) and shutdown (close Redis pool, dispose DB engine).

**Middleware stack (outermost to innermost):**
1. GZipMiddleware (>= 1024 bytes)
2. CORSMiddleware
3. LoggingMiddleware (OpenTelemetry)
4. RequestIDMiddleware
5. ApiResponseEnvelopeMiddleware (wraps all responses in `{data, error, request_id}`)
6. IdempotencyMiddleware
7. RequestSizeLimitMiddleware
8. CorrelationIdMiddleware
9. RLSMiddleware (sets PostgreSQL tenant context)
10. RequestLoggingMiddleware
11. FinanceOpsCSRFMiddleware (exempt: /api/*, /health/*, /metrics/*, webhooks)

**Dependency graph:** `api/deps.py` provides `get_async_session`, `get_current_user`, `get_redis`, `require_org_setup`, `require_entitlement`, `require_role`, etc.

**Response envelope:** All API responses are wrapped in `{data: ..., error: null}` or `{data: null, error: {code, message, details}}`.

**Patterns:**
- All route handlers: `async def`
- All DB calls: `await`
- Financial arithmetic: `Decimal` with `ROUND_HALF_UP`
- Insert-only on financial tables (no UPDATE/DELETE)
- Chain hash on every financial row: `compute_chain_hash(record_data, previous_hash)`
- RLS context: `set_tenant_context(session, tenant_id)` before every query

---

## 3. MODULES & SERVICES

### 3.1 Phase 0 — Foundation

**Authentication** (`/api/v1/auth`)
- Register, login (with TOTP), MFA setup/verify, refresh token, logout, revoke all sessions
- Forgot password, reset password (token-based), change password, accept invite
- `/me` endpoint returning user + tenant info
- Rate limits: 5/min login, 5/min token, 3/min MFA

**Tenants** (`/api/v1/tenants`)
- CRUD for tenant management
- Tenant types: `direct`, `white_label`, `partner`

**Users** (`/api/v1/users`)
- User management: list, get, create, update, deactivate
- Role assignments

**Credits** (service layer)
- Reserve → Confirm | Release pattern
- SELECT FOR UPDATE for concurrency safety

**Audit** (service layer)
- `log_action()` called on all state-changing operations

**LLM Gateway** (`financeops/llm/`)
- Fallback chains per task type
- Circuit breaker (open/closed/half-open states)
- AI cost ledger tracking tokens + cost per tenant

**Storage Airlock** (`financeops/storage/`)
- Cloudflare R2 via boto3
- File validation pipeline: MIME check → size check → SHA-256 → ClamAV (stubbed)

### 3.2 Phase 1 — Core Finance Engine

**MIS Manager** (`/api/v1/mis`)
- MIS template management, uploads, snapshots
- Tables: `mis_templates`, `mis_uploads`

**GL/TB Reconciliation** (`/api/v1/recon`)
- GL entries, trial balance rows, recon items
- Tables: `gl_entries`, `trial_balance_rows`, `recon_items`

**Bank Reconciliation** (`/api/v1/bank-recon`)
- Bank statements, transactions, recon items
- Tables: `bank_statements`, `bank_transactions`, `bank_recon_items`

**Working Capital** (`/api/v1/working-capital`)
- AP/AR line items, working capital snapshots
- Tables: `ap_line_items`, `ar_line_items`, `wc_snapshots`, `working_capital_snapshots`

**GST Reconciliation** (`/api/v1/gst`)
- GST returns, recon items
- Tables: `gst_returns`, `gst_recon_items`

**Month-End Checklist** (`/api/v1/monthend`)
- Checklist templates + tasks (mutable), checklist instances (insert-only)
- Tables: `monthend_checklists`, `monthend_tasks`

**Auditor Access** (`/api/v1/auditor`)
- Auditor grants (insert-only, revocation = new row with is_active=False)
- Tables: `auditor_grants`, `auditor_access_logs`

### 3.3 Phase 1 Advanced — Architecture + Controls

**Reconciliation Bridge** (`/api/v1/reconciliation`)
- Reconciliation sessions, scopes, lines, exceptions, resolution events, evidence links
- Tables: `reconciliation_sessions`, `reconciliation_scopes`, `reconciliation_lines`, etc.

**Payroll GL Normalization** (`/api/v1/normalization`)
- Normalization sources, runs, mappings, GL lines, payroll lines, exceptions, evidence links

**Payroll GL Reconciliation** (`/api/v1/payroll-gl-reconciliation`)
- Rules, mappings, runs, run scopes

**Ratio Variance Engine** (`/api/v1/ratio-variance`)
- Metric definitions, metric runs, metric results, variance definitions, trend definitions

**Financial Risk Engine** (`/api/v1/financial-risk`)
- Risk definitions, risk runs, risk results, materiality rules, rollforward events

**Anomaly Pattern Engine** (`/api/v1/anomaly-engine`)
- Anomaly definitions, runs, results, pattern rules, statistical rules, correlation rules

**Board Pack Narrative Engine** (`/api/v1/board-pack` — engine layer)
- Board pack definitions, runs, narrative results, export artifacts

### 3.4 Phase 1 — FX Rate Engine

**FX Rates** (`/api/v1/fx/rates`, `/api/v1/fx/manual-rates`)
- FX rate quotes, manual monthly rates, variance results, fetch runs
- Tables: `fx_rate_quotes`, `fx_manual_monthly_rates`, `fx_variance_results`, `fx_rate_fetch_runs`

**FX Translation Reporting** (`/api/v1/fx/reporting-currencies`, `/api/v1/fx/translation-rules`, `/api/v1/fx/runs`)
- Reporting currency definitions, translation rule definitions, rate selection policies, translation runs

### 3.5 Phase 1 — Revenue, Lease, Prepaid, Fixed Assets

**Revenue Recognition** (`/api/v1/revenue`) — ASC 606 / IFRS 15
- Contracts, performance obligations, line items, schedules, journal entries, runs

**Lease Accounting** (`/api/v1/lease`) — IFRS 16 / ASC 842
- Leases, modifications, payment schedules, liability schedules, ROU schedules, journal entries, runs

**Prepaid Amortization** (`/api/v1/prepaid`)
- Prepaid schedules, amortization entries, adjustments, journal entries, runs

**Fixed Assets Register** (`/api/v1/fixed-assets`)
- Assets, asset classes, depreciation runs, impairments, revaluations, journal entries
- Straight-line and reducing-balance depreciation engines

### 3.6 Phase 2 — Multi-Entity Consolidation

**Multi-Entity Consolidation** (`/api/v1/consolidation`)
- Entity hierarchies, consolidation scopes, rules, intercompany mapping rules, runs

**Multi-Currency Consolidation** (`/api/v1/consolidation`) — legacy
- Consolidation runs, entities, line items, results, eliminations, intercompany pairs

**FX Translation Reporting** (`/api/v1/fx`)
- Translation runs with IAS 21 methodology

**Ownership Consolidation** (`/api/v1/ownership`)
- Ownership structures, relationships, minority interest rules, consolidation runs

**Cash Flow Engine** (`/api/v1/cash-flow`)
- Statement definitions, line mappings, bridge rule definitions, runs, results

**Equity Engine** (`/api/v1/equity`)
- Statement definitions, line definitions, rollforward rules, source mappings, runs, results

### 3.7 Phase 3 — Observability Engine

**Observability Engine** (`/api/v1/observability`)
- Run registries, observability runs, results, governance events, lineage snapshots, performance metrics, token diff definitions

### 3.8 Phase 4 — ERP Integration

**ERP Sync Kernel** (`/api/v1/erp-sync`)
- External connections, sync definitions, raw/normalized snapshots, period locks, consent logs, drift reports, health alerts, SLA configs

**ERP Integration** (`/api/v1/erp/...`)
- OAuth sessions, connector registry, connector capability registry, mapping definitions

**ERP Push** (`/api/v1/erp-push`)
- Push runs, events, idempotency keys, webhook event ingest

**Supported ERP Connectors:**
- QuickBooks Online (QBO), Xero, SAP, Oracle, Dynamics 365, NetSuite, Odoo, Tally, Sage, FreshBooks, Wave, Zoho, Plaid, Darwinbox, Keka, Razorpay Payroll, Marg, Munim, Busy, AA Framework (account aggregator)

### 3.9 Phase 5+ — Platform Modules

**AI CFO Layer** (`/api/v1/ai-cfo`)
- AI-powered CFO dashboard, recommendations, anomaly analysis, narrative generation

**Analytics Layer** (`/api/v1/analytics`)
- CFO dashboard KPIs, ratio trends, variance analysis, financial statements (P&L, balance sheet, cash flow)

**Accounting Layer** (`/api/v1/accounting`)
- Journal entries (JVs), approval workflows, duplicate detection, financial statement generation, vendor management, attachments, GST/TDS rules

**Accounting Ingestion** (public + authenticated endpoints)
- Invoice upload, OCR processing, classification pipeline

**Payment / Billing** (`/api/v1/billing`)
- Subscription plans, tenant subscriptions, billing invoices, payment methods, credit top-ups, webhook events (Stripe + Razorpay)
- Trial management, grace periods, proration, credit expiry

**Industry Modules** (`/api/v1/industry`)
- Pluggable industry-specific modules (manufacturing, retail, real estate, etc.)

### 3.10 Self-Contained Feature Modules

All located in `backend/financeops/modules/`:

| Module | Purpose | API Prefix |
|---|---|---|
| `anomaly_pattern_engine` | UI layer for anomalies | `/api/v1/anomalies` |
| `auditor_portal` | Auditor portal access + PBC requests | `/api/v1/auditor-portal` |
| `auto_trigger` | Auto-trigger AI pipeline runs | `/api/v1/auto-trigger` |
| `backup` | Backup + DR scheduling | `/api/v1/backup` |
| `board_pack_generator` | Board pack generation + export | `/api/v1/board-packs` |
| `budgeting` | Budget versions, line items | `/api/v1/budgets` |
| `cash_flow_forecast` | Cash flow forecast runs | `/api/v1/treasury` |
| `closing_checklist` | Period close checklists | `/api/v1/close` |
| `coa` | Chart of accounts framework | `/api/v1/coa` |
| `compliance` | SOC2, ISO27001 controls, GDPR | `/api/v1/compliance` |
| `custom_report_builder` | Custom report templates + runs | `/api/v1/reports` |
| `debt_covenants` | Covenant definitions + breach events | `/api/v1/covenants` |
| `digital_signoff` | Director signoff workflow | `/api/v1/signoff` |
| `expense_management` | Expense claims, policies, approvals | `/api/v1/expenses` |
| `fdd` | Financial due diligence engagements | `/api/v1/fdd` |
| `fixed_assets` | Fixed assets (module layer) | `/api/v1/assets` |
| `forecasting` | Forecast runs, assumptions, line items | `/api/v1/forecasts` |
| `invoice_classifier` | Invoice classification rules + results | `/api/v1/invoice-classify` |
| `learning_engine` | AI learning signals + corrections | `/api/v1/learning` |
| `locations` | Locations + cost centres | `/api/v1/locations` |
| `ma_workspace` | M&A workspace, DD tracker, valuation | `/api/v1/ma` |
| `marketplace` | Template marketplace | `/api/v1/marketplace` |
| `multi_gaap` | Multi-GAAP config + runs | `/api/v1/gaap` |
| `notifications` | In-app notifications, preferences | `/api/v1/notifications` |
| `org_setup` | Org setup wizard (groups, entities, ownership) | `/api/v1/org-setup` |
| `partner_program` | Partner profiles, referrals, commissions | `/api/v1/partner` |
| `ppa` | Purchase price allocation | `/api/v1/ppa` |
| `prepaid_expenses` | Prepaid schedules (module layer) | `/api/v1/prepaid-expenses` |
| `scenario_modelling` | Scenario definitions, sets, results | `/api/v1/scenarios` |
| `scheduled_delivery` | Scheduled report delivery | `/api/v1/scheduled-delivery` |
| `search` | Full-text search index | `/api/v1/search` |
| `secret_rotation` | Secret rotation logs | `/api/v1/secrets` |
| `service_registry` | Module + task registry | `/api/v1/services` |
| `statutory` | Statutory filings, registers | `/api/v1/statutory` |
| `tax_provision` | Tax provision runs, positions | `/api/v1/tax` |
| `template_onboarding` | Template-based onboarding flow | `/api/v1/onboarding` |
| `transfer_pricing` | Transfer pricing docs, IC transactions | `/api/v1/transfer-pricing` |
| `white_label` | White-label config per tenant | `/api/v1/white-label` |
| `working_capital` | Working capital module layer | `/api/v1/working-capital` |

### 3.11 Platform Control Plane

Located in `backend/financeops/platform/`:

- **RBAC:** Roles (CpRole), permissions (CpPermission), role-permission maps, user-role assignments
- **Quota:** Quota policies, tenant quota assignments, usage events, quota windows
- **Tenant isolation:** Isolation policies, migration events, module enablements, package assignments
- **Workflow approvals:** Workflow templates, template stages/versions, workflow instances, stage instances, stage events, approvals
- **Org hierarchy:** Organisations (CpOrganisation), entity groups (CpGroup), entities (CpEntity), user-entity assignments, user-org assignments
- **Feature flags:** CpModuleFeatureFlag for per-tenant canary / gradual rollout
- **Service tokens:** Cryptographic context tokens for control-plane enforcement on finance routes

---

## 4. DATABASE

### 4.1 Schema Overview

The database uses PostgreSQL 16 with pgvector extension. All tables follow one of three base patterns:

| Base Class | Purpose | Required Columns |
|---|---|---|
| `Base` | Raw SQLAlchemy base | — |
| `UUIDBase` | Non-financial tables | `id` (UUID PK), `created_at` (TIMESTAMPTZ) |
| `FinancialBase` | All financial tables | `id`, `tenant_id`, `chain_hash`, `previous_hash`, `created_at` |

**Naming convention:** snake_case table names. Tenant isolation via `tenant_id` column on every table + PostgreSQL RLS.

**Financial table invariant:** INSERT ONLY. No UPDATE or DELETE permitted. New versions are new rows with the previous row's `chain_hash` as `previous_hash`.

### 4.2 Complete Table Definitions (by model file)

**Core IAM** (`db/models/tenants.py`, `db/models/users.py`):
- `iam_tenants` — tenant registry (id, tenant_id, display_name, tenant_type, country, timezone, status, slug, org_setup_complete, org_setup_step, chain_hash, previous_hash)
- `iam_users` — user accounts (id, tenant_id, email, hashed_password, full_name, role, is_active, mfa_enabled, mfa_secret_encrypted, force_password_change, requires_mfa_setup, last_login_at, terms_accepted_at, terms_version)
- `iam_sessions` — active sessions (id, user_id, tenant_id, refresh_token_hash, revoked_at, expires_at)

**Auth Tokens** (`db/models/auth_tokens.py`):
- `mfa_recovery_codes` — TOTP recovery codes (id, user_id, tenant_id, code_hash, used_at)
- `password_reset_tokens` — password reset tokens (id, user_id, tenant_id, token_hash, expires_at, used_at)

**Credits** (`db/models/credits.py`):
- `credit_balances` — per-tenant credit balances (FinancialBase)
- `credit_transactions` — credit transaction ledger (FinancialBase)
- `credit_reservations` — in-flight credit reservations (FinancialBase)

**Audit** (`db/models/audit.py`):
- `audit_trail` — immutable audit log (FinancialBase + action, entity_type, entity_id, actor_id, details)

**AI Prompts** (`db/models/prompts.py`):
- `ai_prompt_versions` — prompt version registry with chain hash

**AI Cost** (`db/models/ai_cost.py`):
- `ai_cost_events` — per-request AI cost tracking (tokens, cost_usd, model, provider)
- `tenant_token_budgets` — per-tenant token/cost budget configuration

**Payments** (`db/models/payment.py`):
- `billing_plans`, `tenant_subscriptions`, `billing_invoices`, `payment_methods`
- `credit_ledger`, `credit_top_ups`, `grace_period_logs`, `proration_records`
- `subscription_events`, `webhook_events`

**Reconciliation** (`db/models/reconciliation.py`):
- `gl_entries`, `trial_balance_rows`, `recon_items`

**Bank Reconciliation** (`db/models/bank_recon.py`):
- `bank_statements`, `bank_transactions`, `bank_recon_items`

**GST** (`db/models/gst.py`):
- `gst_returns`, `gst_recon_items`

**MIS** (`db/models/mis_manager.py`):
- `mis_templates`, `mis_uploads` (with MisTemplateVersion supersession chain)

**Month-End** (`db/models/monthend.py`):
- `monthend_checklists` (FinancialBase — insert-only close), `monthend_tasks` (UUIDBase — mutable)

**Auditor** (`db/models/auditor.py`):
- `auditor_grants`, `auditor_access_logs`

**Working Capital** (`db/models/working_capital.py`):
- `working_capital_snapshots` (Phase 0 model)

**FX Rates** (`db/models/fx_rates.py`):
- `fx_rate_quotes`, `fx_manual_monthly_rates`, `fx_variance_results`, `fx_rate_fetch_runs`

**Consolidation** (`db/models/consolidation.py`):
- `consolidation_runs`, `consolidation_entities`, `consolidation_line_items`
- `consolidation_results`, `consolidation_eliminations`, `consolidation_run_events`
- `intercompany_pairs`, `normalized_financial_snapshots`, `normalized_financial_snapshot_lines`

**Revenue** (`db/models/revenue.py`):
- `revenue_contracts`, `revenue_performance_obligations`, `revenue_contract_line_items`
- `revenue_schedules`, `revenue_journal_entries`, `revenue_runs`, `revenue_run_events`, `revenue_adjustments`

**Lease** (`db/models/lease.py`):
- `leases`, `lease_modifications`, `lease_payments`, `lease_liability_schedules`
- `lease_rou_schedules`, `lease_journal_entries`, `lease_runs`, `lease_run_events`

**Prepaid** (`db/models/prepaid.py`):
- `prepaids`, `prepaid_amortization_schedules`, `prepaid_journal_entries`
- `prepaid_runs`, `prepaid_run_events`, `prepaid_adjustments`

**Fixed Assets** (`db/models/fixed_assets.py`):
- `assets`, `asset_depreciation_schedules`, `asset_disposals`, `asset_impairments`
- `asset_journal_entries`, `far_runs`, `far_run_events`

**Multi-Entity Consolidation** (`db/models/multi_entity_consolidation.py`):
- `entity_hierarchies`, `entity_hierarchy_nodes`, `consolidation_scopes_me`
- `consolidation_rule_definitions`, `intercompany_mapping_rules`, `consolidation_adjustment_definitions`
- `multi_entity_consolidation_runs`, various result/evidence tables

**FX Translation** (`db/models/fx_translation_reporting.py`):
- `reporting_currency_definitions`, `fx_translation_rule_definitions`, `fx_rate_selection_policies`
- `fx_translation_runs`, `fx_translated_metric_results`, `fx_translated_variance_results`, `fx_translation_evidence_links`

**Ownership Consolidation** (`db/models/ownership_consolidation.py`):
- `ownership_structure_definitions`, `ownership_relationships`, `minority_interest_rule_definitions`
- `ownership_consolidation_runs`, result/evidence tables

**Cash Flow Engine** (`db/models/cash_flow_engine.py`):
- `cash_flow_statement_definitions`, `cash_flow_line_mappings`, `cash_flow_bridge_rule_definitions`
- `cash_flow_runs`, `cash_flow_line_results`, `cash_flow_evidence_links`

**Equity Engine** (`db/models/equity_engine.py`):
- `equity_statement_definitions`, `equity_line_definitions`, `equity_rollforward_rule_definitions`
- `equity_source_mappings`, `equity_runs`, `equity_line_results`, `equity_statement_results`, `equity_evidence_links`

**Observability Engine** (`db/models/observability_engine.py`):
- `observability_run_registries`, `observability_runs`, `observability_results`
- `governance_events`, `lineage_graph_snapshots`, `run_performance_metrics`
- `run_token_diff_definitions`, `run_token_diff_results`, `observability_evidence_links`

**Financial Risk Engine** (`db/models/financial_risk_engine.py`):
- `risk_definitions`, `risk_definition_dependencies`, `risk_runs`, `risk_results`
- `risk_materiality_rules`, `risk_weight_configurations`, `risk_rollforward_events`
- `risk_contributing_signals`, `risk_evidence_links`

**Anomaly Pattern Engine** (`db/models/anomaly_pattern_engine.py`):
- `anomaly_definitions`, `anomaly_runs`, `anomaly_results`
- `anomaly_pattern_rules`, `anomaly_statistical_rules`, `anomaly_correlation_rules`
- `anomaly_persistence_rules`, `anomaly_rollforward_events`, `anomaly_contributing_signals`, `anomaly_evidence_links`

**Ratio Variance Engine** (`db/models/ratio_variance_engine.py`):
- `metric_definitions`, `metric_definition_components`, `metric_runs`, `metric_results`
- `variance_definitions`, `variance_results`, `trend_definitions`, `trend_results`
- `materiality_rules`, `metric_evidence_links`

**Payroll GL Normalization** (`db/models/payroll_gl_normalization.py`):
- `normalization_sources`, `normalization_source_versions`, `normalization_runs`, `normalization_mappings`
- `gl_normalized_lines`, `payroll_normalized_lines`, `normalization_exceptions`, `normalization_evidence_links`

**Payroll GL Reconciliation** (`db/models/payroll_gl_reconciliation.py`):
- `payroll_gl_reconciliation_rules`, `payroll_gl_reconciliation_mappings`
- `payroll_gl_reconciliation_runs`, `payroll_gl_reconciliation_run_scopes`

**Board Pack Narrative Engine** (`db/models/board_pack_narrative_engine.py`):
- Board pack definitions, runs, narrative results (with supersession chain)

**ERP Sync** (`db/models/erp_sync.py`):
- `external_connections`, `external_connection_versions`, `external_sync_definitions`
- `external_sync_definition_versions`, `external_raw_snapshots`, `external_normalized_snapshots`
- `external_mapping_definitions`, `external_mapping_versions`, `external_period_locks`
- `external_sync_runs`, `external_sync_errors`, `external_sync_evidence_links`
- `external_sync_health_alerts`, `external_sync_sla_configs`, `external_sync_drift_reports`
- `external_data_consent_logs`, `external_backdated_modification_alerts`, `external_sync_publish_events`
- `external_connector_capability_registry`, `external_connector_version_registry`

**Accounting Layer** (`db/models/accounting_*.py`):
- `accounting_jv_heads`, `accounting_jv_lines` — journal entry aggregates
- `accounting_jv_state_machine_events` — JV lifecycle events
- `accounting_approvals`, `accounting_approval_sla_configs` — approval workflows
- `accounting_vendor_profiles`, `accounting_vendor_attachments` — vendor management
- `accounting_duplicate_fingerprints` — duplicate detection
- `accounting_governance_events` — period close governance
- `accounting_notifications` — in-app notifications for accounting
- `accounting_tax_rules` (GST + TDS)

**Analytics / AI CFO** (`db/models/analytics_layer.py`, `db/models/ai_cfo_layer.py`):
- Analytics configuration, AI CFO configuration tables

**Industry Modules** (`db/models/industry_modules.py`):
- Industry module configuration tables

**Platform Control Plane** (`platform/db/models/`):
- `cp_roles`, `cp_permissions`, `cp_role_permissions`, `cp_user_role_assignments`
- `cp_quota_policies`, `cp_tenant_quota_assignments`, `cp_tenant_quota_usage_events`, `cp_tenant_quota_windows`
- `cp_tenants`, `cp_tenant_isolation_policies`, `cp_tenant_migration_events`
- `cp_module_registry`, `cp_tenant_module_enablements`, `cp_module_feature_flags`
- `cp_packages`, `cp_tenant_package_assignments`
- `cp_organisations`, `cp_groups`, `cp_entities`
- `cp_user_entity_assignments`, `cp_user_organisation_assignments`
- `cp_workflow_templates`, `cp_workflow_template_versions`, `cp_workflow_template_stages`
- `cp_workflow_instances`, `cp_workflow_instance_events`, `cp_workflow_stage_instances`
- `cp_workflow_stage_events`, `cp_workflow_approvals`, `cp_workflow_stage_role_maps`, `cp_workflow_stage_user_maps`

**Reconciliation Bridge** (`db/models/reconciliation_bridge.py`):
- `reconciliation_sessions`, `reconciliation_scopes`, `reconciliation_lines`
- `reconciliation_exceptions`, `reconciliation_resolution_events`, `reconciliation_evidence_links`

**Module tables** (from `modules/*/models.py`):
- `checklist_templates`, `checklist_template_tasks`, `checklist_runs`, `checklist_run_tasks` (closing_checklist)
- `wc_snapshots`, `ap_line_items`, `ar_line_items` (working_capital module)
- `expense_policies`, `expense_claims`, `expense_approvals` (expense_management)
- `budget_versions`, `budget_line_items` (budgeting)
- `forecast_runs`, `forecast_line_items`, `forecast_assumptions` (forecasting)
- `scenario_sets`, `scenario_definitions`, `scenario_line_items`, `scenario_results` (scenario_modelling)
- `backup_run_logs` (backup)
- `fdd_engagements`, `fdd_sections`, `fdd_findings` (fdd)
- `ppa_engagements`, `ppa_intangibles`, `ppa_allocations` (ppa)
- `ma_workspaces`, `ma_workspace_members`, `ma_documents`, `ma_dd_items`, `ma_valuations` (ma_workspace)
- `module_registry`, `task_registry` (service_registry)
- `marketplace_templates`, `marketplace_contributors`, `marketplace_purchases`, `marketplace_ratings`, `marketplace_payouts` (marketplace)
- `white_label_configs`, `white_label_audit_logs` (white_label)
- `partner_profiles`, `referral_tracking`, `partner_commissions` (partner_program)
- `notification_events`, `notification_preferences`, `notification_read_states` (notifications)
- `ai_benchmark_results`, `learning_signals`, `learning_corrections` (learning_engine)
- `search_index_entries` (search)
- `cash_flow_forecast_runs`, `cash_flow_forecast_assumptions` (cash_flow_forecast)
- `tax_provision_runs`, `tax_positions` (tax_provision)
- `covenant_definitions`, `covenant_breach_events` (debt_covenants)
- `tp_configs`, `ic_transactions`, `transfer_pricing_docs` (transfer_pricing)
- `director_signoffs` (digital_signoff)
- `statutory_filings`, `statutory_register_entries` (statutory)
- `multi_gaap_configs`, `multi_gaap_runs` (multi_gaap)
- `auditor_portal_accesses`, `auditor_requests` (auditor_portal)
- `coa_industry_templates`, `coa_account_groups`, `coa_account_subgroups`, `coa_ledger_accounts` and many more CoA tables
- `org_groups`, `org_entities`, `org_ownerships`, `org_setup_progress`, `org_entity_erp_configs` (org_setup)
- `fa_asset_classes`, `fa_assets`, `fa_depreciation_runs`, `fa_impairments`, `fa_revaluations` (fixed_assets module)
- `prepaid_schedules`, `prepaid_amortisation_entries` (prepaid_expenses module)
- `classification_rules`, `invoice_classifications` (invoice_classifier)
- `cp_locations`, `cp_cost_centres` (locations)
- `compliance_controls`, `compliance_events`, `user_pii_keys`, `erasure_logs` (compliance)
- `gdpr_consent_records`, `gdpr_data_requests`, `gdpr_breach_records` (compliance.gdpr_models)
- `pipeline_runs`, `pipeline_step_logs` (auto_trigger)
- `secret_rotation_logs` (secret_rotation)
- `onboarding_states` (template_onboarding)
- `scheduled_delivery_configs` and related (scheduled_delivery)

### 4.3 Migration History

All 120 migrations in `backend/migrations/versions/`:

| # | File | Description |
|---|---|---|
| 0001 | 0001_initial_schema.py | IAM, credits, audit, AI prompts, RLS, seed prompts |
| 0002 | 0002_phase1_core_finance.py | Bank recon, GST, MIS, monthend, working capital, auditor, GL/TB recon |
| 0003 | 0003_phase1a_arch_controls.py | Reconciliation bridge, normalization, payroll GL recon, ratio variance, financial risk, anomaly pattern, board pack narrative |
| 0004 | 0004_phase1b_fx_rate_engine.py | FX rate quotes, manual monthly rates, variance, fetch runs |
| 0005 | 0005_phase1c_multi_currency_consolidation.py | Multi-currency consolidation runs + entities |
| 0006 | 0006_phase1d2_revenue_core.py | Revenue recognition (contracts, obligations, schedules, JEs) |
| 0007 | 0007_phase1d3_lease_core.py | Lease accounting (IFRS 16 / ASC 842) |
| 0008 | 0008_phase1e_platform_control_plane.py | Platform control plane (RBAC, quota, isolation, workflow) |
| 0009 | 0009_phase1d4_prepaid_core.py | Prepaid amortization |
| 0010 | 0010_phase1d5_fixed_assets_core.py | Fixed assets register |
| 0011 | 0011_phase1d6_remeasurement_harmonization.py | Remeasurement harmonization |
| 0012 | 0012_phase1f1_mis_manager.py | MIS manager (Phase 1f1 with supersession) |
| 0013 | 0013_phase1f2_reconciliation_bridge.py | Reconciliation bridge (Phase 1f2) |
| 0014 | 0014_phase1f3_payroll_gl_normalization.py | Payroll GL normalization (Phase 1f3) |
| 0015 | 0015_phase1f3_1_payroll_gl_reconciliation.py | Payroll GL reconciliation (Phase 1f3.1) |
| 0016 | 0016_phase1f4_ratio_variance.py | Ratio variance engine (Phase 1f4) |
| 0017 | 0017_phase1f5_financial_risk.py | Financial risk engine (Phase 1f5) |
| 0018 | 0018_phase1f6_anomaly_pattern.py | Anomaly pattern engine (Phase 1f6) |
| 0019 | 0019_phase1f7_board_pack_narrative.py | Board pack narrative engine (Phase 1f7) |
| 0020 | 0020_phase2_3_multi_entity_consolidation.py | Multi-entity consolidation (Phase 2.3) |
| 0021 | 0021_phase2_4_fx_translation_reporting.py | FX translation reporting (Phase 2.4) |
| 0022 | 0022_phase2_5_ownership_consolidation.py | Ownership consolidation (Phase 2.5) |
| 0023 | 0023_phase2_6_cash_flow_engine.py | Cash flow engine (Phase 2.6) |
| 0024 | 0024_phase2_7_equity_engine.py | Equity engine (Phase 2.7) |
| 0025 | 0025_phase3_observability_engine.py | Observability engine (Phase 3) |
| 0026 | 0026_phase4_erp_sync.py | ERP sync kernel (Phase 4) |
| 0027 | 0027_payment_module.py | Payment / billing module |
| 0028 | 0028_board_pack_generator.py | Board pack generator module |
| 0029 | 0029_custom_report_builder.py | Custom report builder |
| 0030 | 0030_scheduled_delivery.py | Scheduled delivery |
| 0031 | 0031_anomaly_ui_layer.py | Anomaly UI layer |
| 0032 | 0032_auto_trigger_pipeline.py | Auto-trigger pipeline |
| 0033 | 0033_template_onboarding.py | Template onboarding |
| 0034 | 0034_secret_rotation.py | Secret rotation |
| 0035 | 0035_fix_float_columns.py | Float → Numeric column migration |
| 0036 | 0036_encrypt_existing_secrets.py | Encrypt existing secrets at rest |
| 0037 | 0037_gdpr_erasure.py | GDPR erasure log |
| 0038 | 0038_ai_cost_ledger.py | AI cost ledger |
| 0039 | 0039_closing_checklist.py | Closing checklist module |
| 0040 | 0040_working_capital.py | Working capital module |
| 0041 | 0041_expense_management.py | Expense management |
| 0042 | 0042_budgeting.py | Budgeting module |
| 0043 | 0043_forecasting.py | Forecasting module |
| 0044 | 0044_scenario_modelling.py | Scenario modelling |
| 0045 | 0045_compliance_controls.py | Compliance controls (SOC2, ISO27001) |
| 0046 | 0046_gdpr_operational.py | GDPR operational controls |
| 0047 | 0047_backup_dr.py | Backup and DR |
| 0048 | 0048_platform_bootstrap.py | Platform bootstrap seed |
| 0049 | 0049_fdd.py | Financial due diligence |
| 0050 | 0050_ppa.py | Purchase price allocation |
| 0051 | 0051_ma_workspace.py | M&A workspace |
| 0052 | 0052_service_registry.py | Service registry |
| 0053 | 0053_marketplace.py | Template marketplace |
| 0054 | 0054_white_label.py | White-label configuration |
| 0055 | 0055_partner_program.py | Partner program |
| 0056 | 0056_notifications.py | Notifications system |
| 0057 | 0057_learning_engine.py | AI learning engine |
| 0058 | 0058_search_index.py | Search index |
| 0059 | 0059_cash_flow_forecast.py | Cash flow forecast |
| 0060 | 0060_tax_provision.py | Tax provision |
| 0061 | 0061_debt_covenants.py | Debt covenants |
| 0062 | 0062_transfer_pricing.py | Transfer pricing |
| 0063 | 0063_director_signoff.py | Director signoff |
| 0064 | 0064_statutory_registers.py | Statutory filings + registers |
| 0065 | 0065_multi_gaap.py | Multi-GAAP |
| 0066 | 0066_auditor_portal.py | Auditor portal |
| 0067 | 0067_add_director_role.py | Add director role enum value |
| 0068 | 0068_entity_isolation.py | Entity-level isolation |
| 0069 | 0069_mfa_recovery_codes.py | MFA recovery codes |
| 0070 | 0070_password_reset_tokens.py | Password reset tokens |
| 0071 | 0071_tenant_slug.py | Tenant slug column |
| 0072 | 0072_terms_acceptance.py | Terms acceptance tracking |
| 0073 | 0073_user_invite_tokens.py | User invite tokens |
| 0074 | 0074_display_scale_preferences.py | Display scale preferences |
| 0075 | 0075_coa_framework.py | Chart of accounts framework |
| 0076 | 0076_org_setup.py | Org setup wizard tables |
| 0077 | 0077_fixed_assets.py | Fixed assets module tables |
| 0078 | 0078_prepaid_expenses.py | Prepaid expenses module tables |
| 0079 | 0079_invoice_classifier.py | Invoice classifier tables |
| 0080 | 0080_locations_and_enrichment.py | Locations and cost centres |
| 0081 | 0081_entity_id_backfill.py | Entity ID backfill |
| 0082 | 0082_location_cost_centre_fks.py | Location/cost centre FK cleanup |
| 0083 | 0083_entity_id_accounting_blockers.py | Entity ID accounting blockers |
| 0084 | 0084_erp_oauth_sessions_and_connection_hardening.py | ERP OAuth sessions |
| 0085 | 0085_accounting_jv_aggregate_core.py | Accounting JV aggregate core |
| 0086 | 0086_accounting_jv_state_machine_events.py | JV state machine events |
| 0087 | 0087_accounting_approval_and_sla.py | Accounting approval + SLA |
| 0088 | 0088_accounting_vendor_and_attachment.py | Vendor management + attachments |
| 0089 | 0089_accounting_duplicate_fingerprints.py | Duplicate detection fingerprints |
| 0090 | 0090_entity_id_category1_remaining.py | Entity ID category 1 remaining |
| 0091 | 0091_coa_crosswalk_external_ref.py | CoA crosswalk + external refs |
| 0092 | 0092_erp_push_runs_events_idempotency.py | ERP push runs, events, idempotency |
| 0093 | 0093_accounting_tax_gst_tds_rules.py | GST/TDS tax rules |
| 0094 | 0094_entity_id_category2_analytics.py | Entity ID category 2 (analytics) |
| 0095 | 0095_entity_id_category2_consolidation.py | Entity ID category 2 (consolidation) |
| 0096 | 0096_entity_id_category2_ops.py | Entity ID category 2 (ops) |
| 0097 | 0097_erp_webhook_event_ingest.py | ERP webhook event ingest |
| 0098 | 0098_inbound_email_vendor_portal.py | Inbound email vendor portal |
| 0099 | 0099_notifications_reminder_workflow.py | Notifications reminder workflow |
| 0100 | 0100_ap_ageing_audit_export.py | AP ageing + audit export |
| 0101 | 0101_accounting_rbac_seed_final.py | Accounting RBAC seed |
| 0102 | 0102_coa_upload_management.py | CoA upload management |
| 0103 | 0103_fx_multi_currency_ias21.py | FX multi-currency IAS 21 |
| 0104 | 0104_period_close_governance_control.py | Period close governance |
| 0105 | 0105_erp_integration_layer.py | ERP integration layer |
| 0106 | 0106_analytics_cfo_dashboard_layer.py | Analytics CFO dashboard layer |
| 0107 | 0107_ai_cfo_layer.py | AI CFO layer |
| 0108 | 0108_industry_modules_layer.py | Industry modules layer |
| 0109 | 0109_saas_platformization_layer.py | SaaS platformization layer |
| 0110 | 0110_allow_anomaly_statistical_rule_updates.py | Allow anomaly statistical rule updates |
| 0111 | 0111_allow_board_pack_definition_updates.py | Allow board pack definition updates |
| 0112 | 0112_board_pack_runs_schema_compat.py | Board pack runs schema compat |
| 0113 | 0113_allow_checklist_run_updates.py | Allow checklist run updates |
| 0114 | 0114_allow_expense_claim_updates.py | Allow expense claim updates |
| 0115 | 0115_allow_forecast_run_updates.py | Allow forecast run updates |
| 0116 | 0116_allow_invoice_classification_updates.py | Allow invoice classification updates |
| 0117 | 0117_allow_cp_entities_updates.py | Allow CP entities updates |
| 0118 | 0118_allow_ppa_allocation_updates.py | Allow PPA allocation updates |
| 0119 | 0119_password_change_verified_flags.py | Password change verified flags |
| 0120 | 0120_normalize_iam_user_emails.py | Normalize IAM user email addresses |

### 4.4 Seed Data

- **CoA Industry Templates** (`seed/coa.py`) — seeded on every startup if migration state is OK
- **Platform Users** (`seed/platform_owner.py`) — seeded only when `SEED_ON_STARTUP=true`, reads `PLATFORM_OWNER_EMAIL`, `PLATFORM_OWNER_PASSWORD`, `PLATFORM_OWNER_NAME`, `PLATFORM_ADMIN_EMAIL`, `PLATFORM_ADMIN_PASSWORD`, `PLATFORM_ADMIN_NAME` from environment
- **Accounting RBAC** (migration 0101) — seeded via migration
- **AI Prompt Versions** (migration 0001) — seeded via migration

### 4.5 Conventions

- All UUIDs use PostgreSQL native UUID type (asyncpg-compatible)
- All timestamps are TIMESTAMPTZ (timezone-aware)
- All financial amounts use NUMERIC (never FLOAT) — migration 0035 retroactively fixed any float columns
- Chain hash: `SHA256(canonical_json(record_data) + previous_hash)` — GENESIS_HASH = "0" * 64
- RLS context: `set_config('app.current_tenant_id', tenant_id, true)` per transaction
- pgvector extension required (for AI embedding storage)

---

## 5. AUTHENTICATION & SECURITY

### 5.1 Auth Flow

**Standard Login:**
1. Frontend POST `/api/v1/auth/login` with `{email, password}`
2. Backend verifies bcrypt hash (SHA-256 pre-hashed → bcrypt)
3. If `mfa_enabled=True`: returns `{requires_mfa: true, mfa_challenge_token: "<JWT>"}`
4. Frontend redirects to `/mfa` with `mfa_challenge_token` in URL params
5. User enters TOTP code; frontend POST `/api/v1/auth/mfa/verify` with `{mfa_challenge_token, totp_code}`
6. Backend verifies TOTP (1-step drift tolerance); returns `{access_token, refresh_token}`
7. Frontend NextAuth `authorize()` calls `/api/v1/auth/me` with access_token
8. NextAuth stores session JWT with `{access_token, refresh_token, access_token_expires_at, tenant_id, role, etc.}`

**Token Refresh:**
- Access token valid 15 minutes (configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`)
- Refresh token valid 7 days (configurable via `JWT_REFRESH_TOKEN_EXPIRE_DAYS`)
- NextAuth JWT callback checks `access_token_expires_at`; on expiry automatically calls `/api/v1/auth/refresh`
- Refresh failure sets `error: "RefreshAccessTokenError"` in token; frontend must re-login

**Password Change Required:**
1. Backend login returns `{requires_password_change: true}`
2. Frontend NextAuth throws `PasswordChangeRequiredError`
3. NextAuth redirects to `/auth/change-password`
4. User sets new password; backend clears `force_password_change` flag

**MFA Setup Required:**
1. Backend login returns `{requires_mfa_setup: true}`
2. Frontend NextAuth throws `MFASetupRequiredError`
3. NextAuth redirects to `/mfa/setup`
4. User scans QR code (otpauth:// URI) and verifies TOTP; backend enables MFA

**Registration:**
1. POST `/api/v1/auth/register` with `{email, password, full_name, tenant_name, tenant_type, country}`
2. Creates tenant + user + default workspace + initial credits
3. Sends welcome email
4. Returns access + refresh tokens

**Token Handoff (MFA/Password-change):**
- `auth-handoff.ts` stores temporary tokens in `sessionStorage` for cross-page handoff

### 5.2 Roles & Permissions

| Role | Level | Access |
|---|---|---|
| `super_admin` | Platform | All access, bypasses all guards |
| `platform_owner` | Platform | Platform admin + all tenant management |
| `platform_admin` | Platform | Tenant management, user management, module config |
| `platform_support` | Platform | Read-only platform support access |
| `finance_leader` | Tenant | Full access to all financial modules |
| `finance_team` | Tenant | Finance operations, limited admin |
| `director` | Tenant | Board pack, signoff, read-only financial |
| `entity_user` | Entity | Entity-scoped finance access |
| `auditor` | Tenant | Read-only audit access via auditor grant |
| `hr_manager` | Tenant | Payroll GL, expense management |
| `employee` | Tenant | Expense submission, limited self-service |
| `read_only` | Tenant | Read-only across all modules |

Frontend route guards:
- `/admin/*` — requires `platform_owner`, `platform_admin`, `super_admin`, or `admin`
- `/trust/*` — requires `finance_leader` only

### 5.3 Multi-Tenancy

- Every DB table has `tenant_id` (UUID) column
- PostgreSQL RLS policies enforce tenant isolation at DB level
- `set_tenant_context(session, tenant_id)` sets `app.current_tenant_id` via `set_config()` in each transaction
- `RLSMiddleware` extracts `tenant_id` from JWT and sets it on `request.state`
- Control plane enforcement: finance routes require a cryptographic `X-Control-Plane-Token` header (issued by platform service)
- Sub-tenant isolation: `CpEntity` table + `entity_id` on relevant tables for entity-level data segregation

### 5.4 Security Measures

- **Password hashing:** bcrypt with SHA-256 pre-hash (avoids 72-byte bcrypt limit)
- **JWT:** HS256, validated on every request via `get_current_user` dependency
- **Field encryption:** AES-256-GCM for TOTP secrets, ERP connection credentials
- **CSRF:** starlette-csrf (cookie + header token validation; exempt for API routes)
- **Rate limiting:** slowapi (IP + tenant composite key) — 5/min login, 5/min token, 3/min MFA, 20/min AI stream
- **CORS:** Configurable via `CORS_ALLOWED_ORIGINS`; wildcard blocked in production
- **Input validation:** Pydantic v2 on all request models; email normalization on user create/update
- **Prompt injection:** `PromptInjectionError` exception class
- **GDPR:** Erasure log, consent records, data request workflow
- **Audit trail:** Immutable `audit_trail` table with chain hash on every state-changing action
- **Chain integrity:** SHA-256 chain hashes on all financial tables — tamper detection
- **ClamAV:** Stubbed (phase 6); `CLAMAV_REQUIRED=True` in Dockerfile
- **Security headers (frontend):** X-Content-Type-Options, X-Frame-Options, HSTS, CSP, Referrer-Policy, Permissions-Policy (set by both Next.js middleware and next.config.mjs)
- **SAST:** Semgrep rules (`.semgrep.yml`) + CI `sast.yml` workflow

---

## 6. INFRASTRUCTURE & DEPLOYMENT

### 6.1 Local Dev Setup

**Prerequisites:** Python 3.11, Node 20, Docker Desktop

**Backend:**
```bash
cd /d/finos/backend
py -3.11 -m venv .venv           # Windows
source .venv/bin/activate         # Unix / .venv\Scripts\activate on Windows
pip install -e ".[dev]"
cp ../.env.example ../.env
# Edit .env with your DB/Redis credentials

# Start infrastructure
cd /d/finos/infra
docker-compose up -d db redis     # Minimal: just DB + Redis

# Run migrations
cd /d/finos/backend
alembic upgrade head

# Seed platform users (optional)
SEED_ON_STARTUP=true python -m financeops.seed.platform_owner

# Start API
uvicorn financeops.main:app --reload --port 8000
```

**Frontend:**
```bash
cd /d/finos/frontend
npm install
# Copy and configure environment:
cp ../.env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
# Set NEXTAUTH_URL=http://localhost:3000
# Set NEXTAUTH_SECRET=<random>
npm run dev
```

**Full stack (Docker Compose):**
```bash
cd /d/finos/infra
docker-compose up    # Starts: db, redis, clamav, temporal, temporal_ui, api, temporal_worker, celery_worker, celery_beat, flower
```
- API: http://localhost:8000
- Frontend: http://localhost:3000
- Flower: http://localhost:5555
- Temporal UI: http://localhost:8088
- API docs: http://localhost:8000/docs

### 6.2 Production Deployment

**Backend (Render.com):**
- Service: `financeops-backend` (web service, Docker, Singapore region)
- Worker: `financeops-worker` (Celery worker)
- Beat: `financeops-beat` (Celery beat scheduler)
- Health check: `GET /ready`
- Entrypoint: `scripts/entrypoint.sh` (runs `alembic upgrade head` then starts uvicorn)
- Dockerfile: `backend/Dockerfile` (python:3.11-slim, runs as non-root `financeops` user, exposes port 10000)

**Frontend (Vercel):**
- Framework: Next.js (auto-detected)
- Install: `npm install`
- Build: `npm run build`
- Output: `.next`
- Sentry integration conditional on `SENTRY_DSN`

**Database:** PostgreSQL 16 + pgvector (Supabase recommended)
**Redis:** Managed Redis (Render Redis, Upstash, or similar)

### 6.3 Environment Variables

**Required for production:**

| Variable | Description | Notes |
|---|---|---|
| `APP_ENV` | Environment name | Must be `production` on Render |
| `SECRET_KEY` | Session signing key | Min 32 chars |
| `JWT_SECRET` | JWT signing secret | Min 32 chars |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://...` |
| `FIELD_ENCRYPTION_KEY` | AES-256 key (32 bytes, URL-safe base64) | Generate: `python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"` |
| `NEXTAUTH_URL` | Frontend URL | e.g. `https://app.financeops.io` |
| `NEXTAUTH_SECRET` | NextAuth session secret | Min 32 chars |
| `NEXT_PUBLIC_API_URL` | Backend API URL | e.g. `https://api.financeops.io` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins | Must match frontend URL |

**Optional integrations:**

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic Claude API |
| `OPENAI_API_KEY` | OpenAI API |
| `GEMINI_API_KEY` | Google Gemini API |
| `OLLAMA_BASE_URL` | Ollama local models |
| `R2_ENDPOINT_URL` | Cloudflare R2 endpoint |
| `R2_ACCESS_KEY_ID` | Cloudflare R2 access key |
| `R2_SECRET_ACCESS_KEY` | Cloudflare R2 secret |
| `R2_BUCKET_NAME` | Cloudflare R2 bucket |
| `SENTRY_DSN` | Sentry error tracking |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry collector |
| `STRIPE_SECRET_KEY` | Stripe payments |
| `RAZORPAY_KEY_ID` | Razorpay payments |
| `RAZORPAY_KEY_SECRET` | Razorpay secret |
| `RAZORPAY_WEBHOOK_SECRET` | Razorpay webhook validation |
| `SMTP_HOST` | Email SMTP host |
| `SMTP_PORT` | Email SMTP port |
| `SMTP_USER` | Email SMTP username |
| `SMTP_PASSWORD` | Email SMTP password |
| `TEMPORAL_ADDRESS` | Temporal.io address |
| `OPEN_EXCHANGE_RATES_API_KEY` | FX rates provider |
| `EXCHANGE_RATE_API_KEY` | FX rates fallback |
| `PLATFORM_OWNER_EMAIL` | Platform owner seed |
| `PLATFORM_OWNER_PASSWORD` | Platform owner seed |
| `PLATFORM_OWNER_NAME` | Platform owner seed |
| `PLATFORM_ADMIN_EMAIL` | Platform admin seed |
| `PLATFORM_ADMIN_PASSWORD` | Platform admin seed |
| `PLATFORM_ADMIN_NAME` | Platform admin seed |

**Feature flags:**

| Variable | Default | Description |
|---|---|---|
| `AUTO_MIGRATE` | false | Run alembic upgrade on startup (non-production only) |
| `MIGRATION_FAIL_FAST` | false | Abort startup on migration mismatch |
| `SEED_ON_STARTUP` | false | Seed platform users on startup |
| `STARTUP_FAIL_FAST` | false | Abort startup on any error |
| `CLAMAV_REQUIRED` | true (Docker) | Require ClamAV for file upload |
| `SMTP_REQUIRED` | false | Require SMTP for email sending |
| `ERP_CONSENT_ENABLED` | false | ERP consent flow |
| `ERP_CONNECTOR_VERSIONING_ENABLED` | false | ERP connector versioning |
| `ERP_CONNECTION_SERVICE_ENABLED` | false | ERP connection service |

### 6.4 Docker Compose (Local)

Services in `infra/docker-compose.yml`:
- `db` — pgvector/pgvector:pg16, port 5432, volume `postgres_data`
- `redis` — redis:7-alpine, port 6379, volume `redis_data`, password-protected, AOF + RDB persistence
- `clamav` — clamav/clamav:stable, volume `clamav_data`
- `temporal_db` — postgres:16-alpine (dedicated for Temporal)
- `temporal` — temporalio/auto-setup:1.25.2, port 7233
- `temporal_ui` — temporalio/ui:2.34.0, port 8088
- `api` — FastAPI app, port 8000, hot-reload volume mount
- `temporal_worker` — Temporal workflow worker
- `celery_worker` — all 4 queues, concurrency 4
- `celery_beat` — scheduled task dispatcher
- `flower` — Celery monitor, port 5555

### 6.5 CI/CD

**GitHub Actions (`.github/workflows/`):**

| Workflow | Trigger | Steps |
|---|---|---|
| `ci.yml` | push main/develop, PR main | backend-tests (pytest), frontend-build (tsc + npm build), alembic-check |
| `dependency_matrix.yml` | scheduled | Generates DEPENDENCY_MATRIX.md |
| `sast.yml` | push | Semgrep SAST scan |
| `schema_check.yml` | push | Schema validation |

**CI test environment:** PostgreSQL 16 + Redis 7 as services, FIELD_ENCRYPTION_KEY and JWT_SECRET from GitHub Secrets.

---

## 7. BACKGROUND JOBS & WORKFLOWS

### 7.1 Celery Tasks

**Broker:** Redis 7
**Result backend:** Redis 7
**Serialization:** JSON

**Queue Priority:**

| Queue | Routing Key | Use Cases |
|---|---|---|
| `critical_q` | `critical` | Payment tasks |
| `high_q` | `high` | Core financeops tasks |
| `normal_q` | `normal` | Module tasks (default) |
| `low_q` | `low` | Search indexing, metrics updates |

**Task imports (modules registering tasks):**
- `financeops.tasks.payment_tasks`
- `financeops.modules.scheduled_delivery.tasks`
- `financeops.modules.erp_push.application.push_task`
- `financeops.modules.erp_push.application.webhook_task`
- `financeops.modules.accounting_ingestion.application.ocr_task`
- `financeops.modules.accounting_layer.application.beat_tasks`
- `financeops.modules.auto_trigger.pipeline`
- `financeops.modules.search.tasks`
- `financeops.modules.ai_cfo_layer.tasks`

**Beat Schedule:**

| Task | Schedule | Description |
|---|---|---|
| `payment.check_trial_conversions` | Daily | Convert expired trials to paid/cancelled |
| `payment.check_grace_periods` | Every 6h | Process grace period expirations |
| `payment.retry_failed_payments` | Daily 06:00 UTC | Retry failed payment attempts |
| `payment.expire_credits` | Daily 23:00 UTC | Expire unused credits |
| `scheduled_delivery.poll_due` | Every 60s | Poll and send due scheduled reports |
| `metrics.update_queue_depths` | Every 30s | Update Prometheus queue depth gauge |
| `metrics.update_active_tenants` | Every 5m | Update active tenants Prometheus gauge |
| `accounting_layer.approval_reminder` | Every 1h | Send approval reminder notifications |
| `accounting_layer.sla_breach_check` | Every 30m | Check for SLA breaches on approvals |
| `accounting_layer.daily_digest` | Daily | Send daily accounting digest |

**Reliability settings:**
- `task_acks_late=True` — acknowledge only on successful completion
- `worker_prefetch_multiplier=1` — one task at a time per worker
- `task_reject_on_worker_lost=True` — requeue on worker crash
- `task_soft_time_limit=300s`, `task_time_limit=600s`
- `task_max_retries=3`, `task_default_retry_delay=60s`
- `result_expires=86400s` (24h)

### 7.2 Temporal Workflows

Used for long-running, stateful financial computation runs:
- FX translation runs
- Consolidation runs
- Fixed asset depreciation runs
- Lease accounting runs
- Prepaid amortization runs
- Revenue recognition runs

**Config:**
- `TEMPORAL_ADDRESS`: `temporal:7233` (default)
- `TEMPORAL_NAMESPACE`: `default`
- `TEMPORAL_TASK_QUEUE`: `financeops-default`
- `TEMPORAL_WORKER_IN_PROCESS`: `False` (separate worker process)

Worker: `python -m financeops.temporal.worker`

### 7.3 Queue Config

Four queues consumed by Celery workers:
```
critical_q  →  payment.*
high_q      →  financeops.tasks.*
normal_q    →  financeops.modules.*.tasks.* (default)
low_q       →  financeops.modules.search.tasks.*, metrics.*
```

---

## 8. EXTERNAL INTEGRATIONS

### 8.1 AI Providers

| Provider | SDK | Key Env Var | Use |
|---|---|---|---|
| Anthropic (Claude) | anthropic==0.34.0 | `ANTHROPIC_API_KEY` | Primary AI provider |
| OpenAI | openai==1.51.0 | `OPENAI_API_KEY` | Fallback + embeddings |
| Google Gemini | (aiohttp) | `GEMINI_API_KEY` | Secondary fallback |
| Ollama | ollama==0.3.3 | `OLLAMA_BASE_URL` | Local model support |

**Fallback chains** per task type defined in `llm/fallback.py`. Circuit breaker in `llm/circuit_breaker.py` skips open circuits. AI cost tracking in `ai_cost_events` table.

### 8.2 ERP Connectors

20+ ERP connectors in `financeops/modules/erp_sync/`:
QuickBooks Online, Xero, SAP, Oracle Fusion, Dynamics 365, NetSuite, Odoo, Tally Prime, Sage, FreshBooks, Wave, Zoho Books, Plaid, Darwinbox, Keka, Razorpay (payroll), Marg, Munim, Busy Accounting, Account Aggregator (India)

All connectors implement the same canonical interface with:
- OAuth session management (stored encrypted)
- Webhook event ingest
- Canonical data normalization
- Drift detection
- Period locking
- SLA monitoring

### 8.3 Payment Gateways

| Provider | SDK | Webhook |
|---|---|---|
| Stripe | stripe==11.6.0 | `/api/v1/billing/stripe/webhook` |
| Razorpay | razorpay==1.4.2 | `/api/v1/billing/razorpay/webhook` |

Both providers support: subscription creation, payment retry, webhook event processing, credit top-up.

### 8.4 Storage

**Cloudflare R2** (S3-compatible) via `boto3==1.35.0`
- File upload, download, presigned URLs
- Airlock pipeline: MIME validation → size check → SHA-256 fingerprint → ClamAV scan
- Required env vars: `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`
- Fallback: reports `not_configured` status in health check when credentials absent

### 8.5 Observability

- **OpenTelemetry:** Auto-instrumentation for FastAPI, SQLAlchemy, Redis, Celery. Export via `OTEL_EXPORTER_OTLP_ENDPOINT`
- **Sentry:** Error tracking via `sentry-sdk[fastapi]`. Configured via `SENTRY_DSN`
- **Prometheus:** `/metrics` endpoint via `prometheus_client`. Business metrics: auth failures, upload validation failures, active tenants gauge, task queue depth gauge
- **Structured logging:** python-json-logger with correlation IDs propagated across HTTP requests and Celery tasks

### 8.6 Email

SMTP via built-in Python `aiosmtplib` / `smtplib`:
- Welcome email on registration
- Password reset emails
- MFA setup notifications
- Scheduled report delivery

Configured via: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
Gracefully degrades if `SMTP_REQUIRED=false` (default).

### 8.7 FX Rate Providers

- Open Exchange Rates (`OPEN_EXCHANGE_RATES_API_KEY`)
- Exchange Rate API (`EXCHANGE_RATE_API_KEY`)
- Manual rate entry as fallback

---

## 9. TESTING

### 9.1 Coverage

**Total test files:** ~250+ across unit, integration, and prompt engine suites

**Test categories:**
- **Unit tests** (`tests/unit/`) — service layer, domain logic, engine calculations (no DB)
- **Integration tests** (`tests/integration/`) — API endpoint tests with real DB (PostgreSQL) and real Redis
- **Prompt engine tests** (`tests/prompt_engine/`) — AI prompt governance, dependency gate, execution pipeline

**Test patterns for every finance module:**
1. `test_*_api_*.py` — HTTP endpoint tests (CRUD, happy path)
2. `test_*_append_only_*.py` — Verify no UPDATE/DELETE on financial tables
3. `test_*_determinism_*.py` — Verify chain hash determinism
4. `test_*_rls_*.py` — Verify tenant isolation (cross-tenant data not accessible)
5. `test_*_isolation_*.py` — Multi-tenant isolation
6. `test_*_migration_*.py` — Migration up/down safety
7. `test_*_supersession_*.py` — Insert-only supersession chain integrity

**Key integration test suites:**
- `tests/integration/platform/` — Control plane enforcement, RBAC, quota, feature flags, workflow approvals, tenant onboarding
- `tests/integration/payment/` — Full payment lifecycle (subscription, webhook, credit, idempotency, RLS)
- `tests/integration/erp_sync/` — ERP sync append-only, no-upstream-mutation, publish governance, RLS

**Platform-specific test coverage:**
- Feature flag canary rollout
- Control plane token enforcement on finance routes
- Isolation routing paths
- Quota enforcement (async API tests)
- RBAC denial paths
- Parallel approval race safety
- Tenant migration workflow

**Prompt engine test coverage:**
- CLI root resolution, runner injection
- Codex runner, dependency gate, dependency graph
- Execution lock, execution pipeline
- File size enforcer, guardrails
- Ledger hash chain, patch limits
- Prompt governance, prompt loader
- Rework engine

### 9.2 Test Data

**Fixtures (conftest.py):**
- `engine` (session-scoped) — fresh DB schema via `alembic upgrade head` on test DB
- `async_session` (session-scoped) — rolling transaction with per-test savepoints
- `async_client` (session-scoped) — httpx AsyncClient against FastAPI app
- `redis_client` (session-scoped) — test Redis connection
- `test_tenant` — IamTenant with `org_setup_complete=True`
- `test_user` — IamUser with `finance_leader` role + default CpOrganisation + CpEntity
- `test_access_token` — valid JWT for test_user

**Test DB:** `postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test`
**Test Redis:** `redis://localhost:6380/0`
(Separate ports from dev to avoid interference)

**Windows IOCP fix:** `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())` in conftest.py

---

## 10. CURRENT STATE SUMMARY

### 10.1 Completed

- Phase 0: Foundation (IAM, credits, audit, LLM gateway, storage airlock)
- Phase 1: Core finance engine (MIS, GL/TB recon, bank recon, working capital, GST, month-end, auditor access)
- Phase 1 advanced: Reconciliation bridge, payroll GL normalization + reconciliation, ratio variance, financial risk, anomaly pattern, board pack narrative
- Phase 1 FX: FX rate engine, FX translation reporting
- Phase 1 multi-currency: Multi-currency consolidation
- Phase 1 specialty: Revenue (ASC 606 / IFRS 15), Lease (IFRS 16 / ASC 842), Prepaid, Fixed Assets
- Phase 2: Multi-entity consolidation, FX translation, ownership consolidation, cash flow engine, equity engine
- Phase 3: Observability engine
- Phase 4: ERP sync kernel (20+ connectors), ERP push, ERP webhook ingest
- Additional modules: Payment/billing, board pack generator, custom reports, scheduled delivery, anomaly UI, auto-trigger, template onboarding, secret rotation, compliance (SOC2/ISO27001/GDPR), closing checklist, working capital module, expense management, budgeting, forecasting, scenario modelling, backup/DR, FDD, PPA, M&A workspace, service registry, marketplace, white-label, partner program, notifications, learning engine, search, cash flow forecast, tax provision, debt covenants, transfer pricing, digital signoff, statutory, multi-GAAP, auditor portal, CoA framework, org setup wizard, fixed assets module, prepaid expenses module, invoice classifier, locations
- Platform control plane: Full RBAC, quota enforcement, feature flags, tenant isolation, workflow approvals, multi-layer auth model
- 120 database migrations applied
- Frontend: Full UI for all modules (150+ pages)
- CI/CD: GitHub Actions (test + build + schema check + SAST + dependency matrix)
- Production deployment: Render (backend) + Vercel (frontend) configuration complete
- Test suite: ~250+ test files, 2639+ tests passing

### 10.2 Partial / Known Issues

- **KI-001:** `utils/findings.py` and `utils/quality_signals.py` have broken import paths (`from workbench.backend import ...`)
- **KI-002:** `utils/quality_signals.py` references synchronous SQLite DB module
- **KI-003:** `python-magic` requires libmagic (Windows needs `python-magic-bin`; Docker OK)
- **KI-004:** ClamAV antivirus scanning stubbed — files get `SCAN_SKIPPED` status (Phase 6)
- **KI-005:** Cloudflare R2 requires configured env vars; health check reports `not_configured` without them
- pytest-asyncio version pinned at 0.24.0 in pyproject.toml (should be >=1.0.0 per memory — check for loop teardown issues)
- `TEMPORAL_WORKER_IN_PROCESS=False` — Temporal worker runs as separate process; needs `temporal_worker` service running

### 10.3 Known Issues (from git log)

- ERP consent/versioning/connection service feature-gated behind `ERP_CONSENT_ENABLED`, `ERP_CONNECTOR_VERSIONING_ENABLED`, `ERP_CONNECTION_SERVICE_ENABLED` (all default `false`)
- Auth hardening is recent (commits: ee2fd70, d30ecc2, 00bf0c3) — multi-layer auth model enforced, control plane token required on finance routes
- Some frontend routes rely on `x-e2e-auth-bypass` header for E2E test bypass (non-production only)

### 10.4 Production vs Local Gaps

| Area | Local | Production |
|---|---|---|
| Database | Docker pgvector | Supabase / managed PostgreSQL |
| Redis | Docker redis:7 | Managed Redis (Render / Upstash) |
| ClamAV | Docker clamav | Required (`CLAMAV_REQUIRED=True` in Dockerfile) |
| Temporal | Docker temporal | External Temporal Cloud (or self-hosted) |
| File storage | R2 (optional) | R2 required |
| Email | `SMTP_REQUIRED=false` | Configure SMTP or email service |
| `AUTO_MIGRATE` | Can use `true` | Always `false` (migrations run in entrypoint.sh) |
| Migrations | Manual or auto | Entrypoint script runs `alembic upgrade head` |

---

## 11. HOW TO RUN THE PLATFORM

### 11.1 First Time Setup

```bash
# 1. Clone and configure
cd /d/finos
cp .env.example .env
# Edit .env: set passwords, secrets, DB/Redis credentials

# 2. Generate required secrets
python -c "import secrets; print(secrets.token_hex(32))"   # → SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"   # → JWT_SECRET
python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"  # → FIELD_ENCRYPTION_KEY
python -c "import secrets; print(secrets.token_hex(32))"   # → NEXTAUTH_SECRET

# 3. Start infrastructure
cd infra
docker-compose up -d db redis

# 4. Wait for DB to be ready, then run migrations
cd /d/finos/backend
alembic upgrade head

# 5. Seed platform users
# Set in .env:
# PLATFORM_OWNER_EMAIL=owner@example.com
# PLATFORM_OWNER_PASSWORD=<secure>
# PLATFORM_OWNER_NAME=Platform Owner
# SEED_ON_STARTUP=true
# Then restart backend and it will seed on startup

# 6. Start backend
uvicorn financeops.main:app --reload --port 8000

# 7. Start frontend
cd /d/finos/frontend
npm install
npm run dev
```

### 11.2 Daily Development

```bash
# Backend
cd /d/finos/backend
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uvicorn financeops.main:app --reload --port 8000

# Frontend
cd /d/finos/frontend
npm run dev

# Run tests
cd /d/finos/backend
pytest tests/ -v --timeout=30 -x

# Run single test file
pytest tests/integration/test_auth_endpoints.py -v

# Check migration state
alembic current
alembic history --verbose
```

### 11.3 Adding a Feature

1. **Model:** Add SQLAlchemy model class to `backend/financeops/db/models/` or `backend/financeops/modules/<name>/models.py`, extending `FinancialBase` (financial) or `UUIDBase` (non-financial)
2. **Migration:** `alembic revision --autogenerate -m "description"` then review and edit the generated file in `migrations/versions/`
3. **Service:** Add service logic in `backend/financeops/services/` or `backend/financeops/modules/<name>/application/`
4. **API:** Add router in `backend/financeops/api/v1/<name>.py` or `backend/financeops/modules/<name>/api/routes.py`
5. **Register:** Add router import and `app.include_router()` in `main.py`
6. **Frontend:** Add page in `frontend/app/(dashboard)/<name>/page.tsx`, component in `frontend/components/<name>/`
7. **Tests:** Add unit tests in `tests/unit/test_<name>.py`, integration tests in `tests/integration/test_<name>_endpoints.py`. Test for append-only, RLS, determinism.
8. **Import in conftest:** Add new model import to `tests/conftest.py` before `Base.metadata.create_all()` section

### 11.4 Deploying to Production

```bash
# Backend (Render auto-deploys on git push to main)
git push origin main
# Render runs: docker build → docker push → deploy → /ready health check

# Frontend (Vercel auto-deploys on git push)
git push origin main

# Manual migration (if needed before deploy):
DATABASE_URL=<prod-url> alembic upgrade head

# Emergency rollback
alembic downgrade -1
```

---

## 12. GAPS & IMPROVEMENT AREAS

### 12.1 Architecture

- Temporal worker is not included in Render `render.yaml` — needs separate service definition
- `TEMPORAL_WORKER_IN_PROCESS=False` by default; Temporal workflows won't execute without the worker service
- ERP consent/versioning feature flags are all `false` — ERP write flows may be incomplete
- Module isolation: many modules import from `financeops.db` directly; some use their own `models.py` — inconsistent pattern
- Background job monitoring (Flower) is local-only; not deployed to production

### 12.2 Security

- ClamAV scanning stubbed — uploaded files are not virus-scanned in production
- `utils/findings.py` and `utils/quality_signals.py` have broken imports (KI-001, KI-002) — if these files are imported, ModuleNotFoundError will be thrown
- pytest-asyncio version (0.24.0) in pyproject.toml is older than recommended (>=1.0.0); loop teardown bug may surface
- MFA recovery codes: verify whether they are properly consumed (single-use) and expired
- Session revocation on password change: verify all existing sessions are revoked when password changes

### 12.3 Performance

- Database pool: 20 connections + 10 overflow (reasonable for starter plan but watch connection counts on Supabase)
- No query caching layer (Redis used only for sessions/rate-limiting, not query cache)
- Celery worker concurrency: 4 per worker (may need tuning for heavy financial computation)
- OpenTelemetry + all SQLAlchemy instrumentation adds overhead — monitor latency

### 12.4 Reliability

- Temporal.io is a single point of failure for long-running runs if not HA-deployed
- Redis is both broker and result backend — single Redis failure stops all background jobs
- No dead letter queue configured for Celery failed tasks beyond the 3-retry limit
- `result_expires=86400` — Celery results expire in 24h (acceptable for most cases)
- No circuit breaker for DB connections (only AI provider circuit breakers)

### 12.5 Observability

- Flower (Celery monitor) not deployed to production
- Prometheus metrics endpoint (`/metrics`) is unauthenticated — consider protecting it
- OpenTelemetry exporter configured but `OTEL_EXPORTER_OTLP_ENDPOINT` not set by default
- Sentry DSN not set by default — production error tracking not enabled until `SENTRY_DSN` set
- No distributed tracing correlation between frontend (Sentry) and backend (OTEL/Sentry)

---

## APPENDIX A: API Reference

Complete endpoint table (base path: `/api/v1`):

### Authentication
| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register new tenant + user |
| POST | `/auth/login` | Login (returns tokens or MFA challenge) |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Logout (revoke refresh token) |
| POST | `/auth/revoke-all` | Revoke all sessions |
| GET | `/auth/me` | Get current user + tenant info |
| POST | `/auth/mfa/setup` | Setup TOTP MFA |
| POST | `/auth/mfa/verify-setup` | Verify MFA setup |
| POST | `/auth/mfa/verify` | Verify MFA during login |
| POST | `/auth/forgot-password` | Request password reset email |
| POST | `/auth/reset-password` | Reset password with token |
| POST | `/auth/change-password` | Change password (authenticated) |
| POST | `/auth/accept-invite` | Accept invitation with token |

### Health
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Full health check |
| GET | `/health/live` or `/live` | Liveness probe |
| GET | `/health/ready` or `/ready` | Readiness probe |
| GET | `/healthz` | Health summary |
| GET | `/readyz` | Readiness alias |

### Tenants
| Method | Path | Description |
|---|---|---|
| GET | `/tenants` | List tenants |
| POST | `/tenants` | Create tenant |
| GET | `/tenants/{id}` | Get tenant |
| PUT | `/tenants/{id}` | Update tenant |
| DELETE | `/tenants/{id}` | Deactivate tenant |

### Users
| Method | Path | Description |
|---|---|---|
| GET | `/users` | List users |
| POST | `/users` | Create user |
| GET | `/users/{id}` | Get user |
| PUT | `/users/{id}` | Update user |
| DELETE | `/users/{id}` | Deactivate user |

### MIS Manager
| Method | Path | Description |
|---|---|---|
| GET | `/mis/templates` | List MIS templates |
| POST | `/mis/templates` | Create template |
| GET | `/mis/templates/{id}` | Get template |
| POST | `/mis/templates/{id}/supersede` | Supersede template version |
| GET | `/mis/uploads` | List uploads |
| POST | `/mis/uploads` | Create upload |

### GL/TB Reconciliation
| Method | Path | Description |
|---|---|---|
| GET | `/recon/entries` | List GL entries |
| POST | `/recon/entries` | Create GL entry |
| GET | `/recon/trial-balance` | Get trial balance |
| POST | `/recon/trial-balance` | Upload trial balance rows |
| POST | `/recon/run` | Run reconciliation |
| GET | `/recon/items` | List recon items |

### Bank Reconciliation
| Method | Path | Description |
|---|---|---|
| GET | `/bank-recon/statements` | List bank statements |
| POST | `/bank-recon/statements` | Create bank statement |
| POST | `/bank-recon/run` | Run bank reconciliation |
| GET | `/bank-recon/items` | List recon items |

### Working Capital
| Method | Path | Description |
|---|---|---|
| GET | `/working-capital/snapshots` | List snapshots |
| POST | `/working-capital/snapshot` | Create snapshot |
| GET | `/working-capital/ap-items` | List AP items |
| POST | `/working-capital/ap-items` | Create AP item |
| GET | `/working-capital/ar-items` | List AR items |
| POST | `/working-capital/ar-items` | Create AR item |

### GST Reconciliation
| Method | Path | Description |
|---|---|---|
| GET | `/gst/returns` | List GST returns |
| POST | `/gst/returns` | Create GST return |
| POST | `/gst/run` | Run GST reconciliation |
| GET | `/gst/items` | List GST recon items |

### Month-End Checklist
| Method | Path | Description |
|---|---|---|
| GET | `/monthend/checklists` | List checklists |
| POST | `/monthend/checklists` | Create checklist |
| POST | `/monthend/checklists/{id}/close` | Close checklist (insert-only) |
| GET | `/monthend/tasks` | List tasks |
| POST | `/monthend/tasks` | Create task |
| PUT | `/monthend/tasks/{id}` | Update task |

### Auditor Access
| Method | Path | Description |
|---|---|---|
| GET | `/auditor/grants` | List auditor grants |
| POST | `/auditor/grants` | Create auditor grant |
| DELETE | `/auditor/grants/{id}` | Revoke grant (insert new row with is_active=False) |
| GET | `/auditor/access-logs` | List access logs |

### Billing/Payment
| Method | Path | Description |
|---|---|---|
| GET | `/billing/plans` | List billing plans |
| GET | `/billing/subscription` | Get current subscription |
| POST | `/billing/subscribe` | Subscribe to plan |
| POST | `/billing/cancel` | Cancel subscription |
| POST | `/billing/top-up` | Add credits |
| GET | `/billing/invoices` | List invoices |
| POST | `/billing/stripe/webhook` | Stripe webhook |
| POST | `/billing/razorpay/webhook` | Razorpay webhook |

### ERP Sync
| Method | Path | Description |
|---|---|---|
| GET | `/erp-sync/connections` | List ERP connections |
| POST | `/erp-sync/connections` | Create ERP connection |
| GET | `/erp-sync/connections/{id}` | Get connection |
| POST | `/erp-sync/run` | Run ERP sync |
| GET | `/erp-sync/snapshots` | List raw snapshots |
| GET | `/erp-sync/normalized` | List normalized snapshots |
| GET | `/erp-sync/drift` | Get drift reports |
| GET | `/erp-sync/health` | ERP health alerts |

*(Note: Additional endpoints exist for all 40+ modules. This table covers the most commonly used. Full OpenAPI spec available at `/docs` and `/openapi.json`.)*

---

## APPENDIX B: Frontend Routes

All page routes in `frontend/app/`:

### Root
- `/` — Landing / redirect page

### Authentication Routes (`(auth)` group)
- `/login` — Login page
- `/register` — Registration page
- `/forgot-password` — Forgot password
- `/reset-password` — Reset password (with token)
- `/auth/change-password` — Force password change
- `/accept-invite` — Accept invitation
- `/mfa` — MFA verification
- `/mfa/setup` — MFA setup (TOTP QR code)

### Org Setup Routes (`(org-setup)` group)
- `/org-setup` — Org setup wizard
- `/setup/coa` — Chart of accounts setup

### Dashboard Routes (`(dashboard)` group)

**Dashboard:**
- `/dashboard` — Main dashboard
- `/dashboard/cfo` — CFO dashboard
- `/dashboard/director` — Director dashboard
- `/dashboard/kpis` — KPI dashboard
- `/dashboard/ratios` — Financial ratios
- `/dashboard/trends` — Trend analysis
- `/dashboard/variance` — Variance analysis

**Accounting:**
- `/accounting/journals` — Journal list
- `/accounting/journals/new` — New journal
- `/accounting/journals/[id]` — Journal detail
- `/accounting/trial-balance` — Trial balance
- `/accounting/balance-sheet` — Balance sheet
- `/accounting/pnl` — P&L statement
- `/accounting/cash-flow` — Cash flow statement
- `/accounting/revaluation` — FX revaluation

**AI:**
- `/ai` — AI overview
- `/ai/dashboard` — AI CFO dashboard
- `/ai/anomalies` — Anomaly detection
- `/ai/narrative` — Board pack narrative
- `/ai/recommendations` — AI recommendations

**Advisory:**
- `/advisory` — Advisory overview
- `/advisory/fdd` — FDD engagements list
- `/advisory/fdd/[id]` — FDD engagement detail
- `/advisory/fdd/[id]/report` — FDD report view
- `/advisory/ma` — M&A workspace list
- `/advisory/ma/[id]` — M&A workspace detail
- `/advisory/ma/[id]/documents` — M&A documents
- `/advisory/ma/[id]/valuation` — M&A valuation
- `/advisory/ppa` — PPA list
- `/advisory/ppa/[id]` — PPA detail

**Anomalies:**
- `/anomalies` — Anomaly list
- `/anomalies/[id]` — Anomaly detail
- `/anomalies/thresholds` — Threshold config

**Audit:**
- `/audit` — Audit access list
- `/audit/[engagement_id]` — Audit engagement

**Billing:**
- `/billing` — Billing overview
- `/billing/plans` — Plan selection
- `/billing/invoices` — Invoice list
- `/billing/usage` — Usage stats

**Board Pack:**
- `/board-pack` — Board pack list
- `/board-pack/[id]` — Board pack detail

**Budget:**
- `/budget` — Budget overview
- `/budget/[year]` — Budget by year
- `/budget/[year]/edit` — Edit budget

**Close:**
- `/close` — Month-end close
- `/close/checklist` — Checklist view
- `/close/[period]` — Period detail

**Consolidation:**
- `/consolidation` — Consolidation overview
- `/consolidation/runs/[id]` — Consolidation run detail
- `/consolidation/translation` — FX translation

**Covenants:**
- `/covenants` — Debt covenants

**Director:**
- `/director` — Director overview
- `/signoff` — Digital signoff

**ERP:**
- `/erp/connectors` — ERP connectors
- `/erp/mappings` — ERP field mappings
- `/erp/sync` — ERP sync status
- `/sync` — Sync overview
- `/sync/connect` — Connect new ERP

**Expenses:**
- `/expenses` — Expense list
- `/expenses/[id]` — Expense detail
- `/expenses/submit` — Submit expense

**Fixed Assets:**
- `/fixed-assets` — Asset register list
- `/fixed-assets/[id]` — Asset detail

**Forecast:**
- `/forecast` — Forecast list
- `/forecast/[id]` — Forecast detail

**FX:**
- `/fx/rates` — FX rate management

**GAAP:**
- `/gaap` — Multi-GAAP comparison

**Invoice:**
- `/invoice-classify` — Invoice classification

**Marketplace:**
- `/marketplace` — Template marketplace
- `/marketplace/[id]` — Template detail
- `/marketplace/contribute` — Contribute template
- `/marketplace/my-templates` — My templates

**MIS:**
- `/mis` — MIS dashboard

**Modules:**
- `/modules` — Module list
- `/modules/revenue` — Revenue recognition
- `/modules/lease` — Lease accounting
- `/modules/prepaid` — Prepaid expenses
- `/modules/assets` — Fixed assets

**Notifications:**
- `/notifications` — Notification center

**Onboarding:**
- `/onboarding` — Template onboarding

**Partner:**
- `/partner` — Partner overview
- `/partner/referrals` — Referrals
- `/partner/earnings` — Earnings

**Prepaid:**
- `/prepaid` — Prepaid list
- `/prepaid/[id]` — Prepaid detail

**Reconciliation:**
- `/reconciliation/gl-tb` — GL/TB reconciliation
- `/reconciliation/payroll` — Payroll reconciliation
- `/trial-balance` — Trial balance

**Reports:**
- `/reports` — Report list
- `/reports/[id]` — Report detail

**Scenarios:**
- `/scenarios` — Scenario list
- `/scenarios/[id]` — Scenario detail

**Scheduled Delivery:**
- `/scheduled-delivery` — Delivery list
- `/scheduled-delivery/logs` — Delivery logs

**Settings:**
- `/settings` — Settings overview
- `/settings/chart-of-accounts` — CoA management
- `/settings/coa` — CoA (alternate)
- `/settings/cost-centres` — Cost centre management
- `/settings/entities` — Entity management
- `/settings/erp-mapping` — ERP field mapping config
- `/settings/groups` — Group management
- `/settings/locations` — Location management
- `/settings/users` — User management
- `/settings/white-label` — White-label config
- `/settings/privacy` — Privacy settings
- `/settings/privacy/consent` — Consent management
- `/settings/privacy/my-data` — Personal data

**Statutory:**
- `/statutory` — Statutory filings

**Tax:**
- `/tax` — Tax provision list
- `/tax/[id]` — Tax provision detail

**Transfer Pricing:**
- `/transfer-pricing` — TP list
- `/transfer-pricing/[id]` — TP detail

**Treasury:**
- `/treasury` — Cash flow forecast list
- `/treasury/[id]` — Forecast detail

**Trust/Compliance:**
- `/trust` — Trust center
- `/trust/gdpr` — GDPR overview
- `/trust/gdpr/breach` — GDPR breach log
- `/trust/gdpr/consent` — GDPR consent
- `/trust/soc2` — SOC2 compliance

**Working Capital:**
- `/working-capital` — Working capital dashboard

### Admin Routes (`(admin)` group)
- `/admin` — Admin overview
- `/admin/ai-providers` — AI provider config
- `/admin/ai-quality` — AI quality metrics
- `/admin/backup` — Backup management
- `/admin/compliance` — Compliance controls
- `/admin/compliance/iso27001` — ISO 27001
- `/admin/compliance/soc2` — SOC2
- `/admin/flags` — Feature flags
- `/admin/marketplace` — Marketplace admin
- `/admin/modules` — Module management
- `/admin/partners` — Partner management
- `/admin/rbac` — RBAC management
- `/admin/services` — Service registry
- `/admin/tenants` — Tenant management
- `/admin/users` — Platform user management
- `/admin/white-label` — White-label overview
- `/admin/white-label/[tenant_id]` — Per-tenant white-label

### Legal Routes
- `/legal` — Legal overview
- `/legal/terms` — Terms of service
- `/legal/privacy` — Privacy policy
- `/legal/dpa` — Data processing agreement
- `/legal/sla` — Service level agreement
- `/legal/cookies` — Cookie policy

---

## APPENDIX C: Dependency Tree

### Backend (Python) — Key Dependencies

| Package | Version | Purpose |
|---|---|---|
| fastapi | 0.115.0 | Web framework |
| uvicorn[standard] | 0.30.0 | ASGI server |
| gunicorn | 22.0.0 | Process manager |
| sqlalchemy | 2.0.35 | ORM (async) |
| asyncpg | 0.30.0 | PostgreSQL async driver |
| alembic | 1.13.0 | Database migrations |
| pgvector | 0.3.3 | Vector similarity extension |
| redis | 5.0.8 | Redis client |
| celery[redis] | 5.4.0 | Task queue |
| flower | 2.0.1 | Celery monitor |
| pydantic | 2.9.0 | Data validation |
| pydantic-settings | 2.5.0 | Settings management |
| email-validator | 2.2.0 | Email validation |
| python-jose[cryptography] | 3.3.0 | JWT |
| passlib[bcrypt] | 1.7.4 | Password hashing |
| pyotp | 2.9.0 | TOTP/MFA |
| cryptography | 43.0.0 | AES-256-GCM |
| slowapi | 0.1.9 | Rate limiting |
| starlette-csrf | 3.0.0 | CSRF protection |
| openpyxl | 3.1.5 | Excel reading/writing |
| xlsxwriter | 3.2.0 | Excel writing |
| pandas | 2.2.3 | Data processing |
| numpy | 2.1.0 | Numerical operations |
| python-magic | 0.4.27 | MIME detection |
| python-docx | 1.1.2 | Word document generation |
| clamd | 1.0.2 | ClamAV client |
| boto3 | 1.35.0 | AWS/R2 S3 client |
| httpx | 0.27.0 | Async HTTP client |
| aiohttp | 3.10.0 | Async HTTP |
| stripe | 11.6.0 | Stripe payments |
| razorpay | 1.4.2 | Razorpay payments |
| anthropic | 0.34.0 | Anthropic Claude SDK |
| openai | 1.51.0 | OpenAI SDK |
| ollama | 0.3.3 | Ollama local LLM |
| tiktoken | 0.7.0 | Token counting |
| opentelemetry-sdk | 1.27.0 | Telemetry SDK |
| sentry-sdk[fastapi] | 2.14.0 | Error tracking |
| python-json-logger | 2.0.7 | Structured logging |
| prometheus-client | 0.21.0 | Metrics |
| temporalio | 1.7.0 | Temporal workflows |
| jinja2 | 3.1.4 | Templating |
| python-dateutil | 2.9.0 | Date utilities |
| pytz | 2024.2 | Timezone |
| babel | 2.16.0 | Localization |

**Dev dependencies:**
- pytest==8.3.0, pytest-asyncio==0.24.0, pytest-cov==5.0.0
- httpx==0.27.0, faker==30.0.0, factory-boy==3.3.1
- ruff==0.6.0, mypy==1.11.0

### Frontend (Node/TypeScript) — Key Dependencies

| Package | Version | Purpose |
|---|---|---|
| next | 14.2.35 | React framework |
| next-auth | 5.0.0-beta.30 | Authentication |
| react / react-dom | 18.x | UI library |
| @tanstack/react-query | 5.x | Server state management |
| @tanstack/react-table | 8.x | Data tables |
| zustand | 5.0.11 | Global state |
| axios | 1.x | HTTP client |
| @radix-ui/* | Latest | Headless UI primitives |
| radix-ui | 1.x | Radix UI collection |
| tailwindcss | 3.4.1 | CSS utility framework |
| shadcn | 4.0.5 | Component library |
| class-variance-authority | 0.7.1 | Component variants |
| tailwind-merge | 3.x | Tailwind class merging |
| lucide-react | 0.577.0 | Icons |
| recharts | 3.x | Charts |
| react-hook-form | 7.x | Form management |
| zod | 4.x | Schema validation |
| date-fns | 4.x | Date utilities |
| input-otp | 1.4.2 | OTP input |
| react-qr-code | 2.x | QR code generation |
| react-dropzone | 15.x | File upload |
| @sentry/nextjs | 10.x | Frontend error tracking |

**Dev dependencies:**
- TypeScript 5.x
- @playwright/test 1.x (E2E tests)
- vitest 4.x (unit tests)
- @vitejs/plugin-react 6.x
