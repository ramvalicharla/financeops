# Accounting Layer — Feature Design Document

**Version:** 4.0
**Status:** Draft
**Last Updated:** 2026-03-26
**Changes in v4.0:** Added dedicated org email ingestion, WhatsApp ingestion (V3), vendor self-submission portal, payment status tracking, AP ageing report, PO matching, approval nudges & SLA tracking, rejection analytics, internal notes/comments on JV, document splitting, due date urgency flags, API/webhook for external systems, ERP reverse sync (V3)

---

## 1. Overview

The **Accounting Layer** is an internal platform feature for organisations with multiple legal entities. It provides a unified document ingestion pipeline — via direct upload, connected cloud folders, a platform-managed write-only folder, a dedicated organisational email address, or a vendor self-submission portal — that automatically extracts accounting data using AI/OCR, identifies the correct legal entity, creates Journal Voucher (JV) drafts with correct GST and TDS line splits, routes them through a maker-checker approval workflow, and pushes approved JVs along with source document attachments to the correct ERP instance.

No JV is ever pushed to any ERP without explicit human approval.
No document can be deleted or modified after ingestion.
Every action on every document is immutably logged.

---

## 2. Goals

- Eliminate manual data entry across all group entities
- Provide multiple ingestion methods to fit every workflow — upload, folder, email, WhatsApp, vendor portal
- Auto-identify which legal entity a document belongs to and route accordingly
- Enforce maker-checker segregation of duties at every stage
- Handle Indian tax compliance — GST (CGST/SGST/IGST) and TDS line splits
- Support multi-currency with exchange rate handling
- Prevent duplicate entries with multi-signal detection
- Track payment status and surface AP ageing across entities
- Provide a full, immutable audit trail of every action

---

## 3. Scope — Internal Only

- Accessible only to authenticated users within the organisation
- Vendor portal is the only externally accessible surface — scoped and controlled
- Each internal user is mapped to one or more entities with a defined role
- All documents stored with write-once, read-many (WORM) policy — cannot be deleted by users
- ERP push happens only post explicit Reviewer approval

---

## 4. User Roles & Access Control

### 4.1 Role Definitions

| Role | What They Can Do |
|------|-----------------|
| **Preparer** | Upload documents, view JV drafts, add internal notes, submit for review, resubmit after rejection |
| **Reviewer** | View pending JVs + source documents, approve or reject with comments, add internal notes. Cannot edit JV fields |
| **Senior Reviewer / CFO** | Approve high-value JVs above configured threshold, handle escalations |
| **Admin** | Configure entities, manage users and roles, view all statuses across entities, void JVs, manage ERP connections, force-push in exceptions |
| **Auditor** | Read-only access to all documents, JVs, and audit logs across assigned entities |
| **Payroll Approver** | Dedicated role for payroll entries — separate approval chain, restricted visibility |

### 4.2 Role Flexibility

- A user can be Preparer for Entity A and Reviewer for Entity B simultaneously
- A user cannot be both Preparer and Reviewer for the same entity — enforced by system
- Reviewer sees only entities they are assigned to
- Admin and Auditor have cross-entity visibility scoped to their assigned entities

### 4.3 Approval Thresholds (Configurable per Entity)

| JV Value | Approval Required From |
|----------|----------------------|
| Below ₹1,00,000 | Reviewer |
| ₹1,00,000 – ₹10,00,000 | Reviewer + Senior Reviewer |
| Above ₹10,00,000 | Reviewer + Senior Reviewer + CFO |
| Intercompany entries | Both entity Reviewers |

### 4.4 Delegated Approval

- Each Reviewer configures a delegate for when unavailable
- Delegate has identical approval rights for the configured duration
- All delegate actions flagged in audit trail: "Approved by [Delegate] on behalf of [Reviewer]"

---

## 5. Document Ingestion — Five Methods

### 5.1 Method 1 — Direct Upload (Baseline, Always Available)

- Drag-and-drop zone or file picker on the Accounting Layer tab
- Supported formats: PDF, JPG, PNG, TIFF, XLSX, CSV
- Max file size: 20MB per file (configurable per plan)
- Batch upload: up to 50 files per session
- Upload progress shown per file
- Processing triggered immediately on successful upload

### 5.2 Method 2 — Connected Cloud Folders

Users connect their own cloud storage folders. System watches for new files automatically.

**V1:** Google Drive, Microsoft OneDrive, Box
**V2:** Dropbox, SharePoint, FTP/SFTP

- OAuth connection per provider, configured once in Settings
- User selects specific folder to watch, mapped to entity
- Sync schedule: Real-time / Hourly / Daily
- New file → duplicate check → AI extraction → JV draft → Pending Review
- No auto-push ever — user must approve
- OAuth token expiry → in-app alert + email to user and Admin

### 5.3 Method 3 — Platform-Managed Folder (Recommended for Compliance)

Platform provisions a dedicated write-only cloud folder per entity per organisation.

**Permissions:**

| Action | Permission |
|--------|-----------|
| Upload / Add files | ✅ Allowed |
| View file list | ✅ Allowed |
| Download own uploads | ✅ Allowed |
| Edit / Rename / Delete / Overwrite | ❌ Not allowed |

