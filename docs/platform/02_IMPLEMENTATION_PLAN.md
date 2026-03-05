# FinanceOps Platform â€” Implementation Plan
> Version 1.0 | Status: Locked | Classification: Confidential
> Use this document to instruct Claude Code phase by phase.

---

## How to Use This Document

1. Open Claude Code in your terminal
2. Navigate to your project folder
3. Copy the prompt for the current phase
4. Paste into Claude Code
5. Verify completion against the Definition of Done
6. Move to next phase only when DoD is 100% met
7. After each phase â€” update ERROR_LEDGER.md with what was built

---

## Phase Overview

| Phase | Name | Duration | Outcome |
|---|---|---|---|
| 0 | Foundation & Infrastructure | Week 1-2 | Running skeleton, CI/CD, DB, auth |
| 1 | Core Finance Engine | Week 3-5 | MIS, TB recon, consolidation working |
| 2 | Advanced Accounting Modules | Week 6-8 | FAR, Leases, RevRec, Paysheets |
| 3 | Multi-Tenant SaaS & RBAC | Week 9-10 | Full tenant isolation, portals, roles |
| 4 | AI/LLM Intelligence Layer | Week 11-13 | Multi-agent pipeline, all 4 models |
| 5 | Contracts, People, Forecasting | Week 14-16 | Full FP&A capability |
| 6 | Observability, Compliance, Marketplace | Week 17-20 | Production-ready, certifiable |

All "Claude Code Prompt" blocks in this document must use
`FINOS_EXEC_PROMPT_TEMPLATE v1.1` and include sections 7A and 9A.

---

## Phase 0 â€” Foundation & Infrastructure

### Goal
A running, deployable skeleton with authentication, database, CI/CD, and all infrastructure in place. No finance features yet â€” just the foundation everything will be built on.

### What Gets Built
- Monorepo structure (frontend + backend + shared types)
- PostgreSQL with row-level security enabled
- Redis setup (cache + queues)
- FastAPI skeleton with middleware layer
- Next.js skeleton with auth
- Cloudflare configuration (WAF, Tunnel, R2)
- Docker Compose for local development
- GitHub Actions CI/CD pipeline
- Sentry, Prometheus, Grafana setup
- Doppler secrets management
- Temporal workflow engine setup
- Base audit trail tables (append-only, chain hash)
- Multi-tenancy tables and RLS policies

### Claude Code Prompt â€” Phase 0

```
You are building FinanceOps, an enterprise finance SaaS platform.

PHASE 0: Foundation & Infrastructure

Create a monorepo with the following structure:
financeops/
â”œâ”€â”€ apps/
â”‚   â”œâ”€â”€ web/          â† Next.js 14, TypeScript, shadcn/ui, Tailwind, pnpm
â”‚   â””â”€â”€ desktop/      â† Tauri 2.0 shell (wraps web app)
â”œâ”€â”€ backend/          â† FastAPI, Python 3.12, uv package manager
â”œâ”€â”€ workers/          â† Celery workers (separate from API)
â”œâ”€â”€ shared/           â† Shared TypeScript types + Python schemas
â”œâ”€â”€ infra/            â† Docker Compose, Cloudflare config
â””â”€â”€ docs/             â† Docusaurus documentation site

BACKEND REQUIREMENTS:
1. FastAPI app with comprehensive middleware:
   - JWT verification middleware (verify on every request)
   - Tenant resolution middleware (extract tenant_id, set in DB session)
   - Rate limiting middleware (slowapi + Redis)
   - Request validation middleware (Pydantic)
   - Audit logging middleware (log every request immutably)
   - Correlation ID middleware (inject unique ID per request)
   - Security headers middleware (HSTS, CSP, X-Frame-Options etc.)

2. PostgreSQL setup with SQLAlchemy 2.0 async:
   - Base model with: id (UUID), tenant_id (UUID), created_at, created_by,
     version (int), is_superseded (bool), prev_hash (str), hash (str)
   - Row Level Security on all tables (tenant_id = current_setting)
   - Separate INSERT-only user for audit tables
   - Alembic migrations setup

3. Audit trail system:
   - AuditWriter service (all audit writes go through this, never direct)
   - Chain hash implementation (SHA256 of data + prev_hash)
   - Append-only enforcement (no UPDATE/DELETE on audit tables at DB level)
   - Tamper detection function (verify chain integrity)

4. Multi-tenancy:
   - Tenant table, Organisation table, User table
   - Tenant provisioning service (create tenant â†’ create schema â†’ create storage bucket)
   - Tenant context middleware (set tenant_id in DB session per request)

5. Authentication:
   - JWT tokens (access: 15min, refresh: 7days)
   - OAuth2 password flow + refresh token flow
   - MFA setup (TOTP via pyotp)
   - Role enum: PLATFORM_OWNER, PLATFORM_ENGINEER, PLATFORM_SUPPORT,
     TENANT_ADMIN, ORG_ADMIN, MANAGER, REVIEWER, DATA_ENTRY_PAYROLL,
     DATA_ENTRY_GL, EXECUTIVE, AUDITOR
   - Permission matrix (which role can do what)

6. Redis setup:
   - Cache client (with TTL management)
   - Queue client (Celery broker)
   - Rate limit state

7. Celery workers:
   - Worker base class with: logging, error handling, retry logic, Sentry integration
   - Queues: file_scan, parse, erp_sync, report_gen, email, ai_inference, notification, learning
   - Dead letter queue handling

8. Health check endpoints:
   - GET /health (overall platform health)
   - GET /health/db (PostgreSQL)
   - GET /health/redis (Redis)
   - GET /health/workers (Celery workers)

FRONTEND REQUIREMENTS:
1. Next.js 14 App Router with TypeScript strict mode
2. Auth setup with NextAuth.js v5
3. Base layout with:
   - Sidebar navigation (role-aware â€” shows only permitted sections)
   - Top bar (tenant name, user name, notifications bell, global search Cmd+K)
   - Theme (clean, professional, finance-appropriate â€” dark/light toggle)
4. shadcn/ui components installed and configured
5. TanStack Query setup for server state
6. Zustand store for client state
7. Zod schemas matching backend Pydantic models
8. Placeholder pages for all 6 tab sections

CI/CD REQUIREMENTS:
1. GitHub Actions workflow:
   - On PR: lint, type-check, unit tests, security scan (Semgrep)
   - On merge to main: build, test, deploy to Railway (backend) + Vercel (frontend)
   - Sentry release tracking on deploy
   - Auto-generate changelog from conventional commits
   - Auto-update dependency matrix on merge

DOCKER COMPOSE (local dev):
- PostgreSQL 16 with TimescaleDB + pgvector extensions
- Redis 7
- Temporal server
- ClamAV daemon
- Prometheus + Grafana + Loki
- All services with health checks

PRINCIPLES TO ENFORCE IN ALL CODE:
- No UPDATE or DELETE statements on any *_audit or *_log tables
- Every database write goes through the AuditWriter service
- Every request has a correlation_id in headers and logs
- Tenant ID verified on every database query
- No secrets in code (all from Doppler/environment)
- Type hints on every Python function
- JSDoc on every TypeScript function

Output all files with full content. No placeholders. No TODOs.
```

### Definition of Done â€” Phase 0
- [ ] Monorepo structure created and runs locally with `docker-compose up`
- [ ] `GET /health` returns healthy for all components
- [ ] A user can register, log in, receive JWT, refresh token
- [ ] Multi-tenancy: creating tenant A and tenant B â€” their data is isolated (RLS verified)
- [ ] Audit trail: every request logged, chain hash verified
- [ ] CI/CD pipeline runs green on GitHub Actions
- [ ] Frontend loads at localhost:3000, auth flow works
- [ ] Sentry captures a test error correctly
- [ ] Grafana dashboard shows basic metrics

---

## Phase 1 â€” Core Finance Engine

### Goal
The platform can ingest MIS files, GL/TB data, perform reconciliation, and produce a consolidated multi-currency P&L. This is the heart of the platform.

### What Gets Built
- MIS Manager (upload, template learning, version control)
- GL/TB Reconciliation engine
- Multi-currency Consolidation engine
- Classification Engine (AI-assisted)
- FX Rate Engine (4 sources + manual)
- Assumptions Engine
- Basic reporting (consolidated P&L export)

### Claude Code Prompt â€” Phase 1

```
You are continuing to build FinanceOps. Phase 0 (foundation) is complete.

PHASE 1: Core Finance Engine

Build the following modules. All code must follow Phase 0 patterns:
- AuditWriter for all DB writes
- Append-only (no UPDATE/DELETE)
- Tenant isolation (RLS)
- Pydantic v2 validation
- Async SQLAlchemy
- Full type hints

MODULE 1: MIS Manager (backend/modules/mis_manager/)

1. MIS Template Learning:
   - Accept multi-sheet Excel upload (.xlsx)
   - For each sheet: detect column headers, row structure, data types
   - Save template profile: {sheet_name, columns, row_categories, hierarchy, data_types}
   - Template versioning (append-only)
   - Designate a "Master MIS" template (all reporting uses this structure)

2. MIS Version Control:
   - Every upload creates a new version
   - Structural diff detection: new lines, removed lines, renamed, split, merged, reclassified
   - Backward propagation engine:
     For each structural change detected:
     - Determine if prior months can be auto-mapped
     - If ambiguous: create a UserPromptRequired record
     - Surface prompts to Finance Leader with options
     - Apply confirmed choices to all prior months
     - Log every restatement with before/after values

3. Missing Data Detection:
   - Compare uploaded MIS against Master template
   - Flag: missing sheets, missing columns, blank cells where data expected
   - Generate prompt list for Finance Leader to fill
   - Write corrected file back to working folder

MODULE 2: FX Rate Engine (backend/modules/fx_rates/)

1. Live rate fetching (4 sources):
   - European Central Bank: https://data-api.ecb.europa.eu/service/data/EXR
   - Frankfurter API: https://api.frankfurter.app/latest
   - Open Exchange Rates: https://openexchangerates.org/api/latest.json (free tier)
   - ExchangeRate-API: https://v6.exchangerate-api.com/v6/{key}/latest/USD
   Fetch all 4 simultaneously (asyncio.gather), return side-by-side comparison

2. Manual rate entry:
   - Finance Leader enters rate per currency pair per month
   - Saved to monthly rate profile
   - Rate history maintained (append-only)

3. Supported currencies (all pairs to USD):
   INR, GBP, EUR, USD, AUD, CAD, NTD, CHF + any ISO 4217 currency code

4. Rate application:
   - Apply month-end rate to all transactions in that month
   - Apply daily rate for transaction-level conversion
   - FX variance computation (expected vs actual IC balance difference)

MODULE 3: Classification Engine (backend/modules/classification/)

1. GL â†’ MIS mapping:
   - Accept GL account list with descriptions
   - Call AI Gateway (Stage 1: phi3:mini structures the task,
     Stage 2: Mistral executes classification,
     Stage 3: DeepSeek validates)
   - Return: {gl_account, suggested_mis_line, confidence, reasoning}
   - Finance Leader reviews + confirms/overrides
   - Confirmed mappings saved (append-only)

2. Retrospective reclassification:
   - Finance Leader changes a mapping
   - System asks: "Apply to all prior months? Which months?"
   - Restatement engine applies changes
   - Audit trail: original classification, new classification, date changed, by whom

3. Mapping profiles:
   - Save mapping set as reusable profile (e.g. "India Tally Standard Mapping")
   - Share profiles across tenants (anonymised, marketplace-ready)

MODULE 4: GL/TB Reconciliation (backend/modules/reconciliation/)

1. GL â†’ TB matching:
   - Sum all GL entries per account per period
   - Compare to TB closing balance per account
   - Flag any difference > 0
   - Drill down to GL entries for any break

2. Intercompany matching (cross-entity):
   - Entity A IC receivable must equal Entity B IC payable (same currency)
   - Where different currencies: compute expected FX difference
   - Flag: timing differences (amber), unexplained breaks (red), FX explained (green)

3. Reconciliation workspace:
   - Each break is a "reconciliation item"
   - Assignable to a user
   - Status: Open / In Progress / Resolved / Escalated
   - Notes, attachments per item
   - Resolution requires Finance Leader sign-off

MODULE 5: Multi-Currency Consolidation (backend/modules/consolidation/)

1. Consolidation engine:
   - Accept P&L data per entity in local currency
   - Apply month-end FX rates (from FX Rate Engine)
   - Convert all to parent currency (user-selectable, default USD)
   - Sum all entities to consolidated P&L
   - Intercompany elimination: flag IC transactions, eliminate on consolidation

2. Elimination entries:
   - IC revenue in Entity A eliminated against IC cost in Entity B
   - IC balances eliminated
   - Unexplained IC differences escalated (not silently eliminated)

3. Output:
   - Consolidated P&L in parent currency
   - Local currency columns alongside (toggle on/off)
   - FX impact shown as separate column
   - Export to Excel (formatted, not raw)

MODULE 6: Assumptions Engine (backend/modules/assumptions/)

- Every assumption made by any module creates an Assumption record
- Fields: assumption_id, module, description, basis, affected_entities,
  affected_periods, status (pending/accepted/changed/rejected), created_at
- Finance Leader must action all pending assumptions before report can be published
- Accepted/changed assumptions logged immutably
- Published in working folder as Assumptions_{YYYY_MM}.xlsx

FRONTEND â€” Phase 1:
Build Tab 2 (MIS Manager), Tab 3 (Source Data), Tab 4 (Reconciliation), Tab 5 (Consolidation)
Each tab fully functional with the above backend APIs.
Beautiful UI â€” shadcn/ui components, proper loading states, error states, empty states.
Every table has: sort, filter, export to Excel button.
Every form has: Zod validation, clear error messages.
```

