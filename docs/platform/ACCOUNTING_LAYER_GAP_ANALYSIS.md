# Accounting Layer — Gap Analysis & Implementation Report
<!-- Generated: 2026-03-28 | Based on ACCOUNTING_LAYER_DESIGN.md v4.0 -->

---

## Step 1 — Repo Inventory

### Backend — API Controllers (`backend/financeops/api/v1/`)

| File | Purpose |
|------|---------|
| auth.py | Login, register, MFA, token refresh endpoints |
| tenants.py | Tenant CRUD and onboarding |
| users.py | User management, invites |
| platform_users.py | Platform-level user admin |
| health.py | Health check endpoints |
| gst.py | GST return filing and reconciliation |
| bank_recon.py | Bank reconciliation endpoints |
| reconciliation.py | GL/TB reconciliation |
| reconciliation_bridge.py | Cross-module reconciliation |
| mis_manager.py | MIS manager reports |
| working_capital.py | Working capital module |
| close.py | Month-end checklist |
| auditor.py | Auditor access and grants |
| erp_sync.py | ERP sync triggers and status |
| payment.py | Payment/billing endpoints |
| fx_rates.py | FX rate management |
| fixed_assets.py | Fixed asset register |
| prepaid.py | Prepaid expense management |
| lease.py | Lease management |
| revenue.py | Revenue recognition |
| consolidation.py | Group consolidation |
| ai_stream.py | AI streaming inference |
| admin_ai_providers.py | Admin AI provider config |
| router.py | API router assembly |

### Backend — Platform Layer (`backend/financeops/platform/`)

| File | Purpose |
|------|---------|
| db/models/roles.py | Generic RBAC role model (role_code, role_scope, inheritance) |
| db/models/permissions.py | Permission definitions |
| db/models/role_permissions.py | Role-permission mappings |
| db/models/user_role_assignments.py | User-to-role assignments |
| db/models/workflow_templates.py | Workflow template definitions |
| db/models/workflow_instances.py | Active workflow instances |
| db/models/workflow_approvals.py | Approval decisions on workflow steps |
| db/models/organisations.py | Organisation model |
| services/rbac/evaluator.py | RBAC permission evaluation |
| services/rbac/role_service.py | Role CRUD and management |
| services/workflows/instance_service.py | Workflow instance lifecycle |

### Backend — ERP Integrations

| File | Purpose |
|------|---------|
| modules/erp_sync/infrastructure/connectors/zoho.py | Zoho Books OAuth + **read-only** data extraction (TB, GL, CoA, Vendor Master, GST returns). No JV creation, no attachment upload. |
| modules/coa/application/erp_mapping_service.py | COA mapping between ERP and platform |
| db/models/erp_sync.py | ERP sync job/status model |

> **No QBO connector exists. Zoho connector is read-only.**

### Backend — Document/File Handling

| File | Purpose |
|------|---------|
| storage/airlock.py | 5-step file safety: MIME check, size check, SHA256, ClamAV, result |
| storage/r2.py | Cloudflare R2 S3-compatible storage client (upload, download, presigned URL) |
| storage/provider.py | Storage provider abstraction |

> **No document upload API endpoint. No AWS Textract integration. No document processing worker.**

### Backend — Email Handling

> **Nothing found.** No inbound email parsing, no SMTP client, no email service.

### Backend — Database Models (`backend/financeops/db/models/`)

| File | Purpose |
|------|---------|
| audit.py | Immutable audit trail (FinancialBase, chain-hashed, IP/user-agent) |
| tenants.py | Tenant master |
| users.py | IAM users, sessions |
| gst.py | GST return filings and recon items (references cp_entities FK) |
| bank_recon.py | Bank reconciliation transactions |
| erp_sync.py | ERP sync job tracking |
| fx_rates.py | FX rate records |
| credits.py | AI credit system |

> **No JV/journal entry model. No vendor master model. No legal entity master with GSTIN/PAN/address. No document ingestion model.**

### Backend — Background Jobs (`backend/financeops/tasks/`)

| File | Purpose |
|------|---------|
| celery_app.py | Full Celery + Redis setup (4 priority queues, beat schedule, retry config) |
| base_task.py | Base task class with retry/error handling patterns |
| payment_tasks.py | Trial conversion, grace period, payment retry tasks |

> **No document processing tasks, no ERP push tasks, no notification tasks, no COA/payment sync tasks.**
> Celery references a `notification` queue in metrics (line 106) but no notification tasks are defined.

### Backend — Auth & Authorisation

| File | Purpose |
|------|---------|
| core/auth.py | JWT validation, password hashing |
| core/middleware.py | Request middleware, tenant context |
| platform/services/rbac/ | Full RBAC: roles, permissions, evaluator |
| db/rls.py | PostgreSQL RLS context setter |

> **Generic RBAC exists but no Accounting Layer roles (Preparer, Reviewer, CFO) defined. No entity-scoped role assignments.**

### Frontend — Pages (`frontend/app/`)

> **No `/accounting`, `/ap`, `/jv` routes. No document upload UI. No JV review screen. No vendor portal.**

Key pages present for other modules: auth flow, dashboard, mis, reconciliation, audit, close, consolidation, working-capital, expenses, budget/forecast/scenarios, settings/entities, settings/users, notifications, sync.

### Key Utilities

| File | Purpose |
|------|---------|
| utils/gstin.py | Full GSTIN validation (checksum), state code extraction, PAN validation |
| utils/chain_hash.py | SHA256 chain hash for immutable records |
| utils/pagination.py | Pagination helper |
| utils/formatting.py | Number/date formatting |

---

## Step 2 — Map Existing Capabilities

### Document Ingestion

| Capability | Status | Evidence |
|-----------|--------|---------|
| File upload endpoint (single) | **MISSING** | No upload endpoint in api/v1/ |
| File upload endpoint (batch) | **MISSING** | — |
| File storage client (R2) | **EXISTS** | storage/r2.py — upload, SHA256, presigned URL |
| WORM S3 folder per entity | **MISSING** | R2 client exists; no entity-scoped WORM provisioning |
| Inbound email parsing webhook | **MISSING** | No email handling anywhere |
| Email sender whitelist | **MISSING** | — |
| Auto-reply email sender | **MISSING** | No SMTP/SES client |
| Vendor submission portal | **MISSING** | — |
| Vendor identity verification | **MISSING** | No vendor master |

### AI / OCR Processing

| Capability | Status | Evidence |
|-----------|--------|---------|
| AWS Textract integration | **MISSING** | No Textract client anywhere |
| Document processing worker | **MISSING** | No document worker tasks |
| Field confidence scoring | **MISSING** | — |
| Document splitting | **MISSING** | — |
| Low-quality scan detection | **MISSING** | — |

### ERP Integrations

| Capability | Status | Evidence |
|-----------|--------|---------|
| Zoho Books API client | **PARTIAL** | connectors/zoho.py — OAuth + read-only; no JV creation, no attachment |
| QBO API client | **MISSING** | No QBO connector |
| JV creation in ERP | **MISSING** | — |
| Document attachment upload to ERP | **MISSING** | — |
| COA sync from ERP | **PARTIAL** | modules/coa/application/erp_mapping_service.py exists; no daily sync job |
| Payment status sync | **MISSING** | — |
| ERP error handling + retry | **PARTIAL** | Celery base_task.py has retry pattern; no ERP-specific retry queue |