**Implementation:**
- AWS S3 with PutObject-only bucket policy, WORM policy per entity prefix
- Path: `s3://org-{org_id}/entity-{entity_id}/{year}/{month}/`
- One folder per entity — eliminates entity routing ambiguity
- Folder link shared with users via Settings → Accounting Layer → Managed Folder

### 5.4 Method 4 — Dedicated Organisational Email (New)

Each organisation gets **one dedicated email address** regardless of how many entities are in the group. Entity detection happens purely from document content — not the email address.

**Email format:**
```
invoices@{orgname}.finos.com
or a custom domain the org configures:
invoices@finos.com
```

**How it works:**

```
Vendor / Staff forwards invoice to invoices@finos.com
              │
              ▼
Email received by platform (via SendGrid Inbound Parse / AWS SES)
              │
              ▼
Sender verified against org whitelist
              │
              ├── Not whitelisted → Auto-reply: "Your address is not authorised.
              │                     Contact your Finos accounts team."
              │
              └── Whitelisted → Extract all attachments
                                      │
                                      ▼
                              Feed each attachment into
                              existing AI extraction pipeline
                              (same as direct upload — entity
                              detected from GSTIN/PAN/Billed-To)
                                      │
                                      ▼
                              JV Draft → Pending Review
                              (same flow from here)
```

**Key design decisions:**
- One email per org — not one per entity. Entity routing is handled by document content (GSTIN, PAN, Billed-To) as per Section 6
- If entity cannot be identified from document → flagged "Entity Not Identified" → Admin/Preparer assigns manually
- Multiple attachments in one email → each processed as a separate document independently
- Email body is ignored — only attachments are processed. Email body is never stored
- Original email metadata (sender, subject, message ID, received timestamp) logged in audit trail but raw email not stored

**What triggers auto-replies:**

| Scenario | System Action |
|----------|-------------|
| No attachment found | Auto-reply: "Email received but no attachment found. Please resend with invoice attached." |
| Unsupported file type | Auto-reply: "Attachment format not supported. Please send PDF, JPG, or PNG." |
| Sender not whitelisted | Auto-reply explaining not authorised (or silent discard — configurable) |
| Successful receipt | No auto-reply (to avoid confirming receipt to potential spammers) |
| Duplicate document | Logged, not processed, no auto-reply |

**Sender whitelist (configured per org by Admin):**
- Individual email addresses: `vendor@abcsuppliers.com`
- Domain-level: `*@trustedpartner.com`
- Internal staff: `*@finos.com` (all internal staff can forward)
- Managed in Settings → Accounting Layer → Email Ingestion → Sender Whitelist

**Email ingestion audit fields (additional to standard):**

| Field | Example |
|-------|---------|
| Ingestion Source | Email |
| Sender Email | vendor@abcsuppliers.com |
| Email Subject | Invoice INV-1023 March services |
| Received At | 2026-03-26 10:22 UTC |
| Email Message ID | unique ID for full traceability |
| Attachments Found | 2 (INV-1023.pdf, delivery-note.pdf) |

**Technical implementation:**
- SendGrid Inbound Parse (recommended) or AWS SES + S3 + Lambda
- MX record pointed to provider's servers
- Provider fires webhook POST to platform API with parsed email + base64 attachments
- Platform processes webhook → feeds attachments into existing extraction pipeline
- Zero custom mail server infrastructure needed

### 5.5 Method 5 — Vendor Self-Submission Portal (New)

Vendors submit their own invoices directly through a controlled portal — no email forwarding needed.

**How it works:**
- Each org gets a unique vendor portal URL: `portal.finos.com/submit` or `finos.com/vendor`
- Vendor visits the URL, enters their registered email and invoice details, uploads the document
- Platform verifies vendor email against approved vendor master
- Document fed into standard extraction pipeline
- Vendor sees a submission confirmation with a reference number
- Vendor can check submission status (Received / Under Review / Approved / Paid) — no JV details exposed

**Vendor experience:**
```
Vendor visits portal URL
        │
        ▼
Enters: Email address + optional reference (PO number / invoice number)
        │
        ▼
Uploads invoice file
        │
        ▼
System verifies vendor email against vendor master
        │
        ├── Not found → "Your details are not registered. Contact Finos accounts team."
        │
        └── Found → Submission accepted
                    Reference number shown: "Your invoice has been received.
                    Reference: FIN-2026-00423.
                    You will be notified when payment is processed."
```

**What the vendor can see (read-only):**
- Submission received confirmation
- Reference number
- Status: Received / Under Review / Approved / Payment Processed
- Payment date (once paid)
- They cannot see JV details, account codes, or any internal platform data

**Security:**
- Vendor email verified against vendor master — unknown vendors cannot submit
- Rate limiting on submissions per email per day
- File type and size validation before any processing
- No authentication needed for vendor — just email verification (keeps it frictionless)
- All submissions logged with vendor IP, timestamp, browser agent

---

## 6. Multi-Entity Routing

### 6.1 Entity Master Configuration (per entity, configured by Admin)