### Definition of Done â€” Phase 1
- [ ] Upload a real multi-sheet MIS Excel â€” template is learned and saved
- [ ] Upload a TB and GL â€” reconciliation runs and breaks are identified
- [ ] FX rates fetched from all 4 sources and shown side-by-side
- [ ] 3 entities with different currencies consolidated to USD correctly
- [ ] IC transaction identified, eliminated, unexplained difference flagged
- [ ] Classification: 20 GL accounts AI-classified, 18+ correct on first attempt
- [ ] Assumptions list generated, Finance Leader can accept/change each
- [ ] Consolidated P&L exported to formatted Excel with source file references

---

## Phase 2 â€” Advanced Accounting Modules

### Claude Code Prompt â€” Phase 2

```
PHASE 2: Advanced Accounting Modules

Build the following modules following all Phase 0 patterns.

MODULE 1: Fixed Asset Register (backend/modules/far/)
- Asset master CRUD (append-only updates)
- Depreciation methods: SLM, WDV, Double Declining, Units of Production
- Auto-generate depreciation schedule (monthly)
- Disposal, impairment, revaluation entries
- FAR â†’ TB reconciliation
- Journal entries for ERP posting
- Standards: IAS 16 guidance in all computations

MODULE 2: Lease Accounting (backend/modules/leases/)
- Lease register (operating + finance leases)
- ROU asset computation
- Lease liability amortisation schedule (effective interest method)
- Lease modifications (remeasurement)
- Short-term + low-value exemptions
- IFRS 16 disclosure notes auto-generated
- Journal entries generated

MODULE 3: Revenue Recognition (backend/modules/revenue_recognition/)
- 7 methods: PoC (cost-to-cost, efforts, units), completed contract,
  completed service, milestone, straight-line, usage-based, subscription
- IFRS 15 5-step model applied per contract
- Deferred revenue schedule
- Contract asset / liability tracking
- Variable consideration with constraint
- Modification accounting
- Disclosure notes auto-generated

MODULE 4: Paysheet Engine (backend/modules/paysheets/)
- Accept country paysheet (multiple locations inside)
- Auto-detect location columns
- Apply month-end FX rate per country
- Roll up to consolidated employee cost
- Feed MIS people cost lines
- Paysheet â†’ MIS reconciliation

MODULE 5: Prepaid & Subscription Tracker (backend/modules/prepaid/)
- Prepaid register with amortisation schedules
- Subscription register with renewal alerts
- Auto-charge to P&L monthly
- Balance â†’ TB reconciliation
- Vendor consolidation opportunities flagged

MODULE 6: SG&A Schedules (backend/modules/sga_schedules/)
- Rent schedule (with IFRS 16 overlay)
- Insurance schedule
- Professional fees schedule
- IT & software schedule
- Any GL line â†’ drill to schedule

For all modules:
- Full Temporal workflow for multi-step processes
- AI Gateway integration (classify, validate, suggest)
- Export to Excel (formatted) and PDF
- Journal entries generated for ERP push
- Frontend UI for each module (beautiful, functional)
```

### Definition of Done â€” Phase 2
- [ ] FAR: upload asset register, depreciation computed correctly, TB recon passes
- [ ] Lease: IFRS 16 schedule computed, ROU asset and liability correct
- [ ] RevRec: milestone contract â€” revenue recognised on milestone sign-off
- [ ] Paysheet: 3 countries, 2 locations each, rolled up to consolidated USD correctly
- [ ] All modules generate correct journal entries
- [ ] All modules export formatted Excel and PDF

---

## Phase 3 â€” Multi-Tenant SaaS & RBAC

### Claude Code Prompt â€” Phase 3

```
PHASE 3: Multi-Tenant SaaS & RBAC

Build the full multi-tenancy, RBAC, approval workflows, and portals.

1. TENANT MANAGEMENT:
   - Tenant onboarding automation (signup â†’ provision â†’ welcome email)
   - 3 tenant types: CORPORATE_GROUP, CA_FIRM, SME
   - Subscription tiers: STARTER, PROFESSIONAL, BUSINESS, ENTERPRISE
   - White label configuration per tenant (logo, colours, domain)
   - Developer sandbox per tenant (isolated, separate from production)
   - Feature flags per tenant (enable/disable any module)

2. CA FIRM CAPABILITIES:
   - Client management (add unlimited clients under firm tenant)
   - Team assignment (assign staff to specific clients only)
   - Client portal (client logs in, sees only their data)
   - Client onboarding flow

3. APPROVAL WORKFLOWS:
   Data Entry uploads â†’ Reviewer flags â†’ Manager corrects â†’ Finance Leader approves â†’ Published
   - Every step logged immutably
   - Escalation on inactivity (configurable timeout)
   - Once approved: data locked for that month
   - Change after lock: requires Finance Leader re-approval + new version

4. THREE PORTALS:
   - app.{domain}: Customer portal (tenant users)
   - platform.{domain}: Platform portal (your team)
   - partners.{domain}: Partner/consultant portal
   - Each portal: separate Next.js layout, separate auth flow, separate navigation

5. PLATFORM PORTAL (for you):
   - All tenants dashboard (status, usage, health, cost)
   - Tenant management (create, suspend, configure)
   - Global module enable/disable toggle with blast radius preview
   - Tenant-level module enable/disable
   - User-level permission override
   - Every toggle requires reason, logged immutably

6. SOC2 / ISO EVIDENCE:
   - Live evidence capture for all control activities
   - Evidence dashboard (SOC2 criteria mapped, completion %)
   - Auditor access portal (temporary read-only access)
   - Evidence package export (auto-compiled for audit period)

7. LEGAL & RESPONSIBILITY:
   - ToS acceptance on signup (versioned, re-acceptance on update)
   - Role-specific responsibility agreements
   - Action-level confirmations (with digital signature)
   - Non-repudiation engine (HMAC signed receipts)
   - Legal hold capability
```

### Definition of Done â€” Phase 3
- [ ] Create 2 tenants â€” data completely isolated (verified at DB level)
- [ ] CA Firm: create 3 clients, assign different staff to each, verify isolation
- [ ] Approval workflow: data entry â†’ reviewer â†’ manager â†’ Finance Leader â†’ locked
- [ ] Platform portal: toggle a module off for one tenant, verify it's disabled
- [ ] SOC2 dashboard shows evidence capture for CC6 (logical access)
- [ ] ToS acceptance logged with digital signature and timestamp

---

## Phase 4 â€” AI/LLM Intelligence Layer

### Claude Code Prompt â€” Phase 4

```
PHASE 4: AI/LLM Intelligence Layer

Build the complete multi-agent AI pipeline and AI Gateway.

1. AI GATEWAY (backend/ai_gateway/):
   Task classification engine:
   - SIMPLE: single fact, single entity, no computation â†’ local phi3:mini only
   - MEDIUM: multi-entity, classification, structured analysis â†’ local + cheap cloud
   - COMPLEX: variance analysis, report generation, standards â†’ cloud primary
   - STANDARDS: accounting interpretation â†’ cross-validation (Claude + GPT-4o)
   - SENSITIVE: contains PII or confidential data â†’ local only, never cloud

   Model routing:
   - Local: Ollama API (phi3:mini, Mistral 7B, DeepSeek 6.7B, LLaMA 3.1 8B)
   - Cloud primary: Anthropic API (claude-sonnet-4-5)
   - Cloud validation: OpenAI API (gpt-4o-mini)
   - Cloud tertiary: DeepSeek API
   - Fast inference: Groq API (LLaMA 3.1 70B)

   Gateway responsibilities:
   - API key management (never exposed to modules â€” all via gateway)
   - PII detection + masking (spacy NER before any external call)
   - Token budget per tenant per month (configurable per subscription tier)
   - Response caching (Redis, key = SHA256(query + data_hash))
   - Retry logic with exponential backoff
   - Fallback chain (Claude â†’ GPT-4o â†’ DeepSeek â†’ Local)
   - Immutable call logging (input_hash, model, output_hash, tokens, cost, latency)
   - Streaming support (pass through to frontend)

2. MULTI-AGENT PIPELINE (backend/ai_gateway/pipeline.py):
   Temporal workflow: AIAnalysisPipeline

   Stage 1 â€” TaskPreparationAgent (always phi3:mini local):
   - Decompose complex task into atomic sub-tasks
   - Pull relevant context from DB (prior month data, mappings, standards)
   - Write structured prompt for execution agent (with expected output JSON schema)
   - Define validation rules for validator agent
   - Timeout: 2 seconds

   Stage 2 â€” ExecutionAgent (model per routing table):
   - Execute task using structured prompt from Stage 1
   - Return structured JSON per output schema
   - Include confidence score per field
   - Flag assumptions made
   - Timeout: 10 seconds

   Stage 3 â€” ValidationAgent (different model from Stage 2):
   - Re-derive answer independently (no access to Stage 2 reasoning)
   - Compare to Stage 2 output field by field
   - Compute agreement score (0-100%)
   - If score >= 95%: mark as validated, proceed to Stage 5
   - If score < 95%: trigger Stage 4
   - Timeout: 10 seconds

   Stage 4 â€” CorrectionAgent (Claude Opus â€” only when Stage 3 < 95%):
   - Review both Stage 2 and Stage 3 reasoning
   - Identify source of disagreement
   - Produce corrected output with explanation
   - If still uncertain: flag for human review
   - Log disagreement pattern as learning signal
   - Timeout: 15 seconds

   Stage 5 â€” OutputFormatter (always phi3:mini local):
   - Structure for UI display
   - Generate plain English explanation
   - Attach: confidence score, model chain used, assumptions
   - Prepare streaming chunks
   - Timeout: 2 seconds

   Speed optimisations:
   - Stage 1 starts while user is still typing (debounced 300ms)
   - Stage 3 starts as Stage 2 first tokens arrive (streaming validation)
   - Stage 5 streams to user token by token
   - Parallel execution where possible (asyncio.gather)

3. NATURAL LANGUAGE QUERY ENGINE (backend/ai_gateway/nlq.py):
   - User asks in plain English
   - Stage 1: understand intent, identify required data, write SQL query plan
   - Stage 2: generate SQL from query plan (text-to-SQL)
   - Stage 3: validate SQL (syntax, tenant isolation, no data leakage)
   - Execute SQL against DB
   - Stage 5: convert result to plain English + table/chart recommendation
   - Context window: maintain last 5 queries per session (follow-up questions work)
   - Ambiguity resolution: if intent unclear, ask clarifying question before executing

4. ACCOUNTING STANDARDS KNOWLEDGE GRAPH (backend/ai_gateway/standards.py):
   - PDF ingestion (PyMuPDF): extract text, tables, section structure
   - Build knowledge graph (nodes: standards, paragraphs, concepts, definitions)
   - Store in pgvector (embeddings per paragraph)
   - Query: semantic search â†’ retrieve relevant paragraphs â†’ augment prompt
   - Cross-LLM validation for standards questions (Claude + GPT-4o â†’ consensus)
   - Citation: every standards answer includes standard name + paragraph number

5. LEARNING PIPELINE (backend/ai_gateway/learning.py):
   - Signal capture: every AI interaction outcome (approved/modified/rejected)
   - Only approved, final outputs become learning signals
   - Signal metadata: industry, company_size, jurisdiction, erp, module, task_type
   - Tenant ID: SHA256 hashed (never raw)
   - Financial values: never stored (patterns and ratios only)
   - Nightly aggregation job (Celery Beat)
   - A/B testing framework for model improvements

6. AI SAFETY (backend/ai_gateway/safety.py):
   - Prompt injection scanner (regex + ML-based detection)
   - System prompt lockdown (hardcoded, not configurable by users)
   - Output validator (cross-check financial figures vs DB before rendering)
   - PII masker (spacy NER: names, emails, phone, account numbers)
   - Jailbreak detector + logger + alerter
   - Confidence threshold enforcer (below 60%: always ask human)

FRONTEND â€” Phase 4:
- Tab 1: Chat interface (streaming, context-aware, follow-up questions)
  - Message history with model chain shown
  - Confidence indicator (colour-coded)
  - "This is AI-generated â€” review before use" banner
  - ðŸ‘ / ðŸ‘Ž feedback on every response
- AI loading states (show which stage is running)
- Standards query: show paragraph citations
```