### Accounting & Tax Logic

| Capability | Status | Evidence |
|-----------|--------|---------|
| JV / journal entry data model | **MISSING** | — |
| GST line split (CGST/SGST vs IGST) | **MISSING** | utils/gstin.py has extract_state_code (lines 55–62); no split calculator |
| TDS deduction line logic | **MISSING** | — |
| Multi-currency / FX | **PARTIAL** | db/models/fx_rates.py exists; no AP-context FX handling |
| PO data store / PO sync | **MISSING** | — |
| PO matching logic | **MISSING** | — |
| AP ageing calculation | **MISSING** | — |
| Recurring entry templates | **MISSING** | — |

### Entity & Vendor Management

| Capability | Status | Evidence |
|-----------|--------|---------|
| Legal entity master (GSTIN, PAN, address) | **PARTIAL** | cp_entities table referenced in db/models/gst.py:29 but no full model in repo |
| Entity detection logic | **MISSING** | — |
| Vendor master | **MISSING** | Zoho connector can sync vendor master from ERP but no platform model |

### Workflow & Approvals

| Capability | Status | Evidence |
|-----------|--------|---------|
| JV status state machine | **MISSING** | — |
| Maker-checker enforcement | **MISSING** | — |
| Multi-level approval (threshold-based) | **PARTIAL** | platform/db/models/workflow_approvals.py — generic; not wired to JV |
| Internal notes / comments | **MISSING** | — |
| Due date urgency flags | **MISSING** | — |
| Approval reminder nudges | **MISSING** | No notification system |
| SLA tracking | **MISSING** | — |

### Auth & RBAC

| Capability | Status | Evidence |
|-----------|--------|---------|
| Role-based access control | **EXISTS** | platform/services/rbac/ — full RBAC evaluator |
| Accounting Layer roles | **MISSING** | No Preparer/Reviewer/CFO roles seeded |
| Entity-scoped role assignments | **MISSING** | user_role_assignments has no entity_id FK |

### Duplicate Detection

| Capability | Status | Evidence |
|-----------|--------|---------|
| SHA-256 deduplication | **PARTIAL** | SHA-256 computed in airlock.py:101 but not checked against DB |
| Invoice number + vendor name | **MISSING** | — |
| Fuzzy match (vendor + amount + date) | **MISSING** | — |

### Notifications

| Capability | Status | Evidence |
|-----------|--------|---------|
| In-app notification system | **MISSING** | Frontend page exists; no backend model or API |
| Transactional email | **MISSING** | No email service |
| Outbound webhook system | **MISSING** | Payment webhooks in payment/api/webhooks.py are inbound only |

### Reporting & Analytics

| Capability | Status | Evidence |
|-----------|--------|---------|
| Dashboard infrastructure | **PARTIAL** | Multiple dashboards for other modules; no AP dashboard |
| AP ageing report | **MISSING** | — |
| Rejection analytics | **MISSING** | — |
| SLA metrics | **MISSING** | — |
| Export CSV/PDF | **PARTIAL** | Some modules have exports; no AP export |

### Audit

| Capability | Status | Evidence |
|-----------|--------|---------|
| Immutable audit log model | **EXISTS** | db/models/audit.py — FinancialBase, chain-hashed, IP/user-agent |
| AP-specific event logging | **PARTIAL** | Audit service exists; no AP event types |
| Audit log export | **MISSING** | No export endpoint |

---

## Step 3 — Identify Gaps

### Category A — Build from Scratch

```
Gap Name: JV Data Model & Ingestion Document Model
Category: A | Complexity: Medium
Description: No DB models for: SourceDocument (S3 key, SHA256, ingestion method,
  entity assignment, processing status), JournalVoucher (header: entity, vendor, date,
  currency, FX rate, status, rejection count, ERP ref), JVLineItem (account code, Dr/Cr,
  amount, GST type), JVNote (internal comments), VendorMaster (GSTIN, PAN, TDS section/rate,
  entity mapping).
Relevant: backend/financeops/db/base.py (FinancialBase pattern to follow)
```

```
Gap Name: Legal Entity Master Model
Category: A | Complexity: Medium
Description: cp_entities is referenced as FK in gst.py but no full model in repo.
  Need: GSTIN, PAN, registered address, functional currency, ERP connection reference,
  default AP/expense account codes, approval thresholds, managed folder path.
Relevant: utils/gstin.py (validation ready), db/models/gst.py:29 (FK reference)
```

```
Gap Name: Document Upload API Endpoint
Category: A | Complexity: Low
Description: Single-file and batch (≤50) upload endpoints: Airlock validation,
  SHA256 dedup, R2 entity-scoped storage, SourceDocument creation, enqueue extraction
  Celery task, return job ID for polling.
Relevant: storage/airlock.py (validation ready), storage/r2.py (client ready),
  tasks/celery_app.py (queue ready)
```

```
Gap Name: AWS Textract Document Extraction Pipeline
Category: D/A | Complexity: High
Description: Async Celery task calling AWS Textract Analyze Expense API. Extract all
  fields (vendor, GSTIN, PAN, invoice number, date, due date, line items, GST breakdown,
  TDS section, amounts, currency, PO number) with per-field confidence scores. Detect
  multi-invoice documents. Flag low-quality scans (<60% avg confidence).
  NOTE: Textract cannot read Cloudflare R2 directly — requires copy to AWS S3 or
  synchronous bytes mode (20MB limit).
Relevant: storage/r2.py (boto3 thread-pool pattern to replicate), tasks/celery_app.py
External: AWS Textract (boto3 already present for R2)
```

```
Gap Name: Entity Detection from Document Content
Category: A | Complexity: High
Description: Multi-signal pipeline: (1) S3 folder path, (2) GSTIN match vs entity master,
  (3) PAN match, (4) Billed-To name fuzzy match (difflib SequenceMatcher, threshold 0.85),
  (5) vendor master mapping, (6) user context (single entity user).
  Returns EntityDetectionResult(entity_id, confidence, signal_used).
Relevant: utils/gstin.py (validate_gstin, extract_state_code ready)
```

```
Gap Name: GST Line Split Calculation (CGST/SGST vs IGST)
Category: C | Complexity: Low
Description: Compare first 2 digits of supplier GSTIN vs buyer GSTIN (entity master)
  to determine intra/inter-state. Intra: CGST + SGST at rate/2 each (accounts 1310/1311).
  Inter: IGST at full rate (account 1312). Handle exempt/zero-rated/non-GST invoices.
  All amounts as Decimal with ROUND_HALF_UP.
Relevant: utils/gstin.py:55–62 (extract_state_code ready)
```

```
Gap Name: TDS Deduction Line Logic
Category: A | Complexity: Medium
Description: Look up TDS section (194C/194J/194I) and rate from vendor master.
  Create TDS Payable credit line reducing AP credit. Account mapping:
  194C→2210, 194J→2211, 194I→2212 (configurable per entity).
Relevant: utils/gstin.py (PAN validation for vendor identity)
```