| Field | Example |
|-------|---------|
| Entity Name | Finos India Pvt Ltd |
| Short Code | FINO-IN |
| GSTIN | 36AABCF1234A1Z5 |
| PAN | AABCF1234A |
| Registered Address | Hyderabad, Telangana, India |
| Functional Currency | INR |
| ERP Connection | Zoho Books — India Instance |
| Default AP Account | 2100 |
| Default Expense Account | 6000 |
| Approval Thresholds | As per Section 4.3 |
| Managed Folder Path | s3://org-x/entity-india/ |
| Assigned Preparers | user1, user2 |
| Assigned Reviewers | user3, user4 |

### 6.2 Entity Detection Signal Priority

| Priority | Signal | How |
|----------|--------|-----|
| 1 | Upload folder | Uploaded to entity-specific managed folder → certain |
| 2 | GSTIN on document | Extracted GSTIN matched against entity master |
| 3 | PAN on document | Extracted PAN matched against entity master |
| 4 | Billed To name | Entity name or alias matched |
| 5 | Registered address | Address on document matched to entity address |
| 6 | Vendor master | Vendor pre-mapped to always invoice a specific entity |
| 7 | User context | Logged-in user assigned to only one entity |

For email and vendor portal ingestion, signals 2–6 are used (no folder signal available).

### 6.3 Confidence Handling

- High confidence (GSTIN/PAN match) → Auto-assign, preparer can override
- Medium confidence (name/address) → Suggest entity, preparer must confirm
- No match → "Entity Not Identified" → preparer/admin must manually assign

### 6.4 Intercompany Documents

- System flags document as Intercompany when vendor is a group entity
- Two JV drafts created — one per entity, linked as a pair
- Both go through independent approval workflows
- Both entity Reviewers must approve before either is pushed
- If one is rejected, paired JV is put on hold automatically

---

## 7. Document Types Supported

| Document Type | JV Structure | Notes |
|---------------|-------------|-------|
| Vendor Invoice | DR Expense / CR AP | Most common |
| Credit Note | DR AP / CR Expense | Reversal of prior invoice |
| Debit Note | DR Expense / CR AP | Supplement to prior invoice |
| Expense Claim | DR Expense / CR Employee Payable | Employee reimbursements |
| Bank Payment Advice | DR AP / CR Bank | Payment against invoice |
| Intercompany Invoice | Two-sided JV | Both entities affected |
| Recurring Entry | Template-based JV | Rent, retainer — scheduled |
| Payroll Entry | DR Payroll / CR Payroll Payable | Payroll Approver role only |
| Bank Statement Line | DR/CR Bank / various | Reconciliation entries |

---

## 8. Document Splitting

Sometimes a single uploaded PDF or email attachment contains multiple invoices (e.g., a supplier sends a monthly statement with multiple line invoices, or scans several invoices into one PDF).

**How it works:**
- During AI extraction, system checks for multiple invoice numbers, dates, or vendor headers within a single document
- If multiple invoices detected → prompts preparer:
  - "We detected 3 invoices in this document. Would you like to split into separate JV drafts?"
- Preparer options:
  - **Split** — system creates one JV draft per detected invoice, attaches relevant pages to each
  - **Keep as one** — process as a single document (preparer handles manually)
- Each split JV goes through the full workflow independently
- Original unsplit document is retained in storage — splits reference back to it in audit trail

---

## 9. AI Document Processing Pipeline

### 9.1 Extraction Engine

| Provider | Notes |
|----------|-------|
| AWS Textract (Analyze Expense API) | Recommended — strong on Indian invoices |
| Google Document AI | High accuracy on varied layouts |
| Azure Form Recognizer | Best if already on Azure stack |

### 9.2 Fields Extracted

- Vendor name, address, GSTIN, PAN
- Invoice number, date, due date
- Line items: description, HSN/SAC, quantity, unit price, amount
- Subtotal, discount, GST breakdown (CGST/SGST/IGST/UTGST amounts and rates)
- TDS section and amount
- Total payable, currency, payment terms
- PO number (if present)
- Buyer GSTIN, buyer name

### 9.3 Confidence Scoring

| Score | Indicator | Action |
|-------|-----------|--------|
| Above 85% | 🟢 Green | Auto-populated, reliable |
| 50–85% | 🟡 Amber | Populated, preparer should verify |
| Below 50% | 🔴 Red | Left blank, preparer must fill |

Documents with average confidence below 60% → flagged: "Low Quality Scan — Manual Review Recommended"

### 9.4 Edge Cases

| Scenario | Handling |
|----------|---------|
| Handwritten document | OCR attempted, likely low confidence, flagged |
| Password-protected PDF | Alert: "Document is password protected. Please upload unlocked version." |
| Low DPI scan | Flagged as low quality |
| Multi-page invoice | All pages processed as one document |
| Non-English document | Language detected, extraction attempted, flagged for review |
| Multiple invoices in one PDF | Document splitting triggered (Section 8) |

---

## 10. GST & TDS Handling (India Compliance)

### 10.1 GST Line Split

System determines intra vs inter-state by comparing first 2 digits of supplier and buyer GSTIN:

**Intra-state (CGST + SGST):**
```
DR  Office Expense      (6000)   ₹1,00,000
DR  Input CGST 9%       (1310)      ₹9,000
DR  Input SGST 9%       (1311)      ₹9,000
    CR  Accounts Payable (2100)              ₹1,18,000
```