### Definition of Done â€” Phase 4
- [ ] Simple query answered in <2 seconds from local model
- [ ] Complex query answered in <8 seconds with validation score shown
- [ ] Stage 4 triggered and corrects disagreement between Stage 2 and Stage 3
- [ ] SQL generated from natural language, executed, result explained in English
- [ ] PII masked before external API call (verified in logs)
- [ ] Standards PDF uploaded, paragraph cited in answer
- [ ] Fallback: Claude API disabled â†’ GPT-4o answers correctly
- [ ] Learning signal captured for an approved classification

---

## Phase 5 â€” Contracts, People, Forecasting

### Claude Code Prompt â€” Phase 5

```
PHASE 5: Contracts, People Analytics, FP&A, and ERP

MODULE 1: Contract & Backlog Engine (backend/modules/contracts/)
- MSA/SOW/PO/WO register (hierarchical: MSA â†’ SOW â†’ PO â†’ WO, or flat)
- Upload (Excel/PDF â€” AI extracts key terms) or manual entry
- Backlog computation: contract value - recognised revenue = open balance
- Order book view: monthly burn schedule per customer
- Rate integrity check: contracted rate vs actual billing rate (flag discrepancies)
- Expiry alerts: 30/60/90 day warnings
- Intercompany contracts flagged separately

MODULE 2: Headcount & People Analytics (backend/modules/people/)
- Monthly HC movement: opening + joiners - leavers = closing (per entity, location, designation)
- Every exit: system asks "Voluntary or Involuntary?" + optional reason
- Classification changeable later with full audit trail
- Utilisation: billable hours / available hours per resource per month
- Seat cost methodology: flexible, retrospective application
- Attrition metrics: monthly rate, rolling 12M, annualised, by location/designation
- Cost of attrition computation
- Bench report: who is unbilled, for how long, at what cost

MODULE 3: Budgeting & Planning (backend/modules/budgeting/)
- Annual budget entry (by entity, by MIS line, by month)
- Budget versions (v1, v2, board-approved) â€” all append-only
- Board-approved version locked (cannot be changed without re-approval)
- Budget vs actual loaded automatically into all reports

MODULE 4: Forecasting & Scenarios (backend/modules/forecasting/)
- 3 revenue projection layers:
  Layer 1: Contracted backlog (certain)
  Layer 2: Run rate from actuals (last 3 months trend)
  Layer 3: Pipeline (probability-weighted, optional)
- 3 scenarios: Base (backlog + run rate), Upside (+pipeline at 70%), Downside (-attrition risk)
- Horizons: current quarter, next quarter, YTD, full year, 12M rolling
- Shortfall computation: projected vs budget â†’ gap â†’ "you need $X of new business"
- Backfill hints: AI suggests which customers to expand, which to renew
- Cost forecasting: fixed (straight-line) + variable (% of revenue) + committed (paysheets + POs)
- All in local currency + parent currency

MODULE 5: ERP Connectors (backend/modules/erp_connectors/)
- Base connector interface: {authenticate, pull_tb, pull_gl, pull_coa, push_journal}
- Implement connectors for:
  * Tally (XML API)
  * Zoho Books (REST API)
  * QuickBooks Online (OAuth2 + REST)
  * Xero (OAuth2 + REST)
  * SAP (RFC/BAPI)
  * Microsoft Dynamics 365 (OAuth2 + OData)
  * Sage (REST API)
  * Oracle NetSuite (SuiteAPI)
- On-demand pull (user clicks "Sync Now")
- Scheduled pull (Celery Beat â€” configurable per connector)
- ERP write-back: approved journals â†’ posted to ERP via API
  Approval gate: Manager review â†’ Finance Leader approve â†’ Post â†’ Confirm â†’ TB refresh

MODULE 6: Debt Covenant Compliance (backend/modules/debt_covenants/)
- Debt register (facility, lender, amount, drawn, rate, maturity, covenants)
- Covenant auto-computation from actuals (Net Debt/EBITDA, ICR, Current Ratio etc.)
- Headroom calculation and trend
- Projected covenant position using forecast engine
- Bank submission package auto-generation
- Breach alerts (approaching + actual)

MODULE 7: Working Capital & Cash Flow (backend/modules/cash_flow/)
- Working capital ratios (current, quick, cash)
- DSO, DPO, DIO, cash conversion cycle
- 13-week rolling cash flow forecast
- Expected inflows (invoice due dates, contract milestones)
- Expected outflows (payroll, rent, loan repayments, tax)
- Scenario: what if customer pays 30 days late?

MODULE 8: Compliance Calendar (backend/modules/compliance_calendar/)
- Pre-loaded compliance dates by jurisdiction
- User-added activities with due dates
- Task assignment with role (who is responsible)
- Status workflow: Not Started â†’ In Progress â†’ Under Review â†’ Completed
- Escalation: overdue â†’ auto-escalate to manager â†’ Finance Leader
- Integration with month-end workflow (completion of TB triggers MIS task)
- Export to iCal (Outlook + Google Calendar)
```

### Definition of Done â€” Phase 5
- [ ] Contract uploaded (PDF), key terms extracted by AI correctly
- [ ] Backlog burn schedule shows correct open balances
- [ ] Rate integrity: billing at $120/hr vs contract $115/hr â€” flagged correctly
- [ ] Headcount: joiner + leaver tracked, voluntary/involuntary recorded
- [ ] Forecast: shortfall computed, backfill hints generated
- [ ] QuickBooks connector pulls real TB data
- [ ] Journal entry approved and posted back to connected ERP
- [ ] Covenant computed correctly from actuals, breach alert triggered at threshold

---

## Phase 6 â€” Observability, Compliance, Reporting, Marketplace

### Claude Code Prompt â€” Phase 6

```
PHASE 6: Observability, Compliance, Reporting, and Marketplace

1. FOUNDER ANALYTICS DASHBOARD (apps/web/app/platform/analytics/)
   Real-time (WebSocket updates every 5 seconds):
   - Platform health: all services RAG status
   - Active tenants, users, sessions
   - Error rate + latest errors (file, line, stack trace, blast radius)
   - AI pipeline metrics (stage times, agreement rate, cost per model)
   - Worker queue depths (all 8 queues)
   - Cost per tenant (compute + storage + AI)
   Beautiful charts: Recharts + D3, dark theme option

2. MODULE / SERVICE / TASK HEALTH DASHBOARDS
   Module Dashboard: list of all modules, version, status, tenants using, health
   Service Dashboard: list of all services, uptime %, avg response, error rate, queue depth
   Task Dashboard: list of all tasks, success rate, avg duration, last run, dead letter count
   All: filterable, sortable, drillable
   Founder toggle: enable/disable any module/service/task at any level
   Every toggle: requires reason, shows blast radius preview, confirms, logs immutably

3. MONTH-END REPORT GENERATOR (backend/modules/reporting/)
   Generate complete 10-section PDF pack:
   Section 1: Executive Summary (KPIs, traffic lights, AI-written highlights)
   Section 2: P&L (consolidated, actual vs budget vs prior month vs prior year)
   Section 3: Revenue Analysis (customer-wise, region-wise, waterfall chart)
   Section 4: Cost Analysis (SG&A breakdown, contractor costs, seat cost)
   Section 5: Headcount & People (HC movement, attrition, utilisation)
   Section 6: Cash & Working Capital (ratios, 13-week forecast)
   Section 7: Contract & Backlog (order book, expiring contracts, rate exceptions)
   Section 8: Forecast (quarterly, full year, scenarios, backfill required)
   Section 9: Reconciliation Status (entity-level, IC recon, outstanding items)
   Section 10: Variance Commentary (AI-generated, Finance Leader edits before publish)

   PDF: WeasyPrint (HTMLâ†’PDF), formatted, logo, headers, footers, page numbers
   Excel: openpyxl, formatted, source file references in every sheet

   Auto-email distribution (SendGrid):
   - Full Board Pack â†’ CEO, Board, Finance Leader
   - Management Pack â†’ All Managers
   - Entity Pack â†’ Country Finance Lead (their entity only)
   Email body: 3 bullet summary, key charts embedded, full PDF attached

4. CONTROLS DASHBOARD (apps/web/app/platform/controls/)
   100% visibility of all controls:
   - Security controls (47)
   - SOC2 criteria (9 categories)
   - ISO 27001 Annex A (93 controls)
   - Financial controls (per module)
   - Operational controls
   RAG status per control, evidence link, last tested date
   Auto-evidence capture for all SOC2 criteria
   Auditor access: grant temporary read-only, auto-expire

5. DEPENDENCY MATRIX AUTO-GENERATOR
   GitHub Actions job on every merge:
   - Parse Python imports (ast module)
   - Parse SQLAlchemy model relationships
   - Build directed dependency graph
   - Detect circular dependencies (alert if found)
   - Generate DEPENDENCY_MATRIX.md
   - Update docs site

6. MARKETPLACE (backend/modules/marketplace/ + apps/web/app/marketplace/)
   - Template/connector/module listings
   - Contributor submission flow (Studio â†’ Validation â†’ Review â†’ Publish)
   - Automated validation checks (security, schema, completeness)
   - Revenue share engine (Stripe Connect for payouts)
   - Buyer: discovery, one-click install, version updates
   - Contributor: dashboard (sales, revenue, ratings, usage)
   - Trust badge system (Official, Verified Partner, Community)

7. PRICING ENGINE (backend/modules/pricing/)
   - Usage metering (API calls, storage GB, users, entities, modules)
   - Stripe Billing integration (subscription + metered)
   - Invoice generation
   - Failed payment handling (dunning)
   - Upgrade/downgrade workflow
   - Cost attribution per tenant (for your margin analysis)

8. BUSINESS NEWS TAB (apps/web/app/news/)
   - Pull from RSS feeds: Reuters, FT, ET, Mint, regulatory bodies
   - Filter by tenant's industry and jurisdictions
   - Regulatory updates section
   - Industry events section (with registration links)
   - Refresh every 4 hours (Celery Beat)
   - Source link always shown (never reproduce full article)
```

### Definition of Done â€” Phase 6
- [ ] Founder dashboard shows real-time health of all services
- [ ] Error in any service: file, line number, and blast radius shown in dashboard
- [ ] Month-end PDF pack generated for a test tenant (all 10 sections)
- [ ] Auto-email sent with PDF attached and charts in body
- [ ] Marketplace: template submitted, validated, published, installed by tenant
- [ ] Stripe: subscription created, invoice generated, usage metered
- [ ] Controls dashboard: all SOC2 criteria shown with evidence links
- [ ] Dependency matrix auto-generated correctly after a code change

