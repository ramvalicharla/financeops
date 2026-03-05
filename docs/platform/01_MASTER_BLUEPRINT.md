# FinanceOps Platform â€” Master Blueprint
> Version 1.0 | Status: Locked | Classification: Confidential
> Last Updated: 2025-03-02 | Owner: Platform Founder

---

## Table of Contents
1. [Vision & Principles](#1-vision--principles)
2. [Platform Philosophy](#2-platform-philosophy)
3. [Complete Module Register](#3-complete-module-register)
4. [Tech Stack â€” Every Layer](#4-tech-stack--every-layer)
5. [Architecture â€” Zero State + Zero Trust](#5-architecture--zero-state--zero-trust)
6. [Multi-Tenant Data Architecture](#6-multi-tenant-data-architecture)
7. [AI / LLM Intelligence Layer](#7-ai--llm-intelligence-layer)
8. [Security Architecture](#8-security-architecture)
9. [Observability & Analytics](#9-observability--analytics)
10. [Compliance & Governance](#10-compliance--governance)
11. [Immutability Architecture](#11-immutability-architecture)
12. [Document Ecosystem](#12-document-ecosystem)
13. [Marketplace Architecture](#13-marketplace-architecture)
14. [Living Documentation System](#14-living-documentation-system)
15. [Platform Portals](#15-platform-portals)
16. [Service Register](#16-service-register)
17. [Module Register](#17-module-register)
18. [Task Register](#18-task-register)
19. [Dependency Matrix Design](#19-dependency-matrix-design)
20. [Controls Dashboard](#20-controls-dashboard)

---

## 1. Vision & Principles

### Vision Statement
FinanceOps is a self-improving, AI-native, enterprise finance operating system that consolidates multi-entity, multi-currency, multi-geography financial operations into a single intelligent platform. It gets smarter with every transaction, faster with every task, and more valuable with every tenant.

### What We Are Building
A category-defining SaaS platform that replaces:
- Manual Excel-based consolidation
- Disconnected ERP exports
- Expensive BI tools (PowerBI, Tableau)
- Siloed FP&A software (Anaplan, Adaptive Insights)
- Fragmented compliance tracking
- Manual month-end reporting

With a single, intelligent, auditable, certifiable platform accessible to CFOs, CA firms, and finance teams globally.

### Core Principles

| Principle | Definition |
|---|---|
| **Zero State** | No server holds session or memory between requests. Every component stateless. Scale to zero. Pay nothing when idle. |
| **Zero Trust** | Every request verified independently. No implicit trust. Frontend, modules, APIs â€” all treat each other as untrusted. |
| **Immutable by Design** | No source data ever modified. Append-only everywhere. Every change creates a new version. Full audit trail always. |
| **Human in the Loop** | AI suggests. Human approves. Nothing actioned without explicit human confirmation. Legal protection layer. |
| **Local First** | Sensitive data processed locally. Cloud used only when needed. Platform works fully offline. |
| **Graceful Degradation** | Every external dependency has a fallback. Platform never fully breaks. Always informs user clearly. |
| **Transparency Always** | Every assumption published. Every AI output explained. Every change attributed. Nothing hidden. |
| **Compounding Intelligence** | Every approved action is a learning signal. Platform gets smarter over time. Network effect moat. |
| **Certifiable** | Every design decision made with SOC2, ISO27001, GDPR, DPDP, HIPAA in mind from day one. |
| **No Tech Headache** | Maximum 3 levels of service dependency. Every dependency has a fallback. Stability over novelty. |

---

## 2. Platform Philosophy

### Who Uses This Platform

| User Type | Who They Are | What They Need |
|---|---|---|
| **Platform Founder** | You | Full visibility, control, analytics, business metrics |
| **Tenant Admin (CFO)** | Group CFO / CA Firm Partner | All entities, all data, approve and publish |
| **Finance Manager** | Senior Finance | Corrections, reclassifications, submissions |
| **Reviewer** | Senior Accountant | Review, flag, comment |
| **Data Entry â€” Payroll** | Payroll Team | Upload paysheets only |
| **Data Entry â€” GL/TB** | Accounts Team | Upload GL, TB, ERP exports |
| **Executive / CEO** | C-Suite | Clean dashboard, KPIs, no raw data |
| **Auditor** | External Auditor | Read-only evidence access |
| **CA Firm Partner** | Professional Firm | All clients, team management |
| **CA Firm Associate** | Junior Staff | Assigned clients only |
| **Client (of CA Firm)** | End Client | Own data portal only |
| **Marketplace Contributor** | Template Designers | Studio access, revenue share |
| **Implementation Consultant** | Partners | Tenant configuration, sandbox |

### Three Tenant Types
1. **Corporate Group** â€” Multiple legal entities, one consolidation
2. **Professional Firm (CA/CPA)** â€” Multiple clients, team assignments
3. **SME / Individual** â€” Single entity, simple setup

---

## 3. Complete Module Register

### Base Platform (Always Present)
| Module | Description | Version |
|---|---|---|
| Authentication & RBAC | JWT, OAuth2, MFA, role management | 1.0 |
| Multi-Tenancy Engine | Tenant isolation, provisioning, lifecycle | 1.0 |
| Audit Trail | Append-only, chain-hash, tamper-evident | 1.0 |
| Security Layer | 7-layer security, Airlock, injection protection | 1.0 |
| Document Ecosystem | Drive, OneDrive, Dropbox, SharePoint, Box | 1.0 |
| AI Gateway | Multi-model routing, cost control, PII masking | 1.0 |
| Learning Engine Core | Signal capture, metadata, privacy-safe | 1.0 |
| Notification Engine | Email, in-app, mobile push, alerts | 1.0 |
| News & Events | Business news, regulatory updates, events | 1.0 |
| Compliance Calendar | Deadlines, tasks, assignments, escalations | 1.0 |
| Global Search | Cmd+K universal search across all data | 1.0 |
| Controls Dashboard | 100% control visibility, RAG status | 1.0 |

### Finance Modules (Standalone, Plug-in)
| Module | Standard | Description |
|---|---|---|
| MIS Manager | â€” | Template learning, versioning, backward propagation |
| GL/TB Reconciliation | â€” | Entity-level recon, IC matching, FX separation |
| Multi-Currency Consolidation | IAS 21 | 8+ currencies, IC elimination, FX rates |
| Classification Engine | â€” | AI GLâ†’MIS mapping, retrospective reclassification |
| Paysheet Engine | â€” | Country paysheets, location rollup, FX conversion |
| Fixed Asset Register | IAS 16 / IFRS 16 | Depreciation, disposal, impairment, revaluation |
| Prepaid Schedule | â€” | Amortisation, balance tracking, TB recon |
| Subscription Tracker | â€” | SaaS/service tracking, renewal alerts, cost/user |
| Lease Accounting | IFRS 16 / ASC 842 | ROU assets, lease liability, modifications |
| Revenue Recognition | IFRS 15 / ASC 606 | 7 methods: PoC, milestone, straight-line, etc. |
| SG&A Schedules | â€” | Rent, insurance, professional fees, IT schedules |
| Debt Covenant Compliance | â€” | Covenant tracking, bank submissions, breach alerts |
| Working Capital & Cash Flow | â€” | Ratios, 13-week forecast, cash position |
| Tax Provision & Position | IAS 12 | Current tax, deferred tax, effective rate |
| Intercompany Billing | OECD TP | Management fees, cost allocations, transfer pricing |
| Budgeting & Planning | â€” | Annual budget, versions, board-approved |
| Forecasting & Scenarios | â€” | 3 scenarios, multi-horizon, backfill intelligence |
| Contract & Backlog | â€” | MSA/SOW/PO/WO lifecycle, order book, rate integrity |
| Headcount & People | â€” | HC analytics, utilisation, attrition, seat cost |
| Customer P&L & Margins | â€” | Customer-wise revenue, cost, margin analysis |
| Variance Analysis | â€” | Quantitative + qualitative AI commentary |
| ERP Connectors | â€” | 7 ERPs + open connector, pull + push |
| ERP Migration Readiness | â€” | Assessment, gap analysis, action plan |
| Accounting Standards AI | â€” | PDF ingestion, knowledge graph, cross-LLM validation |
| Audit Management | â€” | PBC tracker, auditor portal, query log |
| Board & Investor Reporting | â€” | Board pack, investor format, KPI definitions |
| Document Generation | â€” | Auto-generate letters, certificates, e-signature |
| Whistleblower Channel | â€” | Anonymous reporting, SOC2 control |
| Pricing Engine | â€” | Usage metering, invoicing, Stripe/Razorpay integration |

### Premium Advisory Modules (High-Value, Credit-Intensive)
| Module | Standard | Description | Credits |
|---|---|---|---|
| Financial Due Diligence (FDD) | IFRS / GAAP | Auto-compile QoE, revenue quality, WC analysis, debt, people diligence from platform data | 1,000â€“2,500 |
| Purchase Price Allocation (PPA) | IFRS 3 / ASC 805 | Identify intangibles, fair value adjustments, goodwill computation, amortisation schedules | 1,500 |
| M&A Workspace | â€” | Deal register, valuation engine (DCF/comps/LBO), DD tracker, integration planning, synergy tracking | 500 setup + usage |

### Credits & Payments System
| Component | Description |
|---|---|
| Credit Ledger | Real-time credit balance, reservations, usage, expiry per tenant |
| Payment Gateway Abstraction | Routes to correct gateway by tenant country |
| Razorpay | India â€” UPI, netbanking, cards, EMI |
| Stripe | USA, UK, Australia, Singapore, UAE â€” international cards |
| Telr | UAE, Saudi Arabia, MENA â€” local payment methods |
| PayU | India backup + Middle East |
| Credit Packages | Subscription (monthly allocation) + Top-up (Ã  la carte) |
| Zero-on-zero | No credits = no service runs (reads/views always free) |

---

## 4. Tech Stack â€” Every Layer

### Frontend â€” Web
```
Framework:        Next.js 14 (App Router)
Language:         TypeScript (strict mode)
UI Library:       shadcn/ui + Tailwind CSS
Charts:           Recharts + D3.js
Tables:           TanStack Table v8
Forms:            React Hook Form + Zod
State:            Zustand
Server State:     TanStack Query v5
Auth UI:          NextAuth.js v5
Real-time:        Server-Sent Events + WebSockets
Deployment:       Vercel
Package Manager:  pnpm
Testing:          Vitest + Playwright
Linting:          ESLint + Prettier
```

### Backend â€” API
```
Framework:        FastAPI (Python 3.12)
Language:         Python 3.12
Task Queue:       Celery 5 + Redis 7
Workflow:         Temporal (durable multi-step workflows)
Scheduler:        Celery Beat
WebSockets:       FastAPI WebSockets
Auth:             JWT (python-jose) + OAuth2
Validation:       Pydantic v2
API Docs:         Auto-generated OpenAPI / Swagger
Deployment:       Railway (MVP) â†’ AWS ECS (scale)
Package Manager:  uv (fastest Python package manager)
Testing:          pytest + httpx
Linting:          Ruff + mypy
```

### Database Layer
```
Primary DB:       PostgreSQL 16
Extensions:       pgvector, TimescaleDB, pg_audit
Cache:            Redis 7 (cache + queues + pub/sub)
Search:           PostgreSQL FTS â†’ Elasticsearch (at scale)
File Storage:     Cloudflare R2 (S3-compatible)
Object Lock:      Cloudflare R2 Object Lock (immutability)
Local (offline):  SQLite + SQLCipher (encrypted)
Migrations:       Alembic
ORM:              SQLAlchemy 2.0 (async)
Connection Pool:  PgBouncer
```

### AI / LLM Layer
```
Local Inference:  Ollama
Local Models:     phi3:mini, Mistral 7B, DeepSeek 6.7B, LLaMA 3.1 8B
Cloud Primary:    Claude API (claude-sonnet-4-5, claude-opus-4-5)
Cloud Secondary:  OpenAI API (gpt-4o, gpt-4o-mini)
Cloud Tertiary:   DeepSeek API (deepseek-chat)
Fast Cloud:       Groq API (LLaMA 3.1 70B â€” ultra fast inference)
Embeddings:       sentence-transformers (local) + text-embedding-3-small (cloud)
Vector DB:        pgvector on PostgreSQL
Document AI:      PyMuPDF + pdfplumber + EasyOCR
Orchestration:    Temporal workflows for all AI pipelines
```

### Desktop Application
```
Framework:        Tauri 2.0 (Rust + WebView)
UI:               Same Next.js frontend (100% reused)
Local AI:         Ollama (bundled)
Local DB:         SQLite + SQLCipher
Sync:             Background sync when online
OS Support:       Windows 10/11, macOS 12+
Packaging:        NSIS (Windows), DMG (macOS)
Auto-Update:      Tauri updater
```

### Mobile Application
```
Phase 1:          Progressive Web App (PWA)
Phase 2:          React Native + Expo
UI:               NativeWind (Tailwind for React Native)
Push:             Firebase Cloud Messaging
```

### Security Infrastructure
```
Edge Security:    Cloudflare (WAF, DDoS, Bot, Rate Limit, Tunnel, Access)
Secrets:          Doppler (secret management)
Encryption:       AES-256 (at rest), TLS 1.3 (in transit)
File Scanning:    ClamAV + python-magic
Rate Limiting:    slowapi + Redis
Dependency Scan:  Dependabot + Snyk
SAST:             Semgrep
```

### DevOps & Observability
```
Version Control:  GitHub (private)
CI/CD:            GitHub Actions
Containers:       Docker + Docker Compose
Error Tracking:   Sentry
Metrics:          Prometheus + Grafana
Logging:          Loki + Grafana
Tracing:          OpenTelemetry + Tempo
Uptime:           BetterUptime (public status page)
Alerting:         Grafana Alerting â†’ Slack + Email
```

### Documentation
```
API Docs:         Auto-generated (FastAPI OpenAPI)
Code Docs:        Sphinx (Python) + TypeDoc (TypeScript)
User Manual:      Docusaurus (auto-updated via GitHub Actions)
Changelog:        Conventional Commits + auto-generated
Schema Docs:      Auto-generated from SQLAlchemy models
Hosting:          docs.yourplatform.com (Vercel)
```

---

## 5. Architecture â€” Zero State + Zero Trust

### Full Architecture Diagram
```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    CLOUDFLARE EDGE                           â”‚
â”‚  WAF | DDoS | Bot Protection | Rate Limiting                â”‚
â”‚  Cloudflare Workers (edge middleware)                        â”‚
â”‚  Cloudflare Access (portal protection)                       â”‚
â”‚  Cloudflare Tunnel (no exposed public IPs)                  â”‚
â”‚  Cloudflare R2 (file storage + object lock)                 â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                           â”‚ Zero Trust â€” every request verified
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    MIDDLEWARE LAYER                           â”‚
â”‚  1. JWT Verification        5. Audit Logging                â”‚
â”‚  2. Tenant Resolution       6. Prompt Injection Scan        â”‚
â”‚  3. Rate Limit Check        7. Response Sanitisation        â”‚
â”‚  4. Request Validation      8. Correlation ID Injection     â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                           â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    CONTROL PLANE                             â”‚
â”‚  Tenant Lifecycle | Module Registry | Feature Flags         â”‚
â”‚  Quota Management | Health Monitoring | Config Store        â”‚
â”‚  Billing Events   | Onboarding Automation                   â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
           â”‚                            â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”    â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚   FASTAPI CORE       â”‚    â”‚      TEMPORAL ORCHESTRATOR       â”‚
â”‚   (stateless)        â”‚    â”‚   Multi-step workflow engine     â”‚
â”‚   Zero State         â”‚    â”‚   Crash-safe, durable execution  â”‚
â”‚   REST + WebSocket   â”‚    â”‚   AI pipelines, month-end close  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜    â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
           â”‚                            â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                         REDIS 7                              â”‚
â”‚  Task Queues | Response Cache | Pub/Sub | Rate Limit State  â”‚
â”‚  file_scan_q | parse_q | erp_sync_q | report_q | ai_q      â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
           â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                    WORKER POOL (Stateless)                   â”‚
â”‚  File Scanner | Parser | ERP Connector | Report Generator   â”‚
â”‚  Email Worker | AI Worker | Notification | Learning          â”‚
â”‚  All stateless â€” pull from Redis â€” scale to zero            â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
           â”‚
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                      DATA LAYER                              â”‚
â”‚  PostgreSQL 16 (RLS + pgvector + TimescaleDB)               â”‚
â”‚  Redis 7 (cache)                                            â”‚
â”‚  Cloudflare R2 (files + object lock)                        â”‚
â”‚  SQLite + SQLCipher (desktop local)                         â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Zero State Rules
- No server stores session state between requests
- All state lives in PostgreSQL or Redis
- Any worker instance handles any request
- Scale to zero when no traffic â€” zero cost
- Scale instantly when traffic arrives

### Zero Trust Rules
- Every request carries a signed JWT â€” verified at middleware
- Every module treats every other module as untrusted
- Internal service calls authenticated (service-to-service tokens)
- No implicit trust based on network location
- Tenant ID verified on every single database query (row-level security)

---

## 6. Multi-Tenant Data Architecture

### Database Isolation
```sql
-- Every table has tenant_id
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    org_id UUID NOT NULL REFERENCES organisations(id),
    -- ... data fields
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID NOT NULL REFERENCES users(id),
    version INTEGER NOT NULL DEFAULT 1,
    is_superseded BOOLEAN NOT NULL DEFAULT FALSE
);

-- Row Level Security enforced at DB level
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON transactions
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

### Storage Isolation
```
/data/
  â”œâ”€â”€ {tenant_id_hash}/
  â”‚     â”œâ”€â”€ {org_id}/
  â”‚     â”‚     â”œâ”€â”€ source/          â† original uploads, immutable
  â”‚     â”‚     â”œâ”€â”€ working/         â† computations, workings
  â”‚     â”‚     â”œâ”€â”€ mis/             â† MIS versions
  â”‚     â”‚     â”œâ”€â”€ output/          â† approved outputs
  â”‚     â”‚     â””â”€â”€ archive/         â† older versions
  â”‚     â””â”€â”€ shared/                â† tenant-level shared docs
  â””â”€â”€ platform/                    â† platform team only
```

### Tenant Hierarchy
```
Platform (FinanceOps)
  â””â”€â”€ Tenant (e.g. ABC Group / XYZ CA Firm)
        â””â”€â”€ Organisation (e.g. ABC India / Client A)
              â””â”€â”€ User (with role scoped to org)
```

---

## 7. AI / LLM Intelligence Layer

### Multi-Agent Pipeline
```
INPUT â†’ [Stage 1: Prepare] â†’ [Stage 2: Execute] â†’ [Stage 3: Validate]
                                                          â†“
                                              Score â‰¥ 95%? â†’ OUTPUT
                                              Score < 95%? â†’ [Stage 4: Correct] â†’ OUTPUT
```

### Stage Definitions
| Stage | Role | Model | Time | Cost |
|---|---|---|---|---|
| 1 â€” Prepare | Decompose & structure task | phi3:mini (local) | ~400ms | FREE |
| 2 â€” Execute | Perform computation/analysis | Claude Sonnet / Mistral | ~1-3s | Low |
| 3 â€” Validate | Independent re-derivation | GPT-4o-mini / DeepSeek | ~1-3s | Very Low |
| 4 â€” Correct | Arbitrate disagreements | Claude Opus (rare) | ~2-4s | Medium |
| 5 â€” Format | Structure output for UI | phi3:mini (local) | ~300ms | FREE |

### Model Roster
```
CLAUDE (Anthropic)
  Models: claude-sonnet-4-5 (primary), claude-opus-4-5 (arbitration)
  Role: Complex analysis, report generation, standards interpretation
  SDK: anthropic (Python)

GPT-4o (OpenAI)
  Models: gpt-4o-mini (validation), gpt-4o (complex validation)
  Role: Validation agent, cross-checking, structured output
  SDK: openai (Python)

DEEPSEEK
  Models: deepseek-chat (API), deepseek-coder (local via Ollama)
  Role: Financial calculations, formula validation, structured data
  API: OpenAI-compatible format (cheap, strong at maths)

LLAMA (Meta)
  Models: LLaMA 3.1 8B (local), LLaMA 3.1 70B (via Groq)
  Role: Offline mode, sensitive data, local execution
  Runtime: Ollama (local), Groq API (fast cloud)
```

### AI Gateway
```
Every module â†’ AI Gateway â†’ Correct model chain â†’ Response

Gateway responsibilities:
â”œâ”€â”€ Task classification (simple / medium / complex / standards)
â”œâ”€â”€ Model routing (local vs cloud based on sensitivity + complexity)
â”œâ”€â”€ API key management (never exposed to modules)
â”œâ”€â”€ PII detection + masking before external API calls
â”œâ”€â”€ Token budget enforcement per tenant per month
â”œâ”€â”€ Response caching (query hash + data hash)
â”œâ”€â”€ Retry + fallback chain
â”œâ”€â”€ Immutable call logging
â””â”€â”€ Cost tracking per model per tenant
```

### Fallback Chain
```
Claude API unavailable â†’ GPT-4o â†’ DeepSeek API â†’ Local Mistral
All cloud unavailable â†’ Local models only (platform keeps working)
Local Ollama unavailable â†’ Cloud models only
All unavailable â†’ Queue + process when available + user notified
```

### Cost Model
```
Simple queries (70% volume):     Local only          = $0
Medium analysis (20% volume):    Local + cheap cloud = ~$0.002/query
Complex analysis (8% volume):    Cloud primary       = ~$0.008/query
Standards/arbitration (2%):      Premium models      = ~$0.018/query

Estimated per active tenant/month: $15-30
Charge to tenant: $99-499/month
AI cost as % of revenue: <10%
```

### AI Safety Rules
```
1. Every user input scanned for prompt injection before LLM
2. System prompts hardened â€” cannot be overridden by user input
3. LLM output validated â€” financial figures cross-checked vs DB
4. PII masked before any external API call
5. Jailbreak attempts logged + platform team alerted
6. No AI output ever actioned without human approval
7. Every AI output includes: confidence score, model used, assumptions
8. One-click feedback on every output â†’ learning signal
```

---

## 8. Security Architecture

### 7 Layers of Security
```
Layer 1 â€” PERIMETER (Cloudflare)
  WAF, DDoS protection, bot management, IP whitelisting, rate limiting

Layer 2 â€” AUTHENTICATION
  MFA mandatory for Manager+, SSO/OAuth2/SAML, short-lived JWTs,
  device fingerprinting, brute force lockout

Layer 3 â€” AUTHORISATION
  Row-level security at DB, zero trust, least privilege,
  scoped API keys per integration

Layer 4 â€” INPUT VALIDATION
  Server-side validation always, Pydantic v2, SQL injection prevention
  (parameterised queries only), XSS prevention, CSRF tokens

Layer 5 â€” FILE AIRLOCK
  Every upload â†’ isolated sandbox â†’ ClamAV + python-magic scan â†’
  macro detection â†’ PDF sanitisation â†’ only clean files proceed
  Infected files quarantined, tenant notified, never processed

Layer 6 â€” AI SECURITY
  Prompt injection detection, system prompt hardening,
  output validation, PII masking, jailbreak logging

Layer 7 â€” INFRASTRUCTURE
  AES-256 at rest, TLS 1.3 in transit, field-level PII encryption,
  Doppler secrets management, container isolation, network segmentation
```

---

## 9. Observability & Analytics

### Founder Live Dashboard
```
Real-time metrics:
â”œâ”€â”€ Platform health (all services RAG status)
â”œâ”€â”€ Active tenants, active users, active sessions
â”œâ”€â”€ Error rate, error details (file, line, stack trace, blast radius)
â”œâ”€â”€ AI pipeline health (stage times, agreement rate, cost)
â”œâ”€â”€ Worker queue depths (all queues)
â”œâ”€â”€ Cost per tenant (compute + storage + AI)
â”œâ”€â”€ Revenue metrics (MRR, ARR, churn, new tenants)
â””â”€â”€ Learning engine metrics (signal volume, model accuracy)
```

### Error Tracking (Sentry)
```
Every error captures:
â”œâ”€â”€ Full stack trace (file name, line number, function)
â”œâ”€â”€ Tenant context (which tenant affected)
â”œâ”€â”€ Blast radius (how many tenants/users affected)
â”œâ”€â”€ User context (what user was doing when error occurred)
â”œâ”€â”€ Environment (module, service, version, deploy hash)
â”œâ”€â”€ Frequency (how often this error occurs)
â”œâ”€â”€ Regression detection (was this previously fixed?)
â””â”€â”€ Auto-assigned severity (P0-P4)
```

### Observability Stack
```
Sentry:           Error tracking, stack traces, blast radius
Prometheus:       Metrics collection
Grafana:          Dashboards (metrics + logs + traces unified)
Loki:             Log aggregation
OpenTelemetry:    Distributed tracing (request flows end-to-end)
Tempo:            Trace storage
BetterUptime:     Public status page (status.yourplatform.com)
Grafana Alerting: Alerts â†’ Slack + Email + PagerDuty
```

---

## 10. Compliance & Governance

### Supported Standards
| Standard | Scope |
|---|---|
| SOC 2 Type II | Security, availability, confidentiality controls |
| ISO 27001 | Information security management |
| ISO 27701 | Privacy information management |
| GDPR | EU data protection |
| DPDP | India Digital Personal Data Protection |
| HIPAA | Healthcare data (for healthcare tenants) |

### SOC2 Live Evidence Capture
```
Every control activity auto-captures:
â”œâ”€â”€ Control ID (maps to SOC2 criteria)
â”œâ”€â”€ Timestamp (server-side, UTC, immutable)
â”œâ”€â”€ Actor (hashed user ID)
â”œâ”€â”€ Action (specific, not generic)
â”œâ”€â”€ Outcome (success / failure / exception)
â”œâ”€â”€ System context (module, service, version)
â””â”€â”€ Chain hash (tamper-evident)
```

### User Responsibility Architecture
```
Layer 1 â€” Platform ToS (on signup, versioned, re-accepted on update)
Layer 2 â€” Role-Specific Agreements (Finance Leader, Manager, Data Entry)
Layer 3 â€” Action-Level Confirmations (every approval, posting, publish)

Each confirmation captures:
â”œâ”€â”€ Full legal name
â”œâ”€â”€ User ID + role at time
â”œâ”€â”€ IP address + device fingerprint
â”œâ”€â”€ Server-side UTC timestamp
â”œâ”€â”€ Exact text accepted (versioned â€” cannot change retroactively)
â”œâ”€â”€ Session ID
â””â”€â”€ HMAC digital signature
```

### Non-Repudiation Engine
- Every approval digitally signed + timestamped
- Evidence package downloadable per action
- Admissible in dispute or audit
- Instant: "Show proof CFO approved March consolidation" â†’ evidence package generated

---

## 11. Immutability Architecture

### 4-Level Enforcement
```
Level 1 â€” APPLICATION:    No UPDATE/DELETE in ORM for audit tables
Level 2 â€” DATABASE:       PostgreSQL RLS blocks UPDATE/DELETE on audit tables
                          Triggers block + alert on any attempt
                          INSERT-only DB user for audit tables
Level 3 â€” CHAIN HASH:     Every entry hashes previous entry
                          Tampering breaks chain â€” mathematically detectable
Level 4 â€” INFRASTRUCTURE: Cloudflare R2 Object Lock (files)
                          PostgreSQL WAL (transaction log)
                          Hash snapshots in separate immutable storage
```

### Version Pattern (All Entities)
```json
{
  "id": "uuid",
  "entity_id": "uuid-of-what-this-describes",
  "version": 3,
  "data": { "...actual content..." },
  "is_current": true,
  "supersedes_version": 2,
  "created_at": "2025-03-31T22:14:03Z",
  "created_by": "user-uuid",
  "reason": "Reclassified per Q1 review",
  "prev_hash": "sha256-of-version-2",
  "hash": "sha256-of-this-record"
}
```

---

## 12. Document Ecosystem

### Supported Platforms
| Platform | Auth | Capabilities |
|---|---|---|
| Google Drive | OAuth2 | Watch, read, write, webhooks |
| Microsoft OneDrive | OAuth2 (MSAL) | Watch, read, write, webhooks |
| Dropbox | OAuth2 | Watch, read, write, webhooks |
| SharePoint | OAuth2 (MSAL) | Document libraries, Teams integration |
| Box | OAuth2 | Enterprise document management |
| Local Folder | File system | Watch, read, write |
| Network Drive | SMB/NFS | Read, write |

### Auto Folder Structure
```
FinanceAgent/                    â† root (user designates this)
â”œâ”€â”€ 00_Source/                   â† originals, never modified
â”‚   â”œâ”€â”€ Paysheets/
â”‚   â”œâ”€â”€ TrialBalance/
â”‚   â”œâ”€â”€ GL/
â”‚   â””â”€â”€ Contracts/
â”œâ”€â”€ 01_Working/                  â† all workings per month
â”‚   â””â”€â”€ {YYYY_MM}/
â”‚       â”œâ”€â”€ FX_Rates.xlsx
â”‚       â”œâ”€â”€ IC_Reconciliation.xlsx
â”‚       â”œâ”€â”€ Assumptions.xlsx
â”‚       â””â”€â”€ GL_Classification.xlsx
â”œâ”€â”€ 02_MIS/                      â† MIS versions
â”œâ”€â”€ 03_Output/                   â† approved final outputs
â”‚   â””â”€â”€ {YYYY_MM}/
â””â”€â”€ 04_Archive/                  â† older versions
```

### File Reference Header (Every Output)
```
Generated by:    FinanceOps Platform v{version}
Generated on:    {UTC timestamp}
Approved by:     {Finance Leader name}
Approval time:   {UTC timestamp}
Source files:    {list of source files with version and upload timestamp}
Assumptions:     See Assumptions_{YYYY_MM}.xlsx
Platform build:  {git commit hash}
```

---

## 13. Marketplace Architecture

### Contributor Tiers
| Tier | Revenue Share | Review Process |
|---|---|---|
| Platform (Official) | 100% platform | Internal only |
| Verified Partner | 70% contributor / 30% platform | 48hr review |
| Community | 60% contributor / 40% platform | 72hr review |

### Contribution Flow
```
Build in Studio â†’ Auto-Validation â†’ Platform Review â†’ Publish â†’ Earn
```

### Auto-Validation Checks
- Schema compliance (follows platform rules)
- Security scan (no macros, scripts, malicious content)
- Data integrity (formulas, mappings, references valid)
- Completeness (all required fields present)
- GDPR/DPDP compliant (no PII hardcoded)

---

## 14. Living Documentation System

### Auto-Update Triggers
```
Code commit merged â†’ GitHub Actions runs:
â”œâ”€â”€ Sphinx / TypeDoc rebuilds API + code docs
â”œâ”€â”€ Changelog updated (conventional commits)
â”œâ”€â”€ Affected modules in dependency matrix updated
â”œâ”€â”€ Schema changes â†’ data dictionary updated
â”œâ”€â”€ User manual sections flagged for review if affected
â””â”€â”€ docs.yourplatform.com redeployed (Vercel)
```

### Error & Update Ledger Format
```
Every entry auto-populated on merge:
â”œâ”€â”€ Version number
â”œâ”€â”€ Timestamp
â”œâ”€â”€ Module affected
â”œâ”€â”€ Files changed (with line ranges)
â”œâ”€â”€ What changed and why
â”œâ”€â”€ Known risks
â”œâ”€â”€ Fix instructions if something breaks
â”œâ”€â”€ Rollback command
â””â”€â”€ Dependencies affected
```

---

## 15. Platform Portals

### Three Separate Portals
```
app.yourplatform.com          â† Customer Portal
  Tenants, clients, end users, consultants

platform.yourplatform.com     â† Platform Portal (your team)
  Founder, engineers, support, sales, compliance, security

partners.yourplatform.com     â† Partner/Consultant Portal
  Implementation consultants, CA firm customisation, sandbox
```

### Platform Portal Roles
| Role | Access |
|---|---|
| Platform Owner (Founder) | Everything â€” full control |
| Platform Engineer | Infrastructure, deployments, logs |
| Platform Support | Tenant issues, user resets (no data) |
| Platform Sales | Tenant list, usage, subscription (no data) |
| Compliance Officer | Audit logs, compliance reports, breach workflow |
| Security Officer | Security alerts, scan results, threat dashboard |

---

## 16. Service Register

Every service registered with:
```json
{
  "service_id": "uuid",
  "name": "paysheet-parser",
  "module": "paysheet-engine",
  "version": "1.2.3",
  "status": "healthy",
  "uptime_pct": 99.94,
  "avg_response_ms": 234,
  "error_rate_pct": 0.02,
  "last_error": null,
  "dependencies": ["postgresql", "redis", "ai-gateway"],
  "can_operate_without": ["ai-gateway"],
  "queue": "parse_queue",
  "queue_depth": 3,
  "instances": 2,
  "last_deployed": "2025-03-30T14:22:00Z",
  "health_check_url": "/health/paysheet-parser"
}
```

---

## 17. Module Register

Every module registered with:
```json
{
  "module_id": "uuid",
  "name": "lease-accounting",
  "display_name": "Lease Accounting (IFRS 16)",
  "version": "1.0.4",
  "status": "active",
  "services": ["lease-calculator", "rou-asset-engine", "disclosure-generator"],
  "tenants_using": 14,
  "enabled_globally": true,
  "subscription_tier_required": "professional",
  "dependencies": ["mis-manager", "gl-tb-reconciliation"],
  "accounting_standard": "IFRS 16 / ASC 842 / IND AS 116",
  "can_disable_without_breaking": ["forecasting"],
  "health": "healthy",
  "last_updated": "2025-03-15T09:00:00Z"
}
```

---

## 18. Task Register

Every task registered with:
```json
{
  "task_id": "uuid",
  "name": "generate-depreciation-schedule",
  "service": "asset-depreciation-engine",
  "module": "fixed-asset-register",
  "queue": "compute_queue",
  "status": "active",
  "avg_duration_ms": 1240,
  "success_rate_pct": 99.8,
  "retry_policy": { "max_attempts": 3, "backoff": "exponential" },
  "timeout_seconds": 30,
  "last_run": "2025-03-31T23:59:00Z",
  "last_success": "2025-03-31T23:59:01Z",
  "last_failure": null,
  "runs_today": 47,
  "dead_letter_queue": "dlq_compute"
}
```

---

## 19. Dependency Matrix Design

### Purpose
- Know exactly what breaks if any component changes
- Impact analysis before any update
- Circular dependency detection
- Auto-updated on every code commit

### Matrix Structure
```
Module A depends on â†’ Service B, Service C, Schema Table D
Service B depends on â†’ PostgreSQL, Redis, AI Gateway
Schema Table D used by â†’ Module A, Module E, Module F

Impact of changing Table D:
  â†’ Module A (HIGH impact â€” core dependency)
  â†’ Module E (MEDIUM impact â€” reads only)
  â†’ Module F (LOW impact â€” optional feature)
```

### Auto-Generation
```
GitHub Actions on merge:
1. Parse Python imports â†’ build service dependency graph
2. Parse SQLAlchemy models â†’ build schema dependency graph
3. Cross-reference â†’ identify module-schema dependencies
4. Generate DEPENDENCY_MATRIX.md
5. Alert on: new circular dependency, new breaking dependency
6. Update docs.yourplatform.com/dependency-matrix
```

---

## 20. Controls Dashboard

### 100% Visibility
```
Every control in the platform visible in one place:

SECURITY CONTROLS (47 controls)
â”œâ”€â”€ Authentication controls        âœ… 12/12
â”œâ”€â”€ Authorisation controls         âœ… 8/8
â”œâ”€â”€ Encryption controls            âœ… 6/6
â”œâ”€â”€ Network security controls      âœ… 9/9
â”œâ”€â”€ File security controls         âœ… 7/7
â””â”€â”€ AI security controls           âœ… 5/5

COMPLIANCE CONTROLS (93 ISO controls)
â”œâ”€â”€ Information security policies  âœ… 5/5
â”œâ”€â”€ Organisation of security       âœ… 7/7
â”œâ”€â”€ Human resource security        âš ï¸ 5/6 â€” 1 pending
â”œâ”€â”€ Asset management               âœ… 8/8
â””â”€â”€ ... (all 93 Annex A controls)

FINANCIAL CONTROLS (per module)
â”œâ”€â”€ Segregation of duties          âœ… Enforced via RBAC
â”œâ”€â”€ Approval workflows             âœ… All modules
â”œâ”€â”€ Reconciliation controls        âœ… Automated
â””â”€â”€ Covenant monitoring            âœ… Real-time

OPERATIONAL CONTROLS
â”œâ”€â”€ Backup verification            âœ… Last verified: today
â”œâ”€â”€ Disaster recovery test         âœ… Last tested: 2025-03-01
â”œâ”€â”€ Self-healing verification      âœ… All services auto-recover
â””â”€â”€ Dependency vulnerability scan  âœ… No critical CVEs
```

### Founder/CTO Master Toggle
```
Any module / service / task can be:
â”œâ”€â”€ Enabled / Disabled at platform level (affects all tenants)
â”œâ”€â”€ Enabled / Disabled at tenant level (affects one company)
â”œâ”€â”€ Enabled / Disabled at org level (affects one entity)
â””â”€â”€ Enabled / Disabled at user level (affects one person)

Every toggle:
â”œâ”€â”€ Requires reason (mandatory text field)
â”œâ”€â”€ Logged immutably (who, when, why, what)
â”œâ”€â”€ Confirmation dialog (shows blast radius before confirming)
â””â”€â”€ Instant effect (no deploy required)
```

---

*End of Master Blueprint v1.0*
*Next document: Implementation Plan*

---

## 21. Credits Architecture

### Credit Value
```
1 credit = $0.10 USD
Subscription tiers allocate credits monthly.
Top-up available Ã  la carte at slightly higher per-credit rate.
Unused credits roll over for 3 months then expire.
```

### Credit Cost Per Task
```
ROUTINE TASKS                        CREDITS    USD EQUIVALENT
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Run GL/TB Reconciliation             5          $0.50
Run Consolidation (per entity)       3          $0.30
Run Consolidation (5+ entities)      10         $1.00
AI Natural Language Query            2          $0.20
AI Complex Analysis                  8          $0.80
Upload + Process Paysheet            5          $0.50
ERP Sync (on-demand)                 10         $1.00
Upload + Parse Contract (AI)         8          $0.80
Run Covenant Compliance              5          $0.50
Run Forecast (3 scenarios)           15         $1.50
Variance Analysis (AI commentary)    12         $1.20
Run Revenue Recognition              8          $0.80
Generate Month-End PDF Pack          25         $2.50
Generate Board Pack                  30         $3.00
Standards Query (cross-LLM)          15         $1.50
MIS Backward Propagation             20         $2.00

PREMIUM ADVISORY TASKS               CREDITS    USD EQUIVALENT
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FDD Report (basic â€” QoE + WC)        1,000      $100
FDD Report (comprehensive â€” full)    2,500      $250
PPA Computation (full IFRS 3)        1,500      $150
M&A Deal Workspace setup             500        $50
Valuation Engine (DCF + comps)       500        $50
DD Tracker setup                     200        $20
```

### User ROI â€” What $100 Delivers
```
SCENARIO                     CREDITS USED    VALUE REPLACED      ROI
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
CA Firm â€” 3 clients month-end   169 = $16.90  $825 labour saved   48x
Corporate â€” 5 entity close      212 = $21.20  $2,100â€“3,600/month  14â€“24x
FDD + PPA (one deal)            4,000 = $400  $70,000â€“280,000     175â€“700x
```

### Subscription Tiers
```
TIER            CREDITS/MONTH    PRICE/MONTH    PER CREDIT    MARGIN
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Starter         500              $49            $0.098        ~78%
Professional    2,000            $149           $0.075        ~79%
Business        8,000            $449           $0.056        ~80%
Enterprise      Custom           Negotiated     Negotiated    ~75%+

TOP-UP PACKAGES (Ã  la carte):
500 credits     $45    ($0.090/credit)
2,000 credits   $160   ($0.080/credit)
5,000 credits   $350   ($0.070/credit)
20,000 credits  $1,200 ($0.060/credit)
```

### Platform Cost Structure (per 1,000 credits = $100 revenue)
```
AI inference (cloud models):     $8â€“12     (8â€“12%)
Compute (Railway/AWS workers):   $5â€“8      (5â€“8%)
Storage (Cloudflare R2):         $1â€“2      (1â€“2%)
Payment gateway fees:            $3â€“4      (3â€“4%)
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Total COGS:                      $17â€“26    (17â€“26%)
GROSS MARGIN:                    $74â€“83    (74â€“83%) âœ… exceeds 70% target

Key lever: local-first AI (67%+ of queries hit local Ollama = zero AI cost)
```

### Zero-Credit Enforcement
```
When credits = 0:
â”œâ”€â”€ All task RUN buttons disabled (greyed out)
â”œâ”€â”€ Hover tooltip: "Insufficient credits â€” top up to continue"
â”œâ”€â”€ Platform banner: "0 credits remaining â€” [Buy Credits]"
â”œâ”€â”€ Reads, views, downloads of existing data: always free
â”œâ”€â”€ Scheduled ERP sync jobs: queued, run when topped up
â”œâ”€â”€ Finance Leader receives email alert at 0 and at low-credit threshold
â””â”€â”€ Task reservation system:
    Queued â†’ credits RESERVED (not deducted)
    Completed â†’ credits DEDUCTED
    Cancelled â†’ reservation RELEASED (zero charge)
    Platform error â†’ zero deduction + auto-retry
```

### Payment Gateway Matrix
```
GATEWAY      COUNTRIES              METHODS                    WHEN TO USE
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Stripe       USA, UK, AUS,          Cards, Apple/Google Pay,   International default
             Singapore, UAE         SEPA, ACH, local methods
Razorpay     India (primary)        UPI, Netbanking, Cards,    All India tenants
                                    Wallets, EMI, NEFT/RTGS
Telr         UAE, Saudi, MENA       Cards, local bank transfer MENA local methods
PayU         India (backup)         UPI, Netbanking, Cards     India fallback

ROUTING LOGIC:
Tenant country = India â†’ Razorpay (primary), PayU (backup)
Tenant country = UAE/Saudi/Bahrain/Kuwait/Oman/Qatar â†’ Telr
Tenant country = everything else â†’ Stripe
```

---

## 22. Financial Due Diligence (FDD) Module

### What It Compiles From Platform Data
```
AUTOMATICALLY PULLED FROM PLATFORM:
â”œâ”€â”€ 24-month TB/GL history (from ERP connectors + uploads)
â”œâ”€â”€ MIS versions (normalised to Master MIS structure)
â”œâ”€â”€ Contract & backlog data (SOW/PO/WO register)
â”œâ”€â”€ Headcount & people data (HC movement, attrition, paysheets)
â”œâ”€â”€ Revenue recognition schedules (per customer, per method)
â”œâ”€â”€ Working capital history (from balance sheet data)
â”œâ”€â”€ Debt register + covenant data
â”œâ”€â”€ Fixed asset register
â””â”€â”€ Customer P&L and margin data
```

### FDD Report Sections (Auto-Compiled)
```
1. QUALITY OF EARNINGS (QoE)
   â”œâ”€â”€ Normalised EBITDA bridge (reported â†’ adjusted â†’ normalised)
   â”œâ”€â”€ One-off / non-recurring item identification (AI flags, user confirms)
   â”œâ”€â”€ Pro forma adjustments with basis
   â””â”€â”€ 12-month and 24-month LTM EBITDA

2. QUALITY OF REVENUE
   â”œâ”€â”€ Revenue by customer (concentration, HHI index)
   â”œâ”€â”€ Revenue by type (recurring, project, one-time %)
   â”œâ”€â”€ Contract coverage (% under contract)
   â”œâ”€â”€ Customer tenure, churn, NRR
   â””â”€â”€ Pipeline and backlog quality score

3. WORKING CAPITAL ANALYSIS
   â”œâ”€â”€ 24-month historical working capital
   â”œâ”€â”€ Normalised WC peg computation
   â”œâ”€â”€ Seasonality analysis
   â”œâ”€â”€ AR/AP aging (from GL)
   â””â”€â”€ WC bridge (movement explanation)

4. DEBT & DEBT-LIKE ITEMS
   â”œâ”€â”€ All debt from debt register
   â”œâ”€â”€ Lease liabilities (IFRS 16 â€” from lease module)
   â”œâ”€â”€ Deferred revenue (from RevRec module)
   â”œâ”€â”€ Pension/gratuity obligations
   â””â”€â”€ Contingent liabilities

5. NET DEBT COMPUTATION
   â”œâ”€â”€ Gross debt âˆ’ Cash + Debt-like items
   â””â”€â”€ Equity bridge (EV â†’ Equity Value)

6. HEADCOUNT & PEOPLE DILIGENCE
   â”œâ”€â”€ HC movement (24 months, from People module)
   â”œâ”€â”€ Key person concentration (AI flags)
   â”œâ”€â”€ Attrition trends and voluntary/involuntary split
   â””â”€â”€ Contractor vs permanent ratio

7. CONTRACTS & COMMERCIAL DILIGENCE
   â”œâ”€â”€ Key customer contract terms (from contract module)
   â”œâ”€â”€ Expiry and renewal risk profile
   â”œâ”€â”€ Key vendor dependencies
   â””â”€â”€ IP and technology contracts

8. FINANCIAL CONTROLS ASSESSMENT
   â”œâ”€â”€ Reconciliation quality (from recon module history)
   â”œâ”€â”€ Accounting policy review
   â””â”€â”€ Red flags identified by platform controls

OUTPUT:
â”œâ”€â”€ Professional PDF (branded, paginated, indexed)
â”œâ”€â”€ Excel workbook (all supporting schedules)
â”œâ”€â”€ Every number traceable to source (TB line / GL entry / contract)
â””â”€â”€ AI-generated executive summary (Finance Leader edits before finalising)
```

---

## 23. Purchase Price Allocation (PPA) Module

### IFRS 3 / ASC 805 Compliant Computation
```
STEP 1: Consideration (user inputs)
â”œâ”€â”€ Cash paid
â”œâ”€â”€ Deferred consideration â†’ NPV computed (discount rate input)
â”œâ”€â”€ Earn-out â†’ probability-weighted expected value
â”œâ”€â”€ Equity issued â†’ fair value (user inputs or market price)
â””â”€â”€ Total Purchase Price

STEP 2: Net Identifiable Assets at Fair Value
â”œâ”€â”€ Upload target balance sheet â†’ auto-loaded
â”œâ”€â”€ Fair value adjustments per asset class (user inputs with basis)
â””â”€â”€ Net Fair Value of Identifiable Assets

STEP 3: Identified Intangibles (with valuation methods)
â”œâ”€â”€ Customer relationships â†’ MEEM (uses revenue + margin from platform)
â”œâ”€â”€ Trade name / Brand â†’ Relief from Royalty
â”œâ”€â”€ Technology / IP â†’ Relief from Royalty or Cost approach
â”œâ”€â”€ Non-compete agreements â†’ With/Without method
â”œâ”€â”€ Order backlog â†’ from Contract module (pre-populated automatically)
â””â”€â”€ Each: fair value + useful life + amortisation schedule

STEP 4: Deferred Tax
â”œâ”€â”€ DTL on identified intangibles
â””â”€â”€ Net DTA/DTL impact

STEP 5: Goodwill
â”œâ”€â”€ Purchase price âˆ’ Net FV assets âˆ’ Intangibles + DTL
â””â”€â”€ Goodwill impairment testing template (annual)

OUTPUT:
â”œâ”€â”€ Full PPA schedule (Excel)
â”œâ”€â”€ Day-1 opening balance sheet journal entries
â”œâ”€â”€ Intangible amortisation schedules (auto-fed into FAR module)
â”œâ”€â”€ IFRS 3 disclosure notes
â””â”€â”€ Goodwill impairment model template
```

---

## 24. M&A Workspace Module

### Architecture
```
Completely isolated deal workspace per transaction.
No crossover with operational entity data.
Deal team access separate from operational finance access.
Post-close: target entity imported into core platform as new organisation.
```

### Capabilities
```
DEAL ROOM
â”œâ”€â”€ Deal register with stage tracking
â”‚   Origination â†’ NDA â†’ IOI â†’ DD â†’ LOI â†’ Exclusivity â†’ Close
â”œâ”€â”€ Stage gate approvals
â”œâ”€â”€ Document vault (NDA, IOI, LOI, SPA)
â””â”€â”€ Deal team management

TARGET ANALYSIS
â”œâ”€â”€ Upload target financials â†’ auto-normalised to your MIS structure
â”œâ”€â”€ Comparable company analysis (EV/EBITDA, EV/Rev, P/E multiples)
â”œâ”€â”€ LTM / NTM financial profiles

VALUATION ENGINE
â”œâ”€â”€ DCF (revenue/margin/capex assumptions â†’ WACC â†’ EV)
â”œâ”€â”€ Comparable company multiples
â”œâ”€â”€ Precedent transaction multiples
â”œâ”€â”€ LBO model (for PE transactions)
â”œâ”€â”€ Football field chart (valuation range across all methods)
â””â”€â”€ Sensitivity tables

DUE DILIGENCE TRACKER
â”œâ”€â”€ Workstream tracker (Financial, Legal, Tax, Commercial, HR, IT)
â”œâ”€â”€ PBC list (sent to target, tracked to completion)
â”œâ”€â”€ DD finding log (issue, severity, deal impact, resolution)
â””â”€â”€ Red flag report (auto-compiled from findings)

INTEGRATION PLANNING (post-LOI)
â”œâ”€â”€ 100-day integration plan
â”œâ”€â”€ Synergy identification (revenue + cost + financial)
â”œâ”€â”€ Synergy tracking vs plan (post-close)
â””â”€â”€ Integration risk register

POST-CLOSE
â”œâ”€â”€ Triggers PPA module automatically
â”œâ”€â”€ Creates new organisation in core platform
â”œâ”€â”€ Imports target financials as historical data
â””â”€â”€ Actual vs projected synergy dashboard
```


---

## 25. Output Transparency & Formula Integrity

### Non-Negotiable Rules for Every Excel Output

Every workbook the platform generates must be self-explaining.
A CFO or auditor must trace every number without logging into the platform.

```
MANDATORY SHEET STRUCTURE (every workbook):
  00_Cover        â€” document metadata, sources, assumptions, integrity check
  01_Summary      â€” main output (first thing user sees)
  02_Workings     â€” every computation shown step by step
  03_Sources      â€” raw source data from platform
  04_Assumptions  â€” every assumption with basis and who accepted it
  05_Audit_Trail  â€” every change, who, when, why
  06_Formulas_Key â€” legend of every formula used

FORMULA RULES:
  â”œâ”€â”€ NO hardcoded numbers in formula cells â€” ever
  â”œâ”€â”€ Every formula cell has a comment explaining what it computes
  â”œâ”€â”€ Cross-sheet references use named ranges, not cell addresses
  â”œâ”€â”€ Every SUM has a validation check: =IF(SUM(B4:B12)<>B13,"MISMATCH","OK")
  â””â”€â”€ Color coding:
        Blue  = hardcoded input (user entered)
        Black = formula (computed by platform)
        Green = linked from another sheet/workbook
        Red   = validation fail / needs attention

CROSS-WORKBOOK LINKS:
  â”œâ”€â”€ Every output links back to source files with upload timestamp
  â”œâ”€â”€ Source file SHA256 hash stored â€” if file changes, link turns red
  â”œâ”€â”€ Cell comment example:
  â”‚     "Source: TallyGL_March2025.xlsx
  â”‚      Sheet: Transactions, Rows 1-4847
  â”‚      SHA256: a3f9c2...
  â”‚      Uploaded: 31-Mar-2025 22:14 UTC by Ravi Kumar"
  â””â”€â”€ Broken link detection on every file open

COVER SHEET (every output â€” mandatory):
  Document name and period
  Generated by: FinanceOps Platform vX.X.X
  Generated at: UTC timestamp
  Approved by: name + role + timestamp
  Source files: name + SHA256 + upload time + uploaded by
  Assumptions: count + link to 04_Assumptions sheet
  Integrity check: âœ… All validations passed / âŒ X issues found
  Formula check:   âœ… No hardcoded values / âŒ X hardcoded values found
  Link check:      âœ… All source files verified / âŒ X broken links

DRILL-DOWN PATH (every number):
  Consolidated Revenue $4.2M
    â†’ Entity breakdown (click)
      â†’ GL account detail (click)
        â†’ Individual transactions (click)
  No number exists without a traceable source path.

DECIMAL PRECISION RULES:
  Currency values:  2 decimal places (Decimal, not float)
  FX rates:         6 decimal places
  Percentages:      4 decimal places
  Headcount:        0 decimal places (whole numbers only)
  Never use Python float for any financial computation.
  Always use: from decimal import Decimal, ROUND_HALF_UP
```

---

## 26. Complete Backend Library Stack

```
PACKAGE MANAGER: uv (install: curl -LsSf https://astral.sh/uv/install.sh | sh)

WEB FRAMEWORK:
  fastapi==0.115.0, uvicorn[standard]==0.30.0,
  gunicorn==22.0.0, python-multipart==0.0.9

DATABASE:
  sqlalchemy==2.0.35, asyncpg==0.30.0,
  alembic==1.13.0, pgvector==0.3.3

CACHE & QUEUES:
  redis==5.0.8, celery[redis]==5.4.0, flower==2.0.1

WORKFLOW:
  temporalio==1.7.0

VALIDATION:
  pydantic==2.9.0, pydantic-settings==2.5.0, email-validator==2.2.0

AUTH & SECURITY:
  python-jose[cryptography]==3.3.0, passlib[bcrypt]==1.7.4,
  pyotp==2.9.0, cryptography==43.0.0, slowapi==0.1.9

FILE PROCESSING:
  openpyxl==3.1.5 (read uploads),
  xlsxwriter==3.2.0 (write outputs â€” superior formatting),
  pandas==2.2.3, numpy==2.1.0,
  python-magic==0.4.27, python-docx==1.1.2

PDF:
  pymupdf==1.24.10 (text extraction),
  pdfplumber==0.11.4 (table extraction),
  weasyprint==62.3 (HTMLâ†’PDF reports),
  easyocr==1.7.1 (OCR scanned docs),
  pypdf==5.0.0 (merge/split/rotate),
  reportlab==4.2.2 (PDF generation alternative)

AI / LLM:
  anthropic==0.34.0, openai==1.51.0, ollama==0.3.3,
  sentence-transformers==3.1.0, tiktoken==0.7.0, langdetect==1.0.9

NLP:
  spacy==3.8.0 (PII detection)
  Post-install: python -m spacy download en_core_web_sm

STORAGE:
  boto3==1.35.0 (Cloudflare R2 â€” S3 compatible)

EMAIL:
  sendgrid==6.11.0, jinja2==3.1.4, aiosmtplib==3.0.1

PAYMENTS:
  stripe==10.12.0, razorpay==1.4.2

HTTP / ERP CONNECTORS:
  httpx==0.27.0, aiohttp==3.10.0,
  zeep==4.2.1 (Tally SOAP), xmltodict==0.13.0

TELEMETRY:
  opentelemetry-sdk==1.27.0, opentelemetry-api==1.27.0,
  opentelemetry-exporter-otlp==1.27.0,
  opentelemetry-instrumentation-fastapi==0.48b0,
  opentelemetry-instrumentation-sqlalchemy==0.48b0,
  opentelemetry-instrumentation-redis==0.48b0,
  opentelemetry-instrumentation-celery==0.48b0,
  sentry-sdk[fastapi]==2.14.0, prometheus-client==0.21.0

UTILITIES:
  python-dateutil==2.9.0, pytz==2024.2, babel==2.16.0,
  pycountry==24.6.1

MICROSOFT TEAMS BOT (HR module â€” Phase 2):
  botbuilder-core==4.15.0
  botbuilder-schema==4.15.0
  botbuilder-integration-aiohttp==4.15.0

SLACK BOT (HR module â€” Phase 2):
  slack-bolt==1.18.0
  slack-sdk==3.30.0

SSO INTEGRATION:
  msal==1.30.0              â€” Azure AD / Microsoft 365 (SAML + OAuth2)
  python3-saml==1.16.0      â€” Generic SAML 2.0 (Okta + any IdP)

IMAGE PROCESSING:
  Pillow==10.4.0            â€” Image preprocessing before OCR
                              (expense receipts, scanned documents)

DIGITAL SIGNOFF:
  qrcode[pil]==8.0          â€” QR codes on signoff certificates
                              (verifiable certificate QR linking to audit trail)

CRM CONNECTORS (Phase 3 â€” Sales module):
  simple-salesforce==1.12.5 â€” Salesforce REST API client
                              (much simpler than raw httpx for Salesforce)
  Note: HubSpot, Pipedrive, Zoho CRM â†’ use httpx directly âœ…

BUILT-IN (no install):
  decimal  â€” ALL financial math (never use float for money)
  hashlib  â€” SHA256 chain hash
  uuid     â€” UUID generation
  gzip     â€” backup compression
  json     â€” GSTR-2B parsing, API responses
  subprocess â€” pg_dump for backups

DEV / TESTING:
  pytest==8.3.0, pytest-asyncio==0.24.0, pytest-cov==5.0.0,
  faker==30.0.0, factory-boy==3.3.1,
  ruff==0.6.0, mypy==1.11.0, pre-commit==3.8.0

INSTALL ORDER NOTE:
  Install torch BEFORE sentence-transformers and easyocr.
  Install Pillow BEFORE qrcode and easyocr.
  spaCy model after spaCy: python -m spacy download en_core_web_sm
  
  Full install sequence:
  uv add torch==2.4.0 Pillow==10.4.0
  uv add sentence-transformers==3.1.0 easyocr==1.7.1
  uv add [all other libraries]
  uv run python -m spacy download en_core_web_sm
```

---

## 27. Number Formatting Engine

```
USER CONTROLS AT THREE LEVELS:

Platform setting (tenant default):
  Display unit: Units | Thousands | Lakhs | Millions | Crores | Billions
  Number system: Indian (1,00,000) | International (100,000)
  Currency symbol, decimal places, negative display

Per-report setting (overrides default for that report):
  Set at report generation time

On-the-fly via chat:
  "show in millions" â†’ re-renders immediately

INDIAN NUMBER SYSTEM:
  1,00,000 = 1 Lakh | 1,00,00,000 = 1 Crore
  babel library: Locale('en', 'IN') for Indian formatting

EXCEL OUTPUT RULES:
  â”œâ”€â”€ Raw values always stored in Units in source sheets
  â”œâ”€â”€ Display sheets divide by format factor (formula, not hardcoded)
  â”œâ”€â”€ Cover sheet states: "All figures in â‚¹ Lakhs unless stated"
  â”œâ”€â”€ Every sheet header repeats unit: "(â‚¹ in Lakhs)"
  â””â”€â”€ Reconciliation: Summary Ã— factor = Source total âœ…

FORMAT FACTORS:
  Units:     Ã· 1
  Thousands: Ã· 1,000
  Lakhs:     Ã· 100,000
  Crores:    Ã· 10,000,000
  Millions:  Ã· 1,000,000
  Billions:  Ã· 1,000,000,000

DECIMAL RULE (non-negotiable):
  ALL financial math uses Python Decimal, never float.
  from decimal import Decimal, ROUND_HALF_UP
```

---

## 28. Adjustment Engine

```
ADJUSTMENT TYPES:
  Capitalisation, Reclassification, Accrual, Prepayment,
  Elimination, Normalisation, Currency correction, Custom journal

FLOW:
  User identifies item â†’ Platform proposes Dr/Cr â†’ shows impact preview
  â†’ Finance Leader provides basis â†’ confirms â†’ posted append-only
  â†’ All downstream modules re-computed automatically

CAPITALISATION OF RESOURCES:
  User specifies: employees, period, % time on project, asset name
  Platform computes: salary + employer costs Ã— % Ã— period
  Creates: capitalisation journal + FAR entry + amortisation schedule
  Removes cost from P&L, adds asset to balance sheet
  Every number traceable to individual paysheet line

EXCEL OUTPUT â€” ADJUSTMENT SHOWN AS:
  02_Workings sheet:
  Line: Employee Cost
    Per TB:               â‚¹1,20,00,000
    Adj-001 (Capitalise): (â‚¹45,00,000)  â† orange highlight
    Adjusted:             â‚¹75,00,000
    Basis: IAS 38, approved by [name] [timestamp]

All adjustments: reversible, auditable, append-only in DB.
```

---

## 29. Storage Tiers and Metering

```
INCLUDED STORAGE PER TIER:
  Starter ($49):       5 GB
  Professional ($149): 25 GB
  Business ($449):     100 GB
  Enterprise:          Custom

OVERAGE PRICING:
  First 10 GB over:    $2/GB/month
  Next 40 GB over:     $1.50/GB/month
  Beyond 50 GB over:   $1/GB/month

WHAT COUNTS: uploaded files + generated outputs + PDFs/contracts
WHAT DOES NOT COUNT: audit trail, platform logs, backups

ENFORCEMENT:
  Pre-upload check: used + file_size > limit â†’ StorageLimitExceeded
  At 80%: in-app warning
  At 90%: email alert
  At 100%: uploads blocked, reads always allowed

USER-CONFIGURABLE RETENTION:
  Auto-delete source files after X months
  (processed data kept, raw file deleted â€” frees 60-70% storage)

YOUR MARGIN ON STORAGE:
  R2 cost: $0.015/GB/month
  Overage charge: $2/GB/month
  Margin: 99.25% on overage âœ…
```

---

## 30. Intercompany Loan & Interest Tracking

```
IC Loan Register:
  â”œâ”€â”€ Lender entity, borrower entity, principal, currency
  â”œâ”€â”€ Interest rate (fixed/floating â€” linked to LIBOR/SOFR/MCLR)
  â”œâ”€â”€ Drawdown date, repayment schedule (bullet/amortising)
  â”œâ”€â”€ Transfer pricing: rate vs arm's length benchmark
  â””â”€â”€ Thin capitalisation: debt/equity ratio monitored

Auto-computation monthly:
  â”œâ”€â”€ Interest accrual (Dr Interest Expense / Cr Interest Payable)
  â”œâ”€â”€ Both sides booked in respective entities automatically
  â”œâ”€â”€ IC elimination in consolidation (principal + accrued interest)
  â””â”€â”€ Transfer pricing alert if rate deviates from benchmark

Credits: 5 per month per loan register run
```

---

## 31. Transfer Pricing Documentation & Monitoring

```
TP Transaction Register:
  â”œâ”€â”€ All related party transactions auto-identified from GL
  â”œâ”€â”€ Transaction types: goods, services, loans, IP royalties, guarantees
  â”œâ”€â”€ Pricing method suggested by AI: CUP, TNMM, CPM, RPM, PSM
  â”œâ”€â”€ Comparable benchmarks suggested
  â””â”€â”€ Documentation: auto-draft TP study section per transaction

Monitoring:
  â”œâ”€â”€ Monthly: actual price vs arm's length range
  â”œâ”€â”€ Alert if deviation >10% from benchmark
  â””â”€â”€ Annual Form 3CEB data auto-populated (India)

Credits: 15 per TP analysis run
Penalty avoided: 200-300% in India for non-compliance
```

---

## 32. GST / VAT Reconciliation & Filing Support

```
GST Reconciliation (India):
  â”œâ”€â”€ Pull GSTR-2B from GST portal (API or upload)
  â”œâ”€â”€ Pull purchase register from GL/ERP
  â”œâ”€â”€ Reconcile: every invoice matched or flagged
  â”œâ”€â”€ ITC mismatch report: claimable vs claimed
  â”œâ”€â”€ Vendor-wise mismatch: which vendors not filing (ITC at risk)
  â”œâ”€â”€ Auto-draft communication to non-compliant vendors
  â””â”€â”€ GSTR-3B computation: tax payable after ITC

UAE VAT / Singapore GST: same structure, different rates and forms

Credits: 20 per GST reconciliation run
Value: replaces 2-5 days of manual work every month
```

---

## 33. Working Capital Management Dashboard

```
Dashboard (zero credits â€” drives daily login):
  â”œâ”€â”€ AR Aging: current, 30, 60, 90, 90+ days per customer
  â”œâ”€â”€ AP Aging: current, 30, 60, 90+ days per vendor
  â”œâ”€â”€ DSO, DPO, Cash Conversion Cycle trends (12 months)
  â”œâ”€â”€ Top 10 overdue customers (amount + days + last contact)
  â”œâ”€â”€ Early payment discount opportunities
  â””â”€â”€ WC forecast: projected WC next 4 weeks

Collections Intelligence:
  â”œâ”€â”€ AI drafts dunning emails for overdue AR
  â”œâ”€â”€ Payment prediction score per overdue invoice
  â”‚     "Customer X: 85% probability of paying within 7 days"
  â””â”€â”€ Escalation trigger: >60 days â†’ auto-alert Finance Leader
```

---

## 34. Bank Reconciliation Module

```
Flow:
  â”œâ”€â”€ Upload bank statement (PDF or CSV) â†’ auto-parse
  â”œâ”€â”€ Pull GL cash account transactions for same period
  â”œâ”€â”€ Auto-match: amount + date Â± 3 days
  â”œâ”€â”€ Unmatched items: presented for manual matching or posting
  â”œâ”€â”€ Outstanding items list (auto-populated)
  â”œâ”€â”€ Bank recon statement: classic format
  â”‚     (balance per bank â†’ timing differences â†’ balance per book)
  â””â”€â”€ Auto-pass entries: bank charges, interest (one-click)

Output: classic bank reconciliation statement
Every auditor expects this. Currently done in Excel manually.
Credits: 5 per bank account per month
```

---

## 35. Audit Support Package

```
One-Click Audit Pack (credits: 100):
  â”œâ”€â”€ Fixed asset schedule with movement
  â”œâ”€â”€ Debtors aging
  â”œâ”€â”€ Creditors aging
  â”œâ”€â”€ Loans and advances schedule
  â”œâ”€â”€ Related party transactions
  â”œâ”€â”€ Revenue reconciliation (books vs invoices)
  â”œâ”€â”€ Expense schedules (major heads)
  â”œâ”€â”€ Bank reconciliation statements
  â”œâ”€â”€ Provisions and contingencies
  â””â”€â”€ CARO / Companies Act schedules (India)

Auditor Portal (read-only login):
  â”œâ”€â”€ Auditors view, download, raise queries
  â”œâ”€â”€ Query management: raised â†’ Finance responds â†’ resolved â†’ logged
  â””â”€â”€ PBC tracker: requested vs provided vs pending

Value: replaces 4-8 weeks of CFO preparation time annually
```

---

## 36. Scenario Modelling / What-If Analysis

```
Scenario Engine:
  â”œâ”€â”€ Base case: current MIS/forecast data
  â”œâ”€â”€ User defines scenarios:
  â”‚     "Revenue -15%", "USD/INR rate 90 instead of 84",
  â”‚     "Add 20 headcount at â‚¹12L avg CTC",
  â”‚     "Lose Customer X (â‚¹2Cr revenue, 45% margin)"
  â”œâ”€â”€ Platform computes full P&L, BS, cash flow impact instantly
  â”œâ”€â”€ Side-by-side: Base vs Scenario 1 vs Scenario 2 vs Scenario 3
  â”œâ”€â”€ Bridge chart: what drove the difference
  â””â”€â”€ Export: board-ready slide + Excel workbook

AI commentary:
  "Based on your revenue concentration, losing top 3 customers
   would reduce EBITDA by 67%. Top 3 = 71% of revenue."

Credits: 15 per scenario run
```

---

## 37. Statutory Registers (India)

```
Digital maintenance of all Companies Act 2013 registers:
  â”œâ”€â”€ Register of Members (shareholders)
  â”œâ”€â”€ Register of Directors and KMP
  â”œâ”€â”€ Register of Charges (secured loans)
  â”œâ”€â”€ Register of Related Party Contracts
  â””â”€â”€ Register of Investments

MCA Filing Calendar:
  â”œâ”€â”€ Every Form due date tracked:
  â”‚     MGT-7 (Annual Return), AOC-4 (Financial Statements),
  â”‚     DIR-3 KYC, DPT-3, MSME-1, BEN-2, and all others
  â”œâ”€â”€ Auto-reminder: 30 days, 7 days, 1 day before due
  â”œâ”€â”€ Charge satisfaction tracking (Form CHG-4 when loan repaid)
  â””â”€â”€ Export: registers in MCA-prescribed format

High value for CA firms managing multiple clients.
Each client's MCA calendar managed separately.
```

---

## 38. Temporal Consistency Engine

```
Handles structural changes across time:
  â”œâ”€â”€ Track every MIS structural change with effective date
  â”œâ”€â”€ Comparison across structure change:
  â”‚     AI restates prior periods on new structure
  â”‚     Shows both: as-reported and restated
  â”œâ”€â”€ New entity added mid-year:
  â”‚     Like-for-like: exclude new entity
  â”‚     Full group: include from acquisition date
  â”‚     Pro-forma full year: annualise new entity
  â””â”€â”€ Every comparison states its basis clearly in output

Every CFO deals with this annually. Getting it right = enormous trust.
```

---

## 39. Cash Flow Forecasting (Enhanced)

```
13-WEEK ROLLING (treasury):
  â”œâ”€â”€ Week 1-2: actual (from bank statement)
  â”œâ”€â”€ Week 3-13: forecast
  â”‚     Inflows: AR collection schedule + payment probability score
  â”‚     Outflows: AP schedule + payroll dates + tax due dates
  â”œâ”€â”€ Minimum cash balance alert (covenant or operational threshold)
  â”œâ”€â”€ Funding gap: forecast below minimum â†’ alert with lead time
  â”œâ”€â”€ What-if: "What if Customer X pays 2 weeks late?"
  â””â”€â”€ Actual vs forecast reconciliation (weekly â€” where was forecast wrong?)

ANNUAL CASH FLOW (strategic):
  â”œâ”€â”€ Indirect method: EBITDA â†’ operating CF â†’ investing â†’ financing
  â”œâ”€â”€ Capex schedule (from FAR planned additions)
  â”œâ”€â”€ Debt repayment schedule (from debt register)
  â”œâ”€â”€ Dividend / distribution planning
  â””â”€â”€ Free cash flow: operating CF âˆ’ capex

Credits: 10 per 13-week run, 20 per annual CF model
```

---

## 40. Payroll Reconciliation

```
  â”œâ”€â”€ Upload payroll report â†’ reconcile vs GL payroll accounts
  â”œâ”€â”€ Upload PF/ESI challans â†’ reconcile vs GL statutory liability
  â”œâ”€â”€ Ghost employee detection:
  â”‚     AI flags employees on payroll not in active HRMS list
  â”œâ”€â”€ Duplicate payment detection
  â”œâ”€â”€ Form 16 / Form 24Q reconciliation vs GL (year-end)
  â””â”€â”€ Statutory compliance alerts:
        PF by 15th of month
        ESI by 21st of month
        TDS by 7th of month
        Alert if missed with penalty amount estimated

Credits: 8 per payroll reconciliation run
```

---

## 41. Director / CFO Digital Signoff

```
  â”œâ”€â”€ Any output sent for formal signoff
  â”œâ”€â”€ Signatory sees: document + responsibility statement
  â”œâ”€â”€ OTP/MFA-verified signoff (not just a click)
  â”œâ”€â”€ Recorded: name, role, timestamp, IP, device, MFA method
  â”œâ”€â”€ Certificate: PDF with signoff details embedded
  â”œâ”€â”€ Tamper-evident: document hash stored at signoff
  â””â”€â”€ Evidence package: exportable for legal/regulatory disputes

Use cases:
  Board pack before distribution
  Financial statements before filing
  FDD report before sending to buyer
  Any document with legal consequence

Credits: 5 per signoff workflow initiated
```

---

## 42. Expense Intelligence (Finance Layer)

```
  â”œâ”€â”€ Policy engine: expense limits by grade/category
  â”œâ”€â”€ Receipt OCR: extract amount, vendor, date from receipt photo
  â”œâ”€â”€ Auto-GL coding: AI suggests account (vendor + description)
  â”œâ”€â”€ GST ITC flag: is this expense GST-creditable? (India)
  â”œâ”€â”€ Budget check: real-time check vs department budget
  â””â”€â”€ Anomaly detection:
        Duplicate submissions
        Round number claims (â‚¹5,000 exactly â€” suspicious)
        Weekend/holiday claims
        Personal merchant flags (Amazon, Swiggy, etc.)

Credits: 2 per expense batch processed
```

---

## 43. Multi-GAAP Reporting

```
One set of underlying data â†’ multiple GAAP outputs:
  â”œâ”€â”€ INDAS (India statutory)
  â”œâ”€â”€ IFRS (parent / investor reporting)
  â”œâ”€â”€ US GAAP (US parent or listing)
  â””â”€â”€ Management accounts (internal, simplified)

GAAP Bridge (pre-configured):
  â”œâ”€â”€ INDAS â†’ IFRS: goodwill amortisation, lease differences,
  â”‚     financial instruments, deferred tax methodology
  â”œâ”€â”€ INDAS â†’ IGAAP: simplifications for smaller entities
  â””â”€â”€ Each bridge: Dr/Cr adjustments with standard reference

Output: parallel financial statements side by side
High value for groups with foreign investors or cross-border structure.
Credits: 50 per multi-GAAP pack
```

---

## 44. Month-End Closing Checklist

```
THE HOME SCREEN FOR FINANCE LEADERS DURING CLOSE.

  â”œâ”€â”€ Pre-configured template (standard month-end tasks)
  â”œâ”€â”€ Fully customisable per tenant
  â”œâ”€â”€ Task assignment (who is responsible for each task)
  â”œâ”€â”€ Due dates relative to period-end (T-5, T-3, T, T+2, T+5)
  â”œâ”€â”€ Status: Not Started / In Progress / Completed / Blocked
  â”œâ”€â”€ Dependencies: Task B cannot start until Task A complete
  â”œâ”€â”€ Progress: % of close complete (CFO sees at a glance)
  â”œâ”€â”€ Bottleneck alert: which task is holding up the close
  â”œâ”€â”€ Historical: average close time trend (are we closing faster?)
  â”œâ”€â”€ Target close date: actual vs target per month
  â””â”€â”€ Automated triggers:
        ERP sync complete â†’ marks "TB available" task done
        Recon complete â†’ marks "Reconciliation" task done
        Report approved â†’ marks "Board pack" task done

Zero credits â€” always free.
Drives daily login during close period (days 25-5 every month).
Teams who use this cannot imagine closing without it.
This is the stickiest feature on the entire platform.
```

---

## 45. Automated Backup Architecture

```
FOUR DATA TYPES â€” FOUR STRATEGIES:

POSTGRESQL (most critical):
  Continuous WAL archiving â†’ R2 (real-time, every transaction)
  Daily full snapshot: 02:00 UTC â†’ compressed â†’ AES-256 encrypted â†’ R2
  Retention: 7 daily | 4 weekly | 12 monthly | 7 annual snapshots
  RPO: < 5 minutes | RTO: < 30 minutes
  Backup verification: every backup auto-restored to test instance
    â†’ row count check â†’ chain hash integrity â†’ marked verified
    â†’ Alert P1 if verification fails

R2 FILES:
  Object versioning enabled (every version retained)
  Cross-region replication (primary bucket â†’ replica bucket, real-time)
  Soft delete: 30-day recovery window
  Retention: source files 2 years | reports 7 years | audit trail permanent

REDIS:
  RDB snapshot every 6 hours â†’ R2
  AOF enabled for Celery task state
  Recovery time: 5-10 minutes (acceptable â€” cache rebuilds itself)

PGVECTOR:
  Part of PostgreSQL â€” backed up automatically with DB

ENCRYPTION:
  Every backup encrypted with tenant-specific key before R2 upload
  Key stored in Doppler (separate from backup location)
  Backup without key = unreadable

RTO / RPO TARGETS:
  Database failure:    RTO < 30 min,  RPO < 5 min
  Full region failure: RTO < 2 hours, RPO < 5 min
  Accidental deletion: RTO < 15 min,  RPO = 0 (R2 versioning)
```

---

## 46. Zero-State Standby Deployment

```
ARCHITECTURE: Active-Passive with streaming replication

PRIMARY (Active â€” all live traffic):
  Region A (Mumbai for India tenants)
  FastAPI workers, Celery workers, PostgreSQL primary,
  Redis primary, Temporal server

STANDBY (Passive â€” receives replication, handles no traffic):
  Region B (Singapore)
  FastAPI workers (running, no traffic)
  Celery workers (running, processing nothing)
  PostgreSQL standby (streaming replication from primary â€” < 1s lag)
  Redis replica
  Temporal server (synced)

CLOUDFLARE ROUTING:
  All traffic â†’ Cloudflare â†’ health check primary every 10 seconds
  Primary healthy:   route all traffic to PRIMARY
  Primary unhealthy: auto-failover to STANDBY (30-60 seconds)
  Founder alerted immediately via PagerDuty

WHAT GETS SYNCED:
  Continuous (milliseconds):   PostgreSQL WAL, pgvector, Redis
  Every 5 minutes:             R2 cross-region replication
  At deployment:               Blue-Green (deploy to standby â†’ test â†’
                                swap traffic â†’ deploy to old primary)
  Daily 00:00 UTC:             Verified snapshot + integrity check +
                                health report to founder

END-OF-DAY SYNC (in addition to streaming):
  00:00 UTC daily:
  â”œâ”€â”€ Create verified DB snapshot
  â”œâ”€â”€ Run chain hash integrity check on standby
  â”œâ”€â”€ Verify replication lag = 0
  â”œâ”€â”€ Copy snapshot to cold storage (7-year retention)
  â””â”€â”€ Send daily infrastructure health report to founder

ZERO-STATE PRINCIPLE:
  FastAPI workers carry no in-process state.
  Any worker on primary OR standby handles any request.
  Failover is seamless â€” users experience 30-60 seconds disruption maximum.
  This works BECAUSE stateless architecture was built from day one.
```

---

## 47. Peak Load Management (Month-End Crunch)

```
PROBLEM:
  Every CFO and CA firm hits the platform in the same 8-day window.
  Day 25 to Day 8 of next month = 80% of all tasks in 25% of the time.

5-LAYER SOLUTION:

LAYER 1 â€” PREDICTIVE AUTO-SCALING:
  Day 25 at 09:00: scale to 2Ã— workers automatically
  Day 1 at 09:00:  scale to 3Ã— workers automatically
  Day 8 at 18:00:  scale back to normal
  Scale before peak arrives â€” not during it.
  Extra cost: ~$300-500/month. Worth every rupee.

LAYER 2 â€” INTELLIGENT PRIORITY QUEUING:
  CRITICAL (immediate):  dashboard refresh, AI chat, authentication
  HIGH (< 2 min):        reconciliation, consolidation, report generation
  NORMAL (< 10 min):     ERP sync, email, scheduled reports
  LOW (off-peak only):   FDD/PPA, vector updates, analytics
                         LOW queue PAUSED during 09:00-23:00 on peak days

  Tenants see queue position + estimated wait time.
  Email notification when task complete.

LAYER 3 â€” AGGRESSIVE CACHING:
  Dashboard data:         5-min cache (15-min during peak)
  FX rates:               1-hour cache
  MIS template:           24-hour cache
  AI responses (same query): 1-hour cache
  Standards queries:      permanent cache
  Historical period data: 1-hour cache
  Target cache hit rate:  > 50% during peak

LAYER 4 â€” READ REPLICAS (auto-activated day 25):
  Normal days:   all reads + writes â†’ primary
  Peak period:   writes â†’ primary only
                 report reads â†’ replica 1
                 dashboard reads â†’ replica 2
                 AI queries â†’ replica 1 or 2 (load balanced)
  Primary freed from reads = handles writes much faster

LAYER 5 â€” TENANT STAGGERING:
  Preferred close date setting per tenant:
  "Close on 28th or 1st-3rd: guaranteed < 2 min processing"
  "Close on month-end: standard processing"

  SCHEDULED TASK RESERVATION:
  "Schedule your consolidation for 02:00 AM tonight"
  Platform runs overnight â†’ result ready when CFO arrives at 9am
  Most CFO-friendly feature for peak period.
  No queue. No wait. Guaranteed.

PEAK PERFORMANCE TARGETS:
  Dashboard load:          < 1 second
  Reconciliation run:      < 5 minutes
  Consolidation (5 entities): < 5 minutes
  Report generation:       < 10 minutes
  AI query response:       < 8 seconds
  All targets met for 95th percentile during peak
```

---

## 26B. Complete pyproject.toml (Updated â€” All Libraries)

```toml
[project]
name = "financeops-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    # Web Framework
    "fastapi==0.115.0",
    "uvicorn[standard]==0.30.0",
    "gunicorn==22.0.0",
    "python-multipart==0.0.9",

    # Database
    "sqlalchemy==2.0.35",
    "asyncpg==0.30.0",
    "alembic==1.13.0",
    "pgvector==0.3.3",

    # Cache & Queues
    "redis==5.0.8",
    "celery[redis]==5.4.0",
    "flower==2.0.1",

    # Workflow
    "temporalio==1.7.0",

    # Validation
    "pydantic==2.9.0",
    "pydantic-settings==2.5.0",
    "email-validator==2.2.0",

    # Auth & Security
    "python-jose[cryptography]==3.3.0",
    "passlib[bcrypt]==1.7.4",
    "pyotp==2.9.0",
    "cryptography==43.0.0",
    "slowapi==0.1.9",

    # SSO
    "msal==1.30.0",
    "python3-saml==1.16.0",

    # Image Processing (install before OCR libraries)
    "Pillow==10.4.0",

    # File Processing
    "openpyxl==3.1.5",
    "xlsxwriter==3.2.0",
    "pandas==2.2.3",
    "numpy==2.1.0",
    "python-magic==0.4.27",
    "python-docx==1.1.2",

    # PDF Processing
    "pymupdf==1.24.10",
    "pdfplumber==0.11.4",
    "weasyprint==62.3",
    "easyocr==1.7.1",
    "pypdf==5.0.0",
    "reportlab==4.2.2",

    # Digital Signoff
    "qrcode[pil]==8.0",

    # AI / LLM
    "anthropic==0.34.0",
    "openai==1.51.0",
    "ollama==0.3.3",
    "sentence-transformers==3.1.0",
    "tiktoken==0.7.0",
    "langdetect==1.0.9",

    # NLP
    "spacy==3.8.0",

    # Cloud Storage
    "boto3==1.35.0",

    # Email
    "sendgrid==6.11.0",
    "jinja2==3.1.4",
    "aiosmtplib==3.0.1",

    # Payments
    "stripe==10.12.0",
    "razorpay==1.4.2",

    # HTTP & ERP Connectors
    "httpx==0.27.0",
    "aiohttp==3.10.0",
    "zeep==4.2.1",
    "xmltodict==0.13.0",

    # CRM Connectors (Phase 3)
    "simple-salesforce==1.12.5",

    # Teams Bot (Phase 2 â€” HR module)
    "botbuilder-core==4.15.0",
    "botbuilder-schema==4.15.0",
    "botbuilder-integration-aiohttp==4.15.0",

    # Slack Bot (Phase 2 â€” HR module)
    "slack-bolt==1.18.0",
    "slack-sdk==3.30.0",

    # Telemetry
    "opentelemetry-sdk==1.27.0",
    "opentelemetry-api==1.27.0",
    "opentelemetry-exporter-otlp==1.27.0",
    "opentelemetry-instrumentation-fastapi==0.48b0",
    "opentelemetry-instrumentation-sqlalchemy==0.48b0",
    "opentelemetry-instrumentation-redis==0.48b0",
    "opentelemetry-instrumentation-celery==0.48b0",
    "sentry-sdk[fastapi]==2.14.0",
    "prometheus-client==0.21.0",

    # Utilities
    "python-dateutil==2.9.0",
    "pytz==2024.2",
    "babel==2.16.0",
    "pycountry==24.6.1",
]

[project.optional-dependencies]
dev = [
    "pytest==8.3.0",
    "pytest-asyncio==0.24.0",
    "pytest-cov==5.0.0",
    "faker==30.0.0",
    "factory-boy==3.3.1",
    "ruff==0.6.0",
    "mypy==1.11.0",
    "pre-commit==3.8.0",
]

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Install Sequence (Order Matters)
```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Create project
uv init financeops-backend && cd financeops-backend

# 3. Install in correct order (torch first, then dependents)
uv add torch==2.4.0 Pillow==10.4.0
uv add sentence-transformers==3.1.0 easyocr==1.7.1 transformers==4.45.0
uv sync  # installs all remaining from pyproject.toml

# 4. Post-install steps
uv run python -m spacy download en_core_web_sm

# 5. Install ClamAV (OS level â€” not pip)
apt-get install -y clamav clamav-daemon
freshclam  # update virus definitions

# 6. Verify
uv run uvicorn main:app --reload
```

---

## 48. Expense Management â€” Full Specification

```
PHILOSOPHY:
  Not just expense submission.
  Full cycle: submission â†’ policy check â†’ approval â†’ GL coding â†’
  GST treatment â†’ payment â†’ reconciliation â†’ analytics.
  Every expense traceable to individual, project, department, and period.

EXPENSE LIFECYCLE:
  Employee submits â†’ Policy engine validates â†’ Manager approves â†’
  Finance reviews â†’ GL coded â†’ Payment processed â†’ Reconciled â†’
  Analytics updated

SUBMISSION (employee-facing):
  â”œâ”€â”€ Mobile-first: photo of receipt â†’ OCR extracts all fields
  â”œâ”€â”€ Fields: date, vendor, amount, currency, category, project/cost centre
  â”œâ”€â”€ Receipt OCR: Pillow + easyocr â†’ extract amount, vendor, GST number,
  â”‚     invoice number, date automatically
  â”œâ”€â”€ Multi-currency: submit in any currency, platform converts to base
  â”œâ”€â”€ Mileage claims: enter km â†’ platform applies approved rate per grade
  â”œâ”€â”€ Per diem: select city + nights â†’ platform computes allowance
  â”œâ”€â”€ Advance settlement: link to previously issued advance
  â””â”€â”€ Bulk submission: upload multiple receipts in one batch

POLICY ENGINE (configured by Finance Leader):
  Rules applied automatically at submission:
  â”œâ”€â”€ Category limits by grade:
  â”‚     "Senior Manager: meals max â‚¹2,000/day, travel max â‚¹8,000/night"
  â”œâ”€â”€ Vendor restrictions: personal merchants flagged
  â”‚     (Amazon, Swiggy, Zomato â†’ personal purchase flag)
  â”œâ”€â”€ Advance booking rules: "flights must be booked >7 days ahead"
  â”œâ”€â”€ Receipt mandatory above: â‚¹500 (configurable)
  â”œâ”€â”€ Weekend/holiday flag: claims on non-working days require justification
  â”œâ”€â”€ Duplicate detection: same amount + same vendor Â± 3 days = duplicate flag
  â”œâ”€â”€ Round number flag: â‚¹5,000 exactly without receipt = suspicious
  â”œâ”€â”€ Budget check: real-time check against department budget
  â””â”€â”€ Auto-approve: claims below â‚¹X with valid receipt (configurable)

  Policy violation response:
  SOFT:  claim submittable with mandatory justification field
  HARD:  claim blocked until policy exception approved by Finance Leader

APPROVAL WORKFLOW:
  Tier 1 (â‰¤ â‚¹5,000):    Direct manager approves â†’ Finance codes â†’ pay
  Tier 2 (â‚¹5,001-25,000): Manager + Finance Leader â†’ pay
  Tier 3 (>â‚¹25,000):    Manager + Finance Leader + CFO â†’ pay
  Configurable per tenant.

  Approval SLA:
  â”œâ”€â”€ Manager: 48 hours (reminder at 24h, escalation at 48h)
  â”œâ”€â”€ Finance: 24 hours after manager approval
  â””â”€â”€ If SLA breached: auto-escalate to next level

GL CODING (Finance layer):
  â”œâ”€â”€ AI suggests GL account (based on vendor + category + history)
  â”œâ”€â”€ Finance confirms or overrides
  â”œâ”€â”€ Cost centre: auto from employee's department or overridden to project
  â”œâ”€â”€ GST treatment (India):
  â”‚     Is this expense GST-creditable?
  â”‚     Input credit: yes/no/partial (entertainment = 50% ITC)
  â”‚     GST number of vendor: validated against GSTIN database
  â”‚     ITC amount computed and flagged for GST reconciliation module
  â””â”€â”€ TDS applicability: is TDS deductible on this payment?
        (professional fees, rent, contractor payments)

PAYMENT PROCESSING:
  Approved + GL coded â†’ payment batch generated
  Payment methods:
  â”œâ”€â”€ Bank transfer (NEFT/IMPS â€” India)
  â”œâ”€â”€ Payroll inclusion (add to next payslip)
  â””â”€â”€ Prepaid card (if tenant uses expense cards)
  Payment confirmation â†’ receipt of payment to employee
  Journal entry: Dr Expense Account / Cr Bank/Payroll Payable

ADVANCE MANAGEMENT:
  â”œâ”€â”€ Advance issued: Dr Employee Advance (asset) / Cr Bank
  â”œâ”€â”€ Expense submitted: links to advance
  â”œâ”€â”€ Settlement: Dr Expense / Cr Employee Advance
  â”œâ”€â”€ Excess refund: Dr Bank / Cr Employee Advance
  â”œâ”€â”€ Excess claim: Dr Expense / Cr Bank (additional payment)
  â””â”€â”€ Outstanding advance report: who has unsettled advances + aging

ANALYTICS (Finance Leader view):
  â”œâ”€â”€ Total spend by category (monthly, quarterly, annual)
  â”œâ”€â”€ Spend by department vs budget (variance + %)
  â”œâ”€â”€ Spend by employee (top spenders, outliers)
  â”œâ”€â”€ Spend by project/cost centre (project cost tracking)
  â”œâ”€â”€ Policy violation rate (% of claims flagged)
  â”œâ”€â”€ Average approval time (bottleneck identification)
  â”œâ”€â”€ GST ITC recovered from expenses (monthly)
  â””â”€â”€ Trend: spend per employee is increasing/decreasing?

ANOMALY DETECTION (AI â€” local model):
  â”œâ”€â”€ Employee's spend pattern vs their peer group
  â”œâ”€â”€ Vendor appears in multiple employees' claims same date (split bill)
  â”œâ”€â”€ Same receipt submitted by two employees (duplicate across employees)
  â”œâ”€â”€ Expense category mismatch (dinner claim but vendor is hardware store)
  â””â”€â”€ Frequent small claims just below approval threshold (threshold gaming)

CREDITS: 2 per expense batch processed (unlimited submissions in batch)
```

---

## 49. Statutory Registers â€” Placeholder

```
STATUS: Placeholder â€” full specification in next iteration.

SCOPE (Companies Act 2013 â€” India):
  Register of Members
  Register of Directors and KMP
  Register of Charges
  Register of Related Party Contracts
  Register of Investments
  Minutes Index

MCA Filing Calendar:
  MGT-7, AOC-4, DIR-3 KYC, DPT-3, MSME-1, BEN-2, CHG-4
  All due dates tracked, reminders automated

TO BE SPECIFIED:
  Full data model per register
  MCA XML format export
  E-form pre-population
  Digital signature integration for MCA filing
  Multi-entity management for CA firms

PRIORITY: Build after first 20 paying customers.
```

---

## 50. FDD Module â€” Placeholder for Extended Specification

```
STATUS: Core specification in Section 22. Placeholder for extensions.

WHAT IS FULLY SPECIFIED (Section 22):
  8-section FDD report generation
  QoE, QoR, Working Capital, Debt, Net Debt,
  Headcount, Contracts, Financial Controls

EXTENSIONS TO BE SPECIFIED:
  â”œâ”€â”€ FDD data room indexer (list what documents are needed)
  â”œâ”€â”€ Management accounts normalisation wizard
  â”‚     (guide user through EBITDA normalisation step by step)
  â”œâ”€â”€ Comparable company benchmarks
  â”‚     (industry margins vs target company margins)
  â”œâ”€â”€ Red flag auto-identification
  â”‚     (AI scans for: revenue concentration, customer churn,
  â”‚      related party anomalies, margin erosion, WC deterioration)
  â”œâ”€â”€ FDD findings log (track each finding with severity)
  â”œâ”€â”€ Vendor FDD template (for PE fund's standard format)
  â””â”€â”€ FDD version control (draft v1 â†’ management comments â†’ final)

PLACEHOLDER FOR CLAUDE CODE PROMPT:
  Full Claude Code prompt to be added in Phase 5B.
  Must follow FINOS_EXEC_PROMPT_TEMPLATE v1.1 (sections 1-18, 7A, 9A).
  Architecture and data model already complete.
  Implementation follows same patterns as Phase 1-4.

PRIORITY: After Finance core (Phases 0-4) is stable.
```

---

## 51. AI Accuracy Benchmarks â€” Full Specification

```
WHY THIS MATTERS:
  "AI-validated" means nothing without measuring validation accuracy.
  We must define what accuracy means, how to measure it,
  and what triggers model replacement or retraining.

ACCURACY DIMENSIONS (measured separately):

1. CLASSIFICATION ACCURACY
   Definition: GL account mapped to correct MIS line item
   Measurement: human-labelled test set per industry vertical
   Test set: 500 GL accounts per industry (CA firm, IT services,
             manufacturing, trading, real estate)
   Metric: top-1 accuracy (correct on first suggestion)
   Target: >92% top-1, >98% top-3
   Baseline: established on first 50 tenants' corrected data

2. RECONCILIATION ACCURACY
   Definition: break correctly identified + root cause correct
   Measurement: seeded test cases (known breaks introduced)
   Test set: 200 reconciliation scenarios across entity types
   Metric: % of breaks correctly identified and root-caused
   Target: >95% identification, >88% root cause correct

3. COMMENTARY ACCURACY
   Definition: AI commentary factually consistent with underlying numbers
   Measurement: automated fact-check (every number in commentary
                cross-referenced against source data)
   Metric: fact-check pass rate
   Target: 100% factual accuracy (zero hallucinated numbers)
   Additional: human rating of commentary quality (1-5 scale)
   Target: >4.0 average human quality rating

4. FORECAST ACCURACY
   Definition: AI-suggested assumptions vs actual outcomes
   Measurement: compare AI forecast vs actual for closed periods
   Metric: MAPE (Mean Absolute Percentage Error) per line item
   Target: Revenue MAPE <8%, Cost MAPE <10%, EBITDA MAPE <12%
   Tracked: monthly, rolling 3-month, rolling 12-month

5. VALIDATION AGREEMENT RATE (Stage 3)
   Definition: Stage 2 and Stage 3 models agree without Stage 4
   Measurement: % of pipeline runs where Stage 4 not triggered
   Target: >95% (Stage 4 triggered <5% of runs)
   Alert: if agreement rate drops below 90% for any task type

6. HUMAN ACCEPTANCE RATE
   Definition: Finance Leader accepts AI output without major edit
   Measurement: track accepts vs significant edits vs full rewrites
   Target: >88% acceptance, <8% significant edit, <4% full rewrite
   Tracked: per task type, per tenant, per module
   Action: if acceptance <80% for any task type â†’ investigate model

BENCHMARK TEST SUITE:
  Location: tests/ai_benchmarks/
  Contents:
  â”œâ”€â”€ classification_test_set.json    (500 GL accounts, labelled)
  â”œâ”€â”€ reconciliation_test_set.json    (200 scenarios, known answers)
  â”œâ”€â”€ commentary_test_set.json        (50 MIS + expected commentary facts)
  â”œâ”€â”€ forecast_test_set.json          (historical periods, known actuals)
  â””â”€â”€ run_benchmarks.py              (runs all tests, generates report)

  Run: uv run python tests/ai_benchmarks/run_benchmarks.py
  Output: benchmark_report_{date}.json + human-readable summary
  Schedule: run weekly (Celery Beat, Sunday 03:00 UTC)
  Alert: if any metric drops >3% week-over-week â†’ P2 alert

BENCHMARK REPORT FORMAT:
  {
    "run_date": "2025-04-06",
    "classification": {
      "top1_accuracy": 0.934,
      "top3_accuracy": 0.981,
      "by_industry": {...},
      "worst_performing_categories": [...]
    },
    "reconciliation": {
      "identification_rate": 0.962,
      "root_cause_accuracy": 0.891
    },
    "commentary": {
      "fact_check_pass_rate": 1.0,
      "human_quality_avg": 4.2
    },
    "forecast": {
      "revenue_mape": 0.071,
      "cost_mape": 0.089,
      "ebitda_mape": 0.104
    },
    "validation_agreement": 0.963,
    "human_acceptance": 0.891,
    "overall_health": "GREEN",
    "actions_required": []
  }
```

---

## 52. Model Fallback Chain â€” Full Specification

```
PHILOSOPHY:
  Every AI call must complete. No task fails because one model is down.
  Fallback is automatic, logged, and cost-tracked.
  User never sees a model error â€” they see their result.

FALLBACK CHAIN ARCHITECTURE:

For each task type, a priority-ordered list of models:
If Model 1 fails (timeout/error/rate limit) â†’ try Model 2 â†’ try Model 3

TASK TYPE â†’ FALLBACK CHAIN:

CLASSIFICATION (GL â†’ MIS mapping):
  1. phi3:mini (local Ollama)          â€” fastest, free, private
  2. mistral:7b (local Ollama)         â€” fallback local
  3. claude-haiku-3 (Anthropic API)    â€” fast cloud fallback
  4. gpt-4o-mini (OpenAI API)          â€” secondary cloud
  NEVER reach beyond 4 for classification (simple enough task)

VARIANCE ANALYSIS + COMMENTARY:
  1. mistral:7b (local Ollama)         â€” primary local
  2. deepseek-r1:8b (local Ollama)     â€” fallback local
  3. claude-sonnet-4-5 (Anthropic)     â€” primary cloud
  4. gpt-4o (OpenAI)                   â€” secondary cloud
  5. gemini-1.5-pro (Google)           â€” tertiary cloud

COMPLEX ADVISORY (FDD, PPA, M&A):
  1. claude-opus-4-5 (Anthropic)       â€” primary (best reasoning)
  2. gpt-4o (OpenAI)                   â€” fallback cloud
  3. gemini-1.5-pro (Google)           â€” tertiary
  NO local model for advisory (complexity requires cloud)

VALIDATION (Stage 3):
  1. gpt-4o-mini (OpenAI)              â€” primary validator
  2. claude-haiku-3 (Anthropic)        â€” fallback validator
  3. gemini-1.5-flash (Google)         â€” tertiary
  Rule: validator must be different provider than Stage 2 executor
        (independent validation, not same model checking itself)

STANDARDS LOOKUP:
  1. Platform knowledge graph (local)  â€” fastest, zero cost
  2. mistral:7b with IFRS context      â€” local fallback
  3. claude-haiku-3                    â€” cloud fallback
  ALWAYS try local knowledge graph first

HR MANUAL QUERIES:
  1. mistral:7b (local Ollama)         â€” MANDATORY first (data privacy)
  2. phi3:mini (local Ollama)          â€” local fallback only
  NEVER cloud model for HR manual (local-only policy)

FALLBACK TRIGGER CONDITIONS:
  â”œâ”€â”€ HTTP timeout: >30 seconds â†’ trigger fallback
  â”œâ”€â”€ Rate limit (429): â†’ immediate fallback to next model
  â”œâ”€â”€ API error (5xx): â†’ immediate fallback
  â”œâ”€â”€ Token limit exceeded: â†’ route to model with larger context
  â”œâ”€â”€ Low confidence score (<0.7): â†’ don't fallback, trigger Stage 4
  â””â”€â”€ Model unavailable (Ollama): â†’ skip to cloud immediately

FALLBACK IMPLEMENTATION:
```python
# backend/ai_gateway/fallback.py

class ModelFallbackChain:

    CHAINS = {
        "classification": [
            ModelConfig("phi3:mini", provider="ollama", timeout=15),
            ModelConfig("mistral:7b", provider="ollama", timeout=20),
            ModelConfig("claude-haiku-3", provider="anthropic", timeout=30),
            ModelConfig("gpt-4o-mini", provider="openai", timeout=30),
        ],
        "variance_analysis": [
            ModelConfig("mistral:7b", provider="ollama", timeout=30),
            ModelConfig("deepseek-r1:8b", provider="ollama", timeout=45),
            ModelConfig("claude-sonnet-4-5", provider="anthropic", timeout=60),
            ModelConfig("gpt-4o", provider="openai", timeout=60),
            ModelConfig("gemini-1.5-pro", provider="google", timeout=60),
        ],
        "advisory": [
            ModelConfig("claude-opus-4-5", provider="anthropic", timeout=120),
            ModelConfig("gpt-4o", provider="openai", timeout=120),
            ModelConfig("gemini-1.5-pro", provider="google", timeout=120),
        ],
        "validation": [
            ModelConfig("gpt-4o-mini", provider="openai", timeout=30),
            ModelConfig("claude-haiku-3", provider="anthropic", timeout=30),
            ModelConfig("gemini-1.5-flash", provider="google", timeout=30),
        ],
        "hr_manual": [
            ModelConfig("mistral:7b", provider="ollama", timeout=30),
            ModelConfig("phi3:mini", provider="ollama", timeout=20),
            # NO CLOUD MODELS â€” HR data local only
        ],
    }

    async def execute_with_fallback(
        self,
        task_type: str,
        prompt: str,
        tenant_id: str,
        context: dict
    ) -> AIResult:

        chain = self.CHAINS.get(task_type, self.CHAINS["variance_analysis"])
        last_error = None

        for i, model_config in enumerate(chain):
            try:
                start = time.time()
                result = await self._call_model(model_config, prompt, context)
                duration_ms = (time.time() - start) * 1000

                # Log which model was used and if it was a fallback
                await log_model_usage(
                    task_type=task_type,
                    model=model_config.name,
                    provider=model_config.provider,
                    attempt_number=i + 1,
                    was_fallback=(i > 0),
                    duration_ms=duration_ms,
                    tenant_id=tenant_id,
                )

                if i > 0:
                    # Alert if using fallback model (degraded service)
                    severity = "P2" if i >= 2 else "P3"
                    await send_alert(
                        severity=severity,
                        message=f"Using fallback model {model_config.name} "
                                f"for {task_type} (attempt {i+1})",
                        context={"primary_error": str(last_error)}
                    )

                return result

            except RateLimitError:
                last_error = f"Rate limit: {model_config.name}"
                continue  # immediate fallback, no wait

            except TimeoutError:
                last_error = f"Timeout: {model_config.name}"
                continue

            except APIError as e:
                last_error = f"API error {e.status_code}: {model_config.name}"
                await asyncio.sleep(1)  # brief wait before next attempt
                continue

        # All models exhausted â€” this should never happen
        await send_alert(severity="P1",
            message=f"ALL models failed for {task_type}. Last error: {last_error}")
        raise AllModelsFailedError(task_type, last_error)
```

FALLBACK METRICS (tracked in telemetry):
  â”œâ”€â”€ fallback_rate per task type (target: <2%)
  â”œâ”€â”€ fallback_reason distribution (rate limit vs timeout vs error)
  â”œâ”€â”€ model_availability per provider (uptime % per month)
  â”œâ”€â”€ cost_increase_from_fallback (cloud costs more than local)
  â””â”€â”€ Alert: fallback rate >5% for any task type = P2

PROVIDER HEALTH DASHBOARD:
  Ollama (local):     â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆ 99.9% âœ…
  Anthropic API:      â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆ 99.8% âœ…
  OpenAI API:         â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆ 99.7% âœ…
  Google Gemini:      â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘  99.1% âœ…
  Fallback rate:      1.2%          âœ…
```

---

## 53. Disaster Recovery Runbook

```
CLASSIFICATION: Internal operations document.
OWNER: Founder / CTO
REVIEW: Quarterly or after any P0/P1 incident
LAST TESTED: [date of last DR drill]

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
SECTION 1: INCIDENT CLASSIFICATION
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

P0 â€” COMPLETE OUTAGE (all users affected, data at risk):
  Examples: primary DB down, data centre failure, security breach
  Action: THIS RUNBOOK, full DR activation

P1 â€” SEVERE DEGRADATION (>20% users affected):
  Examples: API workers down, queue processing stopped
  Action: THIS RUNBOOK sections 3-5 only (no failover needed)

P2 â€” PARTIAL DEGRADATION (some features unavailable):
  Examples: single service down, slow queries
  Action: Standard incident response (not this runbook)

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
SECTION 2: CONTACT LIST
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

Primary:    Founder â€” [phone] â€” [email]
Secondary:  Lead Dev â€” [phone] â€” [email]
Database:   Railway Support â€” support.railway.app
Cloud:      Cloudflare Support â€” [account ID]
Payments:   Stripe Support â€” [account ID]
Monitoring: PagerDuty â€” [account URL]

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
SECTION 3: IMMEDIATE ACTIONS (first 5 minutes)
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

STEP 1: ASSESS (2 minutes)
  â–¡ Check Grafana dashboard: what is actually down?
  â–¡ Check PagerDuty: what alerts are firing?
  â–¡ Check Railway dashboard: are services running?
  â–¡ Check Cloudflare: is traffic reaching the platform?
  â–¡ Determine: P0 or P1? (data loss risk or not?)

STEP 2: COMMUNICATE (1 minute)
  â–¡ Post in #platform-alerts Slack: "Investigating incident, ETA 15 min"
  â–¡ If >5 minutes of outage: update status page
  â–¡ Do NOT contact customers until you know what happened

STEP 3: STOP THE BLEEDING (2 minutes)
  â–¡ If active attack: block IP ranges in Cloudflare WAF
  â–¡ If bad deployment: rollback immediately (Railway rollback button)
  â–¡ If runaway query: kill it (pg_cancel_backend)
  â–¡ If queue flood: pause Celery workers (flower dashboard)

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
SECTION 4: DATABASE FAILURE RECOVERY
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

SCENARIO A: Primary DB unresponsive (not crashed, just slow):
  â–¡ Check pg_stat_activity: is there a blocking query?
     SELECT pid, query, state, wait_event FROM pg_stat_activity
     WHERE state != 'idle' ORDER BY duration DESC;
  â–¡ Kill blocking query: SELECT pg_cancel_backend(pid);
  â–¡ Check connection pool: is PgBouncer exhausted?
  â–¡ Check CPU/memory on Railway: is it resource-starved?
  â–¡ If resource-starved: scale up Railway DB instance immediately
  RECOVERY TIME TARGET: 15 minutes

SCENARIO B: Primary DB crashed (process died):
  â–¡ Railway auto-restarts PostgreSQL â†’ wait 2 minutes
  â–¡ If not restarted in 2 min: restart via Railway dashboard
  â–¡ Check WAL integrity: psql -c "SELECT pg_last_wal_receive_lsn();"
  â–¡ Verify data integrity: run chain_hash_check.py script
  â–¡ If data integrity fail: proceed to Scenario C
  RECOVERY TIME TARGET: 10 minutes

SCENARIO C: Data corruption or irreversible failure:
  â–¡ IMMEDIATELY activate standby (Cloudflare DNS failover):
     cloudflare_failover.sh --activate-standby
  â–¡ Verify standby is accepting connections
  â–¡ Verify standby data is current (check replication lag was <60s)
  â–¡ Notify all tenants: "We experienced a brief service interruption.
     All data is intact. Service restored."
  â–¡ Post-incident: investigate root cause before failing back
  RECOVERY TIME TARGET: 30 minutes

SCENARIO D: Total data loss (catastrophic):
  â–¡ This should never happen with WAL archiving + daily snapshots
  â–¡ If it does: restore from most recent verified daily backup
  â–¡ Identify: what is the RPO? (time of last WAL archive)
  â–¡ Restore procedure:
     1. Provision new PostgreSQL instance (Railway)
     2. Run: restore_from_backup.sh --date YYYY-MM-DD --time HH:MM
     3. Apply WAL archives from last backup to failure point
     4. Verify chain hash integrity
     5. Switch traffic to restored instance
  â–¡ Notify affected tenants with exact data loss window
  â–¡ Offer: credit compensation per SLA terms
  RECOVERY TIME TARGET: 2 hours

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
SECTION 5: APPLICATION FAILURE RECOVERY
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

SCENARIO: FastAPI workers all down:
  â–¡ Check Railway: are containers running?
  â–¡ If crashed: Railway auto-restarts â†’ wait 2 minutes
  â–¡ If restart loop: check recent deployment (bad code?)
  â–¡ Rollback: railway rollback --service api
  â–¡ Verify: curl https://api.yourplatform.com/health â†’ 200
  RECOVERY TIME: 5 minutes

SCENARIO: Celery workers down (tasks queuing, not processing):
  â–¡ Check flower dashboard: are workers connected?
  â–¡ Restart workers: railway restart --service celery-worker
  â–¡ Check queue depth: are tasks accumulating?
  â–¡ If high queue: scale up workers temporarily
  â–¡ Verify: submit test task â†’ check it completes
  RECOVERY TIME: 5 minutes

SCENARIO: Bad deployment (new code breaking things):
  â–¡ IMMEDIATE rollback: railway rollback (do not investigate first)
  â–¡ Verify rollback successful: check error rate drops
  â–¡ THEN investigate what went wrong in staging
  RECOVERY TIME: 3 minutes

SCENARIO: DDoS attack:
  â–¡ Cloudflare auto-mitigates most DDoS attacks
  â–¡ If bypassing Cloudflare: enable "Under Attack Mode" in Cloudflare
  â–¡ If targeted: block specific IP ranges in WAF
  â–¡ Check: is this real DDoS or runaway client?
  â–¡ If legitimate user's code in a loop: contact tenant
  RECOVERY TIME: 2 minutes (Cloudflare handles it)

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
SECTION 6: SECURITY INCIDENT RECOVERY
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

SCENARIO: Suspected data breach:
  â–¡ STOP: do not investigate on production systems
  â–¡ IMMEDIATELY: take forensic snapshot of all systems
  â–¡ IMMEDIATELY: rotate ALL secrets (Doppler emergency rotation)
  â–¡ IMMEDIATELY: invalidate ALL active JWT tokens (rotate JWT secret)
  â–¡ IMMEDIATELY: notify affected tenants (legal requirement, 72 hours)
  â–¡ Preserve: all logs (do not clear, do not restart services yet)
  â–¡ Engage: security professional before touching anything
  â–¡ Report: GDPR/DPDP authority within 72 hours if PII involved

SCENARIO: Ransomware / malicious code:
  â–¡ IMMEDIATELY: take all systems offline
  â–¡ DO NOT pay ransom
  â–¡ Restore from last clean backup (verify backup predates infection)
  â–¡ Security audit before bringing systems back online
  â–¡ Notify all tenants

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
SECTION 7: COMMUNICATION TEMPLATES
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

STATUS PAGE UPDATE â€” INVESTIGATING:
  "We are aware of an issue affecting [service].
   We are investigating and will provide an update in 15 minutes.
   Time detected: [time UTC]"

STATUS PAGE UPDATE â€” IDENTIFIED:
  "We have identified the cause of the [service] issue: [brief description].
   We are working on a fix. Estimated resolution: [time].
   No data has been lost."

STATUS PAGE UPDATE â€” RESOLVED:
  "The [service] issue has been resolved as of [time UTC].
   Total duration: [X] minutes.
   Root cause: [brief description].
   We apologise for the inconvenience."

TENANT EMAIL â€” SLA BREACH:
  Subject: Service Interruption â€” [Date] â€” FinanceOps
  "Dear [Name],
   We experienced a service interruption on [date] from [time] to [time]
   ([X] minutes total). This affected [service].
   As per our SLA, we are crediting your account [X] credits.
   Root cause: [description]. Prevention measures: [description].
   We apologise for the disruption."

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
SECTION 8: POST-INCIDENT PROCESS
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

Within 24 hours of any P0/P1 incident:
  â–¡ Write blameless post-mortem (5 whys, not blame)
  â–¡ Document: timeline, root cause, impact, resolution
  â–¡ Identify: what monitoring would have caught this earlier?
  â–¡ Identify: what would have made recovery faster?
  â–¡ Create: action items with owners and due dates
  â–¡ Update: this runbook with lessons learned
  â–¡ Update: Error Ledger (Document 04)

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
SECTION 9: DR DRILL SCHEDULE
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

Monthly (first Sunday): Backup restoration test
  â†’ Restore daily backup to test instance â†’ verify integrity â†’ document

Quarterly: Full failover drill
  â†’ Simulate primary failure â†’ activate standby â†’ verify traffic
  â†’ Fail back to primary â†’ document RTO achieved

Annual: Full DR simulation
  â†’ Simulate total data loss â†’ restore from cold backup â†’ document
```

---

## 54. Data Migration Tooling

```
PROBLEM:
  Every new customer has 2-5 years of historical data in:
  â”œâ”€â”€ Excel workbooks (most common)
  â”œâ”€â”€ Their ERP (Tally, Zoho, etc.)
  â”œâ”€â”€ Google Sheets
  â””â”€â”€ Previous finance software (if any)

  They cannot use the platform without historical data.
  Without history: no trend analysis, no variance vs prior year,
  no forecasting, no multi-year FDD.

MIGRATION TYPES:

TYPE 1 â€” EXCEL MIGRATION (most common, do this first):
  What they have: 2-5 years of MIS in Excel files
  What we need: structured TB/GL data per period per entity

  Migration wizard:
  Step 1: Upload historical Excel files (one per month or year)
  Step 2: Platform maps their columns to our schema
          AI does first pass â†’ user confirms/adjusts
  Step 3: Platform validates: totals balance? gaps in periods?
  Step 4: Historical data imported as "migrated" records
          (separate from live data, clearly labelled)
  Step 5: Verification: prior period report generated â†’ user confirms
          numbers match their records

TYPE 2 â€” ERP HISTORICAL PULL:
  What they have: 2-5 years in Tally/Zoho/QuickBooks
  What we do: use ERP connector to pull historical data
              same connector as live sync, just with historical date range
  Limitation: some ERPs have API limits on historical data
  Solution: offer bulk export + upload path as fallback

TYPE 3 â€” OPENING BALANCE MIGRATION:
  Minimum viable: just opening balances for current year
  Upload opening TB â†’ all modules can function from that date
  Historical analysis limited to current year only
  Simplest migration path for customers who want to start fast

MIGRATION TOOLING:

class DataMigrationWizard:

  STEPS = [
    "upload_files",           # upload historical data files
    "auto_map_columns",       # AI maps their columns to our schema
    "user_confirm_mapping",   # user reviews and adjusts mapping
    "validate_data",          # check totals, gaps, duplicates
    "preview_import",         # show what will be imported
    "confirm_import",         # user confirms
    "run_import",             # background import job
    "verify_import",          # generate prior period report for verification
    "complete"                # mark migration complete
  ]

  Validation checks:
  â”œâ”€â”€ Debit = Credit for every period (TB balance check)
  â”œâ”€â”€ No gaps in period sequence
  â”œâ”€â”€ No duplicate periods
  â”œâ”€â”€ Entity names consistent across periods
  â”œâ”€â”€ Currency consistent (or flagged for review)
  â””â”€â”€ Negative values: are they intentional or data errors?

MIGRATION AUDIT TRAIL:
  Every migrated record flagged: source="migration", source_file="Q1_2023.xlsx"
  Migrated data never mixed with live data in source field
  Migration log: what was imported, when, by whom, validation results

MIGRATION SUPPORT (onboarding):
  Starter plan: self-service migration wizard only
  Professional plan: 1 assisted migration session (60 min call)
  Business plan: full migration assistance (dedicated session)
  Enterprise: full migration service (we do it for them)

CREDITS: Migration is free (included in onboarding fee)
```

---

## 55. Grafana Dashboard Schemas & ClickHouse Configuration

```
GRAFANA DASHBOARD DEFINITIONS:

1. INFRASTRUCTURE DASHBOARD (infra/grafana/dashboards/infrastructure.json)
   Panels:
   â”œâ”€â”€ API request rate (requests/sec) â€” time series
   â”œâ”€â”€ API error rate (4xx, 5xx separately) â€” time series
   â”œâ”€â”€ API p50/p95/p99 latency â€” time series
   â”œâ”€â”€ CPU per service (api, celery, temporal) â€” gauge + time series
   â”œâ”€â”€ Memory per service â€” gauge + time series
   â”œâ”€â”€ Container restarts â€” counter
   â”œâ”€â”€ Network in/out per service â€” time series
   â””â”€â”€ Active deployments â€” annotation overlay
   Refresh: 30 seconds
   Time range default: last 3 hours

2. APPLICATION DASHBOARD (infra/grafana/dashboards/application.json)
   Panels:
   â”œâ”€â”€ Queue depth â€” all 4 queues â€” real-time gauge
   â”œâ”€â”€ Task completion rate (per queue) â€” time series
   â”œâ”€â”€ Task failure rate â€” time series
   â”œâ”€â”€ p50/p95/p99 task duration per task type â€” heatmap
   â”œâ”€â”€ Active Temporal workflows â€” gauge
   â”œâ”€â”€ Stuck workflows â€” alert panel (red if > 0)
   â”œâ”€â”€ Dead letter queue count â€” alert panel
   â””â”€â”€ Top 10 slowest endpoints (last 1 hour) â€” table
   Refresh: 10 seconds
   Time range default: last 1 hour

3. DATABASE DASHBOARD (infra/grafana/dashboards/database.json)
   Panels:
   â”œâ”€â”€ Active connections vs max â€” gauge
   â”œâ”€â”€ Connection pool utilisation â€” time series
   â”œâ”€â”€ Queries per second â€” time series
   â”œâ”€â”€ Slow queries (>1s) count â€” counter
   â”œâ”€â”€ p50/p95/p99 query duration â€” time series
   â”œâ”€â”€ Deadlocks (should be zero) â€” alert panel
   â”œâ”€â”€ Index bloat per table â€” table
   â”œâ”€â”€ Replication lag â€” gauge (alert if > 30s)
   â”œâ”€â”€ Database size growth â€” time series
   â””â”€â”€ Cache hit ratio (pg_stat_bgwriter) â€” gauge
   Refresh: 30 seconds

4. AI PIPELINE DASHBOARD (infra/grafana/dashboards/ai_pipeline.json)
   Panels:
   â”œâ”€â”€ Pipeline runs per hour â€” time series
   â”œâ”€â”€ Stage 4 trigger rate â€” time series (target line at 5%)
   â”œâ”€â”€ Average total pipeline duration â€” gauge
   â”œâ”€â”€ p50/p95 duration per stage â€” bar chart
   â”œâ”€â”€ AI cost per hour (by model) â€” stacked time series
   â”œâ”€â”€ Local vs cloud model ratio â€” pie chart
   â”œâ”€â”€ Cache hit rate â€” gauge
   â”œâ”€â”€ Validation agreement score distribution â€” histogram
   â”œâ”€â”€ Human acceptance rate (30d rolling) â€” time series
   â””â”€â”€ Model availability per provider â€” status panel
   Refresh: 60 seconds

5. BUSINESS DASHBOARD (infra/grafana/dashboards/business.json)
   Panels:
   â”œâ”€â”€ MRR â€” big number with trend arrow
   â”œâ”€â”€ Active tenants â€” big number with delta
   â”œâ”€â”€ NRR (30d) â€” gauge with target line at 110%
   â”œâ”€â”€ Credits consumed today â€” counter
   â”œâ”€â”€ AI cost today â€” counter
   â”œâ”€â”€ Gross margin today â€” gauge
   â”œâ”€â”€ New tenants this month â€” counter
   â”œâ”€â”€ Churned tenants this month â€” counter
   â”œâ”€â”€ Tenant health distribution (green/yellow/red) â€” pie chart
   â””â”€â”€ MRR trend (90 days) â€” time series
   Refresh: 300 seconds (5 minutes)

GRAFANA PROVISIONING (auto-loaded on startup):
  infra/grafana/
  â”œâ”€â”€ grafana.ini              â€” main config
  â”œâ”€â”€ provisioning/
  â”‚   â”œâ”€â”€ datasources/
  â”‚   â”‚   â”œâ”€â”€ prometheus.yaml  â€” Prometheus datasource
  â”‚   â”‚   â”œâ”€â”€ loki.yaml        â€” Loki datasource
  â”‚   â”‚   â””â”€â”€ clickhouse.yaml  â€” ClickHouse datasource
  â”‚   â””â”€â”€ dashboards/
  â”‚       â””â”€â”€ dashboard.yaml   â€” auto-load all JSON dashboards
  â””â”€â”€ dashboards/
      â”œâ”€â”€ infrastructure.json
      â”œâ”€â”€ application.json
      â”œâ”€â”€ database.json
      â”œâ”€â”€ ai_pipeline.json
      â””â”€â”€ business.json

CLICKHOUSE SCHEMA (product analytics):

CREATE DATABASE financeops_analytics;

-- Every user action event
CREATE TABLE financeops_analytics.events (
    event_id        UUID DEFAULT generateUUIDv4(),
    tenant_id_hash  String,          -- SHA256 hashed
    user_id_hash    String,          -- SHA256 hashed
    session_id      String,
    event_name      String,          -- 'module_opened', 'task_run', etc.
    event_category  String,          -- 'activation', 'engagement', 'friction'
    module          Nullable(String),
    feature         Nullable(String),
    properties      String,          -- JSON blob of event properties
    credits_used    Nullable(UInt32),
    duration_ms     Nullable(UInt32),
    device_type     String,          -- 'web', 'mobile', 'pwa'
    created_at      DateTime
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (tenant_id_hash, created_at)
TTL created_at + INTERVAL 3 YEAR;

-- AI pipeline runs (time-series analytics)
CREATE TABLE financeops_analytics.ai_pipeline_runs (
    run_id              UUID,
    tenant_id_hash      String,
    task_type           String,
    module              String,
    stage1_duration_ms  UInt32,
    stage2_duration_ms  UInt32,
    stage3_duration_ms  UInt32,
    stage4_duration_ms  Nullable(UInt32),
    stage4_triggered    UInt8,
    total_duration_ms   UInt32,
    stage2_model        String,
    stage3_model        String,
    validation_score    Float32,
    human_accepted      Nullable(UInt8),
    cache_hit           UInt8,
    total_cost_usd      Float32,
    created_at          DateTime
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (tenant_id_hash, task_type, created_at)
TTL created_at + INTERVAL 2 YEAR;

-- Daily business metrics (permanent)
CREATE TABLE financeops_analytics.business_metrics_daily (
    date                Date,
    mrr                 Decimal(18,2),
    arr                 Decimal(18,2),
    active_tenants      UInt32,
    new_tenants         UInt16,
    churned_tenants     UInt16,
    new_mrr             Decimal(18,2),
    expansion_mrr       Decimal(18,2),
    churned_mrr         Decimal(18,2),
    nrr                 Float32,
    grr                 Float32,
    arpu                Decimal(18,2),
    credits_sold        UInt64,
    credits_consumed    UInt64,
    ai_cost_usd         Decimal(18,4),
    gross_margin_pct    Float32
) ENGINE = ReplacingMergeTree()
ORDER BY date;

-- Tenant health history
CREATE TABLE financeops_analytics.tenant_health_scores (
    tenant_id_hash      String,
    score               UInt8,
    risk_level          String,
    risk_factors        String,    -- JSON array
    positive_factors    String,    -- JSON array
    computed_at         DateTime
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(computed_at)
ORDER BY (tenant_id_hash, computed_at)
TTL computed_at + INTERVAL 2 YEAR;

CLICKHOUSE QUERIES (pre-built for Grafana):

-- Feature adoption funnel
SELECT
    event_name,
    count(DISTINCT tenant_id_hash) as tenants,
    count(DISTINCT user_id_hash) as users
FROM events
WHERE created_at >= now() - INTERVAL 30 DAY
    AND event_name IN (
        'first_mis_upload', 'first_reconciliation_run',
        'first_consolidation_run', 'first_ai_query',
        'first_report_generated'
    )
GROUP BY event_name ORDER BY tenants DESC;

-- AI cost trend by model
SELECT
    toDate(created_at) as date,
    stage2_model,
    sum(total_cost_usd) as daily_cost,
    count() as runs
FROM ai_pipeline_runs
WHERE created_at >= now() - INTERVAL 30 DAY
GROUP BY date, stage2_model
ORDER BY date, daily_cost DESC;
```

---

## 56. ERP Connector Completions & Placeholders

```
FULLY SPECIFIED CONNECTORS (Phases 0-4):
  Tally         âœ… SOAP/XML â€” full spec in Section 10
  Zoho Books    âœ… REST/OAuth2 â€” full spec
  QuickBooks    âœ… REST/OAuth2 â€” full spec
  Xero          âœ… REST/OAuth2 â€” full spec
  SAP           âœ… REST/OData â€” full spec
  Dynamics 365  âœ… REST/OAuth2 â€” full spec
  Sage          âœ… REST/OAuth2 â€” full spec
  NetSuite      âœ… REST/OAuth2 â€” full spec

ADDITIONAL ERP CONNECTORS (implementation follows same base pattern):

Busy Accounting (India â€” SME focused):
  Method: REST API + CSV export
  Priority: HIGH (large India SME market)
  Data: TB, GL, vouchers
  Auth: API key
  Status: Add to Phase 2 ERP connector batch

Marg ERP (India â€” pharma/FMCG):
  Method: ODBC/CSV export (limited API)
  Priority: MEDIUM
  Data: TB, GL via export
  Auth: direct DB connection or export
  Status: Phase 3

Miracle Accounting (India):
  Method: CSV export + manual upload
  Priority: LOW
  Status: Phase 4 â€” self-service upload path covers this

FreshBooks (global freelancer/SME):
  Method: REST/OAuth2
  Priority: MEDIUM (global market)
  Status: Phase 2

Wave Accounting (free, SME global):
  Method: GraphQL API
  Priority: LOW
  Status: Phase 3

Odoo (open source ERP):
  Method: XML-RPC or REST (Odoo 16+)
  Priority: MEDIUM (growing India adoption)
  Status: Phase 2

HRMS CONNECTORS â€” PLACEHOLDERS (Phase 2):
  All follow same base connector interface as ERP connectors.

  Darwinbox:
    Auth: OAuth2
    Endpoints: /employees, /attendance, /leave_balances, /payroll
    Sync: employee master (daily), leave (daily), payroll (monthly)
    Status: PLACEHOLDER â€” full spec when HR module starts

  Keka:
    Auth: OAuth2 + API key
    Endpoints: /employees, /leaves, /attendance, /payroll
    Status: PLACEHOLDER

  greytHR:
    Auth: API key
    Endpoints: /employee, /payroll, /leave
    Status: PLACEHOLDER

  Zoho People:
    Auth: OAuth2 (same Zoho OAuth as Zoho Books)
    Status: PLACEHOLDER

  BambooHR:
    Auth: API key
    Endpoints: /employees, /time_off, /payroll
    Status: PLACEHOLDER

  Workday:
    Auth: OAuth2 (complex â€” Workday has non-standard OAuth)
    Method: SOAP (legacy) or REST (Workday 2020+)
    Status: PLACEHOLDER â€” enterprise connector, Phase 3

CRM CONNECTORS â€” PLACEHOLDERS (Phase 3):
  All follow same base connector interface.

  Salesforce:
    Auth: OAuth2 (Connected App)
    Library: simple-salesforce
    Endpoints: /sobjects/Opportunity, /sobjects/Account
    Sync: pipeline (daily), closed deals (webhook + daily)
    Status: PLACEHOLDER

  HubSpot:
    Auth: OAuth2
    Endpoints: /crm/v3/objects/deals, /crm/v3/objects/companies
    Status: PLACEHOLDER

  Pipedrive:
    Auth: OAuth2
    Endpoints: /deals, /organizations, /products
    Status: PLACEHOLDER

  Zoho CRM:
    Auth: OAuth2 (same Zoho OAuth)
    Status: PLACEHOLDER

  Freshsales:
    Auth: API key
    Status: PLACEHOLDER
```

---

## 57. Report Template Marketplace

```
MARKETPLACE ARCHITECTURE:

THREE TYPES OF TEMPLATES:
  Type 1 â€” Platform Templates (built by FinanceOps team):
    Free, included in all plans
    Examples: Standard MIS, Board Pack, FDD Summary, Audit Schedule

  Type 2 â€” Partner Templates (built by verified CA/Finance partners):
    Paid, revenue share 70% contributor / 30% platform
    Examples: Industry-specific MIS (IT services, manufacturing, retail)
              Big 4 style FDD template, PE investor reporting format

  Type 3 â€” Community Templates (built by any tenant, shared):
    Free or paid (contributor decides)
    Revenue share: 60% contributor / 40% platform
    Requires: platform review before publishing

TEMPLATE REGISTRY (database):
  CREATE TABLE template_marketplace (
    template_id       UUID PRIMARY KEY,
    name              VARCHAR(200),
    description       TEXT,
    type              VARCHAR(20),  -- platform/partner/community
    category          VARCHAR(50),  -- MIS/report/board_pack/FDD/etc
    industry          VARCHAR(50),  -- IT/manufacturing/retail/all
    price_credits     INTEGER,      -- 0 = free
    contributor_id    UUID,
    preview_url       TEXT,
    download_count    INTEGER DEFAULT 0,
    rating_avg        DECIMAL(3,2),
    rating_count      INTEGER DEFAULT 0,
    version           VARCHAR(10),
    created_at        TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ,
    status            VARCHAR(20)   -- draft/review/published/deprecated
  );

TEMPLATE CONTENTS:
  Each template is a ZIP containing:
  â”œâ”€â”€ template.json       â€” metadata + structure definition
  â”œâ”€â”€ mis_structure.json  â€” MIS line items and hierarchy
  â”œâ”€â”€ report_config.json  â€” report layout, sections, formulas
  â”œâ”€â”€ sample_output.pdf   â€” preview of what output looks like
  â””â”€â”€ README.md           â€” instructions for use

MARKETPLACE FRONTEND:
  Browse by: category, industry, price (free/paid), rating
  Preview: sample output PDF before purchase
  One-click install: template applied to tenant's MIS Manager
  Ratings: 1-5 stars + text review after use
  Usage stats: how many tenants use this template

TEMPLATE CONTRIBUTION FLOW:
  1. Contributor builds template (in their own tenant)
  2. Submits for review: fill metadata, upload ZIP
  3. Platform review: structural validity check (automated)
              + quality review (manual, 2 business days)
  4. Published to marketplace
  5. Revenue: credited to contributor's platform account monthly
  6. Updates: contributor can publish new versions

CREDITS:
  Free templates:   0 credits
  Paid templates:   20-200 credits (contributor sets price)
  Commission paid:  to contributor's account, cashable monthly
```

---

## 58. Custom Report Builder

```
WHAT IT IS:
  Drag-and-drop report designer.
  Finance Leader builds their own report layout
  without needing a developer.
  Output: Excel or PDF, same quality as platform-generated reports.

COMPONENTS:

DATA SOURCES (what can be dragged in):
  â”œâ”€â”€ Any MIS line item (from configured MIS)
  â”œâ”€â”€ Any GL account or account group
  â”œâ”€â”€ Headcount metrics (from headcount module)
  â”œâ”€â”€ Pipeline metrics (from sales module â€” Phase 3)
  â”œâ”€â”€ Computed metrics (EBITDA, margin %, growth %)
  â””â”€â”€ Custom formula (user defines their own computation)

LAYOUT ELEMENTS:
  â”œâ”€â”€ Table: rows Ã— columns with headers
  â”œâ”€â”€ Chart: bar, line, waterfall, pie, scatter
  â”œâ”€â”€ KPI Card: single number with trend indicator
  â”œâ”€â”€ Text block: narrative section (AI can populate)
  â”œâ”€â”€ Divider / section header
  â””â”€â”€ Page break (for multi-page reports)

FORMULA BUILDER:
  Visual formula editor (no coding):
  Example: "EBITDA Margin %" = [EBITDA] / [Revenue] Ã— 100
  Supports: +, -, Ã—, Ã·, %, IF, SUM, AVERAGE, MIN, MAX
  Preview: shows computed value on sample data immediately

PERIOD SELECTION:
  Each data element selectable by period:
  Current month | Prior month | Prior year | YTD | Rolling 12M
  Variance: auto-computed vs selected comparison period

TEMPLATE SAVE & SHARE:
  Save as tenant template (reuse every month)
  Share to marketplace (monetise)
  Schedule: auto-generate on specific date each month

IMPLEMENTATION:
  Frontend: React drag-and-drop (react-dnd library)
  Report definition: JSON stored in report_templates table
  Rendering: same Excel/PDF generation engine as platform reports
  Preview: live preview as user builds (uses sample data)

CREDITS: 0 to build, 10 to generate each time (same as other reports)
```

---

## 59. White Label Implementation

```
WHITE LABEL TIERS:

TIER 1 â€” CO-BRANDED (Professional plan+):
  â”œâ”€â”€ Company logo in top-left (replaces FinanceOps logo)
  â”œâ”€â”€ Company colors (primary + secondary)
  â”œâ”€â”€ Company name in browser tab: "Finance | [Company Name]"
  â”œâ”€â”€ Email sender: noreply@[company-domain].com
  â”œâ”€â”€ All PDF/Excel outputs: company logo + branding
  â””â”€â”€ Login page: company logo + optional background image
  Setup: self-service in Settings â†’ Branding
  Cost: included in Professional+ plans

TIER 2 â€” FULLY WHITE LABELED (Business plan + add-on):
  Everything in Tier 1 plus:
  â”œâ”€â”€ Custom domain: finance.clientcompany.com
  â”‚     (CNAME to platform, SSL auto-provisioned via Cloudflare)
  â”œâ”€â”€ No "Powered by FinanceOps" mention anywhere
  â”œâ”€â”€ Custom login page (fully designed)
  â”œâ”€â”€ Custom email templates (company branded)
  â”œâ”€â”€ Custom onboarding flow (company-specific welcome)
  â””â”€â”€ Custom terms of service URL
  Setup: requires DNS change by customer
  Cost: +$100/month add-on

TIER 3 â€” CA FIRM WHITE LABEL (Partner program):
  Everything in Tier 2 plus:
  â”œâ”€â”€ CA firm's own branded platform for all their clients
  â”œâ”€â”€ Each client sees: "ClientName Finance Portal by [CA Firm]"
  â”œâ”€â”€ CA firm is the account manager for all client tenants
  â”œâ”€â”€ CA firm sets their own pricing to clients (reseller model)
  â”œâ”€â”€ CA firm gets wholesale pricing from platform (40% discount)
  â””â”€â”€ Dedicated subdomain: [cafirm].financeops.io or custom domain
  Cost: $499/month + per-client-tenant fees

WHITE LABEL DATABASE:
  CREATE TABLE tenant_branding (
    tenant_id         UUID PRIMARY KEY REFERENCES tenants(id),
    logo_url          TEXT,
    primary_color     VARCHAR(7),   -- hex
    secondary_color   VARCHAR(7),
    company_name      VARCHAR(200),
    custom_domain     VARCHAR(200),
    email_from_name   VARCHAR(200),
    email_from_addr   VARCHAR(200),
    hide_platform_brand BOOLEAN DEFAULT FALSE,
    favicon_url       TEXT,
    login_bg_url      TEXT,
    updated_at        TIMESTAMPTZ
  );

CUSTOM DOMAIN PROVISIONING:
  Tenant adds CNAME: finance â†’ [tenant_id].app.financeops.io
  Platform: Cloudflare Workers detects custom domain â†’ routes to tenant
  SSL: Cloudflare auto-provisions SSL certificate
  Time to live: < 5 minutes after DNS propagation
```

---

## 60. HIPAA Compliance Implementation

```
APPLICABILITY:
  Required if any tenant is a US healthcare entity
  handling Protected Health Information (PHI).
  PHI includes: patient financial data, insurance billing,
  healthcare provider financial statements.
  
  NOTE: FinanceOps handles FINANCIAL data about healthcare companies,
  not clinical data. HIPAA applies to Business Associates
  handling PHI â€” even in financial context.

HIPAA SAFEGUARDS IMPLEMENTED:

ADMINISTRATIVE SAFEGUARDS:
  â”œâ”€â”€ Business Associate Agreement (BAA):
  â”‚     Required before any healthcare tenant onboards
  â”‚     Template BAA in legal/baa_template.md
  â”‚     BAA signed digitally (DocuSign or platform signoff module)
  â”œâ”€â”€ Workforce training: HIPAA training for all team members
  â”œâ”€â”€ Minimum necessary standard:
  â”‚     Users access only PHI necessary for their role
  â”‚     Already enforced by existing RBAC + RLS
  â””â”€â”€ Incident response: 60-day breach notification (HIPAA requirement)
      (stricter than GDPR's 72 hours)

PHYSICAL SAFEGUARDS:
  â”œâ”€â”€ Facility access: cloud infrastructure (AWS/Railway)
  â”‚     Both are HIPAA-eligible (BAA available with AWS)
  â”œâ”€â”€ Workstation security: remote work policy required for team
  â””â”€â”€ Media controls: encrypted storage (already implemented)

TECHNICAL SAFEGUARDS:
  â”œâ”€â”€ Unique user identification: âœ… (existing auth)
  â”œâ”€â”€ Automatic logoff: session timeout 8 hours âœ…
  â”œâ”€â”€ Encryption in transit: TLS 1.3 âœ…
  â”œâ”€â”€ Encryption at rest: AES-256 âœ…
  â”œâ”€â”€ Audit controls:
  â”‚     All PHI access logged with: who, what, when, from where
  â”‚     Logs retained: 6 years (HIPAA requirement)
  â”‚     Existing immutable audit trail covers this âœ…
  â”œâ”€â”€ Integrity controls:
  â”‚     Chain hash integrity on all records âœ…
  â””â”€â”€ Transmission security: TLS âœ…

HIPAA-SPECIFIC ADDITIONS:
  â”œâ”€â”€ PHI data flag: new column phi_data BOOLEAN on relevant tables
  â”‚     If phi_data = TRUE: additional access logging applied
  â”œâ”€â”€ PHI access log: separate table for all PHI record access
  â”‚     (beyond standard audit trail â€” HIPAA requires this specifically)
  â”œâ”€â”€ BAA tracking: table of signed BAAs with expiry dates
  â”œâ”€â”€ HIPAA tenant flag: tenants marked as HIPAA-covered
  â”‚     Additional controls auto-applied
  â””â”€â”€ Annual risk assessment: Celery Beat reminder annually

DATABASE ADDITIONS:
  -- Mark PHI-sensitive records
  ALTER TABLE gl_transactions ADD COLUMN phi_data BOOLEAN DEFAULT FALSE;
  ALTER TABLE contracts ADD COLUMN phi_data BOOLEAN DEFAULT FALSE;

  -- HIPAA-specific access log (6-year retention)
  CREATE TABLE hipaa_phi_access_log (
    log_id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    user_id         UUID NOT NULL,
    record_type     VARCHAR(100),
    record_id       UUID,
    access_type     VARCHAR(20),  -- view/export/modify
    justification   TEXT,
    ip_address      INET,
    accessed_at     TIMESTAMPTZ DEFAULT NOW()
  );

  -- Business Associate Agreements
  CREATE TABLE baa_agreements (
    baa_id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    signed_by       VARCHAR(200),
    signed_at       TIMESTAMPTZ,
    effective_date  DATE,
    expiry_date     DATE,
    document_url    TEXT,
    status          VARCHAR(20) DEFAULT 'active'
  );

AWS BAA:
  AWS provides HIPAA BAA for covered services including:
  RDS (PostgreSQL), S3 (equivalent to R2), EC2
  Must be executed before processing PHI on AWS
  Railway: not HIPAA-eligible â†’ migrate PHI tenants to AWS directly
```

---

## 61. UAE DIFC Data Protection Implementation

```
JURISDICTION: Dubai International Financial Centre
REGULATION: DIFC Data Protection Law (DPL 2020) + amendments
APPLICABILITY: any tenant operating in or from DIFC free zone

KEY REQUIREMENTS vs GDPR:

SIMILARITIES (existing GDPR implementation covers):
  â”œâ”€â”€ Lawful basis for processing âœ…
  â”œâ”€â”€ Data subject rights (access, erasure, portability) âœ…
  â”œâ”€â”€ Privacy by design âœ…
  â””â”€â”€ Data breach notification (72 hours to DIFC Commissioner) âœ…

DIFC-SPECIFIC ADDITIONS:

1. DATA PROTECTION OFFICER (DPO) REGISTRATION:
   Tenants processing "high risk" data in DIFC must register DPO
   Platform: DPO name and contact stored per DIFC tenant
   Reminder: annual re-registration check

2. DATA TRANSFERS OUTSIDE DIFC:
   DIFC has its own adequacy list (different from EU)
   UK, EU, and some others: adequate
   India: NOT on DIFC adequacy list
   UAE mainland: NOT DIFC (different jurisdiction)

   Platform impact:
   â”œâ”€â”€ DIFC tenant data: must stay within DIFC or adequate countries
   â”œâ”€â”€ AI processing: cannot route to India-based AI services
   â”œâ”€â”€ Support access: if accessed from India for debugging â†’ restricted
   â””â”€â”€ Backup: backups must be in adequate jurisdiction

3. DATA PROCESSING REGISTER:
   DIFC requires: maintain register of all data processing activities
   Platform provides: auto-generated processing register per DIFC tenant
   Fields: purpose, legal basis, data categories, retention, transfers

4. PRIVACY NOTICE:
   DIFC tenants: platform generates DIFC-compliant privacy notice
   Language requirements: English (Arabic optional)

5. DATA LOCALISATION:
   DIFC tenant data: stored in AWS me-central-1 (UAE) or me-south-1 (Bahrain)
   No data routed through non-adequate countries

DATABASE ADDITIONS:
  -- DIFC processing register
  CREATE TABLE difc_processing_register (
    entry_id        UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id       UUID NOT NULL,
    processing_purpose VARCHAR(500),
    legal_basis     VARCHAR(100),
    data_categories TEXT,
    data_subjects   TEXT,
    recipients      TEXT,
    transfer_countries TEXT,
    retention_period VARCHAR(100),
    security_measures TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
  );

  -- DPO registration
  ALTER TABLE tenants ADD COLUMN difc_tenant BOOLEAN DEFAULT FALSE;
  ALTER TABLE tenants ADD COLUMN dpo_name VARCHAR(200);
  ALTER TABLE tenants ADD COLUMN dpo_email VARCHAR(200);
  ALTER TABLE tenants ADD COLUMN dpo_registered_at TIMESTAMPTZ;
```

---

## 62. Singapore PDPA & Australia Privacy Act â€” Placeholders

```
SINGAPORE PDPA â€” PLACEHOLDER:
  Personal Data Protection Act (PDPA 2012, amended 2020)
  Key additions needed:
  â”œâ”€â”€ Do Not Call (DNC) registry check for marketing
  â”œâ”€â”€ Data Protection Officer appointment (mandatory for some orgs)
  â”œâ”€â”€ Notification of data breach to PDPC within 3 days
  â”‚     (stricter than GDPR 72 hours â€” only 3 days)
  â”œâ”€â”€ Data portability obligation (from 2021 amendment)
  â””â”€â”€ Singapore data residency: AWS ap-southeast-1 (Singapore)
  Status: PLACEHOLDER â€” implement when Singapore customer count > 5

AUSTRALIA PRIVACY ACT â€” PLACEHOLDER:
  Privacy Act 1988 + Australian Privacy Principles (APPs)
  Key additions needed:
  â”œâ”€â”€ APP 8: cross-border disclosure obligations
  â”œâ”€â”€ APP 11: security of personal information
  â”œâ”€â”€ Notifiable Data Breaches (NDB) scheme:
  â”‚     Notify OAIC + affected individuals if serious breach
  â”œâ”€â”€ Privacy policy: APP-compliant privacy policy per tenant
  â””â”€â”€ Australian data residency: AWS ap-southeast-2 (Sydney)
  Status: PLACEHOLDER â€” implement when Australia customer count > 5

ACTIVATION TRIGGER FOR BOTH:
  When tenant count in jurisdiction exceeds 5:
  â†’ Add to implementation plan as next compliance sprint
  â†’ Legal review of jurisdiction-specific requirements
  â†’ Add to compliance calendar
```

---

## 63. Partner & Reseller Program

```
THREE PARTNER TYPES:

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
TYPE 1 â€” REFERRAL PARTNER
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
Who: Individual CAs, finance professionals, consultants
Commitment: None â€” refer customers, earn commission
Commission: 20% of first year MRR for every referred customer
            (paid monthly as long as customer is active)
Example: Refer 5 Business plan customers ($449/month each)
         = 5 Ã— $449 Ã— 20% = $449/month passive income
         For as long as those customers stay

Mechanics:
  â”œâ”€â”€ Unique referral link (tracked in platform)
  â”œâ”€â”€ Dashboard: referred customers, status, earnings
  â”œâ”€â”€ Payout: monthly via bank transfer (min $50 threshold)
  â””â”€â”€ No cap on referrals or earnings

Qualification: none â€” anyone can become referral partner
Sign-up: self-service at partners.yourplatform.com

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
TYPE 2 â€” RESELLER PARTNER (CA Firms primarily)
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
Who: CA firms managing 10+ client companies
Commitment: minimum 10 active client tenants
Benefit: 40% wholesale discount on all client tenant subscriptions
         White label (Tier 3) included
         Dedicated partner portal to manage all clients
         Partner's own branded platform for clients

Example:
  CA firm manages 20 clients on Business plan
  Retail price: 20 Ã— $449 = $8,980/month
  Reseller price: 20 Ã— $449 Ã— 60% = $5,388/month (they pay)
  CA firm charges clients: their own pricing (e.g. â‚¹15,000/client)
  CA firm revenue: 20 Ã— â‚¹15,000 = â‚¹3,00,000/month
  CA firm cost: $5,388 = â‚¹4,50,000/month
  CA firm profit: â‚¹3,00,000 - â‚¹4,50,000 = ... they need to charge more
  
  REALITY CHECK:
  CA firm charges clients â‚¹25,000/month (full service + platform)
  20 clients Ã— â‚¹25,000 = â‚¹5,00,000/month revenue
  Platform cost: â‚¹4,50,000/month
  Net margin: â‚¹50,000/month (thin â€” but platform replaces 2 staff members)
  
  Better model: CA firm keeps existing staff, uses platform to serve
  more clients without adding headcount.
  Capacity: 1 CA + platform can handle 15 clients vs 5 without platform
  Revenue: 15 Ã— â‚¹25,000 = â‚¹3,75,000/month without adding staff

Qualification:
  â”œâ”€â”€ Minimum 10 active client tenants within 60 days of signing
  â”œâ”€â”€ One team member completes platform certification
  â””â”€â”€ Signed reseller agreement

Partner portal features:
  â”œâ”€â”€ Manage all client tenants from one login
  â”œâ”€â”€ Consolidated billing (one invoice for all clients)
  â”œâ”€â”€ Client health dashboard (which clients are active/at-risk)
  â”œâ”€â”€ Bulk client onboarding tools
  â”œâ”€â”€ Client usage analytics (by CA firm)
  â””â”€â”€ Training resources + certification program

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
TYPE 3 â€” TECHNOLOGY PARTNER / INTEGRATION PARTNER
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
Who: ERP vendors, HRMS vendors, other SaaS companies
Commitment: build and maintain integration connector
Benefit: listed in marketplace, co-marketing, revenue share on
         new customers acquired through their platform

Examples:
  Tally partner: Tally resellers refer customers to FinanceOps
  Zoho partner: listed in Zoho Marketplace
  Keka partner: HR data auto-syncs for Keka customers

Revenue share: 15% of first year for Tally/Zoho referred customers
Listing: co-branded marketplace listing on their platform

â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
PARTNER DATABASE:
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

CREATE TABLE partners (
  partner_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  partner_type      VARCHAR(20),     -- referral/reseller/technology
  name              VARCHAR(200),
  email             VARCHAR(200),
  company           VARCHAR(200),
  country           VARCHAR(50),
  referral_code     VARCHAR(20) UNIQUE,
  commission_rate   DECIMAL(5,2),    -- %
  discount_rate     DECIMAL(5,2),    -- % discount for resellers
  status            VARCHAR(20),     -- pending/active/suspended
  signed_at         TIMESTAMPTZ,
  total_referred    INTEGER DEFAULT 0,
  total_earnings    DECIMAL(18,2) DEFAULT 0,
  created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE partner_referrals (
  referral_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  partner_id        UUID REFERENCES partners(partner_id),
  tenant_id         UUID REFERENCES tenants(id),
  referral_date     TIMESTAMPTZ,
  status            VARCHAR(20),     -- pending/converted/churned
  first_payment_at  TIMESTAMPTZ,
  total_commission  DECIMAL(18,2) DEFAULT 0
);

CREATE TABLE partner_payouts (
  payout_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  partner_id        UUID REFERENCES partners(partner_id),
  period_start      DATE,
  period_end        DATE,
  amount            DECIMAL(18,2),
  currency          VARCHAR(3),
  status            VARCHAR(20),     -- pending/paid/failed
  paid_at           TIMESTAMPTZ,
  payment_reference VARCHAR(200)
);

PARTNER PORTAL (frontend):
  partners.yourplatform.com (separate subdomain)
  â”œâ”€â”€ Dashboard: earnings, referrals, active clients
  â”œâ”€â”€ Referral link generator + QR code
  â”œâ”€â”€ Client management (resellers only)
  â”œâ”€â”€ Payout history + bank details
  â”œâ”€â”€ Training centre + certification
  â””â”€â”€ Marketing assets (logos, pitch deck, one-pagers)

CERTIFICATION PROGRAM:
  FinanceOps Certified Advisor (FCA):
  â”œâ”€â”€ 4-hour online course (platform features + finance best practices)
  â”œâ”€â”€ Assessment: 30 questions, 80% pass rate
  â”œâ”€â”€ Certificate: digital, shareable on LinkedIn
  â”œâ”€â”€ Benefits: listed in partner directory, priority support
  â””â”€â”€ Renewal: annual
```


---

## 64. RTO/RPO Summary Table

| Scenario | RTO | RPO | Priority | Recovery Path |
|---|---|---|---|---|
| DB failure (process died) | 30 min | 5 min | P0 | Auto-restart â†’ WAL replay |
| Region failure (full DC down) | 2 hours | 5 min | P0 | Cloudflare failover â†’ standby |
| Accidental data deletion | 15 min | 0 | P1 | R2 versioning â†’ point-in-time restore |
| Ransomware / data corruption | 4 hours | 24 hours | P0 | Restore from last clean verified backup |
| Bad deployment (code issue) | 3 min | 0 | P1 | Railway rollback â†’ previous image |
| Redis failure | 10 min | 6 hours | P1 | Auto-restart â†’ RDB snapshot restore |
| Celery workers down | 5 min | 0 | P1 | Railway auto-restart â†’ queue replay |
| Single API worker crash | 60 sec | 0 | P2 | Railway auto-restart |
| DDoS attack | 2 min | 0 | P1 | Cloudflare Under Attack Mode |
| SSL certificate expiry | 5 min | 0 | P2 | Cloudflare auto-renewal |

```
DEFINITIONS:
  RTO (Recovery Time Objective): maximum time to restore service
  RPO (Recovery Point Objective): maximum data loss acceptable
  P0: wake up now, all hands
  P1: fix within 1 hour
  P2: fix within 4 hours
```

---

## 65. Library Compatibility Matrix

```
CRITICAL COMPATIBILITY NOTES:

1. OpenCV conflict (most common install error):
   WRONG:  opencv-python        â† includes GUI, conflicts on server
   RIGHT:  opencv-python-headless==4.10.0.84  â† server-safe

2. torch must install BEFORE easyocr and sentence-transformers:
   easyocr==1.7.1 requires torch already present
   sentence-transformers==3.1.0 requires torch already present

3. Verified compatible stack:
   torch==2.4.0
   opencv-python-headless==4.10.0.84
   easyocr==1.7.1
   sentence-transformers==3.1.0
   transformers==4.45.0
   Pillow==10.4.0

4. botbuilder packages require aiohttp â€” already listed âœ…

5. python3-saml requires xmlsec1 OS package:
   apt-get install -y xmlsec1 libxmlsec1-dev

COMPLETE INSTALL SEQUENCE:
  # OS dependencies first
  apt-get install -y xmlsec1 libxmlsec1-dev clamav clamav-daemon

  # Python â€” order matters
  uv add torch==2.4.0
  uv add opencv-python-headless==4.10.0.84
  uv add Pillow==10.4.0
  uv add easyocr==1.7.1
  uv add sentence-transformers==3.1.0 transformers==4.45.0
  uv sync  # install everything else from pyproject.toml

  # Post-install
  uv run python -m spacy download en_core_web_sm
  freshclam  # update ClamAV definitions
```

---

## 66. Immutability Taxonomy

```
THREE TIERS â€” EVERY DATABASE TABLE BELONGS TO ONE:

TIER 1 â€” IMMUTABLE EVIDENTIARY (never UPDATE, never DELETE, ever):
  Tables:
  â”œâ”€â”€ audit_trail              (every user action)
  â”œâ”€â”€ chain_hash_ledger        (chain hash per record)
  â”œâ”€â”€ ai_pipeline_runs         (every AI execution)
  â”œâ”€â”€ signoff_certificates     (Director/CFO signoffs)
  â”œâ”€â”€ hipaa_phi_access_log     (HIPAA access records)
  â”œâ”€â”€ payment_transactions     (every payment event)
  â”œâ”€â”€ auditor_access_log       (auditor activity)
  â””â”€â”€ security_events          (auth anomalies, breaches)
  
  Rule: INSERT only. No UPDATE. No DELETE. No exceptions.
  Even platform admins cannot modify these records.
  Retention: permanent (regulatory requirement).

TIER 2 â€” VERSIONED FINANCIAL OBJECTS (history preserved):
  Tables:
  â”œâ”€â”€ gl_transactions          (new version on adjustment)
  â”œâ”€â”€ mis_data                 (new period = new record)
  â”œâ”€â”€ consolidation_runs       (each run is new record)
  â”œâ”€â”€ ai_outputs               (each generation is new record)
  â”œâ”€â”€ adjustments              (append-only adjustments)
  â”œâ”€â”€ budgets                  (new version on revision)
  â”œâ”€â”€ forecasts                (each scenario is new record)
  â””â”€â”€ contract_versions        (new version on amendment)
  
  Rule: INSERT new version. Mark old as superseded.
        Never DELETE. Never UPDATE financial fields.
        current_version BOOLEAN flag on latest only.
  Retention: 7 years minimum (regulatory).

TIER 3 â€” MUTABLE OPERATIONAL STATE (standard CRUD):
  Tables:
  â”œâ”€â”€ user_preferences         (UPDATE permitted)
  â”œâ”€â”€ notification_settings    (UPDATE permitted)
  â”œâ”€â”€ draft_reports            (UPDATE/DELETE permitted)
  â”œâ”€â”€ closing_checklist_tasks  (status UPDATE permitted)
  â”œâ”€â”€ session_data             (TTL expiry, auto-delete)
  â”œâ”€â”€ cache_entries            (TTL expiry)
  â””â”€â”€ tenant_branding          (UPDATE permitted)
  
  Rule: Standard INSERT/UPDATE/DELETE.
  Retention: as needed, configurable.

DEVELOPER RULE:
  Before writing any UPDATE or DELETE query,
  check which tier the table belongs to.
  Tier 1 or Tier 2 financial fields = STOP, use INSERT instead.
  Document the tier in every table's schema comment.

  Example:
  -- TIER 1: IMMUTABLE EVIDENTIARY
  CREATE TABLE audit_trail ( ... );

  -- TIER 2: VERSIONED FINANCIAL
  CREATE TABLE gl_transactions ( ... );

  -- TIER 3: MUTABLE OPERATIONAL
  CREATE TABLE user_preferences ( ... );
```

---

## 67. Module Dependency Matrix

| Module | Hard Requires | Soft Requires | Blocks |
|---|---|---|---|
| MIS Manager | Core Auth, File Upload | â€” | Everything |
| GL/TB Reconciliation | MIS Manager | ERP Connector | Consolidation |
| Bank Reconciliation | MIS Manager | ERP Connector | â€” |
| Multi-entity Consolidation | MIS Manager, GL/TB Recon | Multi-currency | FDD, Board Pack |
| Budgeting | MIS Manager | Headcount Analytics | Forecasting |
| Forecasting | Budgeting | Revenue Recognition | Board Pack |
| Fixed Asset Register | MIS Manager | â€” | Lease Accounting, PPA |
| Lease Accounting | Fixed Asset Register | â€” | â€” |
| Revenue Recognition | MIS Manager, Contracts | â€” | FDD |
| Headcount Analytics | MIS Manager | Paysheet Integration | HR Module |
| Paysheet Integration | MIS Manager | HRMS Connector | Commission Engine |
| Debt & Covenants | MIS Manager, Forecasting | â€” | â€” |
| Closing Checklist | MIS Manager | Bank Recon, GL/TB Recon | â€” |
| Working Capital | MIS Manager | ERP Connector | â€” |
| GST Reconciliation | MIS Manager | ERP Connector | â€” |
| FDD Report | Consolidation, RevRec, Contracts | Headcount, Paysheets | â€” |
| PPA | Fixed Asset Register, Consolidation | â€” | â€” |
| M&A Workspace | FDD, Valuation Engine | â€” | â€” |
| Audit Support Package | All Finance Modules | â€” | â€” |
| Scenario Modelling | Forecasting, MIS Manager | â€” | â€” |
| HR Module | Core Platform, Paysheet Integration | Finance Headcount | Commission Engine |
| Sales Intelligence | Core Platform | Finance RevRec | Commission Engine |
| Commission Engine | HR Module, Sales Intelligence | Paysheet Integration | â€” |
| Enterprise OS | Finance + HR + Sales Modules | â€” | â€” |

```
IMPLEMENTATION ORDER (derived from dependency matrix):
  Layer 0: Core Auth + File Upload + Multi-tenancy
  Layer 1: MIS Manager
  Layer 2: GL/TB Recon, Bank Recon (parallel)
  Layer 3: Consolidation, Fixed Asset Register (parallel)
  Layer 4: Budgeting, RevRec, Headcount (parallel)
  Layer 5: Forecasting, Lease Accounting, Paysheets (parallel)
  Layer 6: FDD, Board Pack, Closing Checklist (parallel)
  Layer 7: AI Pipeline, NLQ, Vector Memory
  Later:   HR Module â†’ Sales Intelligence â†’ Enterprise OS
```

---

## 68. Offline Capability Matrix

```
CLARIFICATION: "Local First" in FinanceOps means:
  LOCAL AI MODELS for sensitive data (privacy) â€” NOT offline capability.
  The platform requires internet connectivity for most functions.
  This table defines exactly what works in each connectivity state.

| Feature | Online | Degraded* | Offline |
|---|---|---|---|
| View cached dashboards | âœ… | âœ… | âœ… (last cached) |
| View previously generated reports | âœ… | âœ… | âœ… (cached) |
| Closing checklist (view + update) | âœ… | âœ… | âœ… (cached) |
| Upload new files | âœ… | âŒ | âŒ |
| Run reconciliation | âœ… | âŒ | âŒ |
| Run consolidation | âœ… | âŒ | âŒ |
| AI Chat (local Ollama model) | âœ… | âœ… | âœ… (if Ollama running locally) |
| AI Chat (cloud model) | âœ… | âŒ | âŒ |
| HR Manual query | âœ… | âœ… | âœ… (local Ollama only) |
| Generate new reports | âœ… | âŒ | âŒ |
| ERP sync | âœ… | âŒ | âŒ |
| Authentication (new login) | âœ… | âŒ | âŒ |
| Authentication (existing session) | âœ… | âœ… | âœ… (JWT valid) |
| Download/export existing files | âœ… | âœ… | âŒ (needs R2) |

* Degraded = internet available but platform API unreachable

OFFLINE BUFFER (limited):
  Frontend queues these actions when offline, syncs when reconnected:
  â”œâ”€â”€ Closing checklist task status updates
  â”œâ”€â”€ AI chat messages (local model responses only)
  â””â”€â”€ Draft form inputs (not submitted yet)
  
  Queue max: 50 items. User warned when approaching limit.
  Queue stored: browser IndexedDB (encrypted).

MARKETING LANGUAGE GUIDANCE:
  Say: "Local AI processing for sensitive HR and financial data"
  Say: "AI models run on your infrastructure for data privacy"
  Do NOT say: "Works fully offline" or "Local first"
  These phrases imply offline capability we do not provide.
```

---

## 69. Payment Failure Grace Period

```
PAYMENT FAILURE LIFECYCLE:

DAY 0 â€” Payment fails:
  â”œâ”€â”€ Retry immediately (same day, 3 hours later)
  â”œâ”€â”€ Email to Finance Leader: "Payment failed â€” update card"
  â”œâ”€â”€ In-app banner: yellow warning
  â””â”€â”€ All features: FULLY ACTIVE (no disruption)

DAY 1 â€” First retry fails:
  â”œâ”€â”€ Email: second warning with direct link to billing
  â”œâ”€â”€ In-app banner: orange warning
  â””â”€â”€ All features: FULLY ACTIVE

DAY 3 â€” Still unpaid:
  â”œâ”€â”€ Email: final warning before restriction
  â”œâ”€â”€ In-app banner: red warning
  â”œâ”€â”€ READ-ONLY MODE activated:
  â”‚     â”œâ”€â”€ View all data: âœ…
  â”‚     â”œâ”€â”€ Download existing reports: âœ…
  â”‚     â”œâ”€â”€ Run new tasks: âŒ (blocked)
  â”‚     â”œâ”€â”€ Upload new files: âŒ (blocked)
  â”‚     â”œâ”€â”€ AI queries: âŒ (blocked)
  â”‚     â””â”€â”€ ERP sync: âŒ (blocked)
  â””â”€â”€ Auditor access: âœ… maintained (never disrupted)

DAY 7 â€” Still unpaid:
  â”œâ”€â”€ Email: account suspension warning
  â”œâ”€â”€ EXPORT-ONLY MODE:
  â”‚     â”œâ”€â”€ Download all their data (full export): âœ…
  â”‚     â”œâ”€â”€ View data: âœ… (read-only)
  â”‚     â””â”€â”€ Everything else: âŒ
  â””â”€â”€ Prominent: "Export your data before Day 14"

DAY 14 â€” Suspended:
  â”œâ”€â”€ Account suspended: login shows payment required screen
  â”œâ”€â”€ Data: retained for 90 days
  â”œâ”€â”€ Reactivation: update payment â†’ immediate full access restored
  â””â”€â”€ No data loss on reactivation

DAY 104 (90 days after suspension):
  â”œâ”€â”€ Final warning: "Data will be deleted in 7 days"
  â”œâ”€â”€ Day 111: data permanently deleted
  â””â”€â”€ Cannot be reversed

RULES:
  Auditor access is NEVER disrupted by payment failure.
  (Auditor did nothing wrong â€” do not punish them)
  
  Month-end protection: if payment fails on day 25-5 of close period,
  delay READ-ONLY activation until day 8 of next month.
  (Never disrupt a CFO mid-close â€” guaranteed churn if you do)
```

---

## 70. AI Prompt Versioning

```
EVERY SYSTEM PROMPT IS VERSIONED AND DATABASE-STORED.
No hardcoded prompts in application code.

DATABASE:
CREATE TABLE ai_prompt_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_key      VARCHAR(100) NOT NULL,
    -- e.g. 'classification_stage2', 'variance_commentary_stage2',
    --      'fdd_section1_stage2', 'consolidation_stage2'
    version         INTEGER NOT NULL,
    prompt_text     TEXT NOT NULL,
    model_target    VARCHAR(100),  -- which model this prompt is tuned for
    is_active       BOOLEAN DEFAULT FALSE,
    performance_notes TEXT,        -- why this version was created
    activated_by    UUID REFERENCES users(id),
    activated_at    TIMESTAMPTZ,
    deactivated_at  TIMESTAMPTZ,
    acceptance_rate DECIMAL(5,4),  -- measured after activation
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (prompt_key, version)
);

PROMPT LOADING (in application):
  # NEVER do this:
  system_prompt = "You are a finance AI that..."  # hardcoded

  # ALWAYS do this:
  system_prompt = await load_active_prompt('classification_stage2')

  async def load_active_prompt(prompt_key: str) -> str:
      # Cache in Redis for 5 minutes (avoid DB hit per request)
      cached = await redis.get(f'prompt:{prompt_key}')
      if cached:
          return cached
      prompt = await db.fetchone(
          "SELECT prompt_text FROM ai_prompt_versions
           WHERE prompt_key = $1 AND is_active = TRUE",
          prompt_key
      )
      await redis.setex(f'prompt:{prompt_key}', 300, prompt.prompt_text)
      return prompt.prompt_text

PROMPT ROLLBACK:
  If new prompt version causes acceptance rate to drop:
  1. Deactivate new version: is_active = FALSE
  2. Reactivate previous: is_active = TRUE
  3. Flush Redis cache for that prompt key
  4. New version takes effect within 5 minutes (cache TTL)
  
  Total rollback time: < 5 minutes, no code deploy required.

A/B TESTING PROMPTS:
  Optional: run two prompt versions simultaneously
  prompt_variant = 'A' if hash(tenant_id) % 10 < 1 else 'B'
  (10% of tenants get variant B â€” compare acceptance rates)
```

---

## 71. Module Name Registry

| Official Name | API Base Path | DB Schema Prefix | Phase |
|---|---|---|---|
| MIS Manager | /api/v1/mis | mis_ | Phase 1 |
| GL/TB Reconciliation | /api/v1/reconciliation | recon_ | Phase 1 |
| Bank Reconciliation | /api/v1/bank-recon | bank_recon_ | Phase 1B |
| Multi-entity Consolidation | /api/v1/consolidation | consol_ | Phase 2 |
| Fixed Asset Register | /api/v1/assets | far_ | Phase 2 |
| Lease Accounting | /api/v1/leases | lease_ | Phase 2 |
| Revenue Recognition | /api/v1/revenue-recognition | revrev_ | Phase 3 |
| Headcount Analytics | /api/v1/headcount | hc_ | Phase 3 |
| Paysheet Integration | /api/v1/paysheets | paysheet_ | Phase 3 |
| Budgeting | /api/v1/budgets | budget_ | Phase 4 |
| Forecasting | /api/v1/forecasts | forecast_ | Phase 4 |
| Working Capital | /api/v1/working-capital | wc_ | Phase 1B |
| GST Reconciliation | /api/v1/gst-recon | gst_ | Phase 1B |
| Scenario Modelling | /api/v1/scenarios | scenario_ | Phase 1B |
| Debt & Covenants | /api/v1/covenants | covenant_ | Phase 4 |
| Closing Checklist | /api/v1/close-checklist | checklist_ | Phase 1B |
| Expense Management | /api/v1/expenses | expense_ | Phase 1C |
| Contracts | /api/v1/contracts | contract_ | Phase 3 |
| FDD Report | /api/v1/fdd | fdd_ | Phase 5 |
| PPA | /api/v1/ppa | ppa_ | Phase 5 |
| M&A Workspace | /api/v1/ma | ma_ | Phase 5 |
| Board Pack | /api/v1/board-pack | boardpack_ | Phase 6 |
| Audit Support | /api/v1/audit-support | audit_ | Phase 5 |
| Auditor Access | /api/v1/auditor | auditor_ | Phase 1 |
| HR Module | /api/v1/hr | hr_ | Phase 2A |
| Sales Intelligence | /api/v1/sales | sales_ | Phase 3A |
| Commission Engine | /api/v1/commission | commission_ | Phase 3A |
| Partner Portal | /api/v1/partners | partner_ | Phase 4 |

---

## 72. Stage 4 Correction Accuracy & Model Retraining Triggers

```
STAGE 4 CORRECTION ACCURACY (new benchmark â€” add to Section 51):

Definition: % of Stage 4 outputs accepted by Finance Leader
            without further significant edit
Measurement: track accept vs significant_edit vs full_rewrite
             after every Stage 4 human review
Target: >85% accepted without significant edit
Alert: if drops below 80% for any task type â†’ P2 alert

FULL ACCURACY BENCHMARK TARGETS (complete list):

Metric                          Target    Alert Threshold    Action
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
Classification top-1            >92%      <89%               Review model
Classification top-3            >98%      <95%               Review model
Reconciliation identification   >95%      <92%               Review model
Reconciliation root cause       >88%      <85%               Review model
Commentary fact-check           100%      <99%               Immediate P1
Commentary quality (human)      >4.0/5    <3.7               Review prompts
Forecast revenue MAPE           <8%       >12%               Review assumptions
Forecast EBITDA MAPE            <12%      >18%               Review model
Validation agreement (Stage 3)  >95%      <90%               Review Stage 3
Human acceptance rate           >88%      <83%               Review prompts
Stage 4 trigger rate            <5%       >8%                Review Stage 3
Stage 4 correction accuracy     >85%      <80%               Review Stage 4

MODEL RETRAINING / REPLACEMENT TRIGGERS:

TRIGGER 1 â€” Acceptance rate drops >5% in 30-day rolling window:
  Action: P2 alert â†’ review Stage 2 prompt first
          If prompt change doesn't fix: consider model switch
          If model switch doesn't fix: consider fine-tuning

TRIGGER 2 â€” Any metric below alert threshold for 7 consecutive days:
  Action: P1 â†’ immediate investigation
          Suspend task type if below threshold by >10%
          Use Claude Code to analyse where failures occur

TRIGGER 3 â€” New model version available from provider:
  Action: run full benchmark on new version before switching
          Only switch if new version beats current on all metrics
          A/B test with 10% traffic before full switch

TRIGGER 4 â€” Cost per accepted output increases >20% month-over-month:
  Action: review model selection for that task type
          Consider switching cheaper model if quality maintained
```

