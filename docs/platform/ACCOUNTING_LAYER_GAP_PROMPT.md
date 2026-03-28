# Accounting Layer — Gap Analysis & Implementation Prompt
# Version: 3.0 | Updated: 2026-03-26
# Save as: D:\finos\ACCOUNTING_LAYER_GAP_PROMPT.md
# Use alongside: D:\finos\ACCOUNTING_LAYER_DESIGN.md

---

## HOW TO USE THIS FILE

| Tool | Best For | Command |
|------|---------|---------|
| **Claude Code** ⭐ Recommended | Large repos — reads entire codebase directly | `cd D:\finos` → `claude` → paste prompt |
| **Claude.ai** | Smaller repos — upload key files as context | Upload files + paste prompt |
| **Cursor / Windsurf** | IDE-based | Open D:\finos, AI chat, @codebase + paste prompt |

Install Claude Code: `npm install -g @anthropic-ai/claude-code`

---

## SECTION A — MAIN GAP ANALYSIS PROMPT

Paste everything below this line into Claude Code or Claude.ai:

---

You are a senior full-stack software architect performing a thorough codebase
audit for a new platform feature.

The repository is at D:\finos.
The complete feature specification is in `ACCOUNTING_LAYER_DESIGN.md` in this repo.
**Read that file in full before proceeding with any step below.**

---

### WHAT THE FEATURE DOES (Summary)

The **Accounting Layer** is an internal organisational platform feature that:

1. Accepts financial documents (invoices, bills, credit notes, expense claims, bank statements) via five ingestion methods:
   - Direct upload (drag and drop on platform)
   - Connected cloud folders (GDrive, OneDrive, Box)
   - Platform-managed write-only S3 folder per entity
   - Dedicated organisational email address (one per org — not per entity)
   - Vendor self-submission portal (external-facing, controlled)

2. Auto-identifies which legal entity in the group the document belongs to using signals: GSTIN, PAN, Billed-To name, registered address, vendor master mapping, upload folder

3. Extracts accounting fields using AI/OCR (AWS Textract recommended): invoice number, date, line items, GST components (CGST/SGST/IGST/TDS), amounts, currency, PO number

4. Detects and handles multiple invoices in a single document (document splitting)

5. Creates a Journal Voucher (JV) draft with correct Indian tax line splits (CGST+SGST for intra-state, IGST for inter-state, TDS deduction lines)

6. Routes JV through a maker-checker approval workflow — Preparer submits, Reviewer approves or rejects. Multi-level approval for high-value JVs (Reviewer → Senior Reviewer → CFO based on configurable thresholds)

7. Supports internal notes and comments on JVs throughout the workflow

8. Shows due date urgency flags (overdue, due soon, early payment discount available)

9. Attempts PO matching — checks if invoice references an open Purchase Order

10. Pushes approved JVs AND source document attachments to correct ERP (Zoho Books / QuickBooks Online) per entity — only after explicit approval, never auto-push

11. Tracks payment status synced from ERP after push

12. Surfaces AP ageing report, rejection analytics, SLA tracking across entities

13. Fires outbound webhooks and accepts inbound API calls for external system integration

14. Maintains a full immutable audit log of every action on every document

15. Feature is internal-only except for the vendor portal surface

---

### STEP 1 — REPO INVENTORY

Walk through every file and folder in D:\finos.
Build a categorised inventory with file purpose (1 sentence each):

- **Frontend** — components, pages, routes, state management, UI framework
- **Backend** — API controllers, services, background workers, job queues
- **ERP Integrations** — Zoho Books, QuickBooks Online, other ERP connectors
- **Document / File Handling** — upload handlers, storage clients, file processors
- **Email Handling** — any inbound email parsing, SMTP clients, email services
- **Database** — models, schemas, migrations, ORM config
- **Auth & Authorisation** — auth middleware, RBAC, permissions, session management
- **Notification System** — email, in-app alerts, push, webhooks
- **Background Jobs** — job queues, workers, schedulers, cron
- **Infrastructure / Config** — Docker, env, CI/CD, cloud config, S3 config
- **Tests** — unit, integration, e2e test files
- **Documentation** — READMEs, existing specs, API docs

---

### STEP 2 — MAP EXISTING CAPABILITIES

