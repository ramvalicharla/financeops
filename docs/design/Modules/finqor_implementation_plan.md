# Finqor (FinanceOps) — Backend Implementation Plan
### Full Fix Roadmap · 21 P0 Blockers + P1 Gaps · 8 Phases · 8 Weeks
**Repo:** `D:\finos\` · **Stack:** Python 3.11, FastAPI, PostgreSQL 16 + RLS, Celery, Redis  
**Baseline:** v3.0.0 · Migration head: `0101_accounting_rbac_seed_final` · Tests: 2527 passing

---

## Hard Constraints — NEVER Violate

These apply to every task in this document. Read before any implementation.

| Constraint | Rule |
|---|---|
| Python version | Python 3.11 only — never upgrade |
| Financial amounts | `Decimal` everywhere — never `float` |
| History tables | APPEND-ONLY — no `UPDATE` or `DELETE` ever on run/event/history tables |
| Config/master tables | MUTABLE — `UPDATE` allowed |
| ERP status updates | New version row — never UPDATE existing rows |
| Event loop | `WindowsSelectorEventLoopPolicy()` in `main.py` AND `conftest.py` — never touch |
| Asyncio scope | `asyncio_default_test_loop_scope = "session"` in `pyproject.toml` — never touch |
| Warnings | `filterwarnings = "error"` — zero warnings allowed |
| Celery import | `from financeops.tasks.celery_app import celery_app` |
| DB session | `get_async_session` in `financeops/db/session.py` |
| Rate limiting | SlowAPI needs `request: Request` as param in every route signature |
| HTTP client | `httpx.AsyncClient` — never `urllib.request` |
| New models | `entity_id` on ALL new models |
| Financial txn models | `location_id` + `cost_centre_id` required |
| Alembic revision IDs | 32 chars max — `VARCHAR(32)` limit |
| Migration numbering | Strictly sequential, no gaps, one head only |
| Tests | No skipped tests, no xfail markers, 0 warnings, 0 failures |
| Search tool | `rg` not `grep` |

---

## Master P0 Blocker Index

21 P0 blockers across 26 modules.

| # | Blocker | Module | Phase | Category |
|---|---|---|---|---|
| 1 | `change_password()` does not revoke existing sessions | Auth & IAM | Phase 1 | Security |
| 2 | MFA completion not enforced before protected endpoint access | Auth & IAM | Phase 1 | Security |
| 3 | Forgot-password has no exponential backoff or CAPTCHA | Auth & IAM | Phase 1 | Security |
| 4 | Webhook delivery has no HMAC-SHA256 signature | Scheduled Delivery | Phase 1 | Security |
| 5 | COA confirm endpoint not idempotent — double-submit = duplicate accounts | Chart of Accounts | Phase 2 | Data Integrity |
| 6 | ERP sync `publish()` not transactional — GL can post with sync incomplete | ERP Sync | Phase 2 | Data Integrity |
| 7 | `org_setup_complete` flag not enforced on downstream modules | Org Setup | Phase 2 | Data Integrity |
| 8 | Consolidation crashes on missing source entity (uncaught `ValueError`) | Consolidation | Phase 2 | Data Integrity |
| 9 | Scheduled delivery no idempotency check — Celery retry = duplicate sends | Scheduled Delivery | Phase 2 | Data Integrity |
| 10 | Cron expression not validated at schedule creation | Scheduled Delivery | Phase 2 | Data Integrity |
| 11 | `run_bank_reconciliation()` creates only `bank_only` breaks — no GL match | Bank Reconciliation | Phase 3 | Compliance |
| 12 | GST Recon has no portal import and no invoice-level matching | GST Reconciliation | Phase 3 | Compliance |
| 13 | IT Act Section 32 block depreciation not implemented in `get_depreciation()` | Fixed Assets | Phase 3 | Compliance |
| 14 | Audit trail writes missing in 20+ modules | Audit Trail | Phase 4 | Compliance |
| 15 | Working Capital serves hard-coded dummy data (`AR=₹1M`) to real tenants | Working Capital | Phase 3 | Functional |
| 16 | Consolidation board-pack/risk/anomaly endpoints return hardcoded stubs | Consolidation | Phase 3 | Functional |
| 17 | AI CFO Layer has zero LLM calls — pure if-else rules, not AI | AI CFO Layer | Phase 5 | Functional |
| 18 | Narrative Engine executive summary is a single hardcoded string | Narrative Engine | Phase 5 | Functional |
| 19 | Board Pack PDF/Excel export is an unimplemented stub | Board Pack Generator | Phase 5 | Functional |
| 20 | All 3 Accounting Layer beat tasks return `{"status":"ok"}` — never execute | Accounting Layer | Phase 4 | Functional |
| 21 | 18 of 26 modules have zero meaningful tests | Cross-cutting | Phase 6–8 | Quality |

---

## Phase 1 — Security Hardening
**Week 1 · P0 blockers resolved: 4 · Modules: Auth & IAM, Scheduled Delivery**

Fix all security P0s first. A platform with these auth gaps cannot safely onboard any customer.

---

### 1.1 — Auth: Revoke sessions on password change

**File:** `financeops/modules/auth/application/auth_service.py`

**Problem:**
- `change_password()` updates the password hash but leaves all existing `IamSession` rows active
- If a credential is compromised and the user resets, the attacker's session stays valid indefinitely

**Implementation steps:**
1. Open `auth_service.py`, find `change_password()` method
2. After saving new password hash, call `revoke_all_sessions(user_id, db)` helper
3. Check if `IamSession` is mutable (UPDATE) or append-only (INSERT revocation event) — read the model first
4. Wrap password save + session revocation in single `async with db.begin()` transaction
5. Return a new access+refresh token pair so the current user stays logged in
6. Write test: change password → verify old refresh token rejected → new token works

**Claude Code / Codex prompt:**

```
FINANCEOPS — SECURITY FIX: SESSION REVOCATION ON PASSWORD CHANGE

Repo: D:\finos\backend\
File to fix: financeops/modules/auth/application/auth_service.py

HARD CONSTRAINTS: Python 3.11, Decimal not float, no skipped tests,
  asyncio_default_test_loop_scope = "session", filterwarnings = "error"
  Celery: from financeops.tasks.celery_app import celery_app
  DB session: get_async_session in financeops/db/session.py

CONTEXT: Read these files first before writing any code:
  - financeops/modules/auth/application/auth_service.py
  - financeops/db/models/iam.py (check if IamSession is append-only or mutable)
  - financeops/modules/auth/api/routes.py

TASK:
1. In change_password(), after saving new password hash, revoke all active sessions
   for that user_id WITHIN the same DB transaction.
   If IamSession is mutable: UPDATE is_active=False WHERE user_id=X AND is_active=True
   If IamSession is append-only: INSERT a session_revocation event row.
2. After revocation, issue a new token pair and return it so the caller stays logged in.
3. Wrap password save + revocation in async with db.begin().