```
Gap Name: JV Approval State Machine (Maker-Checker)
Category: A | Complexity: High
Description: 12-state lifecycle: Uploaded→Processing→Pending Review→Rejected→
  Resubmitted→Approved→Push in Progress→Pushed→Push Failed→Retry Queued→Escalated→Voided.
  Maker-checker rule (Preparer cannot approve own JV). JV immutability after Approved.
  Resubmission counter: max 3 → Escalated. Admin void with mandatory reason (insert-only).
  SELECT FOR UPDATE on JV row to prevent concurrent approval.
Relevant: platform/db/models/workflow_approvals.py (generic pattern),
  services/credit_service.py (SELECT FOR UPDATE pattern to replicate)
```

```
Gap Name: Duplicate Detection Logic
Category: A | Complexity: Medium
Description: (1) Exact SHA-256 SELECT on source_documents per tenant. (2) Exact
  invoice_number + vendor_name (normalised: lower, strip spaces). (3) Fuzzy:
  vendor similarity >0.9 + amount within 1% + date ±1 day. On duplicate: return for
  side-by-side display, block until preparer overrides with mandatory comment → AuditTrail.
Relevant: storage/airlock.py:101 (SHA256 already computed)
```

```
Gap Name: Document Splitting Detection
Category: A | Complexity: High
Description: During Textract extraction, detect multiple invoice_number/date/vendor
  signals. Prompt preparer to split. On split: create separate SourceDocument + JV
  records per detected invoice, attach relevant page ranges, retain original in storage.
External: AWS Textract page-level analysis
```

```
Gap Name: Inbound Email Ingestion Webhook
Category: D/A | Complexity: High
Description: POST /api/v1/webhooks/email/inbound (public, no JWT). Check message_id
  against EmailIngestionLog for idempotency (return 200 synchronously after writing
  idempotency record). Verify sender against per-org whitelist (individual + domain).
  Extract base64 attachments, run scan_and_seal(), enqueue extraction task.
  Auto-reply via email API for: no attachment, unsupported format, not whitelisted.
  Log: sender, subject, message_id, attachment_count to AuditTrail.
External: SendGrid Inbound Parse (or AWS SES)
```

```
Gap Name: Notification System
Category: A | Complexity: High
Description: Notification DB model (UUIDBase): user_id, tenant_id, notification_type,
  title, body, link, read_at. NotificationService.notify() inserts DB + enqueues email
  if user prefs allow. EmailService wraps SendGrid/SMTP. Daily digest: Celery beat,
  aggregate unread per reviewer. Wire into approval_service, jv_state_machine.
  Celery notification queue already named in celery_app.py:106 but no tasks exist.
External: SendGrid or AWS SES for email
```

```
Gap Name: Outbound Webhook Delivery System
Category: A | Complexity: Medium
Description: WebhookEndpoint model: org_id, url, events[], secret, is_active.
  WebhookDeliveryLog: webhook_id, event_type, http_status, attempt_count.
  Delivery task: POST with X-Finos-Signature (HMAC-SHA256). Retry: 3 attempts,
  backoff 5min/15min/60min. Adapt HMAC pattern from
  modules/payment/infrastructure/webhook_verifier.py (inbound HMAC — reverse for outbound).
```

```
Gap Name: AP Ageing Calculation & Report
Category: A | Complexity: Medium
Description: Query JVs where payment_status NOT IN (Paid) and status = Pushed.
  Compute days_overdue = (today - due_date).days. Buckets: Current/1–30/31–60/61–90/90+.
  Filter by entity/vendor/date range. Export CSV/PDF. Composite index on
  (tenant_id, entity_id, due_date, payment_status) required.
```

```
Gap Name: Vendor Self-Submission Portal
Category: A | Complexity: Medium
Description: POST /api/v1/portal/submit (unauthenticated, rate limited 5/day by vendor
  email via Redis INCR+TTL). Verify vendor email vs VendorMaster. Run Airlock, store
  document, generate reference FIN-{year}-{seq}. GET /portal/status/{reference} returns
  simplified status only (no JV details, no account codes). Log IP, user_agent,
  vendor_email to AuditTrail.
```

```
Gap Name: Due Date Urgency Flags
Category: A | Complexity: Low
Description: Pure function UrgencyCalculator.calculate(due_date) → UrgencyLevel enum
  (OVERDUE/DUE_SOON/UPCOMING/NORMAL). Computed at serialization time, not stored.
  Add to JV list response schema. Reviewer queue sortable by urgency. Celery beat:
  daily check for OVERDUE+Pending Review → Admin alert.
```

```
Gap Name: Inbound API for External Document Push
Category: A | Complexity: Low
Description: API key model (per-org, hashed, rate-limited), authentication middleware,
  document submission endpoint (same Airlock→extraction pipeline as direct upload).
Relevant: core/auth.py (JWT auth pattern to extend for API keys)
```

### Category B — Extend / Modify Existing

```
Gap Name: Zoho Connector — JV Creation & Attachment Upload
Category: B | Complexity: High
Description: Extend read-only connector with write methods: create_journal_entry(lines)
  → journal_id, upload_attachment(file_bytes, filename, content_type) → attachment_id,
  link_attachment(journal_id, attachment_id). Partial failure contract: write journal_id
  to DB in same transaction as Push-In-Progress status change BEFORE calling attachment
  API (prevents double-posting on retry).
  Zoho journal endpoint: POST /books/v3/journals (or /books/v3/journals/{id}/attachments).
Relevant: modules/erp_sync/infrastructure/connectors/zoho.py (OAuth, _fetch pattern)
External: Zoho Books API write endpoints
```

```
Gap Name: COA Sync — Daily Celery Beat Job
Category: B | Complexity: Low
Description: COA mapping service exists (erp_mapping_service.py) but no beat task.
  Add task at 02:00 UTC per active EntityErpConnection: call Zoho/QBO COA endpoint,
  upsert into coa_accounts table, set last_coa_sync_at. Alert Admin on sync failure.
Relevant: tasks/celery_app.py:62–91 (beat_schedule to extend)
```

```
Gap Name: RBAC — Accounting Layer Roles & Entity-Scoped Assignments
Category: B | Complexity: Medium
Description: Seed roles: PREPARER, REVIEWER, SENIOR_REVIEWER, CFO, AL_ADMIN, AL_AUDITOR
  (role_scope="accounting_layer"). Add entity_id FK to user_role_assignments. FastAPI
  dependency require_accounting_role(entity_id, roles). Critical: add integration test
  asserting 403 when Preparer attempts to approve.
Relevant: platform/db/models/roles.py, platform/services/rbac/evaluator.py,
  api/deps.py
```

```
Gap Name: Airlock — Add TIFF Support
Category: B | Complexity: Low
Description: MIME allowlist in airlock.py:13–23 missing image/tiff. Design doc
  Section 5.1 lists TIFF as supported format.
Relevant: storage/airlock.py:13–23
```

```
Gap Name: R2 Storage — WORM Entity-Scoped Path
Category: B | Complexity: Low
Description: Current R2 path: {tenant_id}/{module}/{uuid}/{filename}.
  Need entity-scoped: {tenant_id}/documents/entity-{entity_id}/{year}/{month}/{uuid}/{filename}.
  Also need streaming download→re-upload to ERP for attachment (multipart).
Relevant: storage/r2.py
```