**Inter-state (IGST):**
```
DR  Office Expense      (6000)   ₹1,00,000
DR  Input IGST 18%      (1312)     ₹18,000
    CR  Accounts Payable (2100)              ₹1,18,000
```

**Exempt / Zero-rated / Non-GST:**
```
DR  Office Expense      (6000)   ₹1,00,000
    CR  Accounts Payable (2100)              ₹1,00,000
```

### 10.2 TDS Deduction

```
DR  Professional Fee    (6100)   ₹1,00,000
    CR  Accounts Payable (2100)                ₹90,000
    CR  TDS Payable 194J (2211)                ₹10,000
```

TDS section and rate configured per vendor in vendor master.

### 10.3 GST & TDS Account Mapping (per entity, configurable)

| Type | Default Code |
|------|-------------|
| Input CGST | 1310 |
| Input SGST | 1311 |
| Input IGST | 1312 |
| Input UTGST | 1313 |
| TDS Payable 194C | 2210 |
| TDS Payable 194J | 2211 |
| TDS Payable 194I | 2212 |

### 10.4 GST Validation

- GSTIN format validated (15-character alphanumeric, checksum)
- State code cross-checked for intra vs inter-state determination
- V2: GSTIN verified against live GSTN API
- V2: HSN/SAC code validated against GST rate schedule

---

## 11. Multi-Currency Handling

- System detects currency from document
- If different from entity functional currency → prompts for exchange rate
- V1: Manual rate entry by preparer (logged with user + timestamp)
- V2: Auto-fetch from RBI reference rates / Open Exchange Rates API for invoice date
- Exchange rate locked after JV approval — cannot be changed
- Both foreign currency amount and functional currency equivalent stored and shown
- Unusually different rate from market → warning flag (does not block)

---

## 12. Duplicate Detection

### 12.1 Detection Methods

| Method | Catches |
|--------|---------|
| File hash (SHA-256) | Exact same file uploaded twice |
| Invoice number + Vendor name | Same invoice, different scan |
| Fuzzy: Vendor + Amount + Date ±1 day | Near-duplicates, re-scans |
| Amount + Date + Entity (no invoice number) | Docs without visible invoice numbers |

### 12.2 On Detection

- Preparer shown side-by-side: new doc vs existing
- Options: Skip / Override with mandatory comment / Mark as Related
- All overrides logged with comment in audit trail

---

## 13. PO Matching

When an invoice is received, system attempts to match it against open Purchase Orders:

```
Invoice received → Extract PO number (if present)
        │
        ├── PO number found → Look up PO in platform or ERP
        │       │
        │       ├── PO found, amounts match → Auto-link, show "Matched to PO-456" on JV draft
        │       ├── PO found, amounts differ → Flag: "Amount mismatch vs PO-456 — verify before approval"
        │       └── PO not found → Flag: "PO number on invoice not found in system"
        │
        └── No PO number → Flag: "No PO reference on invoice — verify if PO required"
```

- PO data synced from ERP (daily) or maintained in platform vendor master
- Reviewer sees PO match status on review screen
- 3-way match (PO → GRN → Invoice) in V3
- V1: PO number match only (no GRN)

---

## 14. Recurring Entries

- Admin or Preparer marks a processed JV as a Recurring Template
- Configure: frequency (monthly/quarterly/custom), start date, end date, day of month to create
- On configured date → system auto-creates JV draft from template
- JV still goes through full approval workflow — no auto-push ever
- Preparer can attach monthly source document (e.g., rent receipt) to each recurrence
- If no document attached by review time → flagged: "Recurring JV — No Source Document Attached"
- Reviewer can still approve with this flag — noted in audit log

---

## 15. Internal Notes & Comments

- Any user (Preparer, Reviewer, Admin) can add internal notes to any JV at any stage
- Notes are free text, timestamped, attributed to user
- Notes are visible to all users with access to that entity
- Notes are stored in audit trail but never pushed to ERP
- Notes survive rejection and resubmission — full comment history visible to Reviewer
- Reviewer rejection comment is a special type of note — mandatory, triggers notification to preparer
- Examples of use:
  - Preparer: "This is for Q1 marketing campaign — approved by Ravi verbally"
  - Reviewer: "Please verify GST rate — supplier invoice shows 12% but should be 18%"
  - Admin: "Backdated entry approved by CFO on 26-Mar-2026"

---

## 16. Due Date Urgency Flags

System surfaces payment urgency directly on the JV queue:

| Status | Condition | Display |
|--------|-----------|---------|
| 🔴 Overdue | Due date has passed | "Overdue by X days" |
| 🟠 Due Soon | Due within 3 days | "Due in X days" |
| 🟡 Upcoming | Due within 7 days | "Due on DD-Mon" |
| ⚡ Early Payment Discount | Discount available if paid by date | "2% discount if paid by DD-Mon" |
| 🟢 Normal | Due more than 7 days away | Standard display |

- Due date extracted from invoice during AI extraction
- Urgency flags shown on Reviewer queue, Preparer dashboard, and Admin dashboard
- Reviewer queue can be sorted by urgency / due date
- Overdue invoices not yet approved → escalation alert to Admin