---

## General Claude Code Instructions

### Before Starting Any Phase
```
Read the MASTER_BLUEPRINT.md first.
Read the current phase section of this IMPLEMENTATION_PLAN.md.
Read the ERROR_LEDGER.md to understand what has been built and any known issues.
Then build.
```

### FINOS_EXEC_PROMPT_TEMPLATE (v1.1)
```text
1. PROMPT METADATA
Prompt ID
Subsystem Name
System Layer
Purpose

2. IMPLEMENTATION MATURITY LEVEL
Phase 0 â€” foundation scaffolding
Phase 1 â€” internal validation
Production â€” hardened implementation

3. ROLE
"You are a senior backend engineer and financial systems architect implementing production-grade multi-tenant SaaS infrastructure."

4. REPOSITORY AWARENESS STEP
Before implementing anything:
- analyze repository structure
- inspect existing modules
- inspect migrations
- inspect dependencies
- review ledger history
- avoid duplicate components

5. SCOPE
Define exactly what subsystem must be implemented.

6. DEPENDENCIES
Specify:
- required subsystems
- build order constraints
- interface contracts

7. CONSTRAINTS
Enforce:
- strict tenant isolation
- append-only financial records
- idempotent operations
- secure secret management
- deterministic processing

7A. IDEMPOTENCY REQUIREMENTS

All mutation APIs must support idempotency keys.

Requests with the same idempotency_key must produce identical results.

Duplicate execution must not produce duplicate financial postings or duplicate side effects.

All financial mutation endpoints must enforce idempotency checks before executing business logic.

8. ARCHITECTURE REQUIREMENTS
Specify implementation details for:
- Database schema
- Services/modules
- APIs
- Background jobs
- Event-driven workflows

Financial values must use decimal arithmetic.

Floating point numbers must never be used for financial calculations.

All financial mutations must run inside explicit database transactions.

Ledger postings must use SERIALIZABLE or REPEATABLE READ isolation.

Partial financial state writes are prohibited.

9. INTERFACE CONTRACTS
All APIs must include:
- versioned endpoints (/api/v1/)
- backward compatibility rules
- deprecation policy

9A. EVENT CONTRACT STANDARD

All emitted platform events must follow the FINOS event envelope schema.

Required fields:

event_id
event_type
timestamp
tenant_id
correlation_id
producer_service
payload

Events must be versioned.

Breaking changes require event schema version upgrades.

Events must be immutable once published.

10. DATA MIGRATION STRATEGY
Schema changes must support zero-downtime migration.
Each prompt must define:
- expand phase
- migration/backfill phase
- contract phase
- rollback strategy

11. SECURITY REQUIREMENTS
Require:
- RBAC enforcement
- row-level security policies
- audit logging
- secrets protection

12. RELIABILITY REQUIREMENTS
Every subsystem must implement:
- rate limiting
- retry policies
- circuit breakers
- timeout management

13. OBSERVABILITY REQUIREMENTS
Require:
- structured logs
- metrics instrumentation
- distributed tracing

14. TESTING REQUIREMENTS
Every subsystem implementation must include:
- unit tests for services
- integration tests for APIs
- migration tests if schema changes
- idempotency tests where applicable

Test enforcement:
- tests must execute using pytest
- all new tests must pass
- entire repository pytest suite must pass
- validation command: pytest -q

15. TEST PERFORMANCE RULES
Tests must not hang or run excessively long:
- no indefinite blocking
- no infinite loops or waiting conditions
- practical CI runtime only

16. LEDGER UPDATE REQUIREMENTS
Append-only updates:
- IMPLEMENTATION_LEDGER.md
- PROMPTS_LEDGER.md
- SCHEMA_LEDGER.md (if schema changes)
- DEPENDENCIES_LEDGER.md (if dependencies change)
- FOLDERTREE_LEDGER.md (if structure changes)
- TODO_LEDGER.md (if tasks change)
- DECISIONS_LEDGER.md (if architectural decisions arise)
- KEY_CONSIDERATIONS_LEDGER.md (if risks are identified)

17. OUTPUT CONTRACT
Each implementation must return:
- files changed
- database migrations
- API contracts
- jobs/workflows created
- security validation checks
- observability instrumentation
- test plan and results
- confirmation that pytest suite is green
- ledger updates performed

18. DEFINITION OF DONE
A subsystem implementation is complete only when:
- all tests are implemented
- all tests pass
- full repository pytest suite passes
- no long-running tests exist
- ledger updates are appended

CI validation must pass before completion:
- pytest -q
- ruff or flake8 lint checks
- mypy type checking

If any of these fail, the subsystem implementation is considered incomplete.
```

### Code Standards to Enforce in Every Prompt
```
1. All Python: type hints, docstrings, Ruff-compliant, async where possible
2. All TypeScript: strict mode, JSDoc on exports, Zod validation on all API responses
3. All DB writes: through AuditWriter service, append-only on audit tables
4. All queries: tenant_id verified (RLS + application level)
5. All secrets: from environment variables (never hardcoded)
6. All errors: caught, logged to Sentry with correlation_id, graceful user-facing message
7. All AI calls: through AI Gateway only (never direct model calls from modules)
8. All tests: unit tests for business logic, integration tests for API endpoints
9. Conventional commits: feat:, fix:, docs:, refactor:, test:, chore:
10. No placeholder code, no TODOs, no incomplete functions
11. All mutation APIs: idempotency keys required and enforced before business logic
12. All events: FINOS event envelope fields required (event_id, event_type, timestamp, tenant_id, correlation_id, producer_service, payload)
13. Financial calculations: decimal arithmetic only, never floating point
14. Financial writes: explicit transactions, no partial commits
15. Ledger postings: SERIALIZABLE or REPEATABLE READ isolation
```

### After Completing Each Phase
```
1. Run pytest -q — must be 100% green
2. Update ERROR_LEDGER.md with what was built
3. Update DEPENDENCY_MATRIX.md
4. Update USER_MANUAL.md for any new user-facing features
5. Commit with conventional commit message
6. Run lint checks (ruff or flake8) — must pass
7. Run mypy type checking — must pass
8. Verify CI/CD pipeline passes
9. Deploy to Railway (backend) + Vercel (frontend)
10. Verify health checks pass on deployed environment
```

---

*End of Implementation Plan v1.0*

---

## Phase 5B â€” FDD, PPA, and M&A Modules

### Goal
Build the three premium advisory modules. These are the highest credit-cost, highest ROI modules on the platform. They consume platform data already collected and compile it into advisory-grade outputs.

### Claude Code Prompt â€” Phase 5B

```
PHASE 5B: Premium Advisory Modules

Build the following three modules. All follow Phase 0 patterns.
These modules are credit-intensive â€” deduct credits via the Credit Ledger
service before any task runs (reserve on start, deduct on completion,
release on cancellation or platform error).

MODULE 1: Financial Due Diligence (backend/modules/fdd/)

The FDD module compiles data already in the platform into a
professional FDD report. It does NOT require manual data entry â€”
it reads from: TB, GL, MIS, contracts, paysheets, headcount,
revenue recognition, working capital, and debt register.

1. FDD Compiler Service:
   - Pull 24 months of data from all connected modules
   - For each FDD section: AI Gateway (multi-agent pipeline) drafts the section
   - Each section tagged: GREEN (clean) / AMBER (needs verification) / RED (flag)
   - Finance Leader reviews section by section, edits AI draft, confirms

2. Sections to generate:
   a) Quality of Earnings (QoE)
      - LTM EBITDA computation (auto from P&L data)
      - One-off identification (AI suggests, user confirms)
      - Normalisation bridge (waterfall: reported â†’ adjusted â†’ normalised)
      - Pro forma adjustments

   b) Quality of Revenue
      - Customer concentration (HHI index computed)
      - Revenue type classification (recurring vs project vs one-time)
      - Contract coverage percentage
      - Churn analysis from customer data

   c) Working Capital Analysis
      - 24-month WC history (auto from TB)
      - Normalised WC peg (average of last 12 months, seasonality-adjusted)
      - AR/AP aging from GL data
      - WC bridge

   d) Debt & Debt-Like Items
      - Auto-pulled from: debt register, lease module (IFRS 16 liabilities),
        RevRec (deferred revenue), FAR (asset retirement obligations)
      - User adds: pension/gratuity, contingent liabilities (manual input)

   e) Net Debt Computation
      - Gross debt - Cash + Debt-like = Net Debt
      - Equity bridge table

   f) Headcount & People Diligence
      - Auto-pulled from People module (24 months)
      - Key person concentration: AI flags if >30% revenue linked to <3 people
      - Attrition analysis

   g) Contracts & Commercial
      - Auto-pulled from Contract module
      - Expiry risk profile
      - Customer concentration in contracts

   h) Financial Controls Assessment
      - Reconciliation quality score (from recon history)
      - Assumptions quality (how many overrides vs AI suggestions)

3. Output generation:
   - PDF: WeasyPrint, professional layout, indexed, paginated, branded
   - Excel: full supporting workbooks, all schedules
   - Every number has source reference (hover to see TB line / GL entry)
   - Word export option (python-docx)

4. Credit deduction:
   - Basic FDD (sections a-e): 1,000 credits â€” reserve on start
   - Comprehensive FDD (all sections): 2,500 credits â€” reserve on start
   - Cancelled before completion: release reservation
   - Platform error: release reservation + auto-retry

MODULE 2: Purchase Price Allocation (backend/modules/ppa/)

IFRS 3 / ASC 805 / IND AS 103 compliant PPA engine.

1. Input collection (combination of auto-pulled + user input):
   - Consideration: cash, deferred (NPV auto-computed), earn-out
     (probability-weighted), equity
   - Target balance sheet: upload Excel/CSV â†’ auto-parsed
   - Fair value adjustments: user inputs per asset class
   - Intangibles identification: AI suggests based on industry + business type

2. Valuation methods per intangible:
   Customer relationships: MEEM
   - Inputs: revenue, margins, churn rate (auto-pulled from platform data
     if acquiring company's customer data is available)
   - Outputs: fair value, useful life (default 5-10 years)

   Trade name / Brand: Relief from Royalty
   - Inputs: revenue, royalty rate (industry benchmark suggested by AI)
   - Output: fair value, useful life (default 10-20 years)

   Technology / IP: Relief from Royalty or Cost approach
   - User selects method
   - Inputs: revenue/replacement cost, royalty rate, remaining useful life

   Order backlog: auto-pulled from Contract & Backlog module if available
   - Fair value = remaining contract value Ã— margin % (net of fulfillment costs)

3. Deferred tax:
   - DTL = identified intangibles Ã— applicable tax rate (user inputs rate)
   - Net goodwill adjusted for DTL

4. Goodwill computation:
   - Purchase price âˆ’ Net FV assets âˆ’ Identified intangibles + DTL = Goodwill
   - Goodwill impairment testing template generated (IAS 36 / ASC 350)

5. Output:
   - Full PPA schedule (Excel, all workings shown)
   - Day-1 journal entries (Dr/Cr for every asset and liability)
   - Intangible amortisation schedules â†’ auto-fed into FAR module
   - IFRS 3 disclosure notes (Word/PDF)

6. Credits: 1,500 reserved on start, deducted on completion

MODULE 3: M&A Workspace (backend/modules/ma_workspace/)

Isolated deal workspace. No data crossover with operational entities.

1. Deal management:
   - Deal register CRUD
   - Stage tracking with workflow: Origination â†’ NDA â†’ IOI â†’ DD â†’ LOI â†’ Exclusivity â†’ Close
   - Stage gate: each stage requires approval before advancing
   - Document vault: upload NDAs, IOIs, LOIs, SPA â€” secure, version-controlled

2. Target financial analysis:
   - Upload target financials (Excel) â†’ auto-normalise to platform MIS structure
   - Comparable company data (user inputs or web search via AI)
   - LTM/NTM profile auto-computed

3. Valuation engine:
   DCF model:
   - Revenue/margin/capex/D&A projections (user inputs, AI suggests based on comparables)
   - WACC computation (risk-free rate + beta + ERP + size premium + company premium)
   - Terminal value (Gordon Growth and Exit Multiple methods)
   - Enterprise Value â†’ Equity Value bridge

   Comparable companies:
   - User inputs comparable company multiples
   - EV/EBITDA, EV/Revenue, P/E applied to LTM and NTM metrics

   Football field chart:
   - Visual range across all valuation methods
   - Recharts waterfall + range chart

   Sensitivity tables:
   - WACC vs Terminal Growth Rate â†’ EV matrix
   - Revenue growth vs EBITDA margin â†’ EV matrix

4. DD tracker:
   - Workstream: Financial, Legal, Tax, Commercial, HR, IT, Technology
   - PBC list: items sent to target, status tracking, overdue flagged
   - Finding log: issue, severity (Critical/High/Medium/Low), deal impact, resolution
   - Red flag report: auto-compiled from Critical + High findings

5. Post-close:
   - "Close Deal" action â†’ triggers PPA module
   - Creates new Organisation in core platform
   - Imports target financials as historical data for that org
   - Integration tracker: 100-day plan, synergy tracking

FRONTEND for all three modules:
- New section in navigation: "Advisory" (visible only if module enabled)
- FDD: step-by-step wizard (select period, select sections, review each, approve, export)
- PPA: guided input form with live computation preview as values entered
- M&A: deal card view (kanban by stage) + deal detail page
- All: beautiful, professional â€” these are the most visible outputs to clients
```

