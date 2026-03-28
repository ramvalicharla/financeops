1. Repo Inventory
I reviewed the repo structure under D:\finos and mapped major surfaces to the Accounting Layer scope.

Frontend
frontend/app contains Next.js App Router pages for dashboard modules, auth, onboarding, org setup, and settings.
frontend/components contains reusable UI + module widgets (including sync and review experiences).
frontend/lib/store uses Zustand persisted stores (tenant, location, ui, displayScale).
frontend/hooks uses React Query-based data hooks.
frontend/middleware.ts enforces auth and org-setup gate redirects.
Backend
backend/financeops/main.py is the FastAPI entrypoint registering many module routers and lifecycle startup.
backend/financeops/api + backend/financeops/api/v1 hold API dependencies and v1 route modules.
backend/financeops/modules/* is a large modular domain surface (expense, coa, org_setup, erp_sync, invoice_classifier, locations, etc.).
backend/financeops/services/* contains cross-cutting business services (audit, GST, FX, bank recon, etc.).
ERP Integrations
backend/financeops/modules/erp_sync/infrastructure/connectors/* contains connector clients (Zoho, QuickBooks, Xero, SAP, Oracle, etc.).
backend/financeops/modules/erp_sync/application/* contains sync orchestration, normalization, validation, publishing.
Document / File Handling
Upload endpoint exists in bank reconciliation API.
Storage/airlock utilities exist in backend/financeops/storage (R2 + antivirus/type/size checks).
Email Handling
Outbound email exists via notifications/scheduled delivery SMTP channels.
No inbound email parse receiver found for document ingestion.
Database
Models are split across backend/financeops/db/models and some platform/module model folders.
Migrations in backend/migrations/versions.
RLS/session wiring in backend/financeops/db/session.py, db/rls.py, and deps.
Auth & Authorization
OAuth2 JWT dependency + role guards in backend/financeops/api/deps.py.
User roles in db/models/users.py.
Entity-scoped access in platform/services/tenancy/entity_access.py.
Notification System
modules/notifications handles in-app/email/push + preferences.
modules/scheduled_delivery handles outbound webhook/email scheduled dispatch with logs.
Background Jobs
Celery app in tasks/celery_app.py.
Scheduled delivery tasks in modules/scheduled_delivery/tasks.py.
Additional temporal/workflow orchestration exists.
Infrastructure / Config
Root + backend docker/env/alembic config files.
infra/ contains infrastructure config assets.
Tests
Large backend pytest suite in backend/tests (2200+ style footprint, broad module coverage).
Frontend tests under frontend/tests and Playwright config.
Documentation
Product/platform docs in docs/platform, including:
ACCOUNTING_LAYER_DESIGN.md
ACCOUNTING_LAYER_GAP_PROMPT.md
2. Map Existing Capabilities
Document Ingestion
Capability	Status	Evidence
File upload endpoint (single file)	EXISTS	backend/financeops/api/v1/bank_recon.py:69,73 (/upload-statement, UploadFile)
File upload endpoint (batch / multiple files)	MISSING	Code search found no list[UploadFile]/multi-file upload endpoints
File storage client (S3/GCS/Azure/local)	EXISTS	backend/financeops/storage/r2.py:16,43
Write-only/WORM S3 folder provisioning per entity	MISSING	r2.py includes delete API (backend/financeops/storage/r2.py:75), no WORM/provisioning layer found
Inbound email parsing/webhook receiver	MISSING	No SendGrid/SES/Mailgun inbound parser routes found; only payment webhooks (payment/api/webhooks.py:37,73)
Email sender whitelist verification logic	MISSING	No whitelist model/service for inbound email senders found
Auto-reply email sender	MISSING	Outbound email exists, but no inbound-auto-reply workflow
External-facing vendor submission portal/page	PARTIAL	Public external endpoint exists in partner program (partner_program/api/routes.py:287), but not invoice submission
Vendor identity verification against vendor master	MISSING	Vendor master extraction datasets exist, but no vendor portal verification workflow
AI / OCR Processing
Capability	Status	Evidence
AWS Textract/Document AI/Form Recognizer integration	MISSING	No OCR provider integration found (textract/document ai/form recognizer search empty)
Document processing worker/pipeline	PARTIAL	File security pipeline exists (storage/airlock.py:54,103), invoice classifier exists, but no OCR doc extraction pipeline
Field confidence scoring logic	EXISTS	invoice_classifier/rule_engine.py:8, classifier_service.py:83,97, ai_classifier.py:25,30
Document splitting / multi-invoice detection	MISSING	No split/multi-invoice detection logic found
Low-quality scan detection and flagging	MISSING	No DPI/quality/scan-quality flag logic found
ERP Integrations
Capability	Status	Evidence
Zoho Books API client/wrapper	EXISTS	erp_sync/connectors/zoho.py:17,21,146,176
QuickBooks Online API client/wrapper	EXISTS	erp_sync/connectors/quickbooks.py:36,40,105
Journal entry/JV creation in ERP	MISSING	Connectors are extract-focused; no JV create/post method found
Document attachment upload to ERP	MISSING	No attachment-upload methods found in Zoho/QBO connectors
Attachment linking to ERP JV by ID	MISSING	No link-attachment-to-journal flow found
Chart of Accounts sync from ERP	PARTIAL	Dataset enum supports COA (erp_sync/domain/enums.py:76), extraction framework exists
Payment status sync from ERP	MISSING	No AP/JV payment-status sync path found in ERP sync
ERP error handling and retry queue	PARTIAL	Sync engine has idempotency + resume guards (sync_service.py:120,280), but not JV push+attachment retry sequence
Accounting & Tax Logic
Capability	Status	Evidence
JV/journal entry data model in DB	PARTIAL	Module-specific journals exist (db/models/fixed_assets.py:210, prepaid.py:133, revenue.py:198, lease.py:266), no accounting-layer JV model
GST line split logic (CGST/SGST vs IGST)	MISSING	GST services handle return records/recon, not invoice JV tax line splitting (services/gst_service.py)
TDS deduction line logic by section	MISSING	No 194C/194J/194I JV line generator found
Multi-currency / exchange rate handling	EXISTS	FX services (services/fx/provider_clients.py:23,213,268, fx_rate_service.py:28)
PO data store/sync from ERP	PARTIAL	PO dataset type exists (erp_sync/domain/enums.py:49), base connector marks unsupported (connectors/base.py:92)
PO matching logic	MISSING	No invoice-vs-open-PO matching service found
AP ageing calculation logic	EXISTS	working_capital/models.py:54,83, service.py:238,263,319
Recurring entry/JV template engine	MISSING	No recurring JV engine found
Entity & Vendor Management
Capability	Status	Evidence
Legal entity master	PARTIAL	platform/db/models/entities.py:14,23,36,39,44; has key legal fields but not accounting-layer routing config completeness
Entity detection logic (GSTIN/PAN/Billed-To/address/vendor mapping)	MISSING	Context resolver resolves explicit/default entity only (platform/services/context_resolver.py:13,53)
Confidence scoring for entity detection	MISSING	No entity-detection confidence engine found
Vendor master (name/GSTIN/entity mapping/TDS section)	PARTIAL	ERP dataset VENDOR_MASTER exists (erp_sync/domain/enums.py:77), but no tenant vendor-master module for workflow decisions
Intercompany detection and paired JV creation	MISSING	No doc/JV paired intercompany workflow found
Workflow & Approvals
Capability	Status	Evidence
JV status state machine	MISSING	No accounting-layer JV state machine model/service
Maker-checker enforcement	PARTIAL	Generic workflow approvals exist (platform/services/workflows/approval_service.py), not wired to JV flow
Multi-level approval (threshold tiers)	PARTIAL	approval_service.py:104-132; workflow stage thresholds exist
Delegated approver config	PARTIAL	platform/schemas/workflows.py:49, workflow_approvals.py:45, but no accounting-layer usage
Resubmission flow with max attempt limit	MISSING	No max-resubmission policy flow found
Escalation after max rejections	MISSING	No such escalation logic found
Internal notes/comments on JVs	PARTIAL	Comments exist for expense approvals (expense_management/models.py:117), not JV notes thread
Due date urgency flags	PARTIAL	Overdue metrics in working capital, not JV-review urgency workflow
Approval reminder nudges (24h/48h)	MISSING	No approval reminder scheduler/policy found
SLA tracking (submission→decision)	MISSING	No explicit approval SLA metrics pipeline found
Bulk approval capability	PARTIAL	Frontend bulk action in invoice classify UI exists; no dedicated robust backend bulk-approval workflow/state machine
Auth & RBAC
Capability	Status	Evidence
Role-based access control system	EXISTS	api/deps.py:98,182,191,200
Roles: Preparer/Reviewer/Senior Reviewer/CFO/Admin/Auditor/Payroll Approver	PARTIAL	Generic roles exist (db/models/users.py:14-23) but accounting-specific role taxonomy not present
User-entity assignment	EXISTS	platform/db/models/user_membership.py:43,61
Entity-scoped data filtering	EXISTS	entity_access.py:30,86
Duplicate Detection
Capability	Status	Evidence
File hash (SHA-256) deduplication	PARTIAL	Hash computed (storage/r2.py, storage/airlock.py), file_hash stored (bank_recon.py:54, db/models/bank_recon.py:51), no global dedupe enforcement path
Invoice number + vendor uniqueness	MISSING	No unique constraint/check in invoice classification flow
Fuzzy match (vendor + amount + date ±1)	MISSING	No fuzzy duplicate logic found
Notifications
Capability	Status	Evidence
In-app notification system	EXISTS	modules/notifications/service.py:119,310
Transactional email service	EXISTS	notifications/channels/email_channel.py:127
Background queue for async notifications	EXISTS	Celery + scheduled tasks (tasks/celery_app.py:17,62; scheduled_delivery/tasks.py:23,67)
Notification preference management	EXISTS	notifications/models.py:119,134; service.py:65
Daily digest email	MISSING	No digest scheduler/pipeline found
Webhook outbound delivery system	EXISTS	scheduled_delivery/application/delivery_service.py:334,351; logs include retries (db/models/scheduled_delivery.py:108,159)
Reporting & Analytics
Capability	Status	Evidence
Dashboard infrastructure	EXISTS	Multiple dashboard routes (working_capital/api/routes.py:24, debt_covenants/api/routes.py:108) + frontend dashboard pages
Rejection analytics (preparer/vendor/reason)	MISSING	No dedicated rejection analytics module for accounting approvals
SLA metrics dashboard	MISSING	No approval-SLA dashboard implementation found
AP ageing report	EXISTS	Working capital AP/AR ageing model + service (models.py:54,83; service.py:319)
Export to CSV/PDF	PARTIAL	Exports exist across modules, but not AP ageing export in working_capital module
External Integration
Capability	Status	Evidence
Inbound API with API-key auth for external document push	MISSING	No inbound document endpoint with API-key auth pattern found
Outbound webhook system (events/retry/log)	EXISTS	Scheduled delivery webhook dispatch + retry count/logging (delivery_service.py:159,192,334; db/models/scheduled_delivery.py:108,159)
OAuth integration pattern (GDrive/OneDrive/Box connect)	PARTIAL	OAuth connector pattern exists in sync UX/connectors (frontend/components/sync/ConnectSourceForm.tsx:43,50,85; quickbooks/zoho token refresh logic), but not cloud-folder ingestion watcher implementation
Audit
Capability	Status	Evidence
Immutable audit log model	EXISTS	db/models/audit.py:12,16; chain fields in base (db/base.py:39-41,50,54)
User action event logging	EXISTS	services/audit_service.py:23,63
Audit log export	PARTIAL	Audit retrieval service exists (audit_service.py:147) but no dedicated accounting audit export endpoint found
3. Gaps
Category A — Build from Scratch
Gap Name: Inbound Email Ingestion Pipeline
Category: A
Description: No org-email ingestion webhook, sender whitelist, attachment extraction, auto-reply/idempotency flow.
Relevant Existing Files: None for inbound parsing (only payment webhooks at payment/api/webhooks.py:37,73)
Complexity: High
External Dependency: SendGrid Inbound Parse or AWS SES

Gap Name: OCR/Extraction Pipeline
Category: A
Description: No OCR/Textract-based invoice field extraction pipeline.
Relevant Existing Files: None (no textract/document-ai integration found)
Complexity: High
External Dependency: AWS Textract (recommended)

Gap Name: Accounting-Layer JV Aggregate + State Machine
Category: A
Description: No central accounting JV/document model with lifecycle states and immutability after approval.
Relevant Existing Files: None (only module-specific journal models)
Complexity: High
External Dependency: None

Gap Name: GST/TDS JV Line Engine
Category: A
Description: Missing GST intra/inter-state split + TDS section-based deduction line generation for JV drafts.
Relevant Existing Files: GST service is return/recon-oriented (services/gst_service.py)
Complexity: High
External Dependency: Optional GSTN API later

Gap Name: Duplicate Detection Engine (invoice-level)
Category: A
Description: Missing invoice-level dedupe checks (invoice+vendor + fuzzy date/amount matching).
Relevant Existing Files: Hash utilities exist; no invoice dedupe logic
Complexity: Medium
External Dependency: None

Gap Name: Document Splitting + Low Quality Flags
Category: A
Description: Missing multi-invoice detection/split and scan-quality risk flags.
Relevant Existing Files: None
Complexity: Medium
External Dependency: OCR provider confidence/page analysis

Gap Name: Vendor Submission Portal (external)
Category: A
Description: Missing external vendor invoice submission + status tracking surface with vendor verification and rate limits.
Relevant Existing Files: Partner public tracking exists but unrelated (partner_program/api/routes.py:287)
Complexity: High
External Dependency: Optional custom domain/CDN config

Category B — Extend / Modify Existing
Gap Name: ERP Connectors for Push Sequence
Category: B
Description: Existing connectors are extraction-first; must add validate/create-JV/upload-attachment/link attachment + error mapping.
Relevant Existing Files: erp_sync/connectors/zoho.py, quickbooks.py
Complexity: High
External Dependency: Zoho Books + Intuit APIs

Gap Name: Generic Workflow Engine → Accounting Workflow
Category: B
Description: Workflow engine exists (thresholds/delegation/idempotency) but is not bound to accounting JV roles/states/rules.
Relevant Existing Files: platform/services/workflows/approval_service.py:104-132, platform/api/v1/workflows.py
Complexity: Medium
External Dependency: None

Gap Name: RBAC Role Model for Accounting
Category: B
Description: Current roles are generic; need accounting-specific role matrix + entity-scoped restrictions (Preparer/Reviewer/CFO/etc).
Relevant Existing Files: db/models/users.py:14-23, api/deps.py
Complexity: Medium
External Dependency: None

Gap Name: Vendor Master Product Surface
Category: B
Description: ERP vendor dataset exists, but no first-class vendor master with entity mapping + TDS defaults for accounting decisions.
Relevant Existing Files: erp_sync/domain/enums.py:77
Complexity: Medium
External Dependency: None

Gap Name: AP Ageing Productization
Category: B
Description: AP ageing logic exists in working capital; needs accounting-layer integration, filters, drilldowns, and exports.
Relevant Existing Files: working_capital/service.py:319, api/routes.py
Complexity: Medium
External Dependency: None

Gap Name: Audit Export Surface
Category: B
Description: Audit storage/logging exists, but needs explicit accounting audit export/report endpoints and UI.
Relevant Existing Files: services/audit_service.py:147
Complexity: Medium
External Dependency: None

Category C — Wire Together
Gap Name: Unified Ingestion Orchestration
Category: C
Description: Upload, storage, notifications, invoice classifier, and ERP sync pieces exist but are not wired into one accounting flow.
Relevant Existing Files: api/v1/bank_recon.py, storage/airlock.py, invoice_classifier/*, erp_sync/*
Complexity: High
External Dependency: None

Gap Name: Entity Detection Pipeline
Category: C
Description: Entity master exists; no multi-signal detection chain (GSTIN/PAN/name/address/vendor/folder).
Relevant Existing Files: platform/db/models/entities.py, platform/services/context_resolver.py
Complexity: High
External Dependency: OCR extraction output

Gap Name: ERP Push + Retry + Audit + Notifications
Category: C
Description: Outbound webhook/retry and audit tools exist; need accounting push failure-recovery choreography.
Relevant Existing Files: scheduled_delivery/application/delivery_service.py, services/audit_service.py
Complexity: High
External Dependency: ERP APIs

Gap Name: Reviewer Queue UX + Backend Review Actions
Category: C
Description: Invoice classifier UI has review pieces; full accounting reviewer split-panel + notes + history + SLA not wired.
Relevant Existing Files: frontend/app/(dashboard)/invoice-classify/page.tsx, invoice_classifier/api/routes.py
Complexity: Medium
External Dependency: None

Category D — Third-Party Integration Required
Gap Name: Inbound Email Provider Integration
Category: D
Description: Need inbound parse provider (webhook payload parsing + attachment extraction + idempotency).
Relevant Existing Files: None
Complexity: High
External Dependency: SendGrid Inbound Parse / AWS SES

Gap Name: OCR Vendor Integration
Category: D
Description: Need OCR/expense extraction provider and async processing semantics.
Relevant Existing Files: None
Complexity: High
External Dependency: AWS Textract / Document AI / Form Recognizer

Gap Name: Cloud Folder Watchers
Category: D
Description: OAuth patterns exist, but no GDrive/OneDrive/Box folder watcher ingestion service.
Relevant Existing Files: frontend/components/sync/ConnectSourceForm.tsx; ERP connector OAuth token handling
Complexity: High
External Dependency: Google Drive API, Microsoft Graph, Box API

4. Implementation Plan (by Gap)
Gap: Inbound Email Ingestion Pipeline
Category: A
Complexity: High
New Files to Create:
backend/financeops/modules/accounting_layer/email_ingestion/models.py — whitelist + inbound message dedupe metadata.
backend/financeops/modules/accounting_layer/email_ingestion/api/routes.py — webhook receiver.
backend/financeops/modules/accounting_layer/email_ingestion/service.py — parse/validate/dispatch.
Existing Files to Modify:
backend/financeops/main.py — register router.
backend/financeops/services/audit_service.py usage points for ingestion events.
Implementation Approach: Build provider-agnostic inbound route with verified signature, parse attachments, dedupe by message-id hash, enforce whitelist (email/domain), enqueue each attachment into extraction queue, and log immutable audit events.
Depends On: OCR pipeline, unified ingestion orchestration.
Estimated Effort: 4–5 dev-days
Gap: OCR/Extraction Pipeline
Category: D
Complexity: High
New Files to Create: OCR adapter + extraction worker + normalized extraction schema.
Existing Files to Modify: ingestion orchestrator + invoice classifier service to consume extracted fields.
Implementation Approach: Introduce async task queue stage: document -> OCR parse -> normalized fields + confidences -> downstream classification and JV draft creation.
Depends On: Email/folder/direct ingestion adapters.
Estimated Effort: 5–7 dev-days
Gap: JV Aggregate + State Machine
Category: A
Complexity: High
New Files to Create: JV models, workflow state transition service, API routes, append-only event log.
Existing Files to Modify: generic workflow integration points + audit logging + ERP push trigger layer.
Implementation Approach: Create strict transition map with transactional updates and optimistic locking; enforce immutability post-approved and explicit admin-void path with mandatory reason.
Depends On: RBAC alignment, workflow wiring.
Estimated Effort: 6–8 dev-days
Gap: GST/TDS JV Line Engine
Category: A
Complexity: High
New Files to Create: tax_line_engine service + validators + unit tests.
Existing Files to Modify: JV draft builder and entity/vendor master integrations.
Implementation Approach: Use GSTIN state-code comparison for CGST/SGST vs IGST and configurable TDS section mappings with Decimal-safe arithmetic.
Depends On: Entity detection + vendor master.
Estimated Effort: 3–4 dev-days
Gap: Duplicate Detection Engine
Category: A
Complexity: Medium
New Files to Create: duplicate_service with exact/fuzzy strategies.
Existing Files to Modify: ingestion orchestrator, classification submission route.
Implementation Approach: Layered checks: file hash, invoice+vendor key, fuzzy amount/date/vendor; expose review actions (skip/override/related) with audit.
Depends On: OCR extraction normalization.
Estimated Effort: 2–3 dev-days
Gap: ERP Push Sequence (JV + Attachment + Partial Failure Handling)
Category: B/C
Complexity: High
New Files to Create: ERP push orchestrator + retry job tables/tasks.
Existing Files to Modify: Zoho/QBO connectors + sync service + status surfaces.
Implementation Approach: Sequence: validate -> create journal -> upload attachment -> link. If attachment fails, persist retry task (exponential backoff) without rolling back created journal.
Depends On: JV state machine approved stage.
Estimated Effort: 5–6 dev-days
Gap: Vendor Portal
Category: A
Complexity: High
New Files to Create: external portal routes, submission model, status query endpoint, frontend portal page.
Existing Files to Modify: vendor master integration, rate limiter config, audit logging.
Implementation Approach: Public POST with strict file validation + vendor-email verification + per-email rate limit + reference ID issuance; status endpoint returns only constrained states.
Depends On: Vendor master product surface, ingestion pipeline.
Estimated Effort: 4–5 dev-days
Gap: Entity Detection Pipeline
Category: C
Complexity: High
New Files to Create: entity_detection_service + confidence scoring module.
Existing Files to Modify: ingestion orchestrator + manual assignment APIs.
Implementation Approach: Ordered signal evaluation (folder > GSTIN > PAN > billed-to > address > vendor > user context), return top match + confidence + reasons, fallback manual queue.
Depends On: OCR extraction + entity/vendor masters.
Estimated Effort: 3–4 dev-days
Gap: Workflow Engine Integration
Category: B/C
Complexity: Medium
New Files to Create: accounting workflow template bootstrap + role-policy mappings.
Existing Files to Modify: platform/services/workflows/approval_service.py call sites + accounting JV endpoints.
Implementation Approach: Reuse threshold/delegation/idempotency engine but enforce accounting constraints (no self-approval, max resubmissions, escalation).
Depends On: JV state machine.
Estimated Effort: 3–4 dev-days
Gap: Review Queue SLA + Reminder Nudges
Category: A/B
Complexity: Medium
New Files to Create: reminder scheduler task + SLA metrics aggregator.
Existing Files to Modify: notifications + dashboard endpoints.
Implementation Approach: Scheduled scans for pending-review aging; push in-app/email reminders at policy thresholds and persist SLA metrics for dashboards.
Depends On: JV workflow timestamps.
Estimated Effort: 2–3 dev-days
5. Sprint-by-Sprint Plan (V1)
Sprint 1: Ingestion & Foundations
Goal: Users can upload documents into a normalized ingestion queue with audit events and duplicate pre-check.
Backend Tasks: accounting ingestion models/routes, dedupe engine (hash + key), audit wiring, queue contracts.
Frontend Tasks: Accounting Layer upload page (single + batch UI), ingestion status list.
Gaps Closed: Ingestion orchestration base, duplicate engine base, audit wiring.
Dependencies: None
Sprint 2: OCR + Entity/Tax Drafting
Goal: Uploaded docs produce draft JV candidates with extracted fields, confidence, entity suggestion, GST/TDS split.
Backend Tasks: OCR adapter worker, entity detection pipeline, GST/TDS line engine, draft JV schema.
Frontend Tasks: Draft review/edit screen, confidence indicators, entity override.
Gaps Closed: OCR pipeline, entity detection, GST/TDS engine.
Dependencies: Sprint 1
Sprint 3: Approval Workflow & Ops Controls
Goal: Drafts can be submitted/reviewed/rejected/resubmitted with maker-checker, reminders, and audit trace.
Backend Tasks: JV state machine, workflow integration, maker-checker enforcement, resubmission limits + escalation, reminders.
Frontend Tasks: Reviewer split panel, notes/comments, pending queue with urgency flags.
Gaps Closed: Workflow/maker-checker, reminders/SLA base, notes queue.
Dependencies: Sprint 2
Sprint 4: ERP Push & External Surfaces
Goal: Approved JVs push to Zoho/QBO with attachment + retry handling; vendor portal and email ingestion available.
Backend Tasks: ERP push orchestration, attachment retry queue, inbound email adapter, vendor portal APIs.
Frontend Tasks: Push status/error views, vendor portal UI, admin settings for whitelist/integrations.
Gaps Closed: ERP push sequence, email ingestion, vendor portal.
Dependencies: Sprint 3
6. Risks & Concerns
Technical Debt
Many module patterns are mature, but Accounting Layer needs a new domain aggregate (document+JV+workflow) rather than incremental patching across unrelated modules.
Current extraction/connectors are strongly sync/extract oriented; push choreography is absent.
Architecture Risks
OCR must be async end-to-end; request/response path cannot block on long extraction.
Email webhook idempotency is mandatory (provider retries/duplicates).
Partial ERP failure handling (JV created, attachment failed) must persist deterministic retry state.
State-machine integrity requires strict transition guards and transaction-safe locking.
Security Risks
Inbound document surfaces (email/vendor portal/API) add attack surface; must enforce type/size/malware/abuse controls.
Vendor portal must avoid data leakage and spoofing (whitelist + rate limits + minimal response payload).
Maker-checker must be enforced backend-side; UI controls are insufficient.
PII in invoices requires masking/access controls and retention policies.
Indian Tax Compliance Risks
GST state-code extraction can fail on dirty OCR; fallback validation/manual confirmation needed.
TDS sections/rates should be configurable by vendor/entity, not hardcoded.
GST/TDS mappings must be versioned for regulatory updates.
Performance Risks
Batch upload and OCR fan-out need queue backpressure control.
AP ageing and reviewer queues need indexing for large tenants.
ERP push retries can snowball without idempotent keys and bounded retry policy.
Data Integrity Risks
Duplicate ingestion from multiple channels (upload/email/folder/API) without strong dedupe keys.
Stale COA sync causing push failures.
Concurrent reviewer actions on the same JV without optimistic lock/version checks.
Test Coverage Gaps
No end-to-end tests for accounting-specific ingestion->approve->push flow (because feature absent).
Existing connector tests are extraction-heavy; push/attachment failure paths are untested.
No API-level tests yet for accounting maker-checker invariants.
7. Effort Summary
Module / Gap	Category	Complexity	Est. Days
Ingestion orchestration (upload/email/folder/API adapters)	A/C	High	5
OCR extraction pipeline + confidence normalization	D	High	6
Entity detection engine	C	High	4
GST/TDS tax line engine	A	High	4
Duplicate detection engine	A	Medium	3
JV aggregate + state machine	A	High	8
Workflow integration (threshold/delegation + maker-checker rules)	B/C	Medium	4
Reviewer queue, notes, urgency, reminders/SLA	A/B	Medium	4
ERP push (Zoho/QBO) + attachment + retry/error mapping	B/C	High	6
Vendor portal (public) + verification/rate limits	A/D	High	5
COA/payment status sync wiring for accounting layer	B/C	Medium	3
Audit/report/export surfaces for accounting	B	Medium	3
V1 Total			55 days
V2 Total (cloud folders, multi-level approvers, intercompany, PO matching, webhook/API enrichments)			25–35 days
Timeline Assessment
Is 5 weeks realistic for V1 with 2 people?
No. With current baseline, realistic is closer to 8–10 weeks for a stable V1.
Top 3 risks to timeline:
OCR + entity detection accuracy and fallback UX loops.
ERP push with partial-failure correctness across two ERPs.
Designing a safe JV state machine + maker-checker invariants without regressions.
Safe descopes to V2:
Vendor portal.
Inbound org email ingestion (keep direct upload first).
Advanced SLA/rejection analytics (keep basic queue metrics only).
Existing patterns that accelerate delivery:
Strong generic workflow engine foundations (threshold/delegation/idempotent approvals).
Existing audit chain-hash infrastructure.
Existing outbound notification/webhook and ERP connector scaffolding.
If you want, next I can generate the B1 ticket breakdown (AL-001...) directly from this gap list.