---

## 17. JV Status Lifecycle

```
Uploaded
  └→ Processing
       ├→ Duplicate Detected              ← preparer action needed
       └→ Entity Identified
            └→ Pending Review             ← reviewer action needed
                 ├→ Rejected              ← preparer must fix and resubmit
                 │    └→ Resubmitted      ← back to Pending Review
                 │         (max 3 times → Escalated to Admin)
                 └→ Approved              ← JV locked, no edits
                      └→ Push in Progress
                           ├→ Pushed to ERP ✅
                           └→ Push Failed ⚠️
                                └→ Retry Queued
                                     ├→ Pushed to ERP ✅
                                     └→ Escalated to Admin
```

**Status rules:**
- Approved JVs are immutable — no field editable after approval
- Only Admin can void an approved JV — mandatory reason, logged
- Voided JVs retained permanently with Voided status
- 3 rejections → Escalated status → Admin notified
- Pushed JVs show ERP reference number / Journal ID

---

## 18. Reviewer Experience

### 18.1 Review Screen

```
┌──────────────────────────────┬──────────────────────────────────────┐
│  SOURCE DOCUMENT PREVIEW     │  JV DRAFT                            │
│  (PDF viewer — scrollable)   │                                      │
│                              │  Entity:    Finos India Pvt Ltd      │
│  Invoice: ABC Suppliers      │  Date:      26-Mar-2026              │
│  INV-2024-1023               │  Ref No:    INV-2024-1023            │
│  ₹1,18,000 incl. GST 18%     │  Vendor:    ABC Suppliers            │
│                              │  Currency:  INR                      │
│  [Page 1 of 2]  [◄]  [►]    │  PO Match:  ✅ Matched to PO-456     │
│                              │  Due Date:  🟠 Due in 2 days         │
│                              │                                      │
│                              │  DR  Office Expense   1,00,000       │
│                              │  DR  Input CGST 9%        9,000      │
│                              │  DR  Input SGST 9%        9,000      │
│                              │  CR  Accounts Payable 1,18,000       │
│                              │                                      │
│                              │  Ingested via: Email                 │
│                              │  Prepared by:  john@co.com           │
│                              │  Submitted:    26-Mar-2026 10:31     │
│                              │                                      │
│                              │  💬 Notes (2)                        │
│                              │  john: "Approved by Ravi verbally"   │
│                              │  [ Add Note ]                        │
└──────────────────────────────┴──────────────────────────────────────┘
            [ REJECT WITH COMMENT ]            [ APPROVE ]
```

### 18.2 Reviewer Rules

- Cannot edit JV fields — view and approve/reject only
- Rejection requires mandatory comment
- Once approved → JV locked, ERP push triggered
- High-value JVs show additional approval tier buttons

### 18.3 Bulk Approval

- Table view of all pending JVs, sortable by due date / amount / entity / age
- Filter by entity, date range, amount, vendor, ingestion source, urgency
- Select multiple → Approve all selected
- Bulk reject requires individual comments per JV

---

## 19. Rejection & Resubmission Flow

```
Reviewer rejects with comment
        │
        ▼
Preparer notified (in-app + email) with rejection comment
        │
        ▼
Preparer opens rejected JV — sees comment history + all prior notes
        │
        ├── Fix extracted fields → Resubmit
        ├── Upload replacement document → Resubmit
        └── Abandon → Close with reason (logged)
                │
                ▼
        Back to "Pending Review"
        Reviewer sees: resubmission count + full note history
```

Max 3 resubmissions → after 3rd rejection → Escalated to Admin.

---

## 20. ERP Push & Error Handling

### 20.1 Push Sequence

```
1. Validate JV — required fields, account codes exist in synced COA
2. Check accounting period is open in ERP
3. Create JV in ERP → receive JV / Journal ID
4. Upload source document to ERP attachment endpoint
5. Link attachment to JV using JV ID
6. Store ERP reference number in platform
7. Update status: Pushed to ERP ✅
```

### 20.2 ERP Error Handling

| Error | Action |
|-------|--------|
| Invalid account code | Push fails → "Push Failed — Invalid Account Code". Preparer + Admin alerted |
| Period closed | Push fails → "Push Failed — Period Closed". Admin decides on backdated entry |
| Duplicate in ERP | Push fails → "Push Failed — Duplicate in ERP". Admin reviews |
| Network / timeout | Retry: 3 attempts, exponential backoff (5 min, 15 min, 60 min) |
| Attachment fails | JV pushed, attachment retried separately. JV not rolled back |
| All retries fail | "Escalated to Admin". Alert sent |

### 20.3 COA Sync

- Platform syncs Chart of Accounts from ERP daily
- Account codes validated at draft creation — not at push stage
- Invalid codes flagged early so preparer can correct before submission

### 20.4 ERP Reverse Sync (V3)

For audit completeness — detect JVs posted directly in ERP bypassing the platform:

- Platform periodically pulls JV list from ERP
- Compares against platform-pushed JVs
- Any ERP JV with no matching platform record flagged: "JV found in ERP with no source document on platform"
- Admin notified to investigate and attach source document retroactively
- Closes the audit loop completely