### Definition of Done â€” Phase 5B
- [ ] FDD: upload 24 months of TB/GL â†’ full QoE section generated with AI commentary
- [ ] FDD: normalisation bridge shows correct waterfall (reported â†’ normalised EBITDA)
- [ ] FDD: PDF output professional-quality with source references on every number
- [ ] PPA: MEEM computation for customer relationships correct (manual verification)
- [ ] PPA: Goodwill computed correctly (verified against manual calculation)
- [ ] PPA: Amortisation schedules auto-fed into FAR module correctly
- [ ] M&A: Deal moves through all stages with approval gates working
- [ ] M&A: DCF model computes EV correctly (verified against manual model)
- [ ] M&A: Football field chart renders correctly
- [ ] Credits: reserved on start, deducted on completion, released on cancel/error

---

## Phase 7 â€” Credits, Payments, and Billing

### Goal
Full credit system with multi-gateway payment processing and 70%+ margin enforcement.

### Claude Code Prompt â€” Phase 7

```
PHASE 7: Credits, Payments, and Billing Engine

Build the complete credit and payment infrastructure.

1. CREDIT LEDGER (backend/modules/credits/)

Credit record model (append-only):
- tenant_id, org_id, user_id
- transaction_type: SUBSCRIPTION_ALLOCATION | TOPUP | RESERVATION |
  DEDUCTION | RELEASE | EXPIRY | REFUND | ADJUSTMENT
- credits: positive (credit) or negative (debit)
- task_id: linked task (for deductions/reservations/releases)
- payment_id: linked payment (for allocations/topups)
- expires_at: for allocated/topup credits (3 months from allocation)
- created_at, created_by
- running_balance: computed field (sum of all transactions to date)

NEVER UPDATE OR DELETE credit records â€” append only.

Credit balance computation:
available = sum of all credits WHERE expires_at > NOW() AND NOT reserved
reserved = sum of RESERVATION transactions without matching DEDUCTION or RELEASE
expired = sum of credits WHERE expires_at <= NOW() AND NOT deducted

2. TASK CREDIT ENFORCEMENT (backend/credits/enforcer.py)

Pre-task check:
def check_and_reserve_credits(tenant_id, task_type, task_id) -> bool:
  cost = CREDIT_COST_TABLE[task_type]
  available = get_available_credits(tenant_id)
  if available < cost:
    raise InsufficientCreditsError(available=available, required=cost)
  create_reservation(tenant_id, task_id, cost)
  return True

Post-task deduction:
def deduct_credits(task_id, status):
  if status == "COMPLETED":
    convert_reservation_to_deduction(task_id)
  elif status in ["CANCELLED", "FAILED_PLATFORM_ERROR"]:
    release_reservation(task_id)
  elif status == "FAILED_USER_ERROR":
    release_reservation(task_id)  # user not charged for their own errors either
    # reconsider this policy â€” some platforms charge partial

CREDIT_COST_TABLE = {
  "gl_tb_reconciliation": 5,
  "consolidation_single_entity": 3,
  "consolidation_multi_entity": 10,
  "ai_query_simple": 2,
  "ai_query_complex": 8,
  "paysheet_process": 5,
  "erp_sync": 10,
  "contract_parse_ai": 8,
  "covenant_compliance": 5,
  "forecast_3_scenarios": 15,
  "variance_analysis_ai": 12,
  "revenue_recognition": 8,
  "month_end_pdf_pack": 25,
  "board_pack": 30,
  "standards_query": 15,
  "mis_backward_propagation": 20,
  "fdd_basic": 1000,
  "fdd_comprehensive": 2500,
  "ppa_full": 1500,
  "ma_workspace_setup": 500,
  "valuation_engine_full": 500,
  "dd_tracker_setup": 200,
}

3. PAYMENT GATEWAY ABSTRACTION (backend/payments/)

Base interface â€” all gateways implement this:
class PaymentGateway(ABC):
  def create_order(amount, currency, metadata) -> Order
  def verify_payment(payment_id, signature) -> bool
  def create_subscription(plan_id, customer_id) -> Subscription
  def cancel_subscription(subscription_id) -> bool
  def handle_webhook(payload, headers) -> WebhookEvent

Implement:
- StripeGateway (USA, UK, AUS, Singapore, UAE â€” default international)
- RazorpayGateway (India â€” primary for IN tenants)
- TelrGateway (UAE, Saudi, Bahrain, Kuwait, Oman, Qatar)
- PayUGateway (India backup)

Gateway routing:
def get_gateway(tenant_country: str) -> PaymentGateway:
  if tenant_country == "IN": return RazorpayGateway()
  if tenant_country in ["AE","SA","BH","KW","OM","QA"]: return TelrGateway()
  return StripeGateway()

4. SUBSCRIPTION MANAGEMENT

Subscription tiers:
STARTER:      500 credits/month   $49/month
PROFESSIONAL: 2000 credits/month  $149/month
BUSINESS:     8000 credits/month  $449/month
ENTERPRISE:   custom              negotiated

On subscription payment confirmed (webhook):
- Allocate monthly credits to tenant (with 3-month expiry)
- Send confirmation email
- Update subscription status in DB

On subscription renewal (monthly):
- Gateway webhook fires â†’ allocate new month credits
- Previous month unused credits: check if within 3-month window (keep) or expired (zero out)

Proration on upgrade:
- Upgrade mid-month â†’ charge prorated difference
- Allocate additional credits immediately (prorated)

5. TOP-UP PACKAGES
500 credits   $45
2000 credits  $160
5000 credits  $350
20000 credits $1,200

On top-up payment confirmed:
- Add credits with 3-month expiry
- Send receipt email

6. CREDITS DASHBOARD (frontend)

Real-time credit display (WebSocket updates):
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  CREDITS                                             â”‚
â”‚                                                      â”‚
â”‚  Available:    1,847  â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘â–‘â–‘  (74%)       â”‚
â”‚  Reserved:        45  â–ˆâ–ˆâ–‘â–‘             (2%)         â”‚
â”‚  Used (month):   608                                 â”‚
â”‚  Expiring soon:  200  (in 28 days)                  â”‚
â”‚                                                      â”‚
â”‚  [Buy Credits]  [View Usage]  [Set Alert]           â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

Usage breakdown table:
- Task name, count, credits used, date range filter
- Export to Excel

Low credit alert:
- Finance Leader sets threshold (e.g. 200 credits)
- Email sent when balance crosses threshold
- In-app banner when <100 credits

Zero credit state:
- All RUN buttons disabled
- Tooltip: "Insufficient credits â€” top up to continue"
- Top banner: "You have 0 credits remaining"
- Read/view/download of existing data: always enabled
- [Buy Credits] CTA prominently displayed

7. MARGIN MONITORING (platform admin dashboard)

For each tenant show:
- Credits consumed this month
- Revenue from credits (subscription + top-up)
- Estimated AI cost (from AI Gateway cost logs)
- Estimated compute cost (from Railway usage)
- Estimated gross margin %
- Alert if any tenant's margin drops below 65%

8. PRICING PAGES (frontend)

Subscription page (app.yourplatform.com/pricing):
- 4 tier comparison table
- Monthly/annual toggle (annual = 2 months free)
- Feature comparison per tier
- "Most Popular" badge on Professional
- FAQ section

Top-up page (in-app, when credits low):
- 4 package options
- Current balance shown
- Estimated tasks achievable with each package
  ("500 credits = ~20 month-end reconciliations or 1 basic FDD report")
- Instant purchase flow (Stripe/Razorpay embedded)

FRONTEND CHECKLIST:
- Credits widget visible on every page (top nav, compact)
- Credits dashboard as dedicated page
- Pricing page (public, no auth required)
- Payment success/failure pages
- Subscription management page (upgrade, downgrade, cancel)
- Invoice history page (download PDF invoices)
```

### Definition of Done â€” Phase 7
- [ ] Credit reserve/deduct/release cycle works correctly (verified in DB)
- [ ] Task with 0 credits: RUN button disabled, correct error shown
- [ ] Task cancelled: credits released, balance unchanged
- [ ] Platform error on task: credits released automatically
- [ ] Stripe: subscription created, webhook fires, credits allocated
- [ ] Razorpay: Indian tenant pays via UPI, credits allocated correctly
- [ ] Top-up: payment confirmed, credits visible in dashboard immediately
- [ ] Credit expiry: credits older than 3 months marked expired (Celery Beat job)
- [ ] Margin monitor: shows correct estimated margin per tenant
- [ ] Low credit alert: email sent when threshold crossed
- [ ] Annual subscription: correct 2-month discount applied


---

## Phase 1B â€” CFO Tier 1 Modules

### Goal
Four modules every CFO needs immediately. Build these alongside or immediately after Phase 1 core. These drive daily login, stickiness, and justify the subscription alone.

### Claude Code Prompt â€” Phase 1B