```
Gap Name: ERP Sync — Payment Status Sync Job
Category: B | Complexity: Medium
Description: Celery beat task per entity. Query Zoho/QBO payment records since last sync.
  Match to platform JVs by erp_journal_id. Update payment_status and payment_date.
Relevant: tasks/celery_app.py (beat_schedule)
External: Zoho Books / QBO payment API
```

### Category C — Wire Together

```
Gap Name: Airlock → R2 → DB Document Storage Pipeline
Category: C | Complexity: Low
Description: Airlock and R2 exist independently. Wire: scan_and_seal() → APPROVED →
  store to R2 entity-scoped path → create SourceDocument DB record. SHA-256 from
  airlock step 3 feeds the DB deduplication check before R2 upload.
Relevant: storage/airlock.py, storage/r2.py, tasks/celery_app.py
```

```
Gap Name: GSTIN State Code → GST Split Calculator
Category: C | Complexity: Low
Description: extract_state_code() in utils/gstin.py:55–62 is ready. Entity master
  will have buyer GSTIN. These pieces need wiring into GstCalculator service.
Relevant: utils/gstin.py:55–62
```

### Category D — Third-Party Integration Required

```
Gap Name: QuickBooks Online (QBO) Connector
Category: D | Complexity: High
Description: No QBO connector at all. Need full client: OAuth 2.0 PKCE flow, token
  refresh, journal entry creation (/v3/company/{realm_id}/journalentry), attachment
  upload (/v3/company/{realm_id}/upload then /attachable), COA pull (QBO query language:
  SELECT * FROM Account), payment status pull. QBO rate limit: 500 req/min.
Relevant: modules/erp_sync/infrastructure/connectors/zoho.py (pattern),
  modules/erp_sync/infrastructure/connectors/base.py (AbstractConnector)
External: QuickBooks Online API, Intuit Developer app required
```

```
Gap Name: AWS Textract Integration
Category: D | Complexity: High
Description: boto3 already present for R2. Need textract client wrapper (thread pool async),
  Analyze Expense API, response parser. Key constraint: Textract requires AWS S3 for async
  mode — need copy step from R2 to S3 or use synchronous bytes mode (20MB limit).
Relevant: storage/r2.py (boto3 thread-pool pattern)
External: AWS Textract (Analyze Expense API), possibly AWS S3 bucket for Textract input
```

```
Gap Name: SendGrid Inbound Parse + Transactional Email
Category: D | Complexity: Medium
Description: MX record → SendGrid, webhook POST to platform, multipart form-data parsing.
  Plus outbound transactional email client (SendGrid SDK or AWS SES) for notifications.
Relevant: tasks/celery_app.py (notification queue exists)
External: SendGrid or AWS SES
```

---

## Step 4 — Implementation Plan

```
Gap: JV Data Model & Ingestion Document Model
Category: A | Complexity: Medium | Effort: 2 days
New Files:
  - backend/financeops/db/models/accounting.py — all AP models
  - backend/migrations/versions/0003_accounting_layer.py — migration + RLS + indexes
Existing Files to Modify:
  - backend/financeops/db/models/__init__.py — import new models
  - backend/tests/conftest.py — import new models for test DB setup
Approach: FinancialBase for SourceDocument, JournalVoucher, JVLineItem (immutable
  financial records, chain-hashed). UUIDBase for JVNote (mutable comments) and
  VendorMaster. Add composite indexes: (tenant_id, entity_id, due_date, payment_status)
  on JournalVoucher. Add RLS policies for entity-scoped access.
Depends On: Legal Entity Master
```

```
Gap: Legal Entity Master Model
Category: A | Complexity: Medium | Effort: 1.5 days
New Files:
  - backend/financeops/db/models/entity_master.py
Approach: Check platform migrations for cp_entities definition. Extend/add columns:
  gstin, pan, registered_address, functional_currency, default_ap_account,
  default_expense_account, managed_folder_s3_key. EntityApprovalThreshold table for
  per-entity approval tiers. EntityErpConnection with AES-256-GCM encrypted credentials.
Depends On: None
```

```
Gap: Document Upload API Endpoint
Category: A | Complexity: Low | Effort: 1 day
New Files:
  - backend/financeops/api/v1/accounting.py — upload, batch upload, status endpoints
Existing Files to Modify:
  - backend/financeops/api/v1/router.py — register accounting router
Approach: POST /api/v1/accounting/documents/upload (single) and upload-batch (≤50 files).
  Each: scan_and_seal() → SHA-256 dedup check → R2 entity-scoped path → SourceDocument
  record → enqueue Celery extraction task → return document_id. Do NOT run Airlock
  synchronously for batch — return immediately with job IDs, defer all processing to Celery.
Depends On: JV Data Model, Airlock TIFF extension
```

```
Gap: AWS Textract Document Extraction Pipeline
Category: D/A | Complexity: High | Effort: 4 days
New Files:
  - backend/financeops/modules/accounting/tasks/extract_document.py — Celery task
  - backend/financeops/modules/accounting/services/textract_client.py — boto3 wrapper
  - backend/financeops/modules/accounting/services/extraction_parser.py — response→JV fields
  - backend/financeops/modules/accounting/services/jv_draft_service.py — creates JV from fields
Approach: Use synchronous analyze_expense(Document={Bytes: file_bytes}) for files <20MB.
  For larger: upload to dedicated AWS S3 bucket → start_expense_analysis() → poll
  get_expense_analysis(). Parse AnalyzeExpense response: SummaryFields for header
  (vendor, invoice number, date, totals) and LineItemGroups for line items.
  Confidence per field = ExpenseField.Type.Confidence. Multi-invoice: len(ExpenseDocuments) > 1.
  Low-quality flag: average confidence < 60%. On completion: update SourceDocument status,
  create JVDraft with fields + GST split + TDS lines.
Depends On: Document Upload endpoint, JV Data Model
```

```
Gap: Entity Detection from Document Content
Category: A | Complexity: High | Effort: 2 days
New Files:
  - backend/financeops/modules/accounting/services/entity_detector.py
Approach: EntityDetector.detect(extracted_fields, tenant_id, upload_folder_entity_id=None)
  → EntityDetectionResult. Signal pipeline: (1) folder → High; (2) extracted GSTIN →
  validate_gstin() + EntityMaster.gstin lookup → High; (3) extracted PAN → High;
  (4) billed_to fuzzy match (difflib.SequenceMatcher ratio >0.85) vs entity name/aliases
  → Medium; (5) vendor master entity_id → Medium; (6) uploader's single entity → Medium.
  Return first High or best Medium (with confirm required) or NotIdentified.
  Write result + confidence to SourceDocument. Fire notification if unidentified.
Depends On: Legal Entity Master, JV Data Model
```