---

## 21. Payment Status Tracking

After JV is pushed to ERP, platform tracks payment status by syncing from ERP periodically:

| Status | Meaning |
|--------|---------|
| Pushed | JV created in ERP, payment not yet made |
| Partially Paid | Partial payment recorded in ERP |
| Paid | Full payment processed |
| Overdue | Due date passed, not paid |

- Status shown on document detail screen and preparer dashboard
- Vendor portal shows simplified status to vendor: Received / Under Review / Approved / Payment Processed
- Payment date synced from ERP and shown alongside invoice
- ERP payment sync: daily (V1), real-time webhook from ERP (V2 where ERP supports it)

---

## 22. AP Ageing Report

Surfaces across all entities for Admin and Senior Reviewer:

| Bucket | Invoices |
|--------|---------|
| Current (not yet due) | Count + Total Amount |
| 1–30 days overdue | Count + Total Amount |
| 31–60 days overdue | Count + Total Amount |
| 61–90 days overdue | Count + Total Amount |
| 90+ days overdue | Count + Total Amount |

- Filterable by entity, vendor, date range
- Exportable as CSV or PDF
- Drill-down from bucket → list of invoices in that bucket
- Colour-coded urgency (green → red as ageing increases)
- Visible to Admin, Senior Reviewer, CFO role

---

## 23. Approval Reminders & SLA Tracking

### 23.1 Nudges

| Trigger | Action |
|---------|--------|
| JV pending review > 24 hours | Gentle reminder to Reviewer (in-app + email) |
| JV pending review > 48 hours | Escalation alert to Reviewer + Admin |
| Overdue invoice pending review | Priority alert — "Overdue invoice waiting for your approval" |
| Daily digest (configurable) | Summary email to Reviewer: "You have X JVs pending review" |

### 23.2 SLA Dashboard (Admin View)

| Metric | Shows |
|--------|-------|
| Average time: Upload → Approved | Per entity, per reviewer |
| Average time: Approved → Pushed | System performance metric |
| SLA breaches this month | JVs that exceeded 48-hour review window |
| Reviewer leaderboard | Average turnaround per reviewer (visible to Admin only) |

---

## 24. Rejection Analytics

Surfaces process improvement insights for Admin:

| Metric | Value |
|--------|-------|
| Rejection rate by preparer | Who needs training? |
| Rejection rate by vendor | Which vendor's invoices have data quality issues? |
| Top rejection reasons | What are reviewers most commonly flagging? |
| Resubmission success rate | How often does resubmission lead to approval? |
| Escalation rate | How many JVs reach the 3-rejection escalation? |

- Available in Admin dashboard under "Process Insights"
- Date range and entity filters
- Exportable as CSV

---

## 25. API & Webhook for External Systems

For orgs with other internal tools (procurement systems, ERP satellites, custom apps):

### 25.1 Inbound API

- Platform exposes a secured API endpoint where external systems can push documents programmatically
- E.g., procurement system auto-sends PO-matched invoices to Accounting Layer
- API key authentication, per-org rate limits
- Same pipeline from that point — extraction, JV draft, approval, push

### 25.2 Outbound Webhook

- Platform fires a webhook event when key status changes occur
- Configurable events: JV Approved, JV Pushed to ERP, Payment Received, Push Failed
- Webhook payload includes: document ID, JV reference, entity, ERP reference number, timestamp
- External systems can consume these to update their own records
- Retry logic for failed webhook deliveries (3 attempts, exponential backoff)
- Webhook management in Settings → Accounting Layer → Integrations

---

## 26. WhatsApp Ingestion (V3)

For Indian orgs where vendors and staff share invoices via WhatsApp:

- Org gets a dedicated WhatsApp Business number
- Vendor or staff sends invoice image / PDF to that number
- Platform receives via WhatsApp Business API (Meta)
- Image/PDF extracted and fed into standard AI extraction pipeline
- Same entity detection, JV draft, approval, and push flow
- WhatsApp message metadata logged in audit trail (sender number, timestamp)
- Sender number verified against approved whitelist (same concept as email whitelist)
- V3 because WhatsApp Business API requires Meta approval and has onboarding lead time

---

## 27. Notifications & Alerts — Complete Reference

| Trigger | Notified | Channel |
|---------|----------|---------|
| Document uploaded | Preparer | In-app |
| JV draft created | Preparer | In-app |
| Entity not identified | Preparer + Admin | In-app + Email |
| JV submitted for review | Reviewer | In-app + Email |
| JV pending > 24 hours | Reviewer | In-app + Email |
| JV pending > 48 hours | Reviewer + Admin | In-app + Email |
| Overdue invoice pending review | Reviewer + Admin | In-app + Email (priority) |
| Daily digest — pending reviews | Reviewer | Email |
| JV approved | Preparer | In-app + Email |
| JV rejected | Preparer | In-app + Email + rejection comment |
| JV pushed to ERP | Preparer + Reviewer | In-app |
| Payment received (from ERP sync) | Preparer | In-app |
| Push failed | Preparer + Admin | In-app + Email |
| All retries failed | Admin | In-app + Email |
| Duplicate detected | Preparer | In-app |
| 3rd rejection — escalation | Admin | In-app + Email |
| High-value JV pending CFO | CFO / Senior Reviewer | In-app + Email |
| Intercompany paired JV approved | Both entity Reviewers | In-app + Email |
| OAuth token expired | User + Admin | In-app + Email |
| Email sender not whitelisted | Admin | In-app (daily digest of rejected senders) |
| Vendor portal submission received | Preparer | In-app |
| ERP reverse sync — unmatched JV found | Admin | In-app + Email |
| Recurring JV created (no document) | Preparer | In-app |
| Webhook delivery failed | Admin | In-app |