```
PHASE 1B: CFO Tier 1 Modules

Build the following four modules. All follow Phase 0 patterns.
Tenant isolation, audit trail, append-only writes, credits enforced on all tasks.

MODULE 1: Bank Reconciliation (backend/modules/bank_recon/)

1. Upload bank statement:
   - Accept CSV or PDF
   - PDF: use pdfplumber to extract transaction table
   - CSV: parse with pandas, normalise columns
     (date, description, debit, credit, balance)
   - Store raw transactions in bank_statement_transactions table
   - Append-only, immutable after upload

2. Pull GL cash account:
   - User selects GL account (cash/bank account)
   - Pull all transactions for same period from GL data

3. Auto-matching engine:
   - Match on: amount (exact) + date (Â± 3 calendar days)
   - For each bank transaction: find matching GL entry
   - Confidence score: exact date + exact amount = 100%
   - Near match (date Â± 1-3 days): 80-95%
   - Unmatched: 0% â€” presented to user for manual matching

4. Bank reconciliation statement output:
   Classic format:
   Balance per bank statement:              X
   Add: Deposits in transit:                X
   Less: Outstanding cheques:              (X)
   Adjusted bank balance:                   X
   â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   Balance per GL:                          X
   Add: Bank interest not in books:         X
   Less: Bank charges not in books:        (X)
   Adjusted GL balance:                     X
   â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
   Difference (must be zero):               0 âœ…

5. One-click journal entries:
   - Bank charges: Dr Bank Charges / Cr Bank Account
   - Interest: Dr Bank Account / Cr Interest Income
   - User confirms â†’ posted to adjustment ledger

6. Credits: 5 per bank account per reconciliation run

MODULE 2: Working Capital Dashboard (backend/modules/working_capital/)

1. AR Aging computation:
   - Pull all open AR invoices from GL/ERP
   - Compute age in days from invoice date
   - Bucket: current, 1-30, 31-60, 61-90, 90+ days
   - Per customer breakdown
   - DSO: (Average AR / Revenue) Ã— Days in period

2. AP Aging computation:
   - Same structure for payables
   - DPO: (Average AP / COGS) Ã— Days in period

3. Cash Conversion Cycle:
   CCC = DSO + DIO (if inventory) - DPO
   12-month trend chart

4. Collections intelligence:
   - Payment probability score per overdue invoice:
     Uses: customer's historical payment pattern,
           invoice age, amount, customer segment
   - AI drafts dunning email (local model, personalised per customer)
   - Escalation flag: >60 days overdue â†’ alert Finance Leader

5. WC Forecast (4 weeks):
   - Inflows: open AR invoices Ã— payment probability Ã— expected date
   - Outflows: open AP invoices Ã— due dates
   - Net cash position per week

6. Credits: 0 (always free â€” drives daily login)

MODULE 3: GST Reconciliation (backend/modules/gst_recon/)

India-specific but architecture supports UAE VAT and Singapore GST.

1. GSTR-2B ingestion:
   - Accept GSTR-2B JSON (downloaded from GST portal) or Excel
   - Parse: supplier GSTIN, invoice number, date, taxable value,
     IGST, CGST, SGST, eligible ITC
   - Store in gst_2b_transactions table

2. Purchase register from GL:
   - Pull all purchase/expense entries with GST from GL
   - Extract: vendor name, invoice number, date, amount, GST amount
   - Match by: invoice number + vendor GSTIN + approximate amount

3. Reconciliation engine:
   - Matched: invoice in both GSTR-2B and books âœ…
   - In 2B only: ITC available but not claimed in books â†’ post entry
   - In books only: claimed ITC not in 2B â†’ ITC at risk, vendor not filed
   - Amount mismatch: same invoice, different amount â†’ flag

4. Outputs:
   - Reconciliation report (matched, unmatched, mismatched)
   - ITC mismatch summary (how much ITC at risk per vendor)
   - Vendor non-compliance report (not filed in GSTR-1)
   - Auto-draft vendor communication (AI, local model)
   - GSTR-3B computation: output tax - eligible ITC = tax payable

5. For UAE VAT and Singapore GST:
   - Same architecture, different tax rates and form names
   - Configure per tenant jurisdiction

6. Credits: 20 per GST reconciliation run

MODULE 4: Scenario Modelling (backend/modules/scenarios/)

1. Scenario definition:
   User defines named scenario with one or more adjustments:
   Types of adjustments:
   - Revenue change: "Revenue -15%" or "Add customer X at â‚¹2Cr, 45% margin"
   - Cost change: "Add 20 headcount at â‚¹12L avg CTC"
   - FX change: "USD/INR rate 90 instead of 84"
   - Entity change: "Remove Entity Y from group"
   - One-off: "Add â‚¹50L exceptional item in Q3"

2. Computation engine:
   - Start from current approved MIS/forecast data
   - Apply each adjustment in sequence
   - Recompute: full P&L, key BS items, cash flow impact
   - Show impact: absolute change + % change per line item

3. Comparison view:
   - Side by side: Base | Scenario 1 | Scenario 2 | Scenario 3
   - Bridge chart: base EBITDA â†’ adjustments â†’ scenario EBITDA
   - Traffic light: green (improvement), red (deterioration)

4. AI commentary (cloud model â€” this needs nuanced language):
   "In Scenario 2 (FX stress), EBITDA margin compresses from 18% to
    14.2% driven primarily by USD cost exposure in your technology
    and infrastructure spend (62% USD-denominated). 
    Consider natural hedging by increasing USD-billed revenue contracts."

5. Export:
   - Excel: full workings, all three scenarios, bridge chart
   - PDF: board-ready one-pager per scenario

6. Credits: 15 per scenario run

MONTH-END CLOSING CHECKLIST (backend/modules/close_checklist/)

This is the home screen for Finance Leaders during close.
Build it simple but build it right.

1. Checklist template:
   Pre-loaded standard tasks:
   T-5: ERP data frozen, TB extracted
   T-4: Payroll entries posted
   T-3: Accruals and provisions posted
   T-2: IC transactions confirmed with all entities
   T-1: Reconciliations completed (GL/TB + bank)
   T+0: MIS prepared and reviewed
   T+1: Consolidation run and reviewed
   T+2: Variance analysis and commentary complete
   T+3: Board pack generated
   T+5: Board pack approved and distributed

2. Customisation:
   - Add/remove/rename tasks
   - Assign responsible user per task
   - Set due date relative to period-end (T-5, T+3, etc.)
   - Set dependencies (task B blocked until task A complete)

3. Automated triggers:
   - ERP sync completes â†’ auto-check "TB available"
   - Reconciliation approved â†’ auto-check "Reconciliation complete"
   - Report generated â†’ auto-check "Report generated"
   - Report approved â†’ auto-check "Board pack approved"

4. Progress tracking:
   - % complete overall
   - Which tasks are overdue (red)
   - Which tasks are at risk (amber â€” due today)
   - Bottleneck identification: longest-running incomplete task

5. Historical analytics:
   - Average close time per month (trend chart)
   - Which tasks are consistently late (process improvement signal)
   - Target close day vs actual (month over month)

6. Notifications:
   - Task assigned: notify responsible user
   - Task overdue: notify responsible user + Finance Leader
   - All tasks complete: notify Finance Leader + trigger board pack prompt

7. Credits: 0 (always free)

FRONTEND for all Phase 1B modules:
- Bank Recon: upload area + matching review table + recon statement
- WC Dashboard: aging tables + DSO/DPO charts + collections queue
- GST Recon: reconciliation table with match status + mismatch summary
- Scenario Modelling: scenario builder + side-by-side comparison + bridge chart
- Closing Checklist: Kanban-style board (by week) + progress bar + timeline
```

### Definition of Done â€” Phase 1B
- [ ] Bank recon: upload bank statement, auto-match >80% of transactions
- [ ] Bank recon: recon statement balances (difference = 0) on test data
- [ ] WC dashboard: AR aging correct (verified manually on sample data)
- [ ] WC dashboard: DSO computed correctly (formula verified)
- [ ] GST recon: GSTR-2B upload parsed correctly
- [ ] GST recon: matched vs unmatched report accurate on test data
- [ ] Scenario: FX scenario recomputes P&L correctly (manual verification)
- [ ] Scenario: export Excel contains all three scenarios side by side
- [ ] Closing checklist: automated triggers fire correctly
- [ ] Closing checklist: progress % updates in real time
- [ ] All modules: credits deducted correctly (or zero where specified)
- [ ] All modules: audit trail written for every action


---

## Phase 6B â€” Backup, Standby & Peak Load Infrastructure

### Claude Code Prompt â€” Phase 6B

```
PHASE 6B: Backup, Standby Deployment, and Peak Load Management

Build the infrastructure reliability layer.

1. AUTOMATED BACKUP SYSTEM (infra/backup/)

PostgreSQL continuous WAL archiving:
  - Configure postgresql.conf:
      wal_level = replica
      archive_mode = on
      archive_command = 'aws s3 cp %p s3://financeops-wal-archive/%f
                         --endpoint-url https://[R2_ENDPOINT]'
  - WAL archives to Cloudflare R2 continuously

Daily snapshot job (Celery Beat â€” 02:00 UTC):
  def daily_backup():
      timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
      # 1. pg_dump â†’ compressed
      run_command(f'pg_dump {DB_URL} | gzip > /tmp/backup_{timestamp}.sql.gz')
      # 2. Encrypt with tenant-agnostic master key
      encrypt_file(f'/tmp/backup_{timestamp}.sql.gz')
      # 3. Upload to R2
      upload_to_r2(f'/tmp/backup_{timestamp}.sql.gz.enc',
                   f'backups/daily/backup_{timestamp}.sql.gz.enc')
      # 4. Verify backup
      verify_backup(timestamp)
      # 5. Clean up old backups per retention policy
      cleanup_old_backups()

Backup verification job (runs after every backup):
  def verify_backup(timestamp):
      # Restore to test DB instance
      restore_to_test_db(timestamp)
      # Check row counts match production
      assert get_row_counts(TEST_DB) == get_row_counts(PROD_DB)
      # Verify chain hash integrity
      verify_chain_hashes(TEST_DB)
      # Mark backup as verified
      mark_backup_verified(timestamp)
      # Alert if fails
      if not verified:
          send_alert(severity="P1", message="Backup verification failed")

R2 versioning and cross-region replication:
  Configure via Cloudflare R2 API:
  - Enable versioning on primary bucket
  - Enable replication to secondary region bucket
  - Soft delete: 30-day retention on deleted objects

2. STANDBY DEPLOYMENT (infra/standby/)

PostgreSQL streaming replication setup:
  Primary postgresql.conf additions:
    max_wal_senders = 3
    wal_keep_size = 1GB

  Standby recovery.conf:
    standby_mode = on
    primary_conninfo = 'host=PRIMARY_HOST ...'
    restore_command = 'aws s3 cp s3://wal-archive/%f %p ...'

  Standby runs as hot standby (readable replica).

Cloudflare failover configuration:
  - Health check: GET /api/v1/health every 10 seconds
  - Failover threshold: 3 consecutive failures
  - Failover action: route all traffic to standby
  - Notification: PagerDuty webhook on failover

Blue-Green deployment script (deploy.sh):
  1. Deploy new version to STANDBY
  2. Run smoke tests: curl standby /health, /api/v1/health/deep
  3. If tests pass: cloudflare_switch_traffic(to="standby")
  4. Monitor for 5 minutes
  5. Deploy to old PRIMARY (now receiving no traffic)
  6. Verify old primary healthy
  7. Standby is now new PRIMARY

Daily 00:00 UTC sync verification (Celery Beat):
  def daily_standby_check():
      lag = get_replication_lag_seconds()
      if lag > 60:
          send_alert(severity="P2", message=f"Replication lag: {lag}s")
      chain_hash_ok = verify_standby_chain_hashes()
      send_daily_infra_report(lag=lag, chain_hash_ok=chain_hash_ok)

3. PEAK LOAD MANAGEMENT (backend/infrastructure/peak_load.py)

Predictive auto-scaling (Celery Beat â€” runs daily at 08:00 UTC):
  def check_and_scale():
      day = datetime.utcnow().day
      month_days = get_days_in_current_month()

      is_peak = day >= 25 or day <= 8

      if is_peak and day >= 25:
          scale_factor = 2
      elif is_peak and day <= 8:
          scale_factor = 3
      else:
          scale_factor = 1

      set_railway_worker_count('api', BASE_API_WORKERS * scale_factor)
      set_railway_worker_count('celery', BASE_CELERY_WORKERS * scale_factor)
      toggle_read_replicas(enabled=is_peak)
      pause_low_priority_queue(paused=is_peak)

Priority queue routing middleware:
  QUEUE_PRIORITY = {
      'dashboard_refresh': 'critical_q',
      'ai_chat': 'critical_q',
      'reconciliation': 'high_q',
      'consolidation': 'high_q',
      'report_generation': 'high_q',
      'erp_sync': 'normal_q',
      'email': 'normal_q',
      'fdd_generation': 'low_q',
      'vector_update': 'low_q',
      'analytics': 'low_q',
  }

  def route_task(task_type: str, **kwargs):
      queue = QUEUE_PRIORITY.get(task_type, 'normal_q')
      # During peak, check if low_q is paused
      if queue == 'low_q' and is_peak_period():
          queue = 'normal_q'  # bump up or schedule for overnight
      return task.apply_async(queue=queue, **kwargs)

Queue depth monitoring + wait time estimation:
  def get_estimated_wait_time(queue_name: str) -> int:
      depth = get_queue_depth(queue_name)
      avg_task_duration = get_avg_task_duration(queue_name)
      workers = get_active_workers(queue_name)
      return int((depth / workers) * avg_task_duration)

  # Show in frontend: "Estimated wait: 3 minutes"

Scheduled task reservation:
  POST /api/v1/tasks/schedule
  Body: { task_type, params, scheduled_for: "2025-03-31T02:00:00Z" }
  Celery: eta parameter
  Frontend: "Schedule for tonight at 2am" button during peak period

Aggressive caching (Redis â€” extend TTLs during peak):
  def get_cache_ttl(data_type: str) -> int:
      base_ttls = {
          'dashboard': 300,      # 5 minutes
          'fx_rates': 3600,      # 1 hour
          'mis_template': 86400, # 24 hours
      }
      ttl = base_ttls.get(data_type, 300)
      if is_peak_period():
          ttl = ttl * 3  # triple all TTLs during peak
      return ttl

Tenant staggering preference:
  Add to tenant settings:
    preferred_close_day: enum(28, 29, 30, last_day, 1, 2, 3)
  Dashboard: show "Close on 28th for fastest processing this month"
  During peak: show tenant their preferred slot and estimated wait time

4. MONITORING (additions to existing telemetry):
   - Replication lag gauge (alert > 60 seconds)
   - Backup success/failure counter (alert on any failure)
   - Queue depth per queue (all 4 queues)
   - Peak mode active indicator
   - Standby health status
   - Cache hit rate (alert if < 40% during peak)

DEFINITION OF DONE:
[ ] WAL archiving: transactions appear in R2 within 5 minutes
[ ] Daily backup: runs at 02:00 UTC, verified, alert if fails
[ ] Backup restore: tested restore completes in < 30 minutes
[ ] Streaming replication: standby lag < 5 seconds in normal operation
[ ] Failover: simulate primary failure â†’ traffic moves to standby < 60 seconds
[ ] Blue-green deploy: zero-downtime deployment verified
[ ] Peak scaling: workers scale up correctly on day 25 trigger
[ ] Priority queues: critical tasks complete < 30 seconds even with 500 queued tasks
[ ] Scheduled tasks: task scheduled for 02:00 AM runs correctly
[ ] Cache TTL: triples during peak period (verified in Redis)
[ ] Daily health report: email received at 00:30 UTC with all metrics
```