```
Gap: GST Line Split Calculation
Category: C | Complexity: Low | Effort: 1 day
New Files:
  - backend/financeops/modules/accounting/services/gst_calculator.py
Approach: GstCalculator.calculate(supplier_gstin, buyer_gstin, taxable_amount, gst_rate,
  entity_account_codes) → list[JVLineItem]. Use extract_state_code() from utils/gstin.py.
  Intra-state: CGST + SGST at rate/2 each (accounts 1310/1311). Inter-state: IGST at full
  rate (account 1312). All amounts Decimal with ROUND_HALF_UP. Handle exempt/no-GSTIN
  (no tax lines). Full unit tests for all scenarios.
Depends On: Legal Entity Master, JV Data Model
```

```
Gap: TDS Deduction Line Logic
Category: A | Complexity: Medium | Effort: 1 day
New Files:
  - backend/financeops/modules/accounting/services/tds_calculator.py
Approach: TdsCalculator.calculate(vendor_id, taxable_amount, entity_account_codes)
  → JVLineItem | None. Look up tds_section (194C/194J/194I/None) and tds_rate from
  VendorMaster. If no TDS section → return None. tds_amount = taxable_amount * tds_rate
  (Decimal, ROUND_HALF_UP). Reduce AP credit by tds_amount. Create TDS Payable credit
  line: 194C→2210, 194J→2211, 194I→2212. Flag JVs where vendor present but tds_section
  is NULL (preparer must verify).
Depends On: Vendor Master (in JV Data Model)
```

```
Gap: JV Approval State Machine
Category: A/B | Complexity: High | Effort: 3 days
New Files:
  - backend/financeops/modules/accounting/domain/jv_state_machine.py
  - backend/financeops/modules/accounting/services/approval_service.py
  - backend/financeops/api/v1/jv_workflow.py
Approach: JVStatus enum: 12 states from design doc Section 17. JvStateMachine.transition()
  validates: (a) legal transition from current state, (b) actor role authorized,
  (c) for APPROVE: actor != jv.submitted_by (maker-checker), (d) immutability: Approved+
  states return 403 on any field PUT/PATCH. SELECT FOR UPDATE on JV row before transition.
  Resubmission: increment rejection_count; at 3 → Escalated + Admin notification.
  Admin Void: insert new JV row with status=Voided, void_reason, voided_by (insert-only
  maintained). Concurrent approval protection: SELECT FOR UPDATE.
Depends On: JV Data Model, RBAC Accounting Layer Roles
```

```
Gap: Duplicate Detection Logic
Category: A | Complexity: Medium | Effort: 1.5 days
New Files:
  - backend/financeops/modules/accounting/services/duplicate_detector.py
Approach: Three methods: (1) exact SHA-256 SELECT; (2) exact invoice_number + vendor_name
  (normalised); (3) fuzzy — vendor similarity >0.9 (difflib) + amount within 1% +
  date ±1 day. On duplicate: return result to frontend for side-by-side display;
  block processing until preparer explicitly overrides with mandatory comment → AuditTrail.
Depends On: JV Data Model
```

```
Gap: Inbound Email Ingestion Webhook
Category: D/A | Complexity: High | Effort: 3 days
New Files:
  - backend/financeops/api/v1/email_ingestion.py
  - backend/financeops/modules/accounting/services/email_ingestion_service.py
  - backend/financeops/modules/accounting/services/email_autoreply.py
Approach: POST /api/v1/webhooks/email/inbound (public, no JWT auth). Write message_id to
  EmailIngestionLog FIRST, return HTTP 200 synchronously (idempotency). Then check sender
  whitelist (exact email or domain wildcard *@domain.com). Per attachment: extract base64,
  scan_and_seal(), enqueue extraction Celery task. Auto-reply via email API for error cases
  only (not on success, to avoid confirming receipt to spammers). Log everything to AuditTrail.
Depends On: Document Upload endpoint, Notification System
```

```
Gap: Notification System
Category: A | Complexity: High | Effort: 3 days
New Files:
  - backend/financeops/db/models/notifications.py
  - backend/financeops/modules/notifications/service.py
  - backend/financeops/modules/notifications/email_service.py
  - backend/financeops/modules/notifications/tasks.py
  - backend/financeops/api/v1/notifications.py
Approach: Notification model (UUIDBase): user_id, tenant_id, type, title, body, link,
  read_at. NotificationService.notify() inserts DB + enqueues email task if user prefs
  allow. EmailService wraps SendGrid (settings.EMAIL_PROVIDER). Daily digest: Celery beat,
  batch per reviewer. Wire notify() calls into approval_service state transitions (JV
  submitted, rejected, approved, escalated, pushed, push failed).
Depends On: JV Approval State Machine
```

```
Gap: Outbound Webhook Delivery System
Category: A | Complexity: Medium | Effort: 2 days
New Files:
  - backend/financeops/db/models/webhooks.py
  - backend/financeops/modules/webhooks/service.py
  - backend/financeops/modules/webhooks/tasks.py
  - backend/financeops/api/v1/webhooks_config.py
Approach: WebhookEndpoint model: org_id, url, events[], secret, is_active.
  WebhookDeliveryLog: webhook_id, event_type, payload_hash, http_status, attempt_count.
  Delivery task: POST with X-Finos-Signature: HMAC-SHA256(secret, payload). Retry:
  3 attempts, backoff 5min/15min/60min using Celery countdown. Adapt HMAC pattern from
  modules/payment/infrastructure/webhook_verifier.py (reverse for outbound signing).
Depends On: JV Approval State Machine
```

```
Gap: AP Ageing Calculation & Report
Category: A | Complexity: Medium | Effort: 2 days
New Files:
  - backend/financeops/modules/accounting/services/ageing_service.py
  - backend/financeops/api/v1/accounting_reports.py
Approach: AgeingService.calculate(tenant_id, entity_id=None, vendor_id=None) queries
  JVs where payment_status NOT IN (Paid) and status = Pushed. days_overdue =
  (today - due_date).days. Buckets: current (≤0)/1–30/31–60/61–90/90+. Composite index
  on (tenant_id, entity_id, due_date, payment_status). CSV via formatting.py. PDF via
  weasyprint. Rejection analytics: aggregate by submitted_by, vendor, rejection reason.
Depends On: JV Data Model, JV Approval State Machine
```

```
Gap: Zoho Connector — JV Creation & Attachment Upload
Category: B | Complexity: High | Effort: 3 days
Existing Files to Modify:
  - backend/financeops/modules/erp_sync/infrastructure/connectors/zoho.py
  - backend/financeops/modules/erp_sync/infrastructure/connectors/base.py
Approach: Add async create_journal_entry(creds, org_id, payload) → journal_id (POST
  /books/v3/journals), upload_attachment(file_bytes, filename, content_type) →
  attachment_id (POST /books/v3/journals/{journal_id}/attachments multipart),
  link_attachment_to_journal(journal_id, attachment_id). CRITICAL: write journal_id
  to DB in SAME transaction as setting status=Push-In-Progress, before calling attachment
  API. This prevents double-posting on Celery retry if task crashes between JV creation
  and journal_id write.
  Line item format: account_id (Zoho numeric), debit_or_credit, amount, description.
  journal_date: YYYY-MM-DD. notes: memo.
Depends On: JV Data Model
```