---

## 28. Reporting & Dashboard — Complete Reference

### 28.1 Admin Dashboard

- Documents processed this month (count + trend)
- Pending reviews by entity (count, oldest first)
- Pending push (approved, not yet pushed)
- Failed pushes needing attention
- Rejected JVs (count + resubmission rate)
- AP ageing across all entities
- SLA metrics (average review time, breaches)
- Rejection analytics (by preparer, by vendor, by reason)
- Top vendors by document volume
- Ingestion source breakdown (upload / folder / email / vendor portal / API)
- ERP reverse sync alerts (unmatched JVs)

### 28.2 Preparer Dashboard

- My uploads this month
- Status breakdown per document
- Outstanding rejections needing resubmission (highlighted)
- Due date urgency across my pending documents

### 28.3 Reviewer Dashboard

- Pending my review (count, sorted by urgency / due date)
- Approved by me this month
- My average turnaround time
- SLA breach alerts (JVs I have not reviewed within 48 hours)

### 28.4 CFO / Senior Reviewer Dashboard

- High-value JVs pending my approval
- AP ageing summary across all entities
- Total AP outstanding by entity
- Payment status overview

### 28.5 Exports

- All views exportable as CSV
- Audit log exportable as CSV or PDF
- AP ageing exportable as PDF
- Date range and entity filters on all exports

---

## 29. Audit Log

Every action on every document and JV is immutably logged:

| Timestamp | User | Role | Action | Document | Entity | Details |
|-----------|------|------|--------|----------|--------|---------|
| 2026-03-26 10:22 | vendor@abc.com | External | Email Received | INV-1023.pdf | — | Sender whitelisted, 1 attachment |
| 2026-03-26 10:22 | System | — | Entity Identified | INV-1023.pdf | Finos India | Matched via GSTIN |
| 2026-03-26 10:23 | System | — | JV Draft Created | INV-1023.pdf | Finos India | Confidence 91% |
| 2026-03-26 10:31 | john@co.com | Preparer | Note Added | INV-1023.pdf | Finos India | "Approved verbally by Ravi" |
| 2026-03-26 10:31 | john@co.com | Preparer | Submitted for Review | INV-1023.pdf | Finos India | — |
| 2026-03-26 11:45 | priya@co.com | Reviewer | Approved | INV-1023.pdf | Finos India | — |
| 2026-03-26 11:45 | System | — | ERP Push Initiated | INV-1023.pdf | Finos India | Zoho Books |
| 2026-03-26 11:46 | System | — | Pushed to ERP | INV-1023.pdf | Finos India | ERP Ref: ZB-20240326-001 |
| 2026-03-26 11:46 | System | — | Attachment Linked | INV-1023.pdf | Finos India | Attached to ZB-20240326-001 |
| 2026-04-15 09:00 | System | — | Payment Synced | INV-1023.pdf | Finos India | Paid ₹1,18,000 on 15-Apr-2026 |

- Read-only — no one can edit or delete audit entries including Admin
- Retained permanently (documents retained 8 years minimum)
- Exportable as CSV or PDF
- Auditors given filtered read-only access scoped to assigned entities

---

## 30. Compliance & Retention

| Requirement | Implementation |
|-------------|---------------|
| Document retention | 8 years minimum (Indian IT Act) |
| Immutability | WORM on S3, approved JVs locked in DB |
| Encryption at rest | AES-256 |
| Encryption in transit | TLS 1.2+ |
| Access control | RBAC, entity-scoped, enforced at API level |
| Audit trail | Immutable, timestamped, user-attributed, permanent |
| GST compliance | GSTIN validation, correct tax line splits |
| User departure | Documents remain, user access revoked immediately |
| Backdated entries | Admin-only, mandatory reason, ERP period lock respected |
| GDPR / Indian IT Act | User profile deletable on request; accounting docs retained per statute |

---

## 31. Settings & Configuration

**Entity Management:** Add/edit entities, assign users and roles, approval thresholds, account mappings, GST/TDS account codes

**Vendor Master:** Add vendors with entity mapping, TDS section/rate, default expense account, GSTIN, portal access flag

**Email Ingestion:** View org email address, manage sender whitelist (individual + domain level), configure auto-reply behaviour

**Vendor Portal:** Enable/disable portal, view portal URL, manage approved vendor emails, configure status visibility settings

**ERP Connections:** Connect/disconnect per entity, test connection, view last sync, trigger manual COA sync

**Document Sources:** Connected folder OAuth management, managed folder links per entity, file size/format limits