---

## Phase 1C â€” Expense Management (Full)

### Claude Code Prompt â€” Phase 1C

```
PHASE 1C: Full Expense Management Module

Build complete expense lifecycle. All patterns from Phase 0 apply.

1. DATABASE SCHEMA (backend/modules/expenses/)

CREATE TABLE expense_claims (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    employee_id     UUID NOT NULL REFERENCES users(id),
    claim_date      DATE NOT NULL,
    total_amount    DECIMAL(18,2) NOT NULL,
    currency        VARCHAR(3) NOT NULL,
    base_amount     DECIMAL(18,2),
    status          VARCHAR(30) DEFAULT 'draft',
    -- draft/submitted/manager_approved/finance_approved/paid/rejected
    submitted_at    TIMESTAMPTZ,
    manager_approved_at   TIMESTAMPTZ,
    manager_id      UUID REFERENCES users(id),
    finance_approved_at   TIMESTAMPTZ,
    finance_user_id UUID REFERENCES users(id),
    rejected_at     TIMESTAMPTZ,
    rejection_reason TEXT,
    gl_account_id   UUID,
    cost_centre     VARCHAR(100),
    gst_itc_eligible BOOLEAN DEFAULT FALSE,
    gst_itc_amount  DECIMAL(18,2),
    payment_method  VARCHAR(30),
    paid_at         TIMESTAMPTZ,
    notes           TEXT,
    -- append-only
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE expense_line_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id        UUID NOT NULL REFERENCES expense_claims(id),
    tenant_id       UUID NOT NULL,
    line_date       DATE NOT NULL,
    category        VARCHAR(100) NOT NULL,
    vendor_name     VARCHAR(200),
    vendor_gstin    VARCHAR(20),
    description     TEXT,
    amount          DECIMAL(18,2) NOT NULL,
    currency        VARCHAR(3) NOT NULL,
    receipt_url     TEXT,
    ocr_extracted   BOOLEAN DEFAULT FALSE,
    ocr_confidence  DECIMAL(5,4),
    policy_status   VARCHAR(20) DEFAULT 'pass',
    -- pass/soft_flag/hard_block
    policy_flags    JSONB,
    gl_account_id   UUID,
    project_id      UUID,
    gst_amount      DECIMAL(18,2),
    gst_itc_eligible BOOLEAN,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE expense_policy_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    rule_name       VARCHAR(200),
    category        VARCHAR(100),
    grade           VARCHAR(50),      -- null = all grades
    max_amount      DECIMAL(18,2),
    rule_type       VARCHAR(20),      -- soft/hard
    description     TEXT,
    active          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE expense_advances (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    employee_id     UUID NOT NULL,
    amount          DECIMAL(18,2) NOT NULL,
    currency        VARCHAR(3),
    purpose         TEXT,
    issued_at       TIMESTAMPTZ,
    settled_at      TIMESTAMPTZ,
    claim_id        UUID REFERENCES expense_claims(id),
    status          VARCHAR(20) DEFAULT 'outstanding',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

2. RECEIPT OCR (backend/modules/expenses/ocr.py)
   - Accept: image (JPEG/PNG) or PDF single page
   - Pillow: resize to optimal OCR resolution (300 DPI equivalent)
   - easyocr: extract text from image
   - Parse extracted text:
       amount: regex for currency amounts
       vendor: first line or company name pattern
       date: date pattern detection
       GST number: GSTIN format validation (15-char alphanumeric)
       invoice number: invoice/bill number pattern
   - Confidence score per extracted field
   - Return: pre-filled form fields + confidence scores
   - Low confidence (<0.7) field: shown to user for manual confirmation

3. POLICY ENGINE (backend/modules/expenses/policy.py)
   - Load tenant's policy rules on claim submission
   - Check each line item against applicable rules
   - Return: pass / soft_flag (with message) / hard_block (with reason)
   - Duplicate detection:
       same employee, same amount, same vendor, date Â± 3 days
   - Cross-employee duplicate: same receipt amount + vendor + date
     from two different employees
   - Weekend/holiday flag: check against tenant holiday calendar

4. APPROVAL WORKFLOW (backend/modules/expenses/workflow.py)
   - Tier routing based on amount (configurable per tenant)
   - Celery tasks for SLA monitoring:
       24h reminder to approver
       48h auto-escalation
   - Approval notification: email + in-app

5. GL CODING (backend/modules/expenses/gl_coding.py)
   - AI suggestion: Stage 1 local model
     Input: vendor name + category + historical mappings
     Output: suggested GL account (with confidence)
   - GST ITC determination:
       Map category to ITC eligibility rules
       Entertainment: 50% ITC
       Personal expenses: 0% ITC
       Business travel: 100% ITC
       etc.
   - TDS applicability flag

6. ANALYTICS (backend/modules/expenses/analytics.py)
   - Aggregations: by category, department, employee, project
   - Budget vs actual per department (links to budget module)
   - GST ITC recovered this month
   - Policy violation rate
   - Average approval time

7. API ENDPOINTS:
   POST /api/v1/expenses/claims               Submit new claim
   POST /api/v1/expenses/claims/{id}/lines    Add line items
   POST /api/v1/expenses/receipts/ocr         OCR a receipt
   PATCH /api/v1/expenses/claims/{id}/submit  Submit for approval
   PATCH /api/v1/expenses/claims/{id}/approve Manager/Finance approve
   PATCH /api/v1/expenses/claims/{id}/reject  Reject with reason
   GET   /api/v1/expenses/claims              List claims (role-filtered)
   GET   /api/v1/expenses/analytics           Analytics dashboard data
   GET   /api/v1/expenses/policy/check        Check item against policy

DEFINITION OF DONE:
[ ] Receipt OCR extracts amount + vendor + date with >80% accuracy on test set
[ ] Policy engine flags duplicate submissions correctly
[ ] Approval workflow routes to correct approver by amount tier
[ ] GL coding AI suggests correct account >85% on test set
[ ] Budget check integration: real-time vs budget module
[ ] GST ITC computation correct (verify against manual calculation)
[ ] Analytics: spend by category totals match sum of line items
[ ] Credits: 2 deducted per batch processed
```

---

## Phase 6C â€” AI Benchmarks & Model Fallback

### Claude Code Prompt â€” Phase 6C

```
PHASE 6C: AI Accuracy Benchmarks and Model Fallback Chain

1. BENCHMARK TEST SUITE (tests/ai_benchmarks/)

Create benchmark framework:

tests/ai_benchmarks/
â”œâ”€â”€ __init__.py
â”œâ”€â”€ run_benchmarks.py          # main runner
â”œâ”€â”€ datasets/
â”‚   â”œâ”€â”€ classification_test_set.json    # 500 GL â†’ MIS mappings
â”‚   â”œâ”€â”€ reconciliation_test_set.json    # 200 break scenarios
â”‚   â”œâ”€â”€ commentary_test_set.json        # 50 MIS + fact expectations
â”‚   â””â”€â”€ forecast_test_set.json          # historical periods + actuals
â””â”€â”€ evaluators/
    â”œâ”€â”€ classification_evaluator.py
    â”œâ”€â”€ reconciliation_evaluator.py
    â”œâ”€â”€ commentary_evaluator.py
    â””â”€â”€ forecast_evaluator.py

Dataset format (classification_test_set.json):
[
  {
    "gl_account": "4100 - Employee Salaries",
    "gl_description": "Monthly salary payments to permanent staff",
    "expected_mis_line": "Employee Cost - Salaries",
    "expected_category": "People Cost",
    "industry": "IT_services"
  },
  ...500 items across 5 industries
]

Evaluator pattern:
class ClassificationEvaluator:
    async def evaluate(self, test_set: list) -> EvalResult:
        correct_top1 = 0
        correct_top3 = 0
        for item in test_set:
            result = await ai_gateway.classify(
                gl_account=item["gl_account"],
                description=item["gl_description"],
                top_k=3
            )
            if result.predictions[0] == item["expected_mis_line"]:
                correct_top1 += 1
            if item["expected_mis_line"] in result.predictions[:3]:
                correct_top3 += 1
        return EvalResult(
            top1_accuracy=correct_top1/len(test_set),
            top3_accuracy=correct_top3/len(test_set),
            sample_size=len(test_set)
        )

run_benchmarks.py:
  Runs all evaluators, writes benchmark_report_{date}.json
  Compares vs previous week's report
  If any metric drops >3%: send P2 alert

Celery Beat: run weekly (Sunday 03:00 UTC)

2. MODEL FALLBACK CHAIN (backend/ai_gateway/fallback.py)

Implement ModelFallbackChain class as specified in Master Blueprint
Section 52 exactly.

Additional requirements:
- Fallback chain config in settings (not hardcoded):
  FALLBACK_CHAINS = {
      "classification": [...],
      "variance_analysis": [...],
      ...
  }
  Allows updating chains without code deploy.

- Circuit breaker per model:
  If model fails 3 times in 5 minutes:
    â†’ mark as "circuit_open" for 10 minutes
    â†’ skip directly to next model (don't retry)
    â†’ alert P3
  After 10 minutes: try again ("half_open")
  If succeeds: "circuit_closed" (normal operation)

  class CircuitBreaker:
      def __init__(self, failure_threshold=3, timeout=600):
          self.failures = {}  # model_name â†’ failure count
          self.circuit_state = {}  # model_name â†’ open/closed/half_open
          self.last_failure_time = {}

- Fallback metrics in Prometheus:
  model_fallback_total (counter, labels: task_type, from_model, to_model, reason)
  model_circuit_state (gauge, labels: model_name)
  model_availability_pct (gauge, labels: model_name, provider)

3. GOOGLE GEMINI INTEGRATION (backend/ai_gateway/providers/gemini.py)
   pip add google-generativeai
   Implement as additional provider in AI Gateway
   Models: gemini-1.5-pro, gemini-1.5-flash
   Add to fallback chains as tertiary cloud provider

DEFINITION OF DONE:
[ ] Classification benchmark: runs on 500 test items, >92% top-1 accuracy
[ ] Reconciliation benchmark: runs on 200 scenarios, >95% identification
[ ] Commentary: fact-check passes 100% on test set
[ ] Weekly benchmark job: scheduled, outputs report, alerts on regression
[ ] Fallback chain: simulate each model failure â†’ verify fallback triggers
[ ] Circuit breaker: 3 failures â†’ circuit opens â†’ fallback used â†’ auto-recover
[ ] Grafana: fallback rate visible per task type
[ ] Gemini: integrated as tertiary cloud option in all chains
```

---

## Phase 6D â€” Grafana Dashboards & ClickHouse

### Claude Code Prompt â€” Phase 6D