For each capability below state: **EXISTS / PARTIAL / MISSING**
If it exists, cite the specific filename(s) and relevant line ranges.

#### Document Ingestion
- [ ] File upload endpoint (single file)
- [ ] File upload endpoint (batch / multiple files)
- [ ] File storage client (S3 / GCS / Azure Blob / local)
- [ ] Write-only / WORM S3 folder provisioning per entity
- [ ] Inbound email parsing / webhook receiver (SendGrid / AWS SES / Mailgun / Postmark)
- [ ] Email sender whitelist verification logic
- [ ] Auto-reply email sender
- [ ] External-facing vendor submission portal / page
- [ ] Vendor identity verification against vendor master

#### AI / OCR Processing
- [ ] AWS Textract integration (or Google Document AI / Azure Form Recognizer)
- [ ] Document processing worker / pipeline
- [ ] Field confidence scoring logic
- [ ] Document splitting / multi-invoice detection
- [ ] Low-quality scan detection and flagging

#### ERP Integrations
- [ ] Zoho Books API client / wrapper
- [ ] QuickBooks Online API client / wrapper
- [ ] Journal entry / JV creation in ERP
- [ ] Document attachment upload to ERP
- [ ] Attachment linking to ERP JV by ID
- [ ] Chart of Accounts sync from ERP
- [ ] Payment status sync from ERP
- [ ] ERP error handling and retry queue

#### Accounting & Tax Logic
- [ ] JV / journal entry data model in DB
- [ ] GST line split calculation (CGST/SGST vs IGST based on GSTIN state codes)
- [ ] TDS deduction line logic (by section: 194C, 194J, 194I)
- [ ] Multi-currency / exchange rate handling
- [ ] PO data store or PO sync from ERP
- [ ] PO matching logic (invoice PO number vs open POs)
- [ ] AP ageing calculation logic
- [ ] Recurring entry / JV template engine

#### Entity & Vendor Management
- [ ] Legal entity master (entity name, GSTIN, PAN, address, currency, ERP connection)
- [ ] Entity detection logic (GSTIN/PAN/Billed-To/address/vendor master matching)
- [ ] Confidence scoring for entity detection
- [ ] Vendor master (vendor name, GSTIN, entity mapping, TDS section)
- [ ] Intercompany entity detection and paired JV creation

#### Workflow & Approvals
- [ ] JV status state machine (Uploaded → Processing → Pending Review → Approved → Pushed)
- [ ] Maker-checker enforcement (Preparer cannot approve own JV)
- [ ] Multi-level approval (threshold-based tiers)
- [ ] Delegated approver configuration
- [ ] Resubmission flow with max attempt limit
- [ ] Escalation after max rejections
- [ ] Internal notes / comments on JV
- [ ] Due date urgency flag calculation
- [ ] Approval reminder nudges (24h, 48h)
- [ ] SLA tracking (time from submission to decision)
- [ ] Bulk approval capability

#### Auth & RBAC
- [ ] Role-based access control system
- [ ] Roles: Preparer, Reviewer, Senior Reviewer / CFO, Admin, Auditor, Payroll Approver
- [ ] User-entity assignment (user mapped to specific entities with specific roles)
- [ ] Entity-scoped data filtering (Reviewer only sees their entities)

#### Duplicate Detection
- [ ] File hash (SHA-256) deduplication
- [ ] Invoice number + vendor name uniqueness check
- [ ] Fuzzy match (vendor + amount + date ±1 day)

#### Notifications
- [ ] In-app notification system
- [ ] Transactional email service (SMTP / SendGrid / SES)
- [ ] Background job / queue for async notification delivery
- [ ] Notification preference management per user
- [ ] Daily digest email
- [ ] Webhook outbound delivery system

#### Reporting & Analytics
- [ ] Dashboard infrastructure (charts, widgets, filters)
- [ ] Rejection analytics (by preparer, by vendor, by reason)
- [ ] SLA metrics dashboard
- [ ] AP ageing report
- [ ] Export to CSV / PDF

#### External Integration
- [ ] Inbound API with authentication (API key) for external document push
- [ ] Outbound webhook system (configurable events, retry, delivery log)
- [ ] OAuth integration pattern (for GDrive/OneDrive/Box folder connect in V2)