```
Gap: QBO Connector (full)
Category: D | Complexity: High | Effort: 4 days
New Files:
  - backend/financeops/modules/erp_sync/infrastructure/connectors/qbo.py
Approach: Follow ZohoConnector structure (AbstractConnector base). QBO OAuth:
  authorize URL: https://appcenter.intuit.com/connect/oauth2, token URL:
  https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer, Basic auth header
  (base64(client_id:client_secret)).
  JV creation: POST /v3/company/{realm_id}/journalentry?minorversion=75 with Line[].
  Line structure: {Id, Amount, DetailType: "JournalEntryLineDetail", Description,
  JournalEntryLineDetail: {PostingType: "Debit"/"Credit", AccountRef: {value: account_id}}}.
  Attachment: POST /v3/company/{realm_id}/upload (multipart), then link via AttachableRef.
  COA: GET /v3/company/{realm_id}/query?query=select * from Account.
  Rate limit: 500 req/min — add rate limiter.
  realm_id stored in EntityErpConnection.credentials.
Depends On: JV Data Model
```

```
Gap: RBAC — AL Roles & Entity-Scoped Assignments
Category: B | Complexity: Medium | Effort: 2 days
New Files:
  - backend/financeops/modules/accounting/rbac.py — entity-scoped role dependency
Existing Files to Modify:
  - backend/migrations/versions/0003_accounting_layer.py — seed AL roles
  - backend/financeops/api/deps.py — add require_accounting_role(entity_id, roles)
  - platform/db/models/user_role_assignments.py — add entity_id FK (nullable)
Approach: Seed roles: PREPARER, REVIEWER, SENIOR_REVIEWER, CFO, AL_ADMIN, AL_AUDITOR
  (role_scope="accounting_layer"). FastAPI dependency require_accounting_role() queries
  user_role_assignments WHERE user_id = current_user AND (entity_id = ? OR entity_id IS NULL)
  AND role IN roles. Add to ALL AP endpoints. Integration test: Preparer attempts approve
  → assert 403.
Depends On: Legal Entity Master
```

```
Gap: Frontend — Accounting Layer Module
Category: A | Complexity: High | Effort: 8 days
New Files:
  - frontend/app/(dashboard)/accounting/page.tsx — document list + status
  - frontend/app/(dashboard)/accounting/upload/page.tsx — drag-drop upload + progress
  - frontend/app/(dashboard)/accounting/jv/[id]/page.tsx — JV detail (Preparer)
  - frontend/app/(dashboard)/accounting/review/[id]/page.tsx — reviewer split-panel
  - frontend/app/(dashboard)/accounting/reports/ageing/page.tsx — AP ageing report
  - frontend/app/(dashboard)/accounting/dashboard/page.tsx — role-based dashboards
  - frontend/app/(public)/vendor/page.tsx — vendor portal (public route)
  - frontend/components/accounting/ — reusable JV, document, urgency components
Approach: Follow existing Next.js page patterns. Reviewer split-panel: react-pdf left
  (PDF viewer) + read-only JV form right. Upload: react-dropzone with per-file progress.
  Role-based dashboard: three views (Preparer/Reviewer/Admin) loaded conditionally.
  Vendor portal: isolated public route, minimal styling, no auth, rate-limited API.
Depends On: All backend gaps
```

```
Gap: Vendor Self-Submission Portal (Backend)
Category: A | Complexity: Medium | Effort: 2 days
New Files:
  - backend/financeops/api/v1/vendor_portal.py
  - backend/financeops/modules/accounting/services/vendor_portal_service.py
Approach: POST /api/v1/portal/submit (unauthenticated). Rate limit: Redis INCR+TTL per
  normalised vendor email (lowercase, strip dots for Gmail variants) + secondary IP limit.
  Verify vendor email vs VendorMaster → 404 if unknown (configured message). Run Airlock,
  store document, create SourceDocument (ingestion_source=VENDOR_PORTAL), generate
  reference FIN-{year}-{seq}. GET /portal/status/{reference} → simplified status only.
  Log IP, user_agent, vendor_email to AuditTrail.
Depends On: Vendor Master, JV Approval State Machine
```

```
Gap: COA Sync Daily Job + Payment Status Sync
Category: B | Complexity: Low/Medium | Effort: 2 days total
New Files:
  - backend/financeops/modules/accounting/tasks/coa_sync.py
  - backend/financeops/modules/accounting/tasks/payment_sync.py
Existing Files to Modify:
  - backend/financeops/tasks/celery_app.py — add two beat schedule entries
Approach: COA sync: beat task at 02:00 UTC per active EntityErpConnection. Call Zoho/QBO
  COA endpoint, upsert into coa_accounts table, set last_coa_sync_at. Alert Admin on
  failure; provide manual resync trigger. Payment sync: beat task per entity, query Zoho/QBO
  payment records since last sync, match to JVs by erp_journal_id, update payment_status +
  payment_date. Both tasks follow base_task.py retry pattern.
Depends On: Legal Entity Master, Zoho/QBO connectors
```

---

## Step 5 — Sprint-by-Sprint Build Plan

```
Sprint 1: Data Foundation (Week 1)
Goal: All Accounting Layer DB tables exist; backend starts clean; roles seeded.
Backend Tasks:
  - EntityMaster model (verify/extend cp_entities schema from platform migrations)
  - SourceDocument, JournalVoucher, JVLineItem, JVNote, VendorMaster models
  - EmailSenderWhitelist, Notification, WebhookEndpoint models
  - Migration 0003_accounting_layer.py (RLS policies, composite indexes)
  - Seed AL RBAC roles (Preparer, Reviewer, Senior Reviewer, CFO, AL_Admin)
  - Add entity_id FK to user_role_assignments
Frontend Tasks:
  - Scaffold /accounting route with nav item placeholder
  - Scaffold /vendor portal public route (layout only)
Gaps Closed: JV Data Model, Legal Entity Master, RBAC Roles seed
Dependencies: None
```

```
Sprint 2: Document Ingestion & AI Extraction (Weeks 1–2)
Goal: Preparer can upload a PDF invoice and see an auto-populated JV draft with
  extracted fields and confidence scores.
Backend Tasks:
  - Fix TIFF in airlock.py MIME allowlist (30 min)
  - Document upload endpoint (single + batch) with Airlock + R2 entity-scoped path
  - Airlock → R2 → SourceDocument pipeline wiring
  - AWS Textract client wrapper (boto3, thread pool async, R2→S3 copy if needed)
  - Extraction response parser (fields + confidence scores)
  - JV draft creation service (calls GST + TDS calculators)
  - GST line split calculator (uses utils/gstin.py extract_state_code)
  - TDS deduction calculator
  - Document splitting detection (multiple invoice signals from Textract)
  - Entity detection pipeline (5 signals)
  - Extraction Celery task (queued on upload, status polling endpoint)
  - SHA-256 deduplication (method 1 only this sprint)
Frontend Tasks:
  - Upload page: drag-drop zone (react-dropzone), per-file progress
  - Document list: status indicators (Uploaded/Processing/Draft)
  - JV detail page (Preparer): extracted fields + colour-coded confidence
  - Entity not-identified warning + manual assignment UI
Gaps Closed: Document Upload API, Textract Pipeline, Entity Detection, GST Split,
  TDS Logic, Duplicate Detection (method 1), Airlock TIFF, R2 WORM Path,
  Document Splitting, Frontend Upload
Dependencies: Sprint 1
```