**Approval & Workflow:** Thresholds per entity, delegate approver config, escalation period (default 48h), resubmission limit (default 3)

**Notifications:** Per-user preferences, email digest frequency, alert recipients for system failures

**Webhooks & API:** Manage outbound webhook URLs, select trigger events, view delivery logs, manage API keys for inbound API

**Duplicate Detection:** Sensitivity (Strict/Normal/Off), auto-skip exact hash duplicates toggle

**Recurring Entries:** View and manage all recurring templates, pause/resume/cancel schedules

---

## 32. Phased Rollout

### Phase 1 — V1 (~5 weeks, 2-person team)
- [ ] Accounting Layer tab with direct upload UI
- [ ] Platform-managed folder per entity (S3 WORM)
- [ ] Dedicated org email ingestion (SendGrid/AWS SES + webhook)
- [ ] Sender whitelist and auto-reply for email
- [ ] AI extraction (AWS Textract) with confidence scoring
- [ ] Entity master configuration
- [ ] Multi-entity detection and routing (GSTIN/PAN/name)
- [ ] GST line splits (CGST/SGST/IGST) and TDS handling
- [ ] Duplicate detection (hash + invoice number + fuzzy)
- [ ] Document splitting detection and split flow
- [ ] Internal notes / comments on JV
- [ ] Due date urgency flags on review queue
- [ ] JV draft creation with full status lifecycle
- [ ] RBAC: Preparer, Reviewer, Admin
- [ ] Single-level approval with rejection and resubmission (max 3)
- [ ] Reviewer split-panel review screen with notes
- [ ] Approval reminders (24h nudge, 48h escalation)
- [ ] ERP push with attachment (Zoho + QBO)
- [ ] ERP error handling and retry queue
- [ ] COA sync from ERP (daily)
- [ ] Payment status sync from ERP (daily)
- [ ] In-app and email notifications (full list per Section 27)
- [ ] Audit log (immutable, exportable)
- [ ] Basic dashboard (Admin, Preparer, Reviewer views)
- [ ] Manual exchange rate entry for foreign currency

### Phase 2 — V2 (~4 weeks)
- [ ] Multi-level approval (threshold-based: Reviewer → Senior Reviewer → CFO)
- [ ] Delegated approver configuration
- [ ] GDrive / OneDrive / Box folder connect (OAuth + folder watch)
- [ ] Vendor self-submission portal
- [ ] Bulk approval UI for reviewers
- [ ] Intercompany document handling (two-sided JV)
- [ ] Recurring entry templates
- [ ] Payroll entry module (Payroll Approver role)
- [ ] PO matching (invoice PO number vs ERP PO data)
- [ ] AP ageing report
- [ ] Rejection analytics dashboard
- [ ] SLA tracking dashboard
- [ ] Outbound webhook for external systems
- [ ] Inbound API for programmatic document push
- [ ] Auto FX rate fetch (RBI / Open Exchange Rates)
- [ ] Auditor read-only role
- [ ] CFO / Senior Reviewer dashboard
- [ ] Real-time payment status via ERP webhook (where supported)

### Phase 3 — V3 (~4–6 weeks)
- [ ] WhatsApp Business ingestion
- [ ] GSTIN verification against live GSTN API
- [ ] HSN/SAC code extraction and validation
- [ ] Bank statement reconciliation
- [ ] 3-way match: PO → GRN → Invoice
- [ ] ERP reverse sync (detect JVs in ERP with no platform source doc)
- [ ] Vendor auto-categorisation (ML-based)
- [ ] Multi-ERP push (same JV to multiple instances)
- [ ] External auditor portal (direct read-only access)
- [ ] Dropbox / SharePoint / FTP folder integrations
- [ ] GSTN API integration for GSTIN and HSN validation

---

## 33. Non-Functional Requirements

| Requirement | Target |
|-------------|--------|
| Security | AES-256 at rest, TLS 1.2+, RBAC at API level |
| Availability | 99.9% uptime |
| Scalability | 10,000 documents/month per org (standard plan) |
| Performance | AI extraction within 60 seconds for standard documents |
| Email processing | Within 5 minutes of receipt |
| Document retention | 8 years minimum |
| Audit log retention | Permanent |
| Disaster recovery | Daily backups, RPO 24h, RTO 4h |

---

## 34. Open Questions

1. Should very low-value JVs (e.g., below ₹500) have a configurable approval bypass for trusted preparers?
2. Retention policy — does it differ by document type under Indian law?
3. GSTIN verification against GSTN API — V1 or V2?
4. Abandoned / unresolved rejected JVs — auto-archive after 90 days?
5. Multiple ERP connections for a single entity (e.g., Zoho for India + QBO for US sub)?
6. Auditor role — access to failed and voided JVs or only pushed ones?
7. Payroll module — V1 or V2?
8. Intercompany: if one entity rejects, does paired JV auto-reject or go on hold?
9. Should Admin be able to bypass approval gate in urgent situations? What controls govern this?
10. Vendor portal — should vendors be able to see full payment details or just status?
11. WhatsApp — does the org already have a WhatsApp Business account?
12. API / webhook — is there an existing internal system that would consume these immediately?

---

*End of Document — v4.0*