#### Audit
- [ ] Immutable audit log model
- [ ] User action event logging
- [ ] Audit log export

---

### STEP 3 — IDENTIFY GAPS

Compare what exists (Step 2) vs what the feature requires.
Group every gap into:

#### Category A — Build from Scratch
No existing foundation. Must be built new.

#### Category B — Extend / Modify Existing
Foundation exists but needs significant changes or additions.

#### Category C — Wire Together
Individual pieces exist separately but not yet connected into a working flow.

#### Category D — Third-Party Integration Required
Needs an external SDK, API, or service not yet in the repo.

For each gap:

```
Gap Name: [name]
Category: [A / B / C / D]
Description: [what is missing or what needs to change]
Relevant Existing Files: [filename:line if applicable, or "None"]
Complexity: [Low / Medium / High]
External Dependency: [if Category D — name the service/SDK]
```

**Pay special attention to these high-priority gaps:**
- Inbound email parsing and attachment extraction (Method 4 ingestion)
- Entity detection from document content (GSTIN/PAN/Billed-To matching)
- GST line split (CGST vs SGST vs IGST using GSTIN state codes)
- TDS deduction line by section
- Maker-checker approval state machine with immutability after approval
- JV push to ERP + document attachment in sequence (with partial failure handling)
- Vendor self-submission portal (external surface, vendor verification)
- Document splitting (multiple invoices in one PDF)
- Due date urgency flag calculation and display
- AP ageing calculation
- Outbound webhook system
- Immutable audit log

---

### STEP 4 — IMPLEMENTATION PLAN

For every gap from Step 3, provide a structured implementation plan:

```
Gap: [Name]
Category: [A / B / C / D]
Complexity: [Low / Medium / High]
New Files to Create:
  - [filepath] — [purpose]
Existing Files to Modify:
  - [filepath] — [what changes]
Implementation Approach:
  [3–6 sentences. How to build it. What pattern to follow.
   What existing code to reuse or extend. Any gotchas.]
Depends On: [other gaps that must be completed first]
Estimated Effort: [developer-days for 1 experienced developer]
```

---

### STEP 5 — SPRINT-BY-SPRINT BUILD PLAN

Based on gaps and dependencies, produce a sprint plan for V1 of the Accounting Layer.
Assume a 2-person team (1 frontend dev, 1 backend dev).
Each sprint is 1–2 weeks.

**V1 scope (from ACCOUNTING_LAYER_DESIGN.md Section 32, Phase 1):**
Direct upload, managed folder, org email ingestion, AI extraction with confidence scoring,
entity detection and routing, GST/TDS line splits, duplicate detection, document splitting,
internal notes, due date urgency flags, JV status lifecycle, RBAC (Preparer/Reviewer/Admin),
single-level approval with rejection/resubmission (max 3), reviewer split-panel UI,
approval reminders, ERP push with attachment (Zoho + QBO), ERP error handling + retry,
COA sync, payment status sync, notifications, audit log, basic dashboard, manual FX rate entry.

Format:

```
Sprint [N]: [Theme]
Goal: [what is fully working at end of this sprint — describe as a user story]
Backend Tasks:
  - [task]
Frontend Tasks:
  - [task]
Gaps Closed: [which gap names from Step 3 are completed]
Dependencies: [what prior sprint must be complete]
```

---

### STEP 6 — RISKS & CONCERNS

Based on what you found in the codebase, flag:

**Technical Debt:**
- Any existing code quality issues that could slow down or complicate this feature

**Architecture Risks:**
- Sync vs async processing decisions (AI extraction must be async — is the job queue ready?)
- Email ingestion webhook reliability (what if webhook fires multiple times?)
- Partial ERP push failure (JV created in ERP but attachment fails — how is this recovered?)
- State machine integrity (can a JV skip states? Is the DB model transaction-safe?)

**Security Risks:**
- File upload vulnerabilities (type validation, malware scanning, path traversal)
- Inbound email injection risks (what if malicious content is in email body?)
- Vendor portal abuse (rate limiting, vendor identity spoofing)
- RBAC gaps (can a Preparer approve their own JV through any API route?)
- PII in documents (invoices contain personal data — is it handled per GDPR/IT Act?)