```
Sprint 3: Approval Workflow (Week 3)
Goal: Reviewer can approve/reject JV drafts; Preparer can resubmit; maker-checker
  enforcement is live at API level.
Backend Tasks:
  - JV state machine (12 states, all transitions, immutability after Approved)
  - Approval service (submit, approve, reject, resubmit, void)
  - Maker-checker: SELECT FOR UPDATE + actor != submitted_by check
  - Resubmission counter (max 3 → Escalated + Admin alert)
  - Internal notes model + API
  - Due date urgency flag calculator + sort param on reviewer queue
  - Fuzzy duplicate detection (methods 2+3)
  - RBAC entity-scoped dependency on all AP endpoints
  - In-app Notification model + list/mark-read API
  - Notification tasks wired to approval state transitions
Frontend Tasks:
  - Reviewer split-panel (react-pdf left + read-only JV form right)
  - Approve / Reject with mandatory comment modal
  - Preparer: rejected JV resubmission flow with full note history
  - Internal notes component on JV detail page
  - Due date urgency badges on reviewer queue (sortable)
  - In-app notification bell with unread count
Gaps Closed: JV Approval State Machine, Internal Notes, Due Date Urgency,
  Duplicate Detection (2+3), Notifications (in-app), RBAC Entity Scope
Dependencies: Sprint 2
```

```
Sprint 4: ERP Push & Payment Tracking (Week 4)
Goal: An approved JV is pushed to Zoho Books with source document attached; push
  failures queue for retry; payment status syncs daily.
Backend Tasks:
  - Zoho write methods: create_journal_entry, upload_attachment, link_attachment,
    validate_account_codes, check_period_open (journal_id written to DB in same tx
    as Push-In-Progress before calling attachment API)
  - QBO connector (full: OAuth, JV create, attachment, COA, payment sync)
  - ERP push Celery task with partial failure handling
  - Retry queue: 3 attempts, exponential backoff 5min/15min/60min
  - ERP error mapping → platform error states (invalid account, period closed, duplicate)
  - COA sync daily beat task (Zoho + QBO)
  - Payment status sync daily beat task
  - Transactional email service (SendGrid / AWS SES)
  - Email notifications: JV rejected, approved, pushed, push failed, daily digest
  - Admin escalation for all-retries-failed
Frontend Tasks:
  - ERP connection settings page (connect/test/disconnect per entity)
  - COA sync status indicator in settings
  - Payment status on JV detail page
  - Push error state display on JV detail + admin dashboard
Gaps Closed: Zoho Write Methods, QBO Connector, ERP Push Pipeline, COA Sync,
  Payment Status Sync, ERP Error Handling, Transactional Email
Dependencies: Sprint 3
```

```
Sprint 5: Reporting, Email Ingestion, Vendor Portal, External Integration (Week 5)
Goal: Admin sees full dashboards; org email ingestion is live; vendors can submit via
  portal; external systems can push documents and receive webhooks.
Backend Tasks:
  - Inbound email webhook (SendGrid, idempotency by message_id, whitelist, auto-reply)
  - Email sender whitelist model + management API
  - AP ageing service + report endpoint (CSV + PDF export)
  - Rejection analytics + SLA tracking aggregation endpoints
  - Vendor portal backend (rate limited, status check, reference number)
  - Outbound webhook system (config, delivery task, retry, HMAC signing)
  - Inbound API key auth for external document push
  - Audit log export endpoint (CSV + PDF)
  - Admin / Preparer / Reviewer dashboard data endpoints
Frontend Tasks:
  - Admin dashboard (Section 28.1 full: AP ageing, SLA, rejection analytics, pending push)
  - Preparer dashboard (uploads, outstanding rejections, urgency summary)
  - Reviewer dashboard (pending queue sorted by urgency, turnaround time, SLA breaches)
  - AP ageing report page with drill-down (entity/vendor/date filters)
  - Vendor portal page (public route, minimal, mobile-friendly)
  - Settings: email ingestion (org email address, sender whitelist CRUD)
  - Settings: webhooks (add/edit/delete, delivery log with retry status)
Gaps Closed: Email Ingestion, AP Ageing, Rejection Analytics, SLA Tracking,
  Vendor Portal, Outbound Webhooks, Inbound API, Audit Export, All Dashboards
Dependencies: Sprint 4
```

---

## Step 6 — Risks & Concerns

### Technical Debt

- **utils/findings.py and utils/quality_signals.py** have broken import paths (`from FinanceOps-native implementation modules`) — KI-001/KI-002. Not on AP critical path but will break test collection if imported by conftest.
- **R2 client uses synchronous boto3 calls** (r2.py:44) called from async routes — blocks the event loop. Comment on r2.py:18 acknowledges this but doesn't fix it. Needs `asyncio.get_event_loop().run_in_executor(None, ...)` wrapping. Latency risk for batch uploads.
- **ClamAV is stubbed** (KI-004) — `CLAMAV_REQUIRED=False` means vendor-supplied documents pass without malware scanning. Significant risk for a feature ingesting external invoices.
- **AES-256-GCM field encryption** exists in security.py but must be explicitly applied to ERP credentials in EntityErpConnection — easy to accidentally store plaintext.

### Architecture Risks

- **Textract + R2 incompatibility**: AWS Textract cannot read from Cloudflare R2. Options: (a) copy to AWS S3 before Textract (adds a step + costs), (b) use synchronous `analyze_expense(Document={Bytes: bytes})` mode (limited to 5MB for sync, workaround: Textract async requires S3). Discovering this on Day 5 of Sprint 2 costs 3–4 days.
- **Email webhook idempotency timing**: SendGrid retries if no HTTP 200 within 20s, but extraction takes 30–60s. The `message_id` dedup write must happen synchronously before enqueuing — return 200 immediately after idempotency record write.
- **Partial ERP push failure / double-posting**: If Celery task crashes after Zoho JV creation but before writing `journal_id` to DB, retry will create a second JV. Fix: write `journal_id` to DB in the same DB transaction as setting status to Push-In-Progress, before the attachment call.
- **Concurrent approval race condition**: Two Reviewers click Approve simultaneously → both transition Pending Review → Approved. Fix: `SELECT FOR UPDATE` on JournalVoucher row before transition (same pattern as credit reservation in services/credit_service.py).

### Security Risks

- **File upload**: Airlock covers MIME, size, SHA256, ClamAV. Risk: MIME spoofing mitigated by libmagic magic bytes. Ensure `fail_on_missing_magic=True` in production (airlock.py:37) or guarantee libmagic installed.
- **Vendor portal abuse**: Rate limit by normalised email (lowercase, strip Gmail dots) + secondary IP limit in middleware.
- **RBAC gap — most critical**: If `require_accounting_role()` dependency is accidentally omitted from any AP endpoint, a Preparer could call the approve endpoint directly. All AP endpoints must use this dependency. Add an integration test asserting 403 when Preparer attempts approval.
- **PII in documents**: Invoices contain vendor PAN, GSTIN, bank details. Textract extraction results stored in DB — `extracted_fields` JSONB column must be AES-256-GCM encrypted using existing security.py pattern.