```
PHASE 6D: Grafana Dashboards and ClickHouse Analytics

1. CLICKHOUSE SETUP (docker-compose.yml addition)

clickhouse:
  image: clickhouse/clickhouse-server:24.3
  ports:
    - "8123:8123"
    - "9000:9000"
  volumes:
    - clickhouse_data:/var/lib/clickhouse
    - ./infra/clickhouse/init.sql:/docker-entrypoint-initdb.d/init.sql
  environment:
    CLICKHOUSE_DB: financeops_analytics
    CLICKHOUSE_USER: analytics
    CLICKHOUSE_PASSWORD: ${CLICKHOUSE_PASSWORD}

infra/clickhouse/init.sql:
  Run all CREATE TABLE statements from Master Blueprint Section 55 exactly.
  Add indexes:
  -- Fast tenant-level analytics
  CREATE INDEX idx_events_tenant ON events (tenant_id_hash, created_at);
  CREATE INDEX idx_pipeline_runs_task ON ai_pipeline_runs (task_type, created_at);

2. EVENT TRACKING (backend/telemetry/product_events.py)

ClickHouse client:
  pip add clickhouse-connect

class ProductAnalytics:
    def __init__(self):
        self.client = clickhouse_connect.get_client(
            host=settings.CLICKHOUSE_HOST,
            user=settings.CLICKHOUSE_USER,
            password=settings.CLICKHOUSE_PASSWORD,
        )

    async def track(self, event: ProductEvent):
        # Hash tenant and user IDs before storing
        self.client.insert('events', [[
            str(uuid4()),
            sha256(event.tenant_id),
            sha256(event.user_id),
            event.session_id,
            event.event_name,
            event.event_category,
            event.module,
            event.feature,
            json.dumps(event.properties),
            event.credits_used,
            event.duration_ms,
            event.device_type,
            datetime.utcnow()
        ]])

Frontend tracking (middleware):
  Every route change, module open, and task run calls:
  POST /api/v1/telemetry/event
  Body: { event_name, module, feature, properties }
  Async (fire and forget, never blocks user)

3. GRAFANA SETUP (infra/grafana/)

docker-compose addition:
  grafana:
    image: grafana/grafana:11.0.0
    ports: ["3001:3000"]
    volumes:
      - grafana_data:/var/lib/grafana
      - ./infra/grafana/provisioning:/etc/grafana/provisioning
      - ./infra/grafana/dashboards:/var/lib/grafana/dashboards
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"

Datasource provisioning files:
  infra/grafana/provisioning/datasources/prometheus.yaml:
    apiVersion: 1
    datasources:
    - name: Prometheus
      type: prometheus
      url: http://prometheus:9090
      isDefault: true

  infra/grafana/provisioning/datasources/clickhouse.yaml:
    apiVersion: 1
    datasources:
    - name: ClickHouse
      type: grafana-clickhouse-datasource
      url: http://clickhouse:8123
      jsonData:
        defaultDatabase: financeops_analytics

  infra/grafana/provisioning/datasources/loki.yaml:
    apiVersion: 1
    datasources:
    - name: Loki
      type: loki
      url: http://loki:3100

Create all 5 dashboard JSON files in infra/grafana/dashboards/
as specified in Master Blueprint Section 55.
Each dashboard auto-loads on Grafana startup.

4. BUSINESS METRICS PIPELINE

Nightly job (Celery Beat 00:05 UTC):
  compute_daily_business_metrics() as specified in doc 08
  Write to: PostgreSQL business_metrics_daily (source of truth)
  Replicate to: ClickHouse business_metrics_daily (for Grafana)

5. ALERTING RULES (infra/grafana/provisioning/alerting/)

Key alerts as code (not manual Grafana config):
  - API error rate > 5% for 5 minutes â†’ P1
  - Queue depth > 100 for 5 minutes â†’ P2
  - DB connections > 80% for 5 minutes â†’ P1
  - AI fallback rate > 10% â†’ P2
  - Replication lag > 60 seconds â†’ P1

DEFINITION OF DONE:
[ ] ClickHouse running in docker-compose
[ ] All 4 tables created from schema in Section 55
[ ] Event tracking: frontend sends events, appear in ClickHouse within 60s
[ ] Grafana running, all 5 dashboards visible on startup
[ ] Prometheus metrics flowing into Grafana infrastructure dashboard
[ ] Business metrics computed nightly, visible in Grafana by 01:00 UTC
[ ] Alerting: simulate high error rate â†’ Slack notification received
[ ] ClickHouse query: activation funnel returns correct data on test events
```

---

## Phase 2A â€” HR Module Core (Reminder: Start After 20 Finance Customers)

```
PLACEHOLDER â€” Full prompt to be written when Finance Phase 0-6 complete.
Architecture fully defined in:
  Master Blueprint Sections 3-17 (HR)
  Document 09 Sections 1-9 (HR detailed spec)
  Document 09 Section 10 (API contracts)

Pre-requisites before starting:
  [ ] Finance platform Phase 0-6 complete
  [ ] 20 paying Finance customers
  [ ] First customer has used platform for 3+ months
  [ ] HR module pricing validated with at least 3 potential customers
```

---

## Phase 3A â€” Sales Intelligence (Reminder: Start After HR Module Stable)

```
PLACEHOLDER â€” Full prompt to be written when HR module Phase 2A-2B complete.
Architecture fully defined in:
  Master Blueprint sections (Sales Intelligence)
  Document 09 Sections 6-8 (Sales detailed spec)
  Document 09 Section 11 (API contracts)

Pre-requisites before starting:
  [ ] HR module stable (3+ months in production)
  [ ] Sales module pricing validated with CROs/Sales Leaders
  [ ] At least 1 pilot customer committed to Sales module
```

---

## Phase 0 Addition â€” Environment Parity Check

```
BEFORE WRITING ANY CODE â€” VERIFY ENVIRONMENT PARITY:

Development, Staging, and Production must be identical in:
  â”œâ”€â”€ Python version (3.12.x â€” exact minor version)
  â”œâ”€â”€ All library versions (pinned in pyproject.toml)
  â”œâ”€â”€ PostgreSQL version (16.x)
  â”œâ”€â”€ Redis version (7.x)
  â”œâ”€â”€ Environment variables structure (all keys present, values differ)
  â””â”€â”€ Docker image versions (all services)

ENVIRONMENT PARITY CHECKLIST:
  â–¡ pyproject.toml committed with exact pinned versions
  â–¡ docker-compose.yml uses exact image tags (not :latest)
  â–¡ .env.example lists ALL required env vars (no values)
  â–¡ Doppler has dev/staging/prod configs with same key structure
  â–¡ Railway: staging environment mirrors production service config
  â–¡ Verify: uv run python --version matches across all envs

DRIFT PREVENTION:
  Pre-commit hook: check pyproject.toml has no unpinned versions
  (no ">=", no "~=", no "*" â€” exact versions only)
  
  Weekly: automated check that staging DB schema matches production
  Alert if drift detected.
```

---

## Phase 1 Addition â€” Closing Checklist Bank Recon Integration

```
INTEGRATION: Bank Reconciliation â†’ Closing Checklist

When all bank accounts for a period are reconciled:
  Closing checklist task "Bank Reconciliation Complete" 
  auto-checks itself.

Implementation:
  In bank_recon service, after all accounts reconciled for period:
  
  async def on_all_accounts_reconciled(tenant_id, period):
      await checklist_service.auto_complete_task(
          tenant_id=tenant_id,
          period=period,
          task_key="bank_reconciliation_complete"
      )

Same pattern for all auto-checkable tasks:
  ERP sync complete    â†’ auto-check "TB Available"
  GL recon approved    â†’ auto-check "GL Reconciliation Complete"
  Consolidation run    â†’ auto-check "Consolidation Complete"
  Board pack approved  â†’ auto-check "Board Pack Distributed"
```

---

## Phase 4 Addition â€” AI Prompt Version Management

```
IMPLEMENT IN PHASE 4 (when AI pipeline is fully built):

1. Create ai_prompt_versions table (schema in Master Blueprint Section 70)

2. Migrate all hardcoded prompts to database:
   Script: scripts/migrate_prompts_to_db.py
   For each task type: INSERT first version into ai_prompt_versions
   Mark as active: is_active = TRUE

3. Update AI Gateway to load prompts from DB:
   Replace all hardcoded system_prompt strings with:
   system_prompt = await load_active_prompt('task_key')
   
   Cache in Redis with 5-minute TTL.

4. Admin endpoint (internal only, founder access):
   GET  /internal/prompts                  list all prompt keys + versions
   GET  /internal/prompts/{key}            get all versions for a key
   POST /internal/prompts/{key}/activate/{version}  activate a version
   POST /internal/prompts/{key}/create     create new version

5. Prompt rollback procedure:
   If new prompt causes acceptance drop:
   POST /internal/prompts/classification_stage2/activate/2
   (activates version 2, deactivates current version 3)
   Takes effect within 5 minutes (Redis TTL)

DEFINITION OF DONE:
[ ] Zero hardcoded prompts in application code
[ ] All prompts loadable from DB with Redis cache
[ ] Rollback tested: activate old version â†’ verify it takes effect
[ ] Admin endpoint secured (internal network only, founder MFA)
```

---

## Phase 5 Addition â€” Data Retention Policy Implementation

```
IMPLEMENT IN PHASE 5 (storage and compliance phase):

Tenant-configurable auto-deletion for source files:

Settings option per tenant:
  "Auto-delete uploaded source files after: [Never / 3 months / 6 months / 12 months / 24 months]"
  Default: Never (user must opt in to auto-deletion)
  
  Note: Generated reports and audit trail are NEVER auto-deleted
        regardless of this setting.
  Note: Processed data is retained even if source file is deleted.

Celery Beat job (monthly, 1st of month 03:00 UTC):
  def auto_delete_old_source_files():
      tenants = get_tenants_with_retention_policy()
      for tenant in tenants:
          cutoff = now() - tenant.source_file_retention_months
          old_files = get_source_files_older_than(tenant.id, cutoff)
          for file in old_files:
              delete_from_r2(file.r2_key)
              mark_file_deleted(file.id)  # soft delete in DB
              log_deletion_to_audit_trail(file.id, reason="retention_policy")
  
  Notify tenant: "X source files auto-deleted per your retention policy"
  Storage usage updates immediately after deletion.
```

---

## Phase 6 Addition â€” Self-Healing Verification Tests

```
ADD TO PHASE 6 DEFINITION OF DONE:

Self-healing verification (run in staging before production deploy):

TEST 1: Worker auto-restart
  â–¡ Kill a FastAPI worker process: docker kill financeops-api-1
  â–¡ Verify: Railway/Docker restarts it within 60 seconds
  â–¡ Verify: No requests lost (load balancer routes to other workers)
  â–¡ Verify: Alert fired (P2 container restart alert)

TEST 2: Celery worker recovery
  â–¡ Kill a Celery worker mid-task
  â–¡ Verify: Task returns to queue (not lost)
  â–¡ Verify: New worker picks up and completes the task
  â–¡ Verify: No duplicate execution (idempotency check)

TEST 3: Redis failure and recovery
  â–¡ Stop Redis: docker stop financeops-redis
  â–¡ Verify: API falls back gracefully (no 500 errors, just cache misses)
  â–¡ Verify: Celery stops processing (expected â€” Redis is the broker)
  â–¡ Restart Redis: docker start financeops-redis
  â–¡ Verify: Celery resumes processing queued tasks
  â–¡ Verify: Cache rebuilds from DB within 5 minutes

TEST 4: DB connection pool exhaustion
  â–¡ Simulate: open 100 connections simultaneously
  â–¡ Verify: PgBouncer queues new connections (no crash)
  â–¡ Verify: Requests complete once connections free up
  â–¡ Verify: Alert fires at 80% pool utilisation

TEST 5: Standby failover
  â–¡ Stop primary DB
  â–¡ Verify: Cloudflare routes traffic to standby within 60 seconds
  â–¡ Verify: Data correct on standby (replication lag was < 30s)
  â–¡ Verify: Founder receives P0 alert
  â–¡ Restore primary and fail back

All tests must pass before Phase 6 is marked complete.
```