**Indian Tax Compliance Risks:**
- Is GSTIN state code extraction reliable enough for intra vs inter-state determination?
- Are TDS sections and rates hardcoded anywhere that would need maintenance?
- What happens when GST rates change? Is the logic configurable?

**Performance Risks:**
- Batch upload of 50 files — does the current infrastructure handle this?
- AI extraction latency (Textract can take 10–60s per document — is this async?)
- AP ageing query on large datasets — are indexes in place?

**Data Integrity Risks:**
- Duplicate webhook delivery from email provider (idempotency handling)
- ERP COA sync failure — stale account codes causing push failures
- Concurrent approval attempts on same JV

**Test Coverage Gaps:**
- Which critical paths in the existing ERP integration have no test coverage?
- Is there any test for RBAC enforcement at API level?

---

### STEP 7 — EFFORT SUMMARY TABLE

| Module / Gap | Category | Complexity | Est. Days |
|-------------|---------|-----------|---------|
| [gap name] | A/B/C/D | Low/Med/High | X |
| ... | | | |
| **V1 Total** | | | **X days** |
| **V2 Total** | | | **X days** |

Then provide your honest assessment:
- Is 5 weeks realistic for V1 with a 2-person team given what you found?
- What are the top 3 risks to that timeline?
- What could be safely descoped to V2 without losing core accounting value?
- Are there any existing patterns in the codebase that significantly speed up delivery?

---

### OUTPUT FORMAT

Respond in structured Markdown with clear numbered headings for each step.
Reference actual filenames and line numbers wherever possible.
Do not assume what exists — only report what you can verify from the actual files in D:\finos.
If a file is ambiguous in purpose, note the uncertainty.
Be specific and direct — this output will be used to plan a real engineering sprint.

---

## SECTION B — TARGETED FOLLOW-UP PROMPTS

Use these after the main gap analysis, one at a time:

---

### B1 — Generate Implementation Tickets

```
Based on the gaps and sprint plan you produced, generate a full set of
implementation tickets for V1.

Format as a markdown table:
Ticket ID | Sprint | Title | Description | Acceptance Criteria | Category | Effort (days)

Group by sprint. Number tickets as AL-001, AL-002, etc.
Each ticket should be specific enough that a developer can pick it up
and know exactly what to build without further clarification.
```

---

### B2 — GST & TDS Logic Design

```
Review all existing tax calculation logic in D:\finos.

Then design the GST and TDS line split logic for the Accounting Layer JV drafts:

1. How to determine intra-state vs inter-state using the first 2 digits of
   supplier GSTIN and buyer GSTIN (from entity master)
2. How to calculate and create CGST + SGST lines (intra-state)
3. How to calculate and create the IGST line (inter-state)
4. How to create the TDS deduction line by section (194C, 194J, 194I)
   using the rate from vendor master
5. How to handle exempt / zero-rated / non-GST invoices

For each, provide:
- The calculation logic
- The DB model fields needed
- The code implementation in the existing language/framework of this repo
- Unit test cases covering all scenarios

Reference ACCOUNTING_LAYER_DESIGN.md Section 10 for the target JV structures.
```

---

### B3 — Email Ingestion Implementation

```
Design and implement the dedicated org email ingestion pipeline (Method 4).

The org has one email address (e.g., invoices@finos.com).
Entity detection happens from document content — not the email address.

Design:
1. MX record setup and email provider choice (SendGrid Inbound Parse recommended)
2. Webhook endpoint to receive parsed email POST from provider
3. Idempotency handling (email provider may fire webhook multiple times for same email)
4. Sender whitelist verification logic
5. Attachment extraction from base64 payload
6. Auto-reply logic (no attachment, unsupported format, not whitelisted)
7. Feeding each attachment into the existing AI extraction pipeline
8. Audit log entries specific to email ingestion (sender, subject, message ID)

Provide:
- API route and controller code for the webhook endpoint
- Sender whitelist model and lookup logic
- Auto-reply template content
- Idempotency mechanism (e.g., email message ID deduplication)
- Integration test cases

Match existing code patterns in D:\finos.
Reference ACCOUNTING_LAYER_DESIGN.md Section 5.4.
```

---