TESTS — write in tests/integration/test_auth_security.py:
- test_password_change_revokes_old_refresh_token
- test_password_change_returns_new_token_pair
- test_old_access_token_rejected_after_password_change
All tests: 0 warnings, 0 skips.
```

---

### 1.2 — Auth: Enforce MFA completion middleware

**File:** `financeops/modules/auth/dependencies.py`

**Problem:**
- `force_mfa_setup=True` is set on new users at registration
- No middleware or dependency checks `mfa_setup_complete` before allowing access to protected routes
- A user can register, skip MFA setup, and use the full platform

**Implementation steps:**
1. Create FastAPI dependency `require_mfa_complete` in `financeops/modules/auth/dependencies.py`
2. Reads current user from JWT, checks `user.mfa_setup_complete`
3. If `force_mfa_setup=True` AND `mfa_setup_complete=False` → raise `HTTPException(403, "MFA_SETUP_REQUIRED")`
4. Apply to all routers EXCEPT: `/auth/*`, `/health`, `/health/deep`
5. Add `IamUser.mfa_setup_complete` field + Alembic migration if missing (sequential, 32-char max revision ID)

**Claude Code / Codex prompt:**

```
FINANCEOPS — SECURITY FIX: ENFORCE MFA COMPLETION

Repo: D:\finos\backend\
HARD CONSTRAINTS: Python 3.11, filterwarnings = "error", asyncio scope = "session"

CONTEXT: Read first:
  - financeops/modules/auth/application/auth_service.py
  - financeops/modules/auth/api/routes.py
  - financeops/main.py (router registration)
  - financeops/db/models/iam.py (IamUser.mfa_setup_complete field)

TASK:
1. Create require_mfa_complete FastAPI dependency in
   financeops/modules/auth/dependencies.py
   Logic:
   - Extract current user from JWT (reuse existing get_current_user dep)
   - If user.force_mfa_setup AND NOT user.mfa_setup_complete:
     raise HTTPException(status_code=403, detail="MFA_SETUP_REQUIRED")
2. Apply require_mfa_complete to all routers in main.py EXCEPT: /auth/*, /health, /health/deep
3. If IamUser.mfa_setup_complete field missing: add it + Alembic migration
   (sequential ID, 32-char max revision ID)

TESTS — tests/integration/test_mfa_enforcement.py:
- test_new_user_blocked_until_mfa_complete
- test_mfa_exempt_routes_work_without_mfa
- test_user_with_mfa_complete_accesses_platform
0 warnings, 0 skips.
```

---

### 1.3 — Auth: Rate limit forgot-password endpoint

**File:** `financeops/modules/auth/api/routes.py`

**Problem:**
- `POST /auth/forgot-password` accepts unlimited requests per email/IP
- Attacker can enumerate valid emails or flood a user's inbox

**Implementation steps:**
1. Add SlowAPI rate limit: 3 requests per 15 minutes per IP — `@limiter.limit("3/15minutes")`
2. Add `request: Request` param to route signature (required by SlowAPI)
3. Return identical response body whether email exists or not — prevents enumeration
4. Add `reset_attempt_count` to `PasswordResetToken` via Alembic migration
5. If `attempt_count >= 3`, add 30-second `asyncio.sleep` delay before sending (async, not blocking)

**Claude Code / Codex prompt:**

```
FINANCEOPS — SECURITY FIX: RATE LIMIT FORGOT-PASSWORD

Repo: D:\finos\backend\
HARD CONSTRAINTS: SlowAPI route MUST have request: Request param. Python 3.11.

CONTEXT: Read first:
  - financeops/modules/auth/api/routes.py
  - financeops/main.py (existing SlowAPI limiter instance)
  - financeops/db/models/iam.py (PasswordResetToken model)

TASK:
1. Add @limiter.limit("3/15minutes") to POST /auth/forgot-password
   Ensure request: Request is in the route signature.
2. Ensure route returns IDENTICAL response whether email exists or not.
3. Add reset_attempt_count to PasswordResetToken model via Alembic migration
   (sequential, 32-char max revision ID).
4. In service: if attempt_count >= 3, await asyncio.sleep(30) before sending email.

TESTS — tests/integration/test_auth_rate_limit.py:
- test_forgot_password_rate_limited_after_3_attempts
- test_forgot_password_same_response_for_valid_and_invalid_email
0 warnings, 0 skips.
```

---

### 1.4 — Scheduled Delivery: HMAC webhook signature

**File:** `financeops/modules/scheduled_delivery/application/delivery_service.py`

**Problem:**
- Webhook deliveries sent with no signature header
- Recipients cannot verify payload came from Finqor — open to spoofing

**Implementation steps:**
1. Add `webhook_secret` (nullable, encrypted) column to `DeliverySchedule` — use existing field encryption pattern from `erp_sync/infrastructure/secret_store.py`
2. On webhook delivery: compute `HMAC-SHA256` of payload bytes using schedule's secret
3. Set header: `X-Finqor-Signature: sha256=<hex_digest>`
4. If no `webhook_secret` configured → raise `DeliveryConfigError`, do not send unsigned
5. Store signature in `DeliveryLog.metadata` JSONB

**Claude Code / Codex prompt:**

```
FINANCEOPS — SECURITY FIX: WEBHOOK HMAC SIGNATURE

Repo: D:\finos\backend\

CONTEXT: Read first:
  - financeops/modules/scheduled_delivery/application/delivery_service.py
  - financeops/db/models/scheduled_delivery.py
  - financeops/modules/erp_sync/infrastructure/secret_store.py
    (use same pattern for encrypting webhook_secret)

TASK:
1. Add webhook_secret (String, nullable, encrypted) to DeliverySchedule model.
   Alembic migration: sequential ID, 32-char max.
2. In delivery_service.py, when channel == WEBHOOK:
   a. Compute: hmac.new(secret.encode(), payload_bytes, hashlib.sha256)
   b. Set header X-Finqor-Signature: sha256={hmac.hexdigest()}
   c. If no webhook_secret: raise DeliveryConfigError (do not send unsigned)
3. Store signature in DeliveryLog.metadata JSONB field.

TESTS — tests/integration/test_scheduled_delivery_webhook.py:
- test_webhook_delivery_includes_hmac_header
- test_webhook_delivery_fails_without_secret_configured
- test_hmac_signature_is_verifiable_by_recipient
0 warnings, 0 skips.
```

---

## Phase 2 — Data Integrity Fixes
**Week 2 · P0 blockers resolved: 6 · Modules: COA, ERP Sync, Org Setup, Consolidation, Scheduled Delivery**

Six P0s that cause silent data corruption. Must be fixed before any financial data flows through the system.

---

### 2.1 — COA: Make confirm endpoint idempotent

**File:** `financeops/modules/chart_of_accounts/application/coa_service.py`

**Problem:** `POST /coa/upload/{batch_id}/confirm` re-inserts `TenantCoaAccount` rows if called twice (network retry, double-click).

**Fix:**
- Add `confirmation_status` enum (`PENDING`/`CONFIRMED`) to `CoaUploadBatch`
- Check status before inserting — if already `CONFIRMED`, return existing result
- Use `SELECT FOR UPDATE` on batch row to prevent race condition
- Add DB unique constraint on `(tenant_id, account_code)` with `ON CONFLICT DO NOTHING`

**Claude Code / Codex prompt:**

```
FINANCEOPS — DATA INTEGRITY: COA CONFIRM IDEMPOTENCY

Repo: D:\finos\backend\

CONTEXT: Read first:
  - financeops/modules/chart_of_accounts/api/routes.py
  - financeops/modules/chart_of_accounts/application/coa_service.py
  - financeops/db/models/coa.py

TASK:
1. Add confirmation_status enum (PENDING/CONFIRMED) to CoaUploadBatch model.
   Alembic migration: sequential, 32-char max.
2. In confirm() service method:
   - Check if batch.confirmation_status == CONFIRMED → return existing result (idempotent)
   - If PENDING: run insertion in transaction, update status to CONFIRMED
   - Use SELECT FOR UPDATE on batch row to prevent race condition
3. Add DB unique constraint on (tenant_id, account_code) in TenantCoaAccount
   with ON CONFLICT DO NOTHING in bulk insert.

TESTS — tests/integration/test_coa_idempotency.py:
- test_confirm_twice_same_batch_idempotent
- test_confirm_concurrent_requests_no_duplicate_accounts
0 warnings, 0 skips.
```

---

### 2.2 — ERP Sync: Wrap publish() in savepoint transaction

**File:** `financeops/modules/erp_sync/application/publish_service.py`

**Problem:** `publish()` creates `JournalEntry` then updates `ExternalSyncRun` in two separate DB operations. If the second fails, GL is posted but sync appears incomplete — causing re-sync and duplicate GL entries.

**Fix:**
- Wrap both operations in `async with db.begin_nested()` (savepoint)
- Add deduplication guard: check for existing `JournalEntry` with same `external_ref` before inserting
- Add `(tenant_id, external_ref)` unique constraint on `journal_entries` via migration

**Claude Code / Codex prompt:**

```
FINANCEOPS — DATA INTEGRITY: ERP SYNC TRANSACTIONAL PUBLISH

Repo: D:\finos\backend\

CONTEXT: Read first:
  - financeops/modules/erp_sync/application/publish_service.py
  - financeops/db/models/erp_sync.py (ExternalSyncRun — append-only)
  - financeops/db/models/accounting_layer.py (JournalEntry — append-only)

HARD CONSTRAINT: ExternalSyncRun and JournalEntry are APPEND-ONLY.
  Status change = insert new row, not UPDATE.

TASK:
1. Wrap GL journal entry creation AND sync run status update in a single
   async with db.begin_nested() (savepoint) block.
2. Before inserting JournalEntry:
   SELECT 1 FROM journal_entries WHERE external_ref=:ref AND tenant_id=:tid
   If exists → skip insert, mark run as ALREADY_POSTED.
3. Add unique constraint (tenant_id, external_ref) on journal_entries via migration.

TESTS — tests/integration/test_erp_sync_publish.py:
- test_publish_atomicity_rollback_on_sync_run_failure
- test_publish_deduplication_same_external_ref
- test_publish_successful_end_to_end
0 warnings, 0 skips.
```

---

### 2.3 — Org Setup: Enforce org_setup_complete gate

**File:** `financeops/modules/org_setup/dependencies.py` (create)

**Problem:** `org_setup_complete` flag is set on org but nothing checks it. Financial modules accept requests from incomplete orgs.

**Fix:**
- Create FastAPI dependency `require_org_complete` — checks `OrgSetupProgress.setup_complete` for tenant
- Apply to all financial module routers. Exempt: `/org-setup/*`, `/auth/*`, `/health`, `/billing/*`
- Add DB unique constraint on `(tenant_id, entity_code)` in `OrgEntity`
- Add parent-entity cycle detection in `OrgOwnership` service before saving

**Claude Code / Codex prompt:**

```
FINANCEOPS — DATA INTEGRITY: ORG SETUP ENFORCEMENT + CYCLE DETECTION

Repo: D:\finos\backend\

CONTEXT: Read first:
  - financeops/modules/org_setup/application/org_service.py
  - financeops/db/models/org_setup.py
  - financeops/main.py (router registration — to know which routers to protect)

TASK:
1. Create FastAPI dependency require_org_complete in
   financeops/modules/org_setup/dependencies.py
   - Read tenant_id from JWT
   - Query OrgSetupProgress.setup_complete for tenant
   - If not complete → HTTPException(403, "ORG_SETUP_INCOMPLETE")
2. Apply to all module routers EXCEPT: org_setup, auth, health, billing.
3. Add DB unique constraint on (tenant_id, entity_code) in OrgEntity via migration.
4. In create_org_ownership(), before INSERT:
   Walk ownership tree upward from proposed parent_id.
   If proposed child_id found in walk → raise CircularOwnershipError.

TESTS — tests/integration/test_org_setup_gate.py:
- test_incomplete_org_blocked_from_financial_module
- test_complete_org_accesses_financial_module
- test_circular_ownership_rejected
- test_entity_code_uniqueness_enforced
0 warnings, 0 skips.
```

---

### 2.4 — Consolidation: Fix uncaught ValueError + stub endpoints

**File:** `financeops/modules/consolidation/application/run_service.py`

**Problem 1:** `execute_run()` raises unhandled `ValueError` at ~line 754-758 if any source entity is missing → HTTP 500 with no context.

**Problem 2:** `/board-pack`, `/risks`, `/anomalies` endpoints all return `{"status": "not_generated", "sections": []}`.

**Fix:**
- Wrap entity fetch in `try/except`, raise typed `MissingSourceEntityError` → HTTP 422 with entity IDs listed
- Wire `/board-pack` to `BoardPackGeneratorService` (already built)
- Wire `/risks` and `/anomalies` to `AnomalyPatternEngine`
- Add `source_run_refs` existence validation before `execute_run()`

**Claude Code / Codex prompt:**

```
FINANCEOPS — DATA INTEGRITY: CONSOLIDATION FIXES

Repo: D:\finos\backend\

CONTEXT: Read first:
  - financeops/modules/consolidation/application/run_service.py (lines 740-780)
  - financeops/modules/consolidation/api/routes.py
  - financeops/modules/board_pack_generator/application/generate_service.py
  - financeops/modules/anomaly_pattern_engine/application/run_service.py

TASK:
1. In execute_run(), at ~line 754-758: replace ValueError with:
   collect all missing entity IDs → raise MissingSourceEntityError(missing_ids=[...])
   → HTTP 422 response with details.
2. Replace /board-pack stub with real call to BoardPackGenerateService.generate().
3. Replace /risks stub with AnomalyPatternEngine filtered by entity scope.
4. Replace /anomalies stub with AnomalyRunResult from anomaly engine.
5. Add source_run_refs existence check before execute_run() proceeds.

TESTS — tests/integration/test_consolidation_run.py:
- test_missing_source_entity_returns_422_not_500
- test_consolidation_board_pack_endpoint_not_stub
- test_consolidation_risks_endpoint_not_stub
0 warnings, 0 skips.
```

---

### 2.5 — Scheduled Delivery: Idempotency + cron validation

**File:** `financeops/modules/scheduled_delivery/application/delivery_service.py`

**Problem 1:** Celery retry re-sends same email/webhook to board members.

**Problem 2:** Invalid cron expression saved silently — schedule never fires, no user feedback.

**Fix:**
- Add `idempotency_key` (UUID) to `DeliveryLog`; Celery task checks before sending
- On `POST /schedules`, validate cron with `croniter.is_valid()` → return 422 if invalid
- Add `croniter` to `pyproject.toml`

**Claude Code / Codex prompt:**

```
FINANCEOPS — DATA INTEGRITY: SCHEDULED DELIVERY FIXES

Repo: D:\finos\backend\

CONTEXT: Read first:
  - financeops/modules/scheduled_delivery/application/delivery_service.py
  - financeops/modules/scheduled_delivery/tasks.py
  - financeops/db/models/scheduled_delivery.py

TASK:
1. Add idempotency_key (UUID) to DeliveryLog model. Alembic migration: sequential, 32-char max.
2. In deliver_schedule_task Celery task:
   - Before sending: check DeliveryLog for matching idempotency_key + DELIVERED status
   - If found → log "already delivered, skipping" → return without sending
   - If not found → send → INSERT new DeliveryLog row (APPEND-ONLY)
3. In POST /schedules route:
   from croniter import croniter
   if not croniter.is_valid(cron_expression):
     raise HTTPException(422, detail=f"Invalid cron: {cron_expression}. Example: '0 9 * * 1'")
   Add croniter to pyproject.toml.

TESTS — tests/integration/test_scheduled_delivery_idempotency.py:
- test_celery_retry_does_not_duplicate_delivery
- test_invalid_cron_expression_rejected_at_creation
- test_valid_cron_expression_accepted
0 warnings, 0 skips.
```

---

## Phase 3 — Compliance Engines
**Weeks 2–3 · P0 blockers resolved: 5 · Modules: Bank Recon, GST Recon, Fixed Assets, Working Capital, Consolidation**

The hardest phase. Bank Recon (~120h) and GST Recon (~100h) require significant net-new logic. Platform is not usable for any Indian SME customer without these.

---

### 3.1 — Bank Reconciliation: Implement GL matching

**File:** `financeops/modules/bank_reconciliation/application/recon_service.py`

**Current state:** 8 routes, 446 LOC service, models exist. `run_bank_reconciliation()` creates `bank_only` break items only. The core GL matching is entirely unimplemented.

**Required implementation — three-pass matching algorithm:**

- **Pass 1 — EXACT:** `abs(bank.amount - gl.amount) == 0` AND `bank.value_date == gl.posting_date` → `MATCHED`
- **Pass 2 — NEAR:** Amounts match exactly AND `abs(bank.value_date - gl.posting_date) <= 3 days` → `NEAR_MATCH` (requires human confirmation)
- **Pass 3 — FUZZY:** Amount within `Decimal('0.0001')%` tolerance AND date within 7 days AND `difflib.SequenceMatcher` description similarity > 0.8 → `FUZZY_MATCH`

Remaining bank transactions → `BANK_ONLY` break items.  
Remaining GL entries → `GL_ONLY` break items.  
All results → INSERT `BankReconItem` rows (APPEND-ONLY).  
Return `BankReconSummary` with all counts + `net_difference: Decimal`.

**Critical:** All amounts `Decimal` — never `float`. Use `Decimal('0.0001')` for tolerance. `BankReconItem` is INSERT-ONLY — re-run creates new items with new `run_id`.

**Claude Code / Codex prompt:**

```
FINANCEOPS — COMPLIANCE: BANK RECONCILIATION GL MATCHING ENGINE

Repo: D:\finos\backend\
Estimated effort: 3–4 days

CONTEXT: Read these files COMPLETELY before writing any code:
  - financeops/modules/bank_reconciliation/application/recon_service.py
  - financeops/db/models/bank_reconciliation.py
  - financeops/db/models/accounting_layer.py (JournalEntry, JournalEntryLine)
  - financeops/modules/accounting_layer/infrastructure/repository.py
  - tests/conftest.py (DB fixture patterns)

HARD CONSTRAINTS:
  - All amounts: Decimal — never float
  - BankReconItem is INSERT-ONLY (no UPDATE/DELETE ever)
  - BankStatement, BankTransaction are INSERT-ONLY
  - Python 3.11, asyncio_default_test_loop_scope = "session"

TASK — implement run_bank_reconciliation() completely:
1. Load BankTransaction rows for statement_id, status=UNMATCHED
2. Load JournalEntryLine rows for same bank_account_id + date range, status=UNMATCHED
3. THREE-PASS MATCHING:
   Pass 1 (EXACT): abs(bank.amount - gl.amount) == 0 AND bank.value_date == gl.posting_date
   Pass 2 (NEAR):  amounts exactly equal AND abs(date diff) <= 3 days
   Pass 3 (FUZZY): abs(bank.amount - gl.amount) / gl.amount < Decimal('0.0001')
                   AND date diff <= 7 days
                   AND difflib.SequenceMatcher(None, bank.description, gl.narration).ratio() > 0.8
4. INSERT BankReconItem per match (MATCHED/NEAR_MATCH/FUZZY_MATCH, BANK_ONLY, GL_ONLY)
5. Return BankReconSummary(matched, near_match, fuzzy, bank_only, gl_only, net_difference: Decimal)

TESTS — tests/integration/test_bank_recon_matching.py (minimum 15 tests):
- test_exact_match_same_day_same_amount
- test_near_match_3_day_tolerance
- test_fuzzy_match_description_similarity
- test_bank_only_break_created_for_unmatched_bank_txn
- test_gl_only_break_created_for_unmatched_gl_entry
- test_net_difference_calculation_decimal
- test_rerun_creates_new_items_not_update_existing
- test_zero_transactions_returns_empty_summary
- test_amounts_stored_as_decimal_not_float
0 warnings, 0 skips.
```

---

### 3.2 — GST Reconciliation: Portal import + ITC rules

**File:** `financeops/modules/gst_reconciliation/application/` (multiple new services)

**Current state:** 11 routes, 370 LOC, IGST/CGST/SGST totals computed. Missing: GSTN JSON import, invoice-level matching, ITC eligibility rules.

**Required implementation — 4 phases:**

**Phase A — GSTN JSON Import:**
- `parse_gstr1_json(json_data)` and `parse_gstr2b_json(json_data)` → `List[GstReturnLineItem]`
- Validate each GSTIN via `validate_gstin()` from `financeops/utils/gstin.py`
- INSERT `GstReturn` + line items (INSERT-ONLY)

**Phase B — Invoice Matching:**
- Same 3-pass approach as bank recon
- Match on: `supplier_gstin` + `invoice_number` + `taxable_value`
- INSERT `GstReconItem` per match/break (INSERT-ONLY)

**Phase C — ITC Eligibility (Rules 36/37/38):**
- Rule 36: ITC eligible only if invoice appears in GSTR-2B
- Rule 37: Reverse ITC if payment not made within 180 days
- Rule 38: Blocked ITC categories (personal expenses, motor vehicles per GST Act Schedule)
- Add `itc_eligible: bool`, `itc_blocked_reason` to `GstReconItem`

**Phase D — Rate Validation:**
- `GST_RATE_MASTER = {0, 5, 12, 18, 28}`
- Flag any invoice line with rate not in master

**Claude Code / Codex prompt:**

```
FINANCEOPS — COMPLIANCE: GST RECONCILIATION ENGINE

Repo: D:\finos\backend\
Estimated effort: 4–5 days

CONTEXT: Read COMPLETELY:
  - financeops/modules/gst_reconciliation/application/gst_service.py
  - financeops/db/models/gst_reconciliation.py
  - financeops/utils/gstin.py (validate_gstin, extract_state_code)
  - financeops/db/models/accounting_layer.py (sales invoices)
  - tests/conftest.py

HARD CONSTRAINTS: Decimal not float, INSERT-ONLY on GstReturn/GstReconItem,
  Python 3.11, asyncio scope = "session"

PHASE A — JSON Import (application/gstn_import_service.py):
  - parse_gstr1_json(json_data) → List[GstReturnLineItem]
  - parse_gstr2b_json(json_data) → List[GstReturnLineItem]
  - Validate each GSTIN via validate_gstin() — reject if invalid
  - INSERT GstReturn header + line items (INSERT-ONLY)

PHASE B — Invoice Matching (application/invoice_match_service.py):
  - 3-pass matching (same pattern as bank recon)
  - Match on: supplier_gstin + invoice_number + taxable_value
  - INSERT GstReconItem per match/break (INSERT-ONLY)

PHASE C — ITC Eligibility (application/itc_eligibility_service.py):
  - Rule 36: itc_eligible=True only if invoice appears in GSTR-2B
  - Rule 37: flag invoices > 180 days unpaid → reverse_itc=True
  - Rule 38: blocked categories list (hardcode from GST Act schedule)
  - Add itc_eligible, itc_blocked_reason to GstReconItem model + migration

PHASE D — Rate Validation (in gst_service.py):
  - GST_RATE_MASTER = {0, 5, 12, 18, 28}
  - Flag any line with rate not in master → GstReconItem.rate_mismatch=True

TESTS — tests/integration/test_gst_recon.py (minimum 12 tests):
- test_gstr1_json_import_valid
- test_invalid_gstin_rejected_on_import
- test_invoice_exact_match
- test_itc_rule_36_only_2b_invoices_eligible
- test_itc_rule_37_180_day_reversal
- test_itc_rule_38_blocked_category
- test_invalid_gst_rate_flagged
0 warnings, 0 skips.
```

---

### 3.3 — Fixed Assets: IT Act Section 32 + monthly scheduler

**File:** `financeops/modules/fixed_assets/application/depreciation_engine.py`

**Problem:** Section 32 block depreciation is defined in the schema but `get_depreciation()` ignores it. No automated monthly depreciation run.

**Fix:**
- Add `BLOCK_IT_ACT_S32` branch in `get_depreciation()`: 100% in acquisition year, pro-rated by `(days_from_acquisition_to_year_end / 365)`
- `IT_ACT_S32_THRESHOLD = Decimal('5000')` — assets below this auto-qualify
- Create `run_monthly_depreciation` Celery beat task, register monthly on 1st at 02:00

**Claude Code / Codex prompt:**

```
FINANCEOPS — COMPLIANCE: FIXED ASSETS IT ACT SECTION 32 + SCHEDULER

Repo: D:\finos\backend\

CONTEXT: Read first:
  - financeops/modules/fixed_assets/application/depreciation_engine.py
  - financeops/db/models/fixed_assets.py (FaAssetClass.depreciation_method)
  - financeops/tasks/celery_app.py (beat schedule pattern)
  - financeops/modules/accounting_layer/tasks/beat_tasks.py (beat task example)

TASK:
1. In depreciation_engine.get_depreciation(), add case for BLOCK_IT_ACT_S32:
   - If acquisition_date.year == period_year:
     depreciation = (days_from_acquisition_to_year_end / 365) * asset_cost  (Decimal)
   - If not acquisition year: depreciation = Decimal('0')
2. Add BLOCK_IT_ACT_S32 to DepreciationMethod enum.
3. Add IT_ACT_S32_THRESHOLD = Decimal('5000') — assets at or below auto-qualify.

SCHEDULER (financeops/modules/fixed_assets/tasks.py):
4. @celery_app.task(queue='normal_q') run_monthly_depreciation(tenant_id, period) → None
   - Load all active FaAsset rows for tenant
   - Call depreciation_engine.get_depreciation() per asset
   - Post depreciation JournalEntry via accounting_layer service
   - INSERT FaDepreciationRun (INSERT-ONLY) with status COMPLETE/FAILED
5. Register in Celery beat: cron('0 2 1 * *') — monthly on 1st at 02:00.

TESTS — tests/integration/test_fixed_assets_depreciation.py:
- test_section_32_full_depreciation_in_acquisition_year
- test_section_32_zero_in_subsequent_years
- test_section_32_prorata_partial_year
- test_sl_depreciation_unchanged_by_s32_addition
- test_monthly_scheduler_posts_journal_entry
0 warnings, 0 skips.
```

---

### 3.4 — Working Capital: Remove hardcoded dummy data

**File:** `financeops/modules/working_capital/application/wc_service.py`

**Problem:** `_load_financial_inputs()` falls back to `AR=₹1M, AP=₹600K, Revenue=₹5M` when no snapshot exists. Real tenants see fake numbers.

**Fix:**
- Remove ALL hardcoded fallbacks
- Query GL via `accounting_layer` repository for real balances by account group
- If no GL data → raise `InsufficientDataError("No GL data available. Complete ERP sync first.")` → HTTP 422

**Claude Code / Codex prompt:**

```
FINANCEOPS — FUNCTIONAL: WORKING CAPITAL REAL GL DATA

Repo: D:\finos\backend\

CONTEXT: Read first:
  - financeops/modules/working_capital/application/wc_service.py
  - financeops/modules/accounting_layer/infrastructure/repository.py
    (how to query GL balances by account group)
  - financeops/db/models/working_capital.py

TASK:
1. In _load_financial_inputs(), remove ALL hardcoded fallback values.
2. Replace with real GL queries:
   - AR      = GL balances for account_group=ACCOUNTS_RECEIVABLE
   - AP      = GL balances for account_group=ACCOUNTS_PAYABLE
   - Revenue = GL balances for account_group=REVENUE (last 12 months)
   - Inventory = GL balances for INVENTORY accounts
3. If no GL data for tenant:
   raise InsufficientDataError("No GL data. Complete ERP sync first.") → HTTP 422
4. All amounts: Decimal. No rounding except at display layer.

TESTS — tests/integration/test_working_capital.py:
- test_wc_snapshot_uses_real_gl_data_not_hardcoded
- test_wc_raises_error_not_dummy_values_when_no_gl
- test_wc_current_ratio_decimal_precision
- test_wc_dso_calculation_correct
0 warnings, 0 skips.
```

---

## Phase 4 — Infrastructure: Celery + Audit Trail Middleware
**Weeks 3–4 · P0 blockers resolved: 2 · Modules: All modules + Accounting Layer**

Two cross-cutting infrastructure fixes that affect every module.

---

### 4.1 — Celery jobs for all synchronous compute modules

16 modules run heavy computation synchronously on the HTTP thread. This causes timeouts on real data volumes.

| Module | Task to create | Queue | HTTP response change |
|---|---|---|---|
| GL/TB Recon | `run_gl_recon_task` | `normal_q` | 200 → 202 Accepted |
| Payroll GL Norm. | `run_payroll_norm_task` | `normal_q` | 200 → 202 Accepted |
| Payroll GL Recon. | `run_payroll_recon_task` | `normal_q` | 200 → 202 Accepted |
| MIS Manager | `generate_mis_report_task` | `normal_q` | 200 → 202 Accepted |
| Month-End Close | `process_checklist_triggers_task` | `high_q` | event-driven |
| Consolidation | `execute_consolidation_run_task` | `normal_q` | 200 → 202 Accepted |
| Anomaly Engine | `run_anomaly_detection_task` | `normal_q` | 200 → 202 Accepted |
| Notifications | `send_notification_task` | `critical_q` | replaces sync SMTP |

**Claude Code / Codex prompt:**

```
FINANCEOPS — INFRASTRUCTURE: CELERY ASYNC JOBS FOR ALL MODULES

Repo: D:\finos\backend\
Run this prompt ONE MODULE AT A TIME, starting with Notifications (most critical).

CONTEXT: Read first:
  - financeops/tasks/celery_app.py (queues: critical_q, high_q, normal_q, low_q)
  - financeops/modules/accounting_layer/tasks/beat_tasks.py (pattern to follow)
  - financeops/modules/board_pack_generator/tasks.py (another example)
  - Each target module's application/run_service.py

HARD CONSTRAINTS:
  - from financeops.tasks.celery_app import celery_app (always)
  - Tasks must be idempotent — safe to retry
  - Tasks receive primitive args only (UUIDs as strings, not ORM objects)
  - All DB access inside task: use get_async_session()

FOR EACH MODULE, create tasks.py with pattern:
  @celery_app.task(queue='<queue>', bind=True, max_retries=3)
  def run_{module}_task(self, run_id: str, tenant_id: str) -> None:
      try:
          # run service method
      except Exception as exc:
          raise self.retry(exc=exc, countdown=60)

NOTIFICATIONS SPECIFICALLY (critical_q, max_retries=5):
  - Replace synchronous SMTP with aiosmtplib
  - Add aiosmtplib to pyproject.toml
  - Task: send_notification_task(notification_event_id, tenant_id)

ROUTE CHANGES for each module:
  - Route now calls: task.delay(str(run_id), str(tenant_id))
  - Returns: HTTP 202 {"task_id": task.id, "status": "queued"}
  - Add: GET /{module}/runs/{id}/status → returns current run status from DB

TESTS — tests/integration/test_celery_tasks.py:
- test_gl_recon_task_completes_successfully
- test_notification_task_uses_async_smtp_not_blocking
- test_all_new_tasks_registered_in_celery_app
- test_task_idempotent_on_retry
0 warnings, 0 skips.
```

---

### 4.2 — Audit Trail: Global middleware + Accounting beat tasks

**File:** `financeops/middleware/audit_middleware.py` (create)

**Problem 1:** Only `accounting_layer` writes to `AuditTrail`. 20+ modules make financial mutations with zero audit capture.

**Problem 2:** All 3 Accounting Layer beat tasks (`approval_reminder_task`, `sla_breach_check_task`, `daily_digest_task`) return `{"status": "ok"}` — never actually execute.

**Fix — Audit Middleware:**
- FastAPI `BaseHTTPMiddleware` fires after all non-GET requests with response status 200-299
- Extracts `user_id`/`tenant_id` from JWT, `resource_type` from URL path, `resource_id` from path params
- Inserts `AuditTrail` row (INSERT-ONLY) with chain hash: `SHA-256(prev_chain_hash + new_row_hash)`
- Fire-and-forget via `asyncio.create_task()` — does not block response
- Exempt: `/health`, `/health/deep`, `/auth/token/refresh`

**Fix — Beat Tasks:**
- `approval_reminder_task`: query pending `AccountingJVApproval` rows > 1h old → `send_notification_task.delay()`
- `sla_breach_check_task`: query breached `ApprovalSLATimer` rows → INSERT `BREACHED` status row → escalate to L+1
- `daily_digest_task`: aggregate pending JVs, SLA breaches, recon exceptions per tenant → send digest

**Claude Code / Codex prompt:**

```
FINANCEOPS — INFRASTRUCTURE: AUDIT TRAIL MIDDLEWARE + BEAT TASKS

Repo: D:\finos\backend\

CONTEXT: Read first:
  - financeops/db/models/audit_trail.py (AuditTrail — INSERT-ONLY)
  - financeops/modules/accounting_layer/application/audit_service.py
  - financeops/main.py (middleware registration order)
  - financeops/modules/auth/dependencies.py (get current user from request)
  - financeops/modules/accounting_layer/tasks/beat_tasks.py (replace stubs here)

TASK — PART 1: Audit Middleware:
1. Create financeops/middleware/audit_middleware.py:
   class AuditMiddleware(BaseHTTPMiddleware):
     async def dispatch(self, request, call_next):
       response = await call_next(request)
       if response.status_code in range(200,300) and request.method != "GET":
         asyncio.create_task(write_audit(request, response))
       return response

   write_audit():
   - Extract user_id, tenant_id from JWT Authorization header
   - Extract resource_type from URL path segments
   - Extract resource_id from path params if present
   - chain_hash = SHA-256(prev_chain_hash + SHA-256(request_body))
   - INSERT AuditTrail row (INSERT-ONLY) — log error if fails, do not raise

2. Register AuditMiddleware in main.py AFTER auth middleware.
3. Exempt: /health, /health/deep, /auth/token/refresh

TASK — PART 2: Replace beat task stubs:
4. approval_reminder_task():
   - Query AccountingJVApproval WHERE status=PENDING AND created_at < now()-1h
   - For each: send_notification_task.delay(event_type="JV_APPROVAL_REMINDER", ...)
5. sla_breach_check_task():
   - Query ApprovalSLATimer WHERE deadline < now() AND status != BREACHED
   - INSERT new status row BREACHED (append-only)
   - send_notification_task.delay(event_type="SLA_BREACH", escalate_to=next_approver)
6. daily_digest_task():
   - Per tenant: count pending JVs + SLA breaches + open recon exceptions
   - send_notification_task.delay(event_type="DAILY_DIGEST", summary={...})

TESTS:
- test_audit_middleware_writes_on_post_200
- test_audit_middleware_skips_on_get
- test_audit_middleware_skips_on_4xx_5xx
- test_audit_chain_hash_is_sequential
- test_approval_reminder_task_sends_notification
- test_sla_breach_task_inserts_breached_row
- test_daily_digest_aggregates_per_tenant
0 warnings, 0 skips.
```

---

## Phase 5 — AI Layer + Board Pack Export
**Week 5 · P0 blockers resolved: 3 · Modules: AI CFO Layer, Narrative Engine, Board Pack Generator**

---

### 5.1 — AI CFO: Wire Claude API

**File:** `financeops/modules/ai_cfo_layer/application/narrative_service.py`

**Problem:** Zero LLM calls anywhere. `narrative_service.py` builds sentences via string formatting. `recommendation_service.py` uses hardcoded if-else rules. "AI CFO" is a mislabelled rules engine.

> **Decision required before implementing:** Choose Option A or Option B.
> - **Option A (recommended):** Wire Claude API — ~2-3 days, real AI output, incurs API costs
> - **Option B:** Rename to "Insights Engine (rule-based)" — ~1 day, honest, no API cost

**Claude Code / Codex prompt (Option A — wire Claude API):**

```
FINANCEOPS — AI LAYER: WIRE CLAUDE API TO AI CFO MODULE

Repo: D:\finos\backend\
ANTHROPIC_API_KEY is already in .env — do not hardcode it.

CONTEXT: Read first:
  - financeops/modules/ai_cfo_layer/application/narrative_service.py
  - financeops/modules/ai_cfo_layer/application/recommendation_service.py
  - financeops/modules/ai_cfo_layer/api/routes.py
  - financeops/tasks/celery_app.py

HARD CONSTRAINTS:
  - Use httpx.AsyncClient — not requests, not anthropic SDK sync client
  - All financial amounts in prompts: format as Decimal strings, never float
  - API calls must be in Celery tasks — never in HTTP request thread
  - Log: prompt_tokens, completion_tokens, model to AiCfoLedger table (INSERT-ONLY)
  - Validate LLM response: check all mentioned numbers exist in source data

TASK:
1. Create financeops/modules/ai_cfo_layer/infrastructure/claude_client.py:
   class ClaudeClient:
     async def complete(self, system: str, user: str, max_tokens: int = 1000) -> str
   Model: claude-haiku-4-5-20251001
   Endpoint: https://api.anthropic.com/v1/messages
   Headers: x-api-key, anthropic-version: 2023-06-01

2. Replace narrative_service.py string templates with:
   - Build structured prompt from KPI/variance data
   - Call claude_client.complete() inside Celery task
   - Validate response (all numbers must reference source data)
   - INSERT NarrativeBlock (INSERT-ONLY): llm_model, token_count, generated_at

3. Replace recommendation_service.py hardcoded rules with:
   - Prompt: "Given these anomalies and variances, what are the top 3 CFO actions?"
   - Parse structured JSON response from Claude
   - Validate each recommendation references a real data point

4. Create AiCfoLedger table in financeops/db/models/ai_cfo.py:
   (tenant_id, feature, model, prompt_tokens, completion_tokens, cost_usd, created_at)
   INSERT-ONLY. Alembic migration: sequential, 32-char max.

5. Raise at startup if ANTHROPIC_API_KEY missing from settings.

TESTS — tests/integration/test_ai_cfo.py:
- test_narrative_service_calls_claude_api (mock httpx)
- test_recommendation_returns_structured_json
- test_llm_cost_tracked_in_ledger
- test_invalid_api_key_raises_at_startup
0 warnings, 0 skips.
```

---

### 5.2 — Board Pack: Implement real PDF + Excel export

**File:** `financeops/modules/board_pack_generator/application/export_service.py`

**Problem:** Export service exists but generates no actual documents. All export endpoints return placeholder data.

**Fix:** Use `WeasyPrint` (HTML→PDF) and `openpyxl` for Excel. Upload to R2. Return signed download URLs (15-minute expiry).

**Claude Code / Codex prompt:**

```
FINANCEOPS — FUNCTIONAL: BOARD PACK REAL PDF + EXCEL EXPORT

Repo: D:\finos\backend\
Add to pyproject.toml if not present: weasyprint, openpyxl

CONTEXT: Read first:
  - financeops/modules/board_pack_generator/application/export_service.py
  - financeops/modules/board_pack_generator/domain/enums.py
  - financeops/storage/r2.py (upload to R2)
  - financeops/db/models/board_pack_generator.py (BoardPackGeneratorArtifact — INSERT-ONLY)

PDF EXPORT:
1. Build Jinja2 HTML template for board pack:
   - Cover page: org name, period, generated_at, CONFIDENTIAL watermark
   - Per section: heading, metric table, narrative text, anomaly callout boxes
   - Footer: page numbers
2. weasyprint.HTML(string=html).write_pdf() → bytes
3. Upload to R2: get_storage().upload_file(key, data)
4. INSERT BoardPackGeneratorArtifact (INSERT-ONLY): r2_key, format=PDF, size_bytes

EXCEL EXPORT:
5. openpyxl workbook:
   - Sheet 1: Executive Summary (key metrics)
   - Sheet per section: data table with variance columns
   - Header fill: #2E4057, font white, freeze top row
   - Financial columns: number format ₹#,##0.00
6. Upload to R2, INSERT artifact record

ROUTES:
7. POST /board-pack/runs/{id}/export → triggers export Celery task → HTTP 202
8. GET /board-pack/runs/{id}/export/{artifact_id} → returns signed R2 URL (15 min TTL)
   Must be signed URL — NOT a public R2 URL.

TESTS — tests/integration/test_board_pack_export.py:
- test_pdf_export_produces_valid_pdf_bytes
- test_excel_export_produces_valid_xlsx
- test_export_artifact_uploaded_to_r2
- test_download_url_is_signed_not_public
0 warnings, 0 skips.
```

---

## Phase 6 — Users & Roles CRUD + P1 Route Gaps
**Weeks 5–6 · Modules: Users & Roles, Auth**

---

### 6.1 — Users & Roles: Add missing CRUD routes + fix async invite

**File:** `financeops/modules/users/api/routes.py`

**Current state:** All service methods exist. Missing routes: `GET /users`, `POST /users`, `PATCH /users/{id}/role`, `DELETE /users/{id}`. User invite email is synchronous (blocks async route). Platform admin can escalate to `platform_owner` with no server-side guard.

**Claude Code / Codex prompt:**

```
FINANCEOPS — USERS: CRUD ROUTES + RBAC + ASYNC INVITE

Repo: D:\finos\backend\

CONTEXT: Read first:
  - financeops/modules/users/application/user_service.py (all methods already exist)
  - financeops/modules/users/api/routes.py (existing routes)
  - financeops/modules/auth/application/permission_matrix.py
  - financeops/db/models/iam.py

TASK:
1. Add missing routes to routes.py:
   GET    /users            → list_tenant_users()     — requires USERS_VIEW
   POST   /users            → create_user() (invite)  — requires USERS_INVITE
   PATCH  /users/{id}/role  → update_user_role()      — requires USERS_MANAGE_ROLES
   DELETE /users/{id}       → offboard_user()         — requires USERS_OFFBOARD
   GET    /users/{id}       → get_user()              — requires USERS_VIEW

2. Fix invite email — replace _send_invite_email_sync() blocking call with:
   send_notification_task.delay(event_type="USER_INVITED", user_id=str(new_user.id))

3. Fix role escalation: in CreatePlatformUserRequest handler add:
   if request.role == UserRole.PLATFORM_OWNER:
     raise HTTPException(403, "Cannot assign platform_owner via API")

4. Apply require_permission(Permission.USERS_VIEW) etc. to each route
   using existing RBAC dependency pattern from permission_matrix.py.

TESTS — tests/integration/test_user_management.py:
- test_get_users_list_as_admin
- test_invite_user_sends_async_notification_not_sync_smtp
- test_update_role_requires_permission
- test_cannot_assign_platform_owner_via_api
- test_offboard_user_revokes_sessions
0 warnings, 0 skips.
```

---

## Phase 7 — Test Coverage: All Financial Engines
**Weeks 6–7 · 18 modules · ~250 new tests**

18 modules have zero or skeleton tests. This phase writes real tests for every financial calculation.

**Test philosophy:**
- Assert on actual computed values — not just `200 OK` responses
- Every financial calculation needs edge case tests: zero, negative, Decimal precision, leap year, mid-period disposal
- Idempotency tests: run same operation twice, verify state unchanged
- RLS tests: verify tenant A cannot see tenant B's data

| Module | Test file | Min tests | Key assertions |
|---|---|---|---|
| GL/TB Recon | `test_gl_recon.py` | 20 | matching algo, variance calc, materiality |
| Bank Recon | `test_bank_recon.py` | 15 | 3-pass matching, net difference Decimal |
| GST Recon | `test_gst_recon.py` | 12 | ITC rules 36/37/38, rate validation |
| Payroll GL Norm. | `test_payroll_norm.py` | 15 | GL gen accuracy, statutory deductions |
| Payroll GL Recon. | `test_payroll_recon.py` | 15 | matching logic, timing differences |
| MIS Manager | `test_mis_manager.py` | 12 | snapshot accuracy, drift detection |
| Month-End Close | `test_month_end.py` | 10 | task dependency chain, period lock |
| Working Capital | `test_working_capital.py` | 10 | ratio calculations, Decimal |
| Consolidation | `test_consolidation.py` | 15 | IC elimination, minority interest |
| Fixed Assets | `test_fixed_assets.py` | 15 | SL/WDV/S32, disposal, impairment |
| Anomaly Engine | `test_anomaly_engine.py` | 12 | Z-score, MAPE, scoring composite |
| Board Pack | `test_board_pack.py` | 10 | section assembly, export formats |
| Budgeting | `test_budgeting.py` | 12 | variance calc, rollup accuracy |
| Forecasting | `test_forecasting.py` | 10 | growth compounding, period shift |
| Notifications | `test_notifications.py` | 10 | async SMTP, quiet hours, dedup |
| Scheduled Delivery | `test_scheduled_delivery.py` | 8 | idempotency, cron validation |
| Audit Trail | `test_audit_trail.py` | 8 | chain hash, tamper detection |
| AI CFO Layer | `test_ai_cfo.py` | 8 | Claude API mock, cost tracking |

**Claude Code / Codex prompt:**

```
FINANCEOPS — TESTS: FULL COVERAGE — ONE MODULE AT A TIME

Repo: D:\finos\backend\
Run this prompt once per module. Do NOT batch multiple modules.

CONTEXT: Read first for EVERY module:
  - tests/conftest.py (follow fixture patterns exactly)
  - tests/integration/test_accounting_layer_journals.py (best example of real tests)
  - The target module's application/*.py files
  - The target module's db/models/*.py

HARD CONSTRAINTS:
  - asyncio_default_test_loop_scope = "session" — never touch
  - WindowsSelectorEventLoopPolicy in conftest.py — never touch
  - filterwarnings = "error" — 0 warnings
  - No xfail, no skip, no pytest.mark.skip
  - Financial assertions: Decimal not float
    CORRECT:   assert result.amount == Decimal("1500.00")
    INCORRECT: assert result.amount == 1500.0
  - RLS: every test must set tenant context before DB queries
    Use existing set_rls_context(db, tenant_id) fixture
  - Test DB: localhost:5433, financeops_test / testpassword

TEST STRUCTURE TEMPLATE:
  class TestModuleName:
    async def test_happy_path(self, db, tenant):
      # arrange: insert test data via direct DB inserts (not HTTP)
      # act: call service method directly (not HTTP client)
      # assert: check exact computed Decimal values

    async def test_edge_case_zero(self, db, tenant): ...
    async def test_edge_case_decimal_precision(self, db, tenant): ...
    async def test_idempotency(self, db, tenant): ...
    async def test_rls_tenant_isolation(self, db, tenant_a, tenant_b): ...

PROCEDURE:
  1. Write all tests for the target module
  2. Run: pytest tests/integration/test_{module}.py -v
  3. Confirm: 0 failures, 0 warnings, 0 skips
  4. Only then move to next module

START WITH: GL/TB Recon (test_gl_recon.py) — 20 tests minimum.
```

---

## Phase 8 — Indian Compliance Rules + Final Cleanup
**Week 8 · Modules: All**

---

### 8.1 — Indian compliance rules

**Claude Code / Codex prompt:**

```
FINANCEOPS — INDIAN COMPLIANCE RULES

Repo: D:\finos\backend\

TASK 1 — Org Setup default timezone:
  In create_org_entity(), set default timezone = "Asia/Kolkata" not "UTC".
  Alembic migration: ALTER COLUMN default_timezone SET DEFAULT 'Asia/Kolkata'.

TASK 2 — GSTIN state code fix:
  In financeops/utils/gstin.py, update regex:
    Valid pattern: ^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$
    Valid state codes: 01–37 only (add explicit range check).
    Test: validate_gstin("00AAAAA0000A1Z5") must return False.

TASK 3 — Payroll statutory deductions:
  In payroll_gl_norm, create application/statutory_deduction_service.py:
  - PF employer: Decimal("0.12") of basic, cap Decimal("1800.00")/month
  - ESI employer: Decimal("0.0325"), employee: Decimal("0.0075")
    Applicable ONLY when gross <= Decimal("21000.00")
  - TDS: compute per current IT Act slab (hardcode FY2025-26 slabs as constants)
  All amounts: Decimal. No float anywhere.

TASK 4 — Working Capital Indian financial year:
  DSO/DPO must use April–March year, not Jan–Dec.
  Add helper:
    def financial_year_start(d: date) -> date:
      return date(d.year, 4, 1) if d.month >= 4 else date(d.year-1, 4, 1)
  Use in DSO = (AR / Revenue) * 365 calculation.

TESTS:
- test_gstin_state_code_00_rejected
- test_gstin_state_code_38_valid
- test_pf_employer_capped_at_1800
- test_esi_not_applicable_above_21000_gross
- test_dso_uses_indian_financial_year_not_calendar
0 warnings, 0 skips.
```

---

### 8.2 — ERP Integration cleanup + permission matrix validation + indexes

**Claude Code / Codex prompt:**

```
FINANCEOPS — CLEANUP: ERP INTEGRATION + PERMISSION MATRIX + DB INDEXES

Repo: D:\finos\backend\

TASK 1 — ERP Integration module resolution:
  rg -r "erp_integration" financeops/ --include="*.py"
  If only referenced within its own directory (not imported by other modules):
    → Delete financeops/modules/erp_integration/ entirely
    → Add drop-table Alembic migration if its tables were ever applied
  If referenced by other modules:
    → Merge unique functionality into erp_sync module
    → Delete the duplicate module after merge

TASK 2 — Permission matrix startup validation:
  In financeops/modules/auth/application/permission_matrix.py:
  Add validate_permission_matrix() called at app startup (add to main.py lifespan):
  - Iterate all permissions, assert no duplicate keys, no None values
  - Raise ValueError("Invalid permission matrix key: {key}") if found
  - Log: f"Permission matrix validated: {count} permissions OK"

TASK 3 — Missing DB indexes:
  Check for missing (tenant_id, created_at) composite indexes on:
  journal_entries, recon_sessions, bank_transactions, gst_returns, audit_trail, erp_sync_jobs
  Command: SELECT indexname, tablename FROM pg_indexes WHERE tablename IN (...) ORDER BY tablename;
  Add Alembic migration for any missing indexes. Sequential numbering.

TASK 4 — Budget approval workflow:
  Add status transitions to BudgetVersion:
    draft → submitted → cfo_approved → board_approved
  Add routes: POST /budgets/{id}/submit, POST /budgets/{id}/approve
  Requires permission: CFO_APPROVER.
  Each transition: INSERT new BudgetVersionStatusEvent (INSERT-ONLY).

TESTS:
- test_permission_matrix_validates_at_startup
- test_budget_approval_draft_to_submitted
- test_budget_approval_requires_cfo_permission
0 warnings, 0 skips.
```

---

## Pre-Launch Checklist

Run after all 8 phases complete. Every item must be confirmed before onboarding a real customer.

| # | Check | How to verify | Phase |
|---|---|---|---|
| 1 | pytest: 0 failures, 0 warnings, 0 skips | `pytest --tb=short -q` | All |
| 2 | Password change revokes all sessions | `test_password_change_revokes_old_refresh_token` | 1 |
| 3 | MFA enforced on all protected endpoints | `test_new_user_blocked_until_mfa_complete` | 1 |
| 4 | Forgot-password rate-limited | `test_forgot_password_rate_limited_after_3_attempts` | 1 |
| 5 | Webhook deliveries signed with HMAC | `test_webhook_delivery_includes_hmac_header` | 1 |
| 6 | COA confirm idempotent | `test_confirm_twice_same_batch_idempotent` | 2 |
| 7 | ERP sync publish transactional | `test_publish_atomicity_rollback_on_sync_run_failure` | 2 |
| 8 | Incomplete org blocked from financial modules | `test_incomplete_org_blocked_from_financial_module` | 2 |
| 9 | Bank recon GL matching works | `test_exact_match_same_day_same_amount` | 3 |
| 10 | GST ITC rules 36/37/38 implemented | `test_itc_rule_36_only_2b_invoices_eligible` | 3 |
| 11 | IT Act Section 32 depreciation works | `test_section_32_full_depreciation_in_acquisition_year` | 3 |
| 12 | Working Capital uses real GL data | `test_wc_raises_error_not_dummy_values_when_no_gl` | 3 |
| 13 | Celery tasks exist for all heavy compute | `test_all_new_tasks_registered_in_celery_app` | 4 |
| 14 | Audit trail writes on all mutations | `test_audit_middleware_writes_on_post_200` | 4 |
| 15 | Accounting beat tasks actually execute | `test_approval_reminder_task_sends_notification` | 4 |
| 16 | AI CFO calls LLM (or honestly labelled) | `test_narrative_service_calls_claude_api` | 5 |
| 17 | Board Pack exports real PDF and Excel | `test_pdf_export_produces_valid_pdf_bytes` | 5 |
| 18 | User invite is async (not blocking SMTP) | `test_invite_user_sends_async_notification` | 6 |
| 19 | GSTIN state code 00 rejected | `test_gstin_state_code_00_rejected` | 8 |
| 20 | PF/ESI calculations correct | `test_pf_employer_capped_at_1800` | 8 |
| 21 | ERP Integration module conflict resolved | `rg 'from financeops.modules.erp_integration'` returns nothing | 8 |

---

## Platform State: Baseline vs Target

| Metric | Current (v3.0.0) | Target (post all phases) |
|---|---|---|
| Git tag | v3.0.0 | v4.0.0 |
| Migration head | `0101_accounting_rbac_seed_final` | ~`0125` (+24 new migrations) |
| Tests passing | 2,527 | 2,527 + ~250 new = 2,775+ |
| P0 blockers | 21 | 0 |
| Modules complete | 5 of 26 | 22+ of 26 |
| Modules with 0 tests | 18 | 0 |
| Celery tasks real | ~4 | 20+ |
| LLM calls in AI layer | 0 | AI CFO + Narrative wired |
| Audit trail coverage | 1 module | All 26 modules |

---

*Finqor (FinanceOps) — Implementation Plan v1.0 — April 2026*  
*`D:\finos\` · Python 3.11 · FastAPI · PostgreSQL 16 + RLS · CONFIDENTIAL*