### Indian Tax Compliance Risks

- **GSTIN extraction reliability**: OCR errors on GSTIN digits → incorrect intra/inter-state determination → wrong GST split. Mitigation: run `validate_gstin()` checksum (utils/gstin.py:80–99) before using GSTIN for split calculation. Flag low-confidence GSTIN extractions for preparer review.
- **TDS vendor master gaps**: If vendor has no `tds_section` configured, TDS lines will be absent → underpayment liability. Flag JVs where vendor exists but `tds_section` is NULL, prompting preparer to verify.
- **GST account code staleness**: GST rates are invoice-sourced (correct — Textract extracts them). But account code mappings (1310/1311/1312) are entity-configurable. Alert Admin to review mappings after GST rate changes.

### Performance Risks

- **Batch upload of 50 files**: Airlock per file ~200–500ms. Do NOT run synchronously in the upload request — return job IDs immediately, defer all processing to Celery tasks.
- **Textract latency**: 2–60s per document. Must be Celery async. Provide `/documents/{id}/status` polling endpoint.
- **AP ageing queries**: Composite index `(tenant_id, entity_id, due_date, payment_status)` required in migration 0003 — without it, full table scan at scale.
- **Notification fan-out**: Daily digest iterates all reviewers per tenant — batch in groups of 100 using Celery chord.

### Data Integrity Risks

- **Duplicate email webhook delivery**: Mitigated by `message_id` idempotency key in EmailIngestionLog. Must return 200 synchronously.
- **Concurrent approval**: SELECT FOR UPDATE on JournalVoucher row.
- **Chain hash on payment status updates**: JournalVoucher uses FinancialBase (chain_hash). Payment status syncs must insert new JV version rows (insert-only), NOT UPDATE existing rows — or hash chain breaks.
- **ERP COA sync failure**: Stale `coa_accounts` table means JV account code validation uses stale data. Alert Admin on sync failure; provide manual resync trigger in settings.

### Test Coverage Gaps

- **No RBAC enforcement tests at API level**: Add tests attempting each privileged action with wrong roles — assert 403.
- **No ERP write integration tests**: Zoho connector has no test file. Mock httpx tests needed for JV creation, attachment upload, partial failure, auth refresh.
- **No Textract mock tests**: Create fixture with sample AnalyzeExpense response for a realistic Indian invoice (multiple tax lines, GSTIN, TDS section).
- **No email idempotency tests**: Post same SendGrid webhook payload twice — assert exactly one SourceDocument record.

---

## Step 7 — Effort Summary Table

| Module / Gap | Category | Complexity | Est. Days |
|---|---|---|---|
| JV Data Model & Document Model | A | Medium | 2.0 |
| Legal Entity Master Model | A | Medium | 1.5 |
| Document Upload API | A | Low | 1.0 |
| AWS Textract Extraction Pipeline | D/A | High | 4.0 |
| Entity Detection Logic | A | High | 2.0 |
| GST Line Split Calculation | C | Low | 1.0 |
| TDS Deduction Logic | A | Medium | 1.0 |
| JV Approval State Machine | A/B | High | 3.0 |
| Duplicate Detection (all 3 methods) | A | Medium | 1.5 |
| Inbound Email Ingestion Webhook | D/A | High | 3.0 |
| Notification System (in-app + email) | A | High | 3.0 |
| Outbound Webhook Delivery | A | Medium | 2.0 |
| AP Ageing Calculation + Report | A | Medium | 2.0 |
| Zoho Write Methods (JV + attachment) | B | High | 3.0 |
| QBO Connector (full) | D | High | 4.0 |
| RBAC — AL Roles + Entity Scope | B | Medium | 2.0 |
| Airlock TIFF + R2 WORM path | B | Low | 0.5 |
| COA Sync Daily Job | B | Low | 1.0 |
| Payment Status Sync Job | B | Medium | 1.5 |
| Due Date Urgency Flags | A | Low | 0.5 |
| Vendor Portal (backend) | A | Medium | 2.0 |
| Inbound API (external push) | A | Low | 1.0 |
| Audit Log Export | B | Low | 0.5 |
| Document Splitting Detection | A | High | 2.0 |
| Frontend — Accounting Layer Module | A | High | 8.0 |
| **V1 Total (Sprints 1–5)** | | | **~52 days** |
| Multi-level approval | B | Medium | 2.0 |
| Delegated approver | A | Low | 1.0 |
| GDrive/OneDrive/Box OAuth | D | High | 4.0 |
| Intercompany JV handling | A | High | 3.0 |
| Recurring entry templates | A | Medium | 2.0 |
| PO matching | A | Medium | 2.0 |
| Rejection analytics dashboard | B | Low | 1.0 |
| SLA tracking dashboard | A | Low | 1.5 |
| Bulk approval UI | B | Low | 1.0 |
| **V2 Total** | | | **~17.5 days** |

### Assessment

**Is 5 weeks realistic for V1 with a 2-person team?**

52 person-days / 2 people = 26 working days ≈ 5.5 weeks. Only achievable if both devs are senior, fully fluent in the stack, and no blocking external dependencies arise. **6–7 weeks is a more honest estimate** when accounting for PR review, ERP sandbox setup, and integration debugging.

**Top 3 risks to timeline:**

1. **AWS Textract + R2 incompatibility** — Textract cannot read Cloudflare R2 directly. Requires either switching document storage to AWS S3 for the accounting module, or implementing a copy step, or using synchronous bytes mode (5MB limit). Discovering this on Day 5 of Sprint 2 costs 3–4 days.
2. **QBO OAuth + Intuit app review** — Production access requires Intuit app review (days to weeks). Sandbox API is inconsistent. The 4-day estimate easily doubles with debugging.
3. **Notification system wiring (22 trigger events)** — Every state transition in approval_service, extraction pipeline, and ERP push must call notify(). Easy to ship 80% and spend weeks on the remaining 20%.

**Safe descopes to V2:**

- **Vendor self-submission portal** — 3 of 5 ingestion methods (direct upload, managed folder, email) cover all invoices. Portal is convenience.
- **Outbound webhook + inbound API** — Already V2 per design doc Section 32. Zero impact on internal AP workflow.
- **Full email notification suite** — In-app covers Day 1; digest emails and reminder nudges can follow.
- **QBO connector** — If org uses only Zoho Books, removes 4 days and a high-complexity external dependency.

**Existing patterns that significantly speed up delivery:**

- `FinancialBase` + chain_hash pattern: immutable JV records need zero new infrastructure.
- Celery + Redis: production-ready with 4 priority queues; all async tasks slot directly in.
- `storage/airlock.py`: document upload security completely solved.
- `utils/gstin.py`: `validate_gstin()` + `extract_state_code()` — the hardest part of Indian tax compliance is already correct and tested.
- Zoho OAuth + async httpx pattern: JV write methods follow the exact same `_fetch` + token refresh pattern already in the connector.
- Platform RBAC evaluator: AL roles are configuration of an existing production system.
- `AuditTrail` model: AP audit logging needs only new event type enum values.