### B4 — Approval State Machine

```
Design the maker-checker approval state machine for JV drafts.

States (from ACCOUNTING_LAYER_DESIGN.md Section 17):
Uploaded → Processing → Duplicate Detected / Entity Identified →
Pending Review → Rejected → Resubmitted →
Approved (locked) → Push in Progress → Pushed to ERP / Push Failed → Retry Queued / Escalated

Design and implement:
1. DB model / schema for JV status with all state fields and timestamps
2. State transition logic — what triggers each transition, what validates it
3. Enforcement that Preparer cannot approve their own JV (at DB and API level)
4. JV immutability after Approved state — no field editable, enforced at API level
5. Resubmission counter — max 3, then auto-escalate
6. Admin void capability — with mandatory reason, logged, JV not deleted
7. Concurrent approval protection (two Reviewers clicking Approve simultaneously)

Provide:
- DB migration / schema
- State machine implementation
- API middleware for immutability enforcement
- Unit tests for all state transitions and edge cases

Match existing patterns in D:\finos.
```

---

### B5 — ERP Push with Attachment

```
Audit the existing Zoho Books and QuickBooks Online integration code in D:\finos.

For the Accounting Layer, the ERP push sequence is:
1. Validate JV (account codes exist in synced COA, period is open)
2. Create JV in ERP → receive JV/Journal ID
3. Upload source document file to ERP
4. Link attachment to JV using the received ID
5. Store ERP reference number in platform
6. Handle partial failure: if attachment fails after JV is created, JV is NOT rolled back — attachment is retried separately

For each ERP (Zoho Books and QuickBooks Online):
- What API endpoints are used for each of the 4 steps?
- What payload structure does each endpoint require?
- Does the existing integration code support all 4 steps?
- What is missing and needs to be built?

Then implement:
- The complete push sequence with partial failure handling
- Retry queue for attachment failures (3 attempts, exponential backoff)
- ERP error mapping (invalid account, period closed, duplicate) to platform error states
- COA sync job (daily, pulls account list from ERP, stores in platform DB)
- Payment status sync job (daily, pulls payment records, updates JV status)

Reference ACCOUNTING_LAYER_DESIGN.md Sections 20 and 21.
```

---

### B6 — Entity Detection Logic

```
Design and implement the multi-signal entity detection logic.

Given a document processed by AI extraction, the system must identify
which legal entity in the org it belongs to.

Signal priority (highest to lowest):
1. Upload folder (if uploaded to entity-specific S3 folder — entity is certain)
2. GSTIN on document matched against entity master
3. PAN on document matched against entity master
4. Billed To name matched against entity name or configured aliases
5. Address on document matched against entity registered address
6. Vendor master (vendor pre-mapped to a specific entity)
7. User context (logged-in user assigned to only one entity)

Implement:
1. Entity master DB model with all fields (name, GSTIN, PAN, address, aliases, currency, ERP connection)
2. Signal evaluation pipeline — check signals in order, return first high-confidence match
3. Confidence scoring per signal type (GSTIN match = high, name match = medium, etc.)
4. Handling for low/no confidence — flag "Entity Not Identified", notify preparer
5. Intercompany detection — when vendor is itself a group entity
6. API endpoint for manual entity assignment by preparer / admin

Provide:
- DB models
- Detection service / function with full signal pipeline
- Unit tests for each signal type and confidence level
- Edge case tests (GSTIN not found, multiple partial matches, intercompany)

Reference ACCOUNTING_LAYER_DESIGN.md Section 6.
```

---

### B7 — Vendor Self-Submission Portal

```
Design and implement the vendor self-submission portal (Method 5).

This is the only externally accessible surface in the Accounting Layer.
Vendors submit their own invoices without needing to log in to the platform.

Requirements:
- Portal URL: portal.{org}.com/submit or configurable custom domain
- Vendor enters their registered email + optional PO/invoice reference
- Vendor uploads invoice file
- System verifies vendor email against vendor master (not authenticated — just verified)
- Unknown vendor → "Not registered. Contact accounts team." No further access
- Known vendor → submission accepted, reference number shown
- Vendor can check status of their submission by reference number:
  Received / Under Review / Approved / Payment Processed
  (No JV details, account codes, or internal data exposed)

Security requirements:
- Rate limiting: max 5 submissions per vendor email per day
- File type and size validation before any processing
- No authentication — just email + vendor master lookup
- All submissions logged with IP, timestamp, browser agent, vendor email

Implement:
1. Vendor portal frontend page (minimal, clean, mobile-friendly)
2. Vendor submission API endpoint (unauthenticated but rate-limited)
3. Vendor email verification against vendor master
4. Reference number generation and storage
5. Status check API endpoint (by reference number — returns simplified status only)
6. Rate limiting middleware
7. Audit log entries for all portal submissions

Reference ACCOUNTING_LAYER_DESIGN.md Section 5.5.
```

---

### B8 — AP Ageing & Payment Tracking

```
Design and implement:

1. Payment Status Tracking
   - After JV is pushed to ERP, platform syncs payment status from ERP daily
   - Status values: Pushed / Partially Paid / Paid / Overdue
   - Payment date synced and stored against JV record
   - Status shown on document detail, preparer dashboard, vendor portal

2. Due Date Urgency Flags
   - Due date extracted from invoice during AI extraction
   - Urgency levels: Overdue / Due in ≤3 days / Due in ≤7 days / Normal
   - Shown on reviewer queue, preparer dashboard, admin dashboard
   - Reviewer queue sortable by urgency

3. AP Ageing Report
   - Buckets: Current / 1–30 days overdue / 31–60 / 61–90 / 90+ days
   - Filterable by entity, vendor, date range
   - Drill-down from bucket to invoice list
   - Exportable as CSV and PDF
   - Visible to Admin, Senior Reviewer, CFO

For each:
- DB model changes needed
- Sync job implementation (daily ERP payment pull)
- API endpoints for dashboard and ageing data
- Frontend components for urgency flags and ageing report

Reference ACCOUNTING_LAYER_DESIGN.md Sections 21, 16, and 22.
```

---

## SECTION C — KEY DESIGN DECISIONS REFERENCE

Paste this as context in any follow-up conversation:

```
Accounting Layer v4.0 — Key Design Decisions

INGESTION:
1. Five methods: Direct upload / Connected folder / Managed S3 folder / Org email / Vendor portal
2. Email: ONE address per org (not per entity). Entity detected from document content
3. Vendor portal: External-facing, vendor email verified against vendor master only
4. All methods feed the same extraction pipeline from ingestion point onwards

ENTITY ROUTING:
5. Detection signals in priority: S3 folder > GSTIN > PAN > Billed-To > Address > Vendor master > User context
6. Entity not identified → flagged, manual assignment required before processing continues
7. Intercompany: two linked JV drafts, both need independent approval before either is pushed

APPROVAL:
8. Maker-checker always enforced — Preparer cannot approve their own entity's JV
9. JV NEVER pushed to ERP without explicit Reviewer approval — no exceptions except Admin override (logged)
10. Approved JVs are immutable — no field editable after approval
11. Max 3 rejections before escalation to Admin
12. Multi-level approval: threshold-based (Reviewer → Senior Reviewer → CFO)

TAX:
13. GST split determined by GSTIN state codes: intra-state = CGST+SGST, inter-state = IGST
14. TDS deduction creates a separate TDS Payable line per section (194C, 194J, 194I)
15. All tax account codes configurable per entity

ERP PUSH:
16. Sequence: Validate → Create JV in ERP → Upload attachment → Link attachment to JV
17. Partial failure: JV created but attachment fails → JV stays, attachment retried separately
18. ERP reverse sync (V3): detect JVs in ERP with no platform source document

STORAGE & AUDIT:
19. WORM storage: S3 PutObject-only — no delete, no overwrite by users
20. Audit log: immutable, every action, every user, every status change — permanent retention
21. Documents retained 8 years minimum (Indian IT Act)

SECURITY:
22. Email sender whitelist: per-org, individual + domain level
23. Vendor portal: rate-limited, vendor email verified, no auth needed, no internal data exposed
24. RBAC enforced at API level — not just UI level
```

---

*Save as: D:\finos\ACCOUNTING_LAYER_GAP_PROMPT.md*
*Use alongside: D:\finos\ACCOUNTING_LAYER_DESIGN.md*
