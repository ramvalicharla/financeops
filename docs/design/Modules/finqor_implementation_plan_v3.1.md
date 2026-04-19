# Finqor (FinanceOps) — Backend Implementation Plan v3.1
### Full Fix Roadmap · 21 P0 Blockers + P1 Gaps · 8 Phases · 8 Weeks
**Repo:** `D:\finos\` · **Stack:** Python 3.11, FastAPI, PostgreSQL 16 + RLS, Celery, Redis  
**Baseline:** v3.0.0 · Migration head: `0101_accounting_rbac_seed_final` · Tests: 2527 passing

> **v3.1 changes from v2.0:**
> - Fixed GSTIN state code range: `01–37` → `01–38` (Ladakh, added post-2019 bifurcation)
> - Added Bank Recon O(n²) index-dict fix for datasets > 1,000 transactions
> - Added GST rate master empty-table guard (`GstRateMasterNotSeededError`)
> - Added Pattern H: Celery migration checklist per module
> - Added test tier split: P0-critical (must ship) vs P1-deferred (post-launch ok)
> - Clarified: Celery already runs in this codebase — Phase 4 extends it, does not introduce it
> - Execution prompt updated: instructs agent that Patterns A–H are defined in the loaded document
> - Pattern C split: task-level runs module tests only; full suite runs once per phase (Pattern C-Phase)

---

## Hard Constraints — NEVER Violate

These apply to every single task in this document. Read before any implementation.

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
| Migration naming | Format: `{NNNN}_{description}.py` e.g. `0102_add_mfa_setup_complete.py` |
| Tests | No skipped tests, no xfail markers, 0 warnings, 0 failures — run pytest and confirm |
| Search tool | `rg` not `grep` |
| Idempotency | All POST/PUT/PATCH endpoints mutating financial data MUST accept `Idempotency-Key` header and store it with response for 24h |
| Delays | Never use `asyncio.sleep()` in an HTTP route — only in Celery tasks |

---

## Standard Patterns — Apply to Every Task

These patterns repeat in every prompt. Read once, apply everywhere.

### Pattern A — Mutability detection (before any model edit)

```
DETERMINE MUTABILITY of [ModelName]:
  rg "class [ModelName]" financeops/db/models/ --include="*.py" -l
  Open the file and check:
  1. Does the model have __table_args__ with a comment "append-only" or "insert-only"? → APPEND-ONLY
  2. Does it have only created_at (no updated_at)? → likely APPEND-ONLY
  3. Does it have updated_at or is_active columns? → likely MUTABLE
  4. Search: rg "@event.listens_for([ModelName]" financeops/ — if found, UPDATE is tracked
  Decision:
    MUTABLE   → UPDATE allowed
    APPEND-ONLY → INSERT new status/event row only, never UPDATE
```

### Pattern B — Rollback instructions (every task)

```
IF YOU CANNOT COMPLETE THIS TASK:
  1. Run: git diff --name-only to list all files you have changed
  2. Revert each changed file: git checkout -- <filepath>
  3. If you created new migrations: delete the file and run alembic history to confirm head is unchanged
  4. State exactly which step failed and why with the full error message
  5. Do not leave partial migrations, half-written tests, or broken imports
  6. Do not commit anything until the full task is passing
```

### Pattern C — Completion validation (every task)

```
BEFORE DECLARING THIS TASK COMPLETE:
  1. Run: pytest tests/integration/test_[module].py -v
  2. Output must show: "X passed, 0 failed, 0 warnings, 0 skipped"
  3. If any test fails: fix before proceeding — do not mark complete

  Do NOT run the full suite after every task.
  Full suite runs happen ONCE at the end of each phase (see Pattern C-Phase below).
```

### Pattern C-Phase — Full suite validation (end of every phase)

```
BEFORE DECLARING THIS PHASE COMPLETE:
  1. Confirm all tasks in the phase have passed their own module tests
  2. Run: pytest --tb=short -q
  3. Full suite must show: 2527+ passed, 0 failed, 0 warnings, 0 skipped
  4. If regressions appear from a previous module: fix before declaring phase done
  5. Tag the phase complete in git: git tag phase-{N}-complete
  6. Run: python scripts/take_clean_backup.py
  7. State: "Phase N complete. Baseline is now X tests passing."

NOTE: Do NOT use -n auto flag. The async session fixtures in this 
codebase are not safe for parallel test execution. All full-suite 
runs use sequential mode only.

```

### Pattern D — Migration creation

```
MIGRATION STEPS:
  1. alembic revision --autogenerate -m "<description>"
  2. Rename generated file to: {next_sequential_number:04d}_{description}.py
     Example: 0102_add_mfa_setup_complete_to_iam_user.py
  3. Open the file and verify: revision ID <= 32 characters
  4. Check: only ONE head exists after: alembic heads
  5. Run: alembic upgrade head (on test DB)
  6. Confirm: alembic current shows new head
```

### Pattern E — Celery task registration verification

```
VERIFY CELERY DISCOVERY:
  1. After creating tasks.py, check it is imported:
     rg "import.*tasks" financeops/tasks/__init__.py
     If missing: add import to financeops/tasks/__init__.py
  2. Start Celery worker in dry-run: celery -A financeops.tasks.celery_app inspect registered
  3. Confirm new task name appears in the output
  4. If not discovered: check __init__.py imports and module path
```

### Pattern F — Standard exception definitions

```
EXCEPTION LOCATION: financeops/modules/{module_name}/domain/exceptions.py

Base pattern:
  class {Module}Error(Exception):
      pass

  class {SpecificError}({Module}Error):
      def __init__(self, message: str, **context):
          self.context = context
          super().__init__(message)

Example for Consolidation:
  class ConsolidationError(Exception):
      pass

  class MissingSourceEntityError(ConsolidationError):
      def __init__(self, missing_ids: list):
          self.missing_ids = missing_ids
          super().__init__(f"Missing source entities: {missing_ids}")

FastAPI handler — add to routes.py:
  @router.exception_handler(MissingSourceEntityError)
  async def missing_entity_handler(request, exc):
      return JSONResponse(status_code=422,
          content={"detail": str(exc), "missing_ids": [str(i) for i in exc.missing_ids]})
```

### Pattern G — Standard test fixtures

```
ASSUMED FIXTURES (from tests/conftest.py — verify they exist before using):
  db          → AsyncSession with RLS context set
  tenant      → TenantContext(tenant_id=UUID, entity_id=UUID)
  tenant_a    → first tenant (for isolation tests)
  tenant_b    → second tenant (for isolation tests)
  superuser   → IamUser with platform_admin role
  org_user    → IamUser with org-level role

If any fixture is missing for the target module:
  Copy pattern from: tests/integration/test_accounting_layer_journals.py
  Do not invent new fixture patterns — follow existing ones exactly.

RLS context — set before every DB query in tests:
  await set_rls_context(db, str(tenant.tenant_id))
```

### Pattern H — Celery migration checklist (for all 8 new Celery modules)

> **Context:** Celery already runs in this codebase with `critical_q, high_q, normal_q, low_q`
> queues, beat schedule, and live tasks (payments, board pack, ERP webhooks). Phase 4 **extends**
> this existing infrastructure — it does not introduce Celery from scratch. The risk is not Celery
> itself but service methods not written with idempotency in mind.

```
BEFORE creating a Celery task for an existing synchronous service, run this checklist:

CHECKLIST — CELERY MIGRATION FOR [MODULE NAME]:

1. IDEMPOTENCY CHECK
   Call the service method twice with the same run_id.
   Does it produce duplicate rows? Fix: add check-before-insert in the service.
   Does it raise on second call? Fix: catch the error, return existing result.
   Celery tasks ARE retried on failure — the underlying service MUST be safe to call twice.

2. STATE MACHINE CHECK
   Does the run/session model have a status column?
   If status is already RUNNING or COMPLETE when task fires: skip and log, do not re-run.
   Prevents duplicate execution if Celery retries before the first run completes.
   Pattern:
     run = await load_run(run_id, db)
     if run.status in (RunStatus.RUNNING, RunStatus.COMPLETE):
         logger.info(f"Run {run_id} already {run.status}, skipping.")
         return

3. DB SESSION SCOPE
   Service was written for HTTP request scope (one session, request-scoped commit).
   In a Celery task: create a FRESH session inside the task function, not outside.
     async def _run():
         async with get_async_session() as db:
             await set_rls_context(db, tenant_id)
             await service.execute(UUID(run_id), UUID(tenant_id))
     asyncio.run(_run())
   Never pass an HTTP request DB session into a Celery task.

4. ERROR HANDLING
   On any exception:
     - INSERT a FAILED status row (append-only) with error_message
     - Log full traceback to Sentry (use existing Sentry setup)
     - Raise self.retry(exc=exc, countdown=60) to let Celery retry
   After max_retries exhausted:
     - INSERT a DEAD_LETTER status row — do not silently drop

5. TIMEOUTS — set per task based on expected data volume
   Small runs (< 1k rows):  soft_time_limit=120,  time_limit=180
   Normal runs (< 10k rows): soft_time_limit=300,  time_limit=360
   Large runs (> 10k rows):  soft_time_limit=900,  time_limit=960
   Notifications:            soft_time_limit=30,   time_limit=60
   Usage: @celery_app.task(queue='normal_q', soft_time_limit=300, time_limit=360)

6. ROUTE CHANGE — document for frontend team
   Before: POST /runs → 200 {result}
   After:  POST /runs → 202 {"task_id": task.id, "status": "queued", "poll_url": "/runs/{id}/status"}
   Add:    GET  /runs/{id}/status → read status from DB → return current run state
   Frontend must handle 202 and poll /status — communicate this change before deploying.
```


---

## Master P0 Blocker Index

21 P0 blockers across 26 modules.

| # | Blocker | Module | Phase | Category |
|---|---|---|---|---|---|
| 1 | `change_password()` does not revoke existing sessions | Auth & IAM | Phase 1 | Security |
| 2 | MFA completion not enforced before protected endpoint access | Auth & IAM | Phase 1 | Security |
| 3 | Forgot-password has no exponential backoff or CAPTCHA | Auth & IAM | Phase 1 | Security |
| 4 | Webhook delivery has no HMAC-SHA256 signature | Scheduled Delivery | Phase 1 | Security |
| 5 | COA confirm endpoint not idempotent — double-submit = duplicate accounts | Chart of Accounts | Phase 2 | Data Integrity |
| 6 | ERP sync `publish()` not transactional — GL can post with sync incomplete | ERP Sync | Phase 2 | Data Integrity |
| 7 | `org_setup_complete` flag not enforced on downstream modules | Org Setup | Phase 2 | Data Integrity |
| 8 | Consolidation crashes on missing source entity (uncaught `ValueError`) | Consolidation | Phase 2 | Data Integrity | P0 |
| 9 | Scheduled delivery no idempotency check — Celery retry = duplicate sends | Scheduled Delivery | Phase 2 | Data Integrity |
| 10 | Cron expression not validated at schedule creation | Scheduled Delivery | Phase 2 | Data Integrity |
| 11 | `run_bank_reconciliation()` creates only `bank_only` breaks — no GL match | Bank Reconciliation | Phase 3 | Compliance |
| 12 | GST Recon has no portal import and no invoice-level matching | GST Reconciliation | Phase 3 | Compliance | P0 |
| 13 | IT Act Section 32 block depreciation not implemented in `get_depreciation()` | Fixed Assets | Phase 3 | Compliance |
| 14 | Audit trail writes missing in 20+ modules | Audit Trail | Phase 4 | Compliance |
| 15 | Working Capital serves hard-coded dummy data (`AR=₹1M`) to real tenants | Working Capital | Phase 3 | Functional | P0 |
| 16 | Consolidation board-pack/risk/anomaly endpoints return hardcoded stubs | Consolidation | Phase 3 | Functional |
| 17 | AI CFO Layer has zero LLM calls — pure if-else rules, not AI | AI CFO Layer | Phase 5 | Functional | P1 |
| 18 | Narrative Engine executive summary is a single hardcoded string | Narrative Engine | Phase 5 | Functional |
| 19 | Board Pack PDF/Excel export is an unimplemented stub | Board Pack Generator | Phase 5 | Functional | P1 |
| 20 | All 3 Accounting Layer beat tasks return `{"status":"ok"}` — never execute | Accounting Layer | Phase 4 | Functional |
| 21 | 18 of 26 modules have zero meaningful tests | Cross-cutting | Phase 6–8 | Quality |

---

## Phase 1 — Security Hardening
**Week 1 · P0 blockers resolved: 4 · Modules: Auth & IAM, Scheduled Delivery**

Fix all security P0s first. A platform with these auth gaps cannot onboard any customer.

---

### 1.1 — Auth: Revoke sessions on password change

**File:** `financeops/modules/auth/application/auth_service.py`

**Problem:**
- `change_password()` updates the password hash but leaves all existing `IamSession` rows active
- If a credential is compromised and the user resets, the attacker's session stays valid indefinitely

**Implementation steps:**
1. Use Pattern A to determine if `IamSession` is mutable or append-only
2. Implement `revoke_all_sessions(user_id, db)` helper in `auth_service.py`
3. Wrap password save + session revocation in `async with db.begin()`
4. Return new access+refresh token pair so the current user stays logged in

**Claude Code / Codex prompt:**

```
FINANCEOPS — SECURITY FIX: SESSION REVOCATION ON PASSWORD CHANGE

Repo: D:\finos\backend\
HARD CONSTRAINTS: Python 3.11, Decimal not float, no skipped tests,
  asyncio_default_test_loop_scope = "session", filterwarnings = "error"
  Celery: from financeops.tasks.celery_app import celery_app
  DB session: get_async_session in financeops/db/session.py

CONTEXT: Read these files COMPLETELY before writing any code:
  - financeops/modules/auth/application/auth_service.py
  - financeops/db/models/iam.py
  - financeops/modules/auth/api/routes.py

STEP 1 — DETERMINE IamSession MUTABILITY:
  rg "class IamSession" financeops/db/models/iam.py
  Check the model:
  - Has __table_args__ with "append-only" or "insert-only" comment? → APPEND-ONLY
  - Has only created_at, no updated_at? → APPEND-ONLY
  - Has updated_at or is_active columns? → MUTABLE
  - rg "@event.listens_for(IamSession" financeops/ → if found, UPDATE is tracked
  State your finding before proceeding.

STEP 2 — IMPLEMENT revoke_all_sessions():
  Add to auth_service.py:
  async def revoke_all_sessions(user_id: UUID, db: AsyncSession) -> None:
    IF IamSession is MUTABLE:
      await db.execute(
        update(IamSession)
        .where(IamSession.user_id == user_id, IamSession.is_active == True)
        .values(is_active=False)
      )
    IF IamSession is APPEND-ONLY:
      INSERT a new IamSessionRevocationEvent row (INSERT-ONLY) with user_id + revoked_at

STEP 3 — CALL from change_password():
  async with db.begin():
    # 1. hash and save new password
    # 2. call await revoke_all_sessions(user_id, db)
    # 3. issue new token pair
  return new token pair to caller

STEP 4 — ACCEPT Idempotency-Key header:
  Add Idempotency-Key: str = Header(None) to the change_password route.
  If same key seen within 24h: return cached response without re-executing.

IF YOU CANNOT COMPLETE THIS TASK:
  1. git diff --name-only → list changed files
  2. git checkout -- <each file> → revert all changes
  3. Delete any new migration files created
  4. State the exact step that failed with the full error message
  5. Do not commit partial work

BEFORE DECLARING COMPLETE:
  Run: pytest tests/integration/test_auth_security.py -v
  Output must show: "X passed, 0 failed, 0 warnings, 0 skipped"
  Run: pytest --tb=short -q → full suite must still show 2527+ passed, 0 failed

TESTS — write in tests/integration/test_auth_security.py:
  FIXTURES NEEDED (check conftest.py — copy pattern from test_accounting_layer_journals.py if missing):
    db, tenant, org_user

  Tests:
  - test_password_change_revokes_old_refresh_token
  - test_password_change_returns_new_token_pair
  - test_old_access_token_rejected_after_password_change
  - test_password_change_idempotent_with_same_idempotency_key
  All: 0 warnings, 0 skips. Assert on exact behaviour, not just status codes.
```

---

### 1.2 — Auth: Enforce MFA completion middleware

**File:** `financeops/modules/auth/dependencies.py`

**Problem:**
- `force_mfa_setup=True` is set on new users at registration
- No middleware or dependency checks `mfa_setup_complete` before allowing protected route access

**Implementation steps:**
1. Check if `IamUser.mfa_setup_complete` field exists — add it only if missing
2. Create `require_mfa_complete` FastAPI dependency
3. Apply to all routers except `/auth/*`, `/health`, `/health/deep`

**Claude Code / Codex prompt:**

```
FINANCEOPS — SECURITY FIX: ENFORCE MFA COMPLETION

Repo: D:\finos\backend\
HARD CONSTRAINTS: Python 3.11, filterwarnings = "error", asyncio scope = "session"

CONTEXT: Read COMPLETELY before writing:
  - financeops/modules/auth/application/auth_service.py
  - financeops/modules/auth/api/routes.py
  - financeops/main.py
  - financeops/db/models/iam.py

STEP 1 — CHECK FIELD EXISTS:
  rg "mfa_setup_complete" financeops/db/models/iam.py
  IF the field exists: skip to Step 2.
  IF the field does not exist:
    Add to IamUser model: mfa_setup_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    Create migration using Pattern D:
      Name: 0102_add_mfa_setup_complete_to_iam_user.py (adjust number to be next sequential)
      Max revision ID: 32 chars

STEP 2 — CREATE DEPENDENCY:
  In financeops/modules/auth/dependencies.py:
  async def require_mfa_complete(
      current_user: IamUser = Depends(get_current_user)
  ) -> IamUser:
      if current_user.force_mfa_setup and not current_user.mfa_setup_complete:
          raise HTTPException(status_code=403, detail="MFA_SETUP_REQUIRED")
      return current_user

STEP 3 — APPLY TO ROUTERS:
  In main.py, for every router EXCEPT /auth/*, /health, /health/deep:
  Add dependencies=[Depends(require_mfa_complete)] to router include.
  Do NOT add to: auth_router, health_router.

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B above)

BEFORE DECLARING COMPLETE: (see Pattern C above)

TESTS — tests/integration/test_mfa_enforcement.py:
  FIXTURES: db, tenant, org_user (check conftest.py)
  - test_new_user_with_force_mfa_blocked_on_protected_route
  - test_mfa_exempt_routes_accessible_without_mfa
  - test_user_with_mfa_complete_accesses_protected_route
  - test_user_without_force_mfa_not_blocked
  0 warnings, 0 skips.
```

---

### 1.3 — Auth: Rate limit forgot-password endpoint

**File:** `financeops/modules/auth/api/routes.py`

**Problem:** `POST /auth/forgot-password` accepts unlimited requests — email enumeration and inbox flooding risk.

**Note:** The delay on repeated attempts must be in a Celery task, NOT in the HTTP route. `asyncio.sleep()` in an HTTP route blocks the event loop for other requests.

**Claude Code / Codex prompt:**

```
FINANCEOPS — SECURITY FIX: RATE LIMIT FORGOT-PASSWORD

Repo: D:\finos\backend\
HARD CONSTRAINTS: SlowAPI route MUST have request: Request param. Python 3.11.
  NEVER use asyncio.sleep() in an HTTP route — only in Celery tasks.

CONTEXT: Read COMPLETELY:
  - financeops/modules/auth/api/routes.py
  - financeops/main.py (existing SlowAPI limiter instance — reuse it, do not create new)
  - financeops/db/models/iam.py (PasswordResetToken model)
  - financeops/modules/auth/application/auth_service.py

STEP 1 — VERIFY SlowAPI SETUP:
  rg "limiter" financeops/main.py
  Confirm the limiter instance name. Use the same instance — do not import a new one.

STEP 2 — ADD RATE LIMIT TO ROUTE:
  @router.post("/auth/forgot-password")
  @limiter.limit("3/15minutes")
  async def forgot_password(request: Request, body: ForgotPasswordRequest, ...):
  Note: request: Request MUST be the first parameter after self/cls.

STEP 3 — IDENTICAL RESPONSE:
  The route must return the EXACT same response body and status code
  whether the email exists in the DB or not.
  Correct:   return {"message": "If that email exists, a reset link has been sent."}
  Incorrect: return 404 if email not found (leaks valid emails)

STEP 4 — ATTEMPT TRACKING (Celery task, not route):
  Add reset_attempt_count (Integer, default=0) to PasswordResetToken.
  Migration: Pattern D. Name: 0103_add_reset_attempt_count_to_password_reset_token.py
  In the Celery email-sending task (NOT the HTTP route):
    if token.reset_attempt_count >= 3:
        await asyncio.sleep(30)  ← OK here, this is a Celery task not an HTTP route
    increment reset_attempt_count before sending

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_auth_rate_limit.py:
  - test_forgot_password_rate_limited_after_3_requests
  - test_forgot_password_returns_same_response_for_valid_email
  - test_forgot_password_returns_same_response_for_invalid_email
  0 warnings, 0 skips.
```

---

### 1.4 — Scheduled Delivery: HMAC webhook signature

**File:** `financeops/modules/scheduled_delivery/application/delivery_service.py`

**Problem:** Webhook deliveries sent with no signature — recipients cannot verify source.

**Claude Code / Codex prompt:**

```
FINANCEOPS — SECURITY FIX: WEBHOOK HMAC SIGNATURE

Repo: D:\finos\backend\

CONTEXT: Read COMPLETELY:
  - financeops/modules/scheduled_delivery/application/delivery_service.py
  - financeops/db/models/scheduled_delivery.py
  - financeops/modules/erp_sync/infrastructure/secret_store.py
    (use SAME encryption pattern for webhook_secret — do not invent a new one)

STEP 1 — DETERMINE DeliverySchedule MUTABILITY:
  Apply Pattern A to DeliverySchedule.
  webhook_secret is a config field → should be on a MUTABLE config table.
  If DeliveryLog is append-only → store signature in metadata JSONB only.

STEP 2 — ADD webhook_secret TO MODEL:
  Add webhook_secret: Mapped[Optional[str]] = mapped_column(String, nullable=True)
  Encrypt using same method as erp_sync secret_store.py (do not write new encryption).
  Migration: Pattern D. Name: 0104_add_webhook_secret_to_delivery_schedule.py

STEP 3 — SIGN OUTGOING WEBHOOKS:
  In delivery_service.py, when channel == WEBHOOK:
    if not schedule.webhook_secret:
        raise DeliveryConfigError("Webhook secret not configured. Cannot send unsigned webhook.")
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = hmac.new(
        schedule.webhook_secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    headers["X-Finqor-Signature"] = f"sha256={signature}"

STEP 4 — DEFINE EXCEPTION:
  In financeops/modules/scheduled_delivery/domain/exceptions.py:
  class ScheduledDeliveryError(Exception): pass
  class DeliveryConfigError(ScheduledDeliveryError):
      def __init__(self, message: str):
          super().__init__(message)

STEP 5 — STORE IN LOG:
  In DeliveryLog INSERT (append-only): include signature in metadata JSONB field.

STEP 6 — ACCEPT Idempotency-Key on trigger endpoint:
  POST /scheduled-delivery/schedules/{id}/trigger must accept Idempotency-Key header.

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_scheduled_delivery_webhook.py:
  - test_webhook_delivery_includes_x_finqor_signature_header
  - test_webhook_signature_is_valid_hmac_sha256
  - test_webhook_delivery_raises_if_no_secret_configured
  - test_recipient_can_verify_signature
  0 warnings, 0 skips.
```

---

## Phase 2 — Data Integrity Fixes
**Week 2 · P0 blockers resolved: 6 · Modules: COA, ERP Sync, Org Setup, Consolidation, Scheduled Delivery**

Six P0s that cause silent data corruption. Must all be fixed before any financial data flows through the system.

---

### 2.1 — COA: Make confirm endpoint idempotent

**File:** `financeops/modules/chart_of_accounts/application/coa_service.py`

**Problem:** `POST /coa/upload/{batch_id}/confirm` re-inserts `TenantCoaAccount` rows if called twice.

**Claude Code / Codex prompt:**

```
FINANCEOPS — DATA INTEGRITY: COA CONFIRM IDEMPOTENCY

Repo: D:\finos\backend\

CONTEXT: Read COMPLETELY:
  - financeops/modules/chart_of_accounts/api/routes.py
  - financeops/modules/chart_of_accounts/application/coa_service.py
  - financeops/db/models/coa.py

STEP 1 — DETERMINE MUTABILITY of CoaUploadBatch:
  Apply Pattern A. This is a config/workflow table — should be MUTABLE.

STEP 2 — ADD confirmation_status:
  Add to CoaUploadBatch: confirmation_status enum (PENDING/CONFIRMED), default PENDING.
  Migration: Pattern D. Name: 0105_add_confirmation_status_to_coa_upload_batch.py

STEP 3 — IDEMPOTENT confirm():
  async def confirm_upload(batch_id, tenant_id, db):
      async with db.begin():
          # SELECT FOR UPDATE to prevent race condition
          batch = await db.execute(
              select(CoaUploadBatch)
              .where(CoaUploadBatch.id == batch_id)
              .with_for_update()
          )
          if batch.confirmation_status == ConfirmationStatus.CONFIRMED:
              return existing_result  # idempotent — return without re-inserting
          # run insertion
          # set batch.confirmation_status = CONFIRMED

STEP 4 — DB UNIQUE CONSTRAINT:
  Add UniqueConstraint("tenant_id", "account_code") to TenantCoaAccount.
  In bulk insert: use INSERT ... ON CONFLICT (tenant_id, account_code) DO NOTHING.
  Migration: include in same migration as Step 2 or a sequential new one.

STEP 5 — ACCEPT Idempotency-Key on confirm route.

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_coa_idempotency.py:
  FIXTURES: db, tenant (check conftest.py)
  - test_confirm_twice_returns_same_result_without_duplicate_rows
  - test_confirm_concurrent_requests_no_duplicate_accounts
  - test_account_code_uniqueness_enforced_at_db_level
  0 warnings, 0 skips.
```

---

### 2.2 — ERP Sync: Wrap publish() in savepoint transaction

**File:** `financeops/modules/erp_sync/application/publish_service.py`

**Problem:** GL can be posted while sync run is marked incomplete — re-sync causes duplicate GL entries.

**Claude Code / Codex prompt:**

```
FINANCEOPS — DATA INTEGRITY: ERP SYNC TRANSACTIONAL PUBLISH

Repo: D:\finos\backend\

CONTEXT: Read COMPLETELY:
  - financeops/modules/erp_sync/application/publish_service.py
  - financeops/db/models/erp_sync.py
  - financeops/db/models/accounting_layer.py

STEP 1 — DETERMINE MUTABILITY:
  Apply Pattern A to: ExternalSyncRun, JournalEntry.
  State findings before proceeding.
  (Both are likely APPEND-ONLY — confirm this.)

STEP 2 — WRAP IN SAVEPOINT:
  async with db.begin_nested() as savepoint:
      try:
          # INSERT JournalEntry rows (append-only)
          # INSERT new ExternalSyncRun row with status PUBLISHED (append-only)
      except Exception:
          await savepoint.rollback()
          # INSERT new ExternalSyncRun row with status FAILED (append-only)
          raise

STEP 3 — DEDUPLICATION GUARD:
  Before inserting any JournalEntry, check:
    existing = await db.scalar(
        select(func.count()).select_from(JournalEntry)
        .where(JournalEntry.external_ref == ref, JournalEntry.tenant_id == tenant_id)
    )
    if existing > 0:
        # mark this line as ALREADY_POSTED in sync run metadata
        continue  # skip insert

STEP 4 — DB UNIQUE CONSTRAINT:
  Add UniqueConstraint("tenant_id", "external_ref") to JournalEntry.
  Migration: Pattern D. Name: 0106_add_external_ref_unique_to_journal_entries.py

STEP 5 — EXCEPTION:
  In financeops/modules/erp_sync/domain/exceptions.py:
  class ErpSyncError(Exception): pass
  class DuplicateGLEntryError(ErpSyncError):
      def __init__(self, external_ref: str):
          self.external_ref = external_ref
          super().__init__(f"GL entry already posted for ref: {external_ref}")

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_erp_sync_publish.py:
  - test_publish_gl_entry_rollback_when_sync_run_update_fails
  - test_publish_deduplication_skips_already_posted_ref
  - test_publish_end_to_end_posts_gl_and_marks_sync_complete
  - test_duplicate_external_ref_raises_not_inserts
  0 warnings, 0 skips.
```

---

### 2.3 — Org Setup: Enforce org_setup_complete gate + cycle detection

**File:** `financeops/modules/org_setup/dependencies.py` (create)

**Problem:** Financial modules accept requests from incomplete orgs. Circular entity ownership possible.

**Claude Code / Codex prompt:**

```
FINANCEOPS — DATA INTEGRITY: ORG SETUP GATE + CYCLE DETECTION

Repo: D:\finos\backend\

CONTEXT: Read COMPLETELY:
  - financeops/modules/org_setup/application/org_service.py
  - financeops/db/models/org_setup.py
  - financeops/main.py

STEP 1 — CHECK FIELD:
  rg "setup_complete\|org_setup_complete" financeops/db/models/org_setup.py
  If field missing: add to OrgSetupProgress model + migration (Pattern D).
  Name: 0107_add_setup_complete_to_org_setup_progress.py

STEP 2 — CREATE DEPENDENCY:
  In financeops/modules/org_setup/dependencies.py:
  async def require_org_complete(
      tenant_id: UUID = Depends(get_current_tenant_id),
      db: AsyncSession = Depends(get_async_session)
  ) -> None:
      progress = await db.scalar(
          select(OrgSetupProgress).where(OrgSetupProgress.tenant_id == tenant_id)
      )
      if not progress or not progress.setup_complete:
          raise HTTPException(status_code=403, detail="ORG_SETUP_INCOMPLETE")

STEP 3 — APPLY TO ROUTERS in main.py:
  Add dependencies=[Depends(require_org_complete)] to ALL financial module routers.
  EXEMPT: org_setup_router, auth_router, health_router, billing_router.
  List every router you are adding it to in your response.

STEP 4 — ENTITY CODE UNIQUENESS:
  Add UniqueConstraint("tenant_id", "entity_code") to OrgEntity.
  Migration: 0108_add_entity_code_unique_to_org_entity.py

STEP 5 — CYCLE DETECTION in create_org_ownership():
  Before INSERT, walk ownership tree upward from proposed parent_id:
    async def _detect_cycle(parent_id, child_id, db, tenant_id) -> bool:
        current = parent_id
        visited = set()
        while current is not None:
            if current == child_id:
                return True  # cycle detected
            if current in visited:
                break
            visited.add(current)
            current = await get_parent_id(current, db, tenant_id)
        return False

  EXCEPTION:
  In financeops/modules/org_setup/domain/exceptions.py:
  class OrgSetupError(Exception): pass
  class CircularOwnershipError(OrgSetupError):
      def __init__(self, child_id, parent_id):
          super().__init__(f"Circular ownership: {child_id} → ... → {parent_id} → {child_id}")

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_org_setup_gate.py:
  - test_incomplete_org_blocked_from_gl_recon_endpoint
  - test_complete_org_accesses_gl_recon_endpoint
  - test_circular_ownership_raises_not_inserts
  - test_duplicate_entity_code_rejected_at_db_level
  0 warnings, 0 skips.
```

---

### 2.4 — Consolidation: Fix ValueError + stub endpoints

**File:** `financeops/modules/consolidation/application/run_service.py`

**Problem:** Uncaught `ValueError` at ~line 754-758 on missing entity → HTTP 500. Three endpoints return hardcoded stubs.

**Claude Code / Codex prompt:**

```
FINANCEOPS — DATA INTEGRITY: CONSOLIDATION ERROR HANDLING + STUBS

Repo: D:\finos\backend\

CONTEXT: Read COMPLETELY:
  - financeops/modules/consolidation/application/run_service.py (focus on lines 740-780)
  - financeops/modules/consolidation/api/routes.py
  - financeops/modules/board_pack_generator/application/generate_service.py
  - financeops/modules/anomaly_pattern_engine/application/run_service.py

STEP 1 — DEFINE EXCEPTIONS:
  Create financeops/modules/consolidation/domain/exceptions.py:
  class ConsolidationError(Exception): pass
  class MissingSourceEntityError(ConsolidationError):
      def __init__(self, missing_ids: list):
          self.missing_ids = missing_ids
          super().__init__(f"Missing source entities: {[str(i) for i in missing_ids]}")
  class InvalidSourceRunError(ConsolidationError):
      def __init__(self, run_ref: str):
          super().__init__(f"Source run not found or incomplete: {run_ref}")

  Add FastAPI exception handler in routes.py for MissingSourceEntityError → 422.

STEP 2 — FIX ValueError AT ~LINE 754-758:
  Replace bare ValueError raise with:
    collected_missing = []
    for entity_id in required_entity_ids:
        entity = await load_entity(entity_id, db)
        if entity is None:
            collected_missing.append(entity_id)
    if collected_missing:
        raise MissingSourceEntityError(missing_ids=collected_missing)

STEP 3 — VALIDATE source_run_refs BEFORE execute_run():
  At start of execute_run(), for each ref in run.source_run_refs:
    exists = await check_run_exists(ref, db)
    if not exists: raise InvalidSourceRunError(run_ref=ref)

STEP 4 — REPLACE STUB ENDPOINTS:
  /board-pack: call BoardPackGenerateService.generate(run_id, tenant_id, db)
               trigger as Celery task → return 202 {"task_id": ...}
  /risks:      call AnomalyPatternEngine.run_for_scope(scope=consolidation_scope, db)
  /anomalies:  same as /risks but return AnomalyRunResult list

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_consolidation_run.py:
  - test_missing_source_entity_returns_422_with_entity_ids_not_500
  - test_invalid_source_run_ref_returns_422
  - test_board_pack_endpoint_calls_generate_service_not_stub
  - test_risks_endpoint_returns_anomaly_results_not_stub
  0 warnings, 0 skips.
```

---

### 2.5 — Scheduled Delivery: Idempotency + cron validation

**File:** `financeops/modules/scheduled_delivery/application/delivery_service.py`

**Claude Code / Codex prompt:**

```
FINANCEOPS — DATA INTEGRITY: SCHEDULED DELIVERY IDEMPOTENCY + CRON VALIDATION

Repo: D:\finos\backend\

CONTEXT: Read COMPLETELY:
  - financeops/modules/scheduled_delivery/application/delivery_service.py
  - financeops/modules/scheduled_delivery/tasks.py
  - financeops/db/models/scheduled_delivery.py

STEP 1 — DETERMINE MUTABILITY of DeliveryLog:
  Apply Pattern A. DeliveryLog is likely APPEND-ONLY (delivery history).
  State finding before proceeding.

STEP 2 — ADD idempotency_key TO DeliveryLog:
  Add idempotency_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
  Migration: Pattern D. Name: 0109_add_idempotency_key_to_delivery_log.py

STEP 3 — IDEMPOTENCY CHECK IN CELERY TASK:
  @celery_app.task(queue='critical_q', bind=True, max_retries=3)
  def deliver_schedule_task(self, schedule_id, idempotency_key):
      # Check: is there already a DELIVERED log with this idempotency_key?
      existing = await db.scalar(
          select(DeliveryLog)
          .where(DeliveryLog.idempotency_key == idempotency_key,
                 DeliveryLog.status == DeliveryStatus.DELIVERED)
      )
      if existing:
          logger.info(f"Already delivered: {idempotency_key}. Skipping.")
          return
      # send → INSERT new DeliveryLog (APPEND-ONLY) with idempotency_key

STEP 4 — CRON VALIDATION AT CREATION:
  First check: rg "croniter" financeops/ pyproject.toml
  If not in pyproject.toml: add croniter to [tool.poetry.dependencies].
  In POST /schedules route:
    from croniter import croniter
    if not croniter.is_valid(body.cron_expression):
        raise HTTPException(422, detail={
            "error": "INVALID_CRON_EXPRESSION",
            "value": body.cron_expression,
            "hint": "Example: '0 9 * * 1' (every Monday at 9am)"
        })

  EXCEPTION:
  class InvalidCronExpressionError(ScheduledDeliveryError):
      def __init__(self, expression: str):
          super().__init__(f"Invalid cron expression: '{expression}'")

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_scheduled_delivery_idempotency.py:
  - test_celery_retry_does_not_duplicate_email_delivery
  - test_celery_retry_does_not_duplicate_webhook_delivery
  - test_invalid_cron_expression_rejected_with_422
  - test_valid_cron_expressions_accepted (test several: '0 9 * * 1', '*/15 * * * *', etc.)
  0 warnings, 0 skips.
```

---

## Phase 3 — Compliance Engines
**Weeks 2–3 · P0 blockers resolved: 5 · Modules: Bank Recon, GST Recon, Fixed Assets, Working Capital, Consolidation**

The hardest phase. Bank Recon (~120h) and GST Recon (~100h) require significant net-new logic.

---

### 3.1 — Bank Reconciliation: Implement GL matching

**File:** `financeops/modules/bank_reconciliation/application/recon_service.py`

**Current state:** 8 routes, 446 LOC. `run_bank_reconciliation()` creates `bank_only` break items only. Core GL matching entirely unimplemented.

**Performance note:** Run `difflib.SequenceMatcher` (Pass 3) only on records that survived Passes 1 and 2 unmatched. Do not run fuzzy match on all records — too slow on large datasets.

**Claude Code / Codex prompt:**

```
FINANCEOPS — COMPLIANCE: BANK RECONCILIATION GL MATCHING ENGINE

Repo: D:\finos\backend\
Estimated effort: 3–4 days. Work through this in multiple sessions if needed.

CONTEXT: Read COMPLETELY before writing a single line of code:
  - financeops/modules/bank_reconciliation/application/recon_service.py
  - financeops/db/models/bank_reconciliation.py
  - financeops/db/models/accounting_layer.py (JournalEntry, JournalEntryLine)
  - financeops/modules/accounting_layer/infrastructure/repository.py
  - tests/conftest.py

HARD CONSTRAINTS:
  - All amounts: Decimal — never float
  - BankReconItem is APPEND-ONLY — never UPDATE
  - BankStatement, BankTransaction are APPEND-ONLY
  - Python 3.11, asyncio scope = "session"

STEP 1 — DETERMINE MUTABILITY of all bank recon models: (Pattern A)
  State findings for: BankStatement, BankTransaction, BankReconItem.

STEP 2 — EXCEPTION DEFINITIONS:
  Create financeops/modules/bank_reconciliation/domain/exceptions.py:
  class BankReconError(Exception): pass
  class InsufficientDataError(BankReconError):
      def __init__(self, message: str): super().__init__(message)
  class StatementAlreadyProcessedError(BankReconError):
      def __init__(self, statement_id): super().__init__(f"Already processed: {statement_id}")

STEP 3 — THREE-PASS MATCHING ALGORITHM:

  Load data FIRST, then match (do not mix I/O with logic):
    bank_txns = load all UNMATCHED BankTransaction for statement_id
    gl_lines   = load all UNMATCHED JournalEntryLine for same bank_account_id + date range

  PRE-PROCESSING — BUILD INDEX DICTS (required for datasets > 1,000 rows):
    # Without this, nested loops = O(n²) = 100M comparisons for 10k×10k.
    # Index by (amount, date) for O(1) lookup in Pass 1 and 2.
    gl_exact_index: dict[tuple, list] = {}  # key=(amount, date), value=[gl_line,...]
    for gl in gl_lines:
        key = (gl.amount, gl.posting_date)
        gl_exact_index.setdefault(key, []).append(gl)

    gl_near_index: dict[Decimal, list] = {}  # key=amount, value=[gl_line,...]
    for gl in gl_lines:
        gl_near_index.setdefault(gl.amount, []).append(gl)

  PASS 1 — EXACT (O(n) with index dict):
    for bank in bank_txns:
        key = (bank.amount, bank.value_date)
        candidates = gl_exact_index.get(key, [])
        if candidates:
            gl = candidates.pop(0)  # take first match
            # remove from gl_lines pool and gl_near_index
            INSERT BankReconItem(type=MATCHED, ...)
            bank_txns pool: remove bank
            continue

  # (fallback nested loop only used when:
  PASS 1 — EXACT (nested loop — only if index build fails):
    for bank in bank_txns:
        for gl in gl_lines:
            if bank.amount == gl.amount and bank.value_date == gl.posting_date:
                INSERT BankReconItem(type=MATCHED, bank_txn_id=bank.id, gl_line_id=gl.id)
                remove bank and gl from respective pools
                break

  PASS 2 — NEAR (run on remaining unmatched only):
    for bank in remaining_bank_txns:
        for gl in remaining_gl_lines:
            if bank.amount == gl.amount and abs((bank.value_date - gl.posting_date).days) <= 3:
                INSERT BankReconItem(type=NEAR_MATCH, ...)
                remove from pools, break

  PASS 3 — FUZZY (run on remaining only — use difflib only here):
    for bank in remaining_bank_txns:
        for gl in remaining_gl_lines:
            amount_ok = abs(bank.amount - gl.amount) / gl.amount < Decimal('0.0001')
            date_ok   = abs((bank.value_date - gl.posting_date).days) <= 7
            if amount_ok and date_ok:
                ratio = difflib.SequenceMatcher(
                    None, bank.description or '', gl.narration or ''
                ).ratio()
                if ratio > 0.8:
                    INSERT BankReconItem(type=FUZZY_MATCH, ...)
                    remove from pools, break

  REMAINING:
    for bank in remaining_bank_txns: INSERT BankReconItem(type=BANK_ONLY, bank_txn_id=bank.id)
    for gl   in remaining_gl_lines:  INSERT BankReconItem(type=GL_ONLY,   gl_line_id=gl.id)

  RETURN BankReconSummary:
    matched: int, near_match: int, fuzzy: int
    bank_only: int, gl_only: int
    net_difference: Decimal  (sum of BANK_ONLY amounts - sum of GL_ONLY amounts)

STEP 4 — DUPLICATE STATEMENT DETECTION:
  Before running, check: has this statement_id already produced a completed recon run?
  If yes: raise StatementAlreadyProcessedError unless force_rerun=True.

STEP 5 — ACCEPT Idempotency-Key on POST /bank-recon/runs.

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_bank_recon_matching.py (minimum 15 tests):
  FIXTURES: db, tenant (check conftest.py)
  - test_exact_match_same_day_same_amount
  - test_exact_match_removes_from_pool_not_double_matched
  - test_near_match_3_day_tolerance
  - test_near_match_4_day_not_matched
  - test_fuzzy_match_description_similarity_above_threshold
  - test_fuzzy_match_below_threshold_not_matched
  - test_bank_only_created_for_unmatched_bank_transaction
  - test_gl_only_created_for_unmatched_gl_entry
  - test_net_difference_is_decimal_not_float
  - test_rerun_creates_new_items_original_items_unchanged
  - test_duplicate_statement_raises_not_processes_twice
  - test_rls_tenant_a_cannot_see_tenant_b_recon_items
  - test_zero_transactions_returns_empty_summary
  All assertions on Decimal values: assert result == Decimal("1500.00") not == 1500.0
  0 warnings, 0 skips.
```

---

### 3.2 — GST Reconciliation: Portal import + ITC rules

**File:** `financeops/modules/gst_reconciliation/application/` (multiple new services)

**GST rate note:** The complete Indian GST rate master includes: `{0, 1.5, 3, 5, 7.5, 12, 18, 28}` percent. 1.5% is for cut/polished diamonds, 3% is for gold/jewellery. Verify the complete list with your finance team before hardcoding — use a constant that can be updated.

**Claude Code / Codex prompt:**

```
FINANCEOPS — COMPLIANCE: GST RECONCILIATION ENGINE

Repo: D:\finos\backend\
Estimated effort: 4–5 days.

CONTEXT: Read COMPLETELY:
  - financeops/modules/gst_reconciliation/application/gst_service.py
  - financeops/db/models/gst_reconciliation.py
  - financeops/utils/gstin.py (validate_gstin, extract_state_code)
  - financeops/db/models/accounting_layer.py (sales invoices)
  - tests/conftest.py

HARD CONSTRAINTS: Decimal not float. INSERT-ONLY on GstReturn/GstReconItem.

STEP 1 — DETERMINE MUTABILITY of GstReturn, GstReconItem: (Pattern A)

STEP 2 — EXCEPTION DEFINITIONS:
  Create financeops/modules/gst_reconciliation/domain/exceptions.py:
  class GstReconError(Exception): pass
  class InvalidGstinError(GstReconError):
      def __init__(self, gstin: str):
          super().__init__(f"Invalid GSTIN format: {gstin}")
  class GstReturnNotFoundError(GstReconError):
      def __init__(self, period: str, return_type: str):
          super().__init__(f"No {return_type} found for period {period}")

STEP 3 — GST RATE MASTER CONSTANT:
  # NOTE: Verify this list with your finance team before going live.
  # This is the known Indian GST rate master as of FY2025-26.
  # Rates in percent.
  GST_RATE_MASTER: frozenset[Decimal] = frozenset([
      Decimal("0"), Decimal("1.5"), Decimal("3"),
      Decimal("5"), Decimal("7.5"), Decimal("12"),
      Decimal("18"), Decimal("28")
  ])

PHASE A — GSTN JSON Import (application/gstn_import_service.py):
  parse_gstr1_json(json_data: dict) -> List[GstReturnLineItem]
  parse_gstr2b_json(json_data: dict) -> List[GstReturnLineItem]
  Steps:
  - Validate each supplier_gstin via validate_gstin() — raise InvalidGstinError if invalid
  - Parse taxable_value, igst, cgst, sgst, cess as Decimal (never float)
  - INSERT GstReturn header + line items (APPEND-ONLY)

PHASE B — Invoice Matching (application/invoice_match_service.py):
  Same 3-pass approach as bank recon (Pass 1 exact, Pass 2 near, Pass 3 fuzzy).
  Match fields: supplier_gstin + invoice_number + taxable_value.
  INSERT GstReconItem per match/break (APPEND-ONLY).

PHASE C — ITC Eligibility (application/itc_eligibility_service.py):
  Rule 36: itc_eligible = True ONLY if invoice appears in GSTR-2B
  Rule 37: if invoice_date < (today - 180 days) AND payment_status != PAID:
             reverse_itc = True, itc_eligible = False
  Rule 38 blocked categories (hardcode from GST Act Schedule — verify with finance team):
    BLOCKED_ITC_CATEGORIES = {"motor_vehicle", "food_beverages", "personal_expenses",
                               "membership_club", "health_insurance_employee"}
    if invoice.expense_category in BLOCKED_ITC_CATEGORIES: itc_eligible = False
  Add itc_eligible (Boolean), itc_blocked_reason (String nullable) to GstReconItem.
  Migration: Pattern D. Name: 0110_add_itc_fields_to_gst_recon_item.py

PHASE D — Rate Validation (in gst_service.py):
  def get_gst_rate_master(db) -> frozenset[Decimal]:
      """Load from DB table. Raise if empty — never silently pass all rates."""
      rates = await db.scalars(select(GstRateMaster.rate))
      rate_set = frozenset(rates.all())
      if not rate_set:
          raise GstRateMasterNotSeededError(
              "gst_rate_master table is empty. "
              "Run: alembic upgrade head to apply seed migration."
          )
      return rate_set

  Add to exceptions.py:
  class GstRateMasterNotSeededError(GstReconError):
      pass

  def validate_gst_rate(rate: Decimal, master: frozenset) -> bool:
      return rate in master
  Flag GstReconItem.rate_mismatch = True if rate not in master.

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_gst_recon.py (minimum 12 tests):
  - test_gstr1_json_import_valid_returns_line_items
  - test_invalid_gstin_raises_invalid_gstin_error
  - test_invoice_exact_match_creates_matched_item
  - test_itc_rule_36_invoice_not_in_2b_is_ineligible
  - test_itc_rule_36_invoice_in_2b_is_eligible
  - test_itc_rule_37_payment_overdue_180_days_reverses_itc
  - test_itc_rule_38_motor_vehicle_blocked
  - test_gst_rate_18_valid
  - test_gst_rate_15_invalid_flagged
  - test_gst_rate_3_valid (gold rate)
  0 warnings, 0 skips.
```

---

### 3.3 — Fixed Assets: IT Act Section 32 + monthly scheduler

**File:** `financeops/modules/fixed_assets/application/depreciation_engine.py`

**Claude Code / Codex prompt:**

```
FINANCEOPS — COMPLIANCE: FIXED ASSETS IT ACT SECTION 32 + SCHEDULER

Repo: D:\finos\backend\

CONTEXT: Read COMPLETELY:
  - financeops/modules/fixed_assets/application/depreciation_engine.py
  - financeops/db/models/fixed_assets.py
  - financeops/tasks/celery_app.py
  - financeops/modules/accounting_layer/tasks/beat_tasks.py

STEP 1 — DETERMINE MUTABILITY of FaAsset, FaDepreciationRun: (Pattern A)

STEP 2 — EXCEPTION DEFINITIONS:
  Create financeops/modules/fixed_assets/domain/exceptions.py:
  class FixedAssetError(Exception): pass
  class DepreciationCalculationError(FixedAssetError):
      def __init__(self, asset_id, reason: str):
          super().__init__(f"Depreciation error for asset {asset_id}: {reason}")

STEP 3 — ADD Section 32 TO DepreciationMethod ENUM:
  Add: BLOCK_IT_ACT_S32 = "block_it_act_s32"
  IT_ACT_S32_THRESHOLD = Decimal("5000")  # assets at or below auto-qualify

STEP 4 — IMPLEMENT in get_depreciation():
  elif method == DepreciationMethod.BLOCK_IT_ACT_S32:
      if acquisition_date.year == period_year:
          # pro-rata: from acquisition_date to year-end
          year_end = date(period_year, 3, 31)  # Indian FY year-end
          days_in_service = (year_end - acquisition_date).days + 1
          depreciation = (Decimal(days_in_service) / Decimal("365")) * asset_cost
      else:
          depreciation = Decimal("0")
      return depreciation

  Handle edge cases:
  - acquisition_date is None → raise DepreciationCalculationError(asset_id, "missing acquisition_date")
  - asset_cost is None or <= 0 → raise DepreciationCalculationError(asset_id, "invalid asset_cost")
  - period_year is None → raise DepreciationCalculationError(asset_id, "missing period_year")

STEP 5 — CELERY MONTHLY SCHEDULER:
  In financeops/modules/fixed_assets/tasks.py:
  @celery_app.task(queue='normal_q', bind=True, max_retries=2)
  def run_monthly_depreciation_task(self, tenant_id: str, period: str) -> None:
      # period format: "YYYY-MM" e.g. "2026-04"
      # 1. Load all active FaAsset rows for tenant
      # 2. For each asset: call depreciation_engine.get_depreciation()
      # 3. Post JournalEntry via accounting_layer service (reuse existing method)
      # 4. INSERT FaDepreciationRun (APPEND-ONLY) with status COMPLETE/FAILED

  Verify Celery discovery: (Pattern E)

  Register in Celery beat (in celery_app.py beat_schedule):
    "fa-monthly-depreciation": {
        "task": "financeops.modules.fixed_assets.tasks.run_monthly_depreciation_task",
        "schedule": crontab(day_of_month=1, hour=2, minute=0),  # 1st of month at 02:00
    }

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_fixed_assets_depreciation.py:
  - test_section_32_100_percent_in_acquisition_year_prorated
  - test_section_32_zero_in_subsequent_years
  - test_section_32_partial_year_calculation_correct
  - test_section_32_threshold_asset_below_5000_auto_qualifies
  - test_get_depreciation_sl_unchanged_by_section_32_addition
  - test_monthly_task_posts_journal_entry_for_each_active_asset
  - test_missing_acquisition_date_raises_calculation_error
  0 warnings, 0 skips.
```

---

### 3.4 — Working Capital: Remove hardcoded dummy data

**File:** `financeops/modules/working_capital/application/wc_service.py`

**Claude Code / Codex prompt:**

```
FINANCEOPS — FUNCTIONAL: WORKING CAPITAL REAL GL DATA

Repo: D:\finos\backend\

CONTEXT: Read COMPLETELY:
  - financeops/modules/working_capital/application/wc_service.py
  - financeops/modules/accounting_layer/infrastructure/repository.py
  - financeops/db/models/working_capital.py

STEP 1 — FIND ALL HARDCODED VALUES:
  rg "1_000_000\|1000000\|600_000\|600000\|5_000_000\|5000000" financeops/modules/working_capital/
  List every occurrence. These are the dummy values to replace.

STEP 2 — EXCEPTION DEFINITION:
  Create financeops/modules/working_capital/domain/exceptions.py:
  class WorkingCapitalError(Exception): pass
  class InsufficientGLDataError(WorkingCapitalError):
      def __init__(self, tenant_id):
          super().__init__(
              f"No GL data for tenant {tenant_id}. "
              "Complete ERP sync first before accessing Working Capital."
          )

STEP 3 — REPLACE _load_financial_inputs() WITH REAL GL QUERIES:
  Remove ALL hardcoded fallback values.
  Replace with queries to accounting_layer repository:
    ar       = await repo.get_balance_by_account_group(tenant_id, "ACCOUNTS_RECEIVABLE", db)
    ap       = await repo.get_balance_by_account_group(tenant_id, "ACCOUNTS_PAYABLE", db)
    revenue  = await repo.get_balance_by_account_group(tenant_id, "REVENUE", db, months=12)
    inventory= await repo.get_balance_by_account_group(tenant_id, "INVENTORY", db)

  If ANY of these returns None or 0 AND this is a new tenant with no sync:
    raise InsufficientGLDataError(tenant_id)  → HTTP 422

  All returned values must be Decimal. Assert this:
    assert isinstance(ar, Decimal), "AR must be Decimal not float"

STEP 4 — INDIAN FINANCIAL YEAR for DSO/DPO:
  DSO = (AR / Revenue) * Decimal("365")
  Use Indian FY (April–March):
    def financial_year_start(d: date) -> date:
        return date(d.year, 4, 1) if d.month >= 4 else date(d.year - 1, 4, 1)

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_working_capital.py:
  - test_wc_snapshot_reads_from_gl_not_hardcoded_values
  - test_wc_raises_insufficient_data_error_for_new_tenant_no_gl
  - test_wc_current_ratio_calculation_with_decimal_precision
  - test_wc_dso_uses_indian_financial_year_april_march
  - test_wc_rls_tenant_a_cannot_see_tenant_b_snapshot
  0 warnings, 0 skips.
```

---

## Phase 4 — Infrastructure: Celery + Audit Trail Middleware
**Weeks 3–4 · P0 blockers resolved: 2 · Modules: All modules + Accounting Layer**

---

### 4.1 — Celery jobs for all synchronous compute modules

| Module | Task | Queue | Route change |
|---|---|---|---|
| GL/TB Recon | `run_gl_recon_task` | `normal_q` | 200 → 202 | P0 |
| Payroll GL Norm. | `run_payroll_norm_task` | `normal_q` | 200 → 202 | P0 |
| Payroll GL Recon. | `run_payroll_recon_task` | `normal_q` | 200 → 202 | P0 |
| MIS Manager | `generate_mis_report_task` | `normal_q` | 200 → 202 | P1 |
| Month-End Close | `process_checklist_triggers_task` | `high_q` | event-driven | P1 |
| Consolidation | `execute_consolidation_run_task` | `normal_q` | 200 → 202 |
| Anomaly Engine | `run_anomaly_detection_task` | `normal_q` | 200 → 202 | P1 |
| Notifications | `send_notification_task` | `critical_q` | replaces sync SMTP | P0 |

**Claude Code / Codex prompt:**

```
FINANCEOPS — INFRASTRUCTURE: CELERY ASYNC JOBS

Repo: D:\finos\backend\
Run once per module. Start with Notifications (most critical — sync SMTP blocks requests).

CONTEXT: Read COMPLETELY:
  - financeops/tasks/celery_app.py (queues: critical_q, high_q, normal_q, low_q)
  - financeops/modules/accounting_layer/tasks/beat_tasks.py (pattern to follow)
  - financeops/modules/board_pack_generator/tasks.py (another example)
  - Target module's application/run_service.py

HARD CONSTRAINTS:
  - from financeops.tasks.celery_app import celery_app (always)
  - Tasks receive primitive args only: UUIDs as str, not ORM objects
  - All DB access inside task: use get_async_session()
  - Tasks must be idempotent — safe to call twice with same args
  - NEVER use asyncio.sleep() in HTTP routes — only in tasks

STEP 1 — CHECK EXISTING tasks.py:
  rg "tasks.py" financeops/modules/{module}/ --include="*.py"
  If tasks.py exists: update it. If not: create it.

STEP 2 — CREATE TASK (one per module):
  @celery_app.task(queue='{queue}', bind=True, max_retries=3)
  def run_{module}_task(self, run_id: str, tenant_id: str) -> None:
      try:
          async def _run():
              async with get_async_session() as db:
                  await set_rls_context(db, tenant_id)
                  service = RunService(db)
                  await service.execute(UUID(run_id), UUID(tenant_id))
          asyncio.run(_run())
      except Exception as exc:
          raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

STEP 3 — VERIFY CELERY DISCOVERY: (Pattern E)

STEP 4 — UPDATE ROUTES:
  Before: result = await service.execute(run_id, tenant_id, db)
          return JSONResponse(result)
  After:  task = run_{module}_task.delay(str(run_id), str(tenant_id))
          return JSONResponse({"task_id": task.id, "status": "queued"}, status_code=202)
  Add: GET /{module}/runs/{run_id}/status → read run status from DB → return current status

FOR NOTIFICATIONS SPECIFICALLY:
  Check pyproject.toml: rg "aiosmtplib" pyproject.toml
  If missing: add aiosmtplib to [tool.poetry.dependencies]
  Replace all synchronous smtplib calls with aiosmtplib.send()
  Push channel (send_push()) — if no push provider configured:
    log warning "Push channel not configured" and skip silently
    Do NOT raise an error — just degrade gracefully

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_celery_tasks.py:
  - test_{module}_task_completes_and_updates_run_status
  - test_{module}_task_idempotent_called_twice
  - test_{module}_route_returns_202_not_200
  - test_{module}_status_endpoint_reflects_celery_result
  - test_all_new_tasks_appear_in_celery_registered_tasks
  0 warnings, 0 skips.
```

---

### 4.2 — Audit Trail: Global middleware + Accounting beat tasks

**File:** `financeops/middleware/audit_middleware.py` (create)

**Claude Code / Codex prompt:**

```
FINANCEOPS — INFRASTRUCTURE: AUDIT TRAIL MIDDLEWARE + BEAT TASKS

Repo: D:\finos\backend\

CONTEXT: Read COMPLETELY:
  - financeops/db/models/audit_trail.py (AuditTrail — likely APPEND-ONLY, verify with Pattern A)
  - financeops/modules/accounting_layer/application/audit_service.py
  - financeops/main.py (middleware registration order)
  - financeops/modules/auth/dependencies.py (how to extract user from request)
  - financeops/modules/accounting_layer/tasks/beat_tasks.py (contains the stub tasks to fix)

STEP 1 — DETERMINE MUTABILITY of AuditTrail: (Pattern A)
  This must be APPEND-ONLY. If it is MUTABLE: flag this as an architecture issue before continuing.

STEP 2 — CREATE AUDIT MIDDLEWARE:
  In financeops/middleware/audit_middleware.py:
  class AuditMiddleware(BaseHTTPMiddleware):
      EXEMPT_PATHS = {"/health", "/health/deep", "/auth/token/refresh"}

      async def dispatch(self, request: Request, call_next):
          response = await call_next(request)
          if (request.method != "GET"
              and response.status_code in range(200, 300)
              and request.url.path not in self.EXEMPT_PATHS):
              asyncio.create_task(self._write_audit(request, response))
          return response

      async def _write_audit(self, request: Request, response: Response):
          try:
              user_id  = extract_user_id_from_jwt(request)  # reuse existing JWT util
              tenant_id = extract_tenant_id_from_jwt(request)
              resource_type = request.url.path.split("/")[2]  # e.g. "recon", "payroll"
              resource_id   = request.path_params.get("id") or request.path_params.get("run_id")
              body_bytes = await request.body()
              row_hash   = hashlib.sha256(body_bytes).hexdigest()
              prev_hash  = await get_latest_chain_hash(tenant_id, db)
              chain_hash = hashlib.sha256(f"{prev_hash}{row_hash}".encode()).hexdigest()
              await insert_audit_trail(
                  tenant_id, user_id, request.method,
                  resource_type, resource_id, row_hash, chain_hash
              )
          except Exception as e:
              logger.error(f"Audit write failed: {e}")  # log but never raise

STEP 3 — REGISTER IN main.py:
  app.add_middleware(AuditMiddleware)
  Add AFTER auth middleware (order matters in FastAPI middleware stack).

STEP 4 — FIX ACCOUNTING BEAT TASKS in beat_tasks.py:
  Replace ALL {"status": "ok"} stubs:

  approval_reminder_task():
    Query: AccountingJVApproval WHERE status=PENDING AND created_at < now() - interval '1 hour'
    For each match: send_notification_task.delay(
        event_type="JV_APPROVAL_REMINDER",
        recipient_user_id=str(approval.assigned_to),
        metadata={"jv_id": str(approval.jv_id)}
    )

  sla_breach_check_task():
    Query: ApprovalSLATimer WHERE deadline < now() AND status != 'BREACHED'
    For each match:
      INSERT new ApprovalSLATimer row with status=BREACHED (APPEND-ONLY)
      send_notification_task.delay(event_type="SLA_BREACH", escalate_to=next_approver_id)

  daily_digest_task():
    For each active tenant:
      pending_jvs    = count pending AccountingJVApproval
      sla_breaches   = count BREACHED ApprovalSLATimer today
      recon_exceptions = count open ReconciliationException
      send_notification_task.delay(event_type="DAILY_DIGEST", summary={...})

VERIFY BEAT TASK REGISTRATION: (Pattern E)

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS:
  - test_audit_middleware_writes_row_on_post_200
  - test_audit_middleware_skips_on_get_request
  - test_audit_middleware_skips_on_4xx_response
  - test_audit_middleware_skips_exempt_paths
  - test_audit_chain_hash_links_to_previous_row
  - test_audit_write_failure_does_not_break_response
  - test_approval_reminder_task_sends_notification_for_pending_approval
  - test_sla_breach_task_inserts_breached_row_not_updates
  - test_daily_digest_task_aggregates_correctly_per_tenant
  0 warnings, 0 skips.
```

---

## Phase 5 — AI Layer + Board Pack Export
**Week 5 · P0 blockers resolved: 3 · Modules: AI CFO Layer, Narrative Engine, Board Pack Generator**

---

### 5.1 — AI CFO: Wire Claude API

**File:** `financeops/modules/ai_cfo_layer/application/narrative_service.py`

**Problem:** Zero LLM calls. Everything is if-else string templates.

> **Decision required before starting:** Choose Option A or B and state your choice.
> - **Option A:** Wire Claude API — ~2-3 days, real AI, ongoing API cost
> - **Option B:** Rename to "Insights Engine (rule-based)" — ~1 day, honest, zero API cost

**Claude Code / Codex prompt:**

```
FINANCEOPS — AI LAYER: WIRE CLAUDE API (Option A)

Repo: D:\finos\backend\
ANTHROPIC_API_KEY is already in .env — do NOT hardcode it anywhere.

CONTEXT: Read COMPLETELY:
  - financeops/modules/ai_cfo_layer/application/narrative_service.py
  - financeops/modules/ai_cfo_layer/application/recommendation_service.py
  - financeops/modules/ai_cfo_layer/api/routes.py
  - financeops/tasks/celery_app.py

HARD CONSTRAINTS:
  - Use httpx.AsyncClient — not requests, not anthropic SDK sync client
  - All financial values in prompts: format as Decimal strings (str(Decimal("1500.00")))
  - API calls MUST be in Celery tasks — never in HTTP request thread (will timeout)
  - Validate LLM response: check all numbers mentioned exist in the source data
  - Log token usage to AiCfoLedger (INSERT-ONLY) — required for cost tracking

STEP 1 — CORRECT MODEL NAME:
  Use: claude-haiku-4-5-20251001
  (Note: if this returns 404, fall back to: claude-3-5-haiku-20241022 and report it)
  Endpoint: https://api.anthropic.com/v1/messages
  Headers: {"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
            "content-type": "application/json"}

STEP 2 — CREATE claude_client.py:
  In financeops/modules/ai_cfo_layer/infrastructure/claude_client.py:
  class ClaudeClient:
      async def complete(self, system: str, user: str, max_tokens: int = 1000) -> str:
          async with httpx.AsyncClient(timeout=30.0) as client:
              resp = await client.post(
                  "https://api.anthropic.com/v1/messages",
                  headers={...},
                  json={"model": "claude-haiku-4-5-20251001",
                        "max_tokens": max_tokens,
                        "system": system,
                        "messages": [{"role": "user", "content": user}]}
              )
              resp.raise_for_status()
              data = resp.json()
              return data["content"][0]["text"]

STEP 3 — CREATE AiCfoLedger TABLE:
  In financeops/db/models/ai_cfo.py:
  class AiCfoLedger(Base):
      __tablename__ = "ai_cfo_ledger"
      id: UUID, tenant_id: UUID, feature: str, model: str
      prompt_tokens: int, completion_tokens: int
      cost_usd: Decimal(10,6), created_at: datetime
  Table is APPEND-ONLY.
  Migration: Pattern D. Name: 0111_add_ai_cfo_ledger.py

STEP 4 — REPLACE TEMPLATES WITH LLM CALLS (in Celery task):
  narrative_service.py:
  - Build prompt with KPI data as Decimal strings
  - Call claude_client.complete()
  - Validate: extract all numbers from response → confirm each exists in source_data dict
  - INSERT NarrativeBlock (APPEND-ONLY) with llm_model, generated_at
  - INSERT AiCfoLedger row with token counts

STEP 5 — RAISE AT STARTUP if ANTHROPIC_API_KEY missing:
  In settings.py validation:
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is required for AI CFO module")

VERIFY CELERY DISCOVERY for new AI tasks: (Pattern E)

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_ai_cfo.py:
  Use respx or pytest-httpx to mock the Claude API endpoint:
  - test_narrative_service_calls_claude_api_endpoint (mock httpx)
  - test_narrative_response_validated_against_source_data
  - test_token_cost_inserted_in_ai_cfo_ledger
  - test_missing_api_key_raises_at_startup
  - test_claude_api_500_triggers_celery_retry
  0 warnings, 0 skips.
```

---

### 5.2 — Board Pack: Real PDF + Excel export

**File:** `financeops/modules/board_pack_generator/application/export_service.py`

**Claude Code / Codex prompt:**

```
FINANCEOPS — FUNCTIONAL: BOARD PACK REAL PDF + EXCEL EXPORT

Repo: D:\finos\backend\

CONTEXT: Read COMPLETELY:
  - financeops/modules/board_pack_generator/application/export_service.py
  - financeops/modules/board_pack_generator/domain/enums.py
  - financeops/storage/r2.py (upload to R2 — use existing methods)
  - financeops/db/models/board_pack_generator.py

STEP 1 — CHECK DEPENDENCIES:
  rg "weasyprint\|openpyxl" pyproject.toml
  If missing: add to [tool.poetry.dependencies]:
    weasyprint = ">=61.0"
    openpyxl = ">=3.1"
  Do not add if already present.

STEP 2 — DETERMINE MUTABILITY of BoardPackGeneratorArtifact: (Pattern A)
  This should be APPEND-ONLY (each export = new artifact record).

STEP 3 — PDF EXPORT:
  Build Jinja2 HTML template at financeops/modules/board_pack_generator/templates/board_pack.html:
    - Cover: org_name, reporting_period, generated_at, "CONFIDENTIAL" watermark
    - Per section: heading, metric table (₹ formatted), narrative, anomaly callout boxes
    - Footer: page numbers
  Convert: weasyprint.HTML(string=rendered_html).write_pdf() → bytes
  Upload: get_storage().upload_file(key=f"board-packs/{tenant_id}/{pack_id}.pdf", data=pdf_bytes)
  INSERT BoardPackGeneratorArtifact (APPEND-ONLY): r2_key, format=PDF, size_bytes, created_at

STEP 4 — EXCEL EXPORT:
  workbook = openpyxl.Workbook()
  Sheet 1: "Executive Summary" — key metrics table
  One sheet per section: section_code as sheet name, data + variance columns
  Styling:
    Header fill: PatternFill(fgColor="2E4057", fill_type="solid"), font white bold
    Freeze top row: ws.freeze_panes = "A2"
    Financial columns: number_format = '₹#,##0.00'
  Upload to R2, INSERT artifact record.

STEP 5 — SIGNED DOWNLOAD URL (not public):
  GET /board-pack/runs/{id}/export/{artifact_id}
  Must return: get_storage().generate_signed_url(r2_key, expires_in=900)  # 15 minutes
  Never return a public R2 URL.

STEP 6 — TRIGGER ROUTE:
  POST /board-pack/runs/{id}/export → trigger export as Celery task → HTTP 202
  Verify Celery discovery: (Pattern E)

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_board_pack_export.py:
  - test_pdf_export_returns_valid_pdf_bytes_not_empty
  - test_excel_export_returns_valid_xlsx_bytes
  - test_export_artifact_inserted_as_append_only_row
  - test_artifact_uploaded_to_r2_not_local_disk
  - test_download_url_is_signed_expires_in_15_min_not_public
  - test_export_route_returns_202_not_200
  0 warnings, 0 skips.
```

---

## Phase 6 — Users & Roles CRUD + P1 Route Gaps
**Weeks 5–6 · Modules: Users & Roles, Auth**

---

### 6.1 — Users & Roles: Missing CRUD routes + async invite

**File:** `financeops/modules/users/api/routes.py`

**Claude Code / Codex prompt:**

```
FINANCEOPS — USERS: CRUD ROUTES + RBAC + ASYNC INVITE

Repo: D:\finos\backend\

CONTEXT: Read COMPLETELY:
  - financeops/modules/users/application/user_service.py (all service methods already exist)
  - financeops/modules/users/api/routes.py (existing 1 route)
  - financeops/modules/auth/application/permission_matrix.py
  - financeops/db/models/iam.py

STEP 1 — VERIFY SERVICE METHODS EXIST:
  rg "def create_user\|def list_tenant_users\|def update_user_role\|def offboard_user\|def deactivate_user" \
     financeops/modules/users/application/user_service.py
  List each method found. If any are missing, state this — do NOT invent them.

STEP 2 — ADD MISSING ROUTES:
  GET    /users              → list_tenant_users()    → requires Permission.USERS_VIEW
  POST   /users              → create_user()          → requires Permission.USERS_INVITE
  GET    /users/{id}         → get_user()             → requires Permission.USERS_VIEW
  PATCH  /users/{id}/role    → update_user_role()     → requires Permission.USERS_MANAGE_ROLES
  DELETE /users/{id}         → offboard_user()        → requires Permission.USERS_OFFBOARD
  Apply RBAC using existing require_permission() dependency — do not write new auth logic.

STEP 3 — FIX INVITE: ASYNC NOT SYNC:
  Find: _send_invite_email_sync() or any synchronous smtplib call in create_user().
  Replace with: send_notification_task.delay(
      event_type="USER_INVITED",
      recipient_user_id=str(new_user.id),
      tenant_id=str(tenant_id)
  )
  Never call SMTP synchronously from an async route.

STEP 4 — FIX ROLE ESCALATION BUG:
  In CreatePlatformUserRequest route handler, add server-side guard:
  if body.role in (UserRole.PLATFORM_OWNER, UserRole.PLATFORM_ADMIN):
      calling_user = get_current_user(...)
      if calling_user.role != UserRole.PLATFORM_OWNER:
          raise HTTPException(403, "Only platform_owner can assign this role")

STEP 5 — ACCEPT Idempotency-Key on POST /users.

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS — tests/integration/test_user_management.py:
  FIXTURES: db, tenant, superuser, org_user (check conftest.py)
  - test_list_users_returns_tenant_scoped_results
  - test_invite_user_triggers_async_notification_not_sync_smtp
  - test_update_role_requires_users_manage_roles_permission
  - test_offboard_user_revokes_sessions_and_marks_inactive
  - test_cannot_assign_platform_owner_without_platform_owner_role
  - test_get_user_returns_404_for_different_tenant_user (RLS)
  0 warnings, 0 skips.
```

---

## Phase 7 — Test Coverage: All Financial Engines
**Weeks 6–7 · 18 modules · ~250 new tests**

Run one module at a time. Confirm pytest passes before moving to next.

**Concern addressed:** 250 tests with strict rules is a genuine velocity impact. The response
is not to reduce tests — financial calculation correctness is non-negotiable — but to
**sequence by risk**. P0-critical tests must pass before launch. P1-deferred tests can
be written post-launch as long as the module is not customer-facing yet.

**P0-Critical** (must pass before any customer uses the module):
Bank Recon, GST Recon, Payroll GL, Consolidation, Fixed Assets, Working Capital, Accounting Layer.

**P1-Deferred** (write post-launch, module can ship with happy-path coverage only):
MIS Manager, Anomaly Engine, Board Pack, Budgeting, Forecasting, Scheduled Delivery.

| Module | Test file | Min tests | Key assertions | Tier |
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
| Budgeting | `test_budgeting.py` | 12 | variance calc, rollup accuracy | P1 |
| Forecasting | `test_forecasting.py` | 10 | growth compounding, period shift | P1 |
| Notifications | `test_notifications.py` | 10 | async SMTP, quiet hours, dedup |
| Scheduled Delivery | `test_scheduled_delivery.py` | 8 | idempotency, cron validation |
| Audit Trail | `test_audit_trail.py` | 8 | chain hash, tamper detection |
| AI CFO Layer | `test_ai_cfo.py` | 8 | Claude API mock, cost tracking |

**Claude Code / Codex prompt:**

```
FINANCEOPS — TESTS: FULL COVERAGE — ONE MODULE AT A TIME

Repo: D:\finos\backend\
Target module this session: [SPECIFY MODULE NAME]

CONTEXT: Read COMPLETELY before writing any test:
  - tests/conftest.py (all fixtures — follow exactly, do not invent new patterns)
  - tests/integration/test_accounting_layer_journals.py (gold standard for test style)
  - Target module: financeops/modules/{module}/application/*.py
  - Target module: financeops/db/models/{module}.py

HARD CONSTRAINTS:
  - asyncio_default_test_loop_scope = "session" — never touch
  - WindowsSelectorEventLoopPolicy in conftest.py — never touch
  - filterwarnings = "error" — 0 warnings
  - No xfail, no skip, no pytest.mark.skip
  - Financial assertions: Decimal not float
    CORRECT:   assert result.amount == Decimal("1500.00")
    WRONG:     assert result.amount == 1500.0
  - RLS: every test sets tenant context:
    await set_rls_context(db, str(tenant.tenant_id))
  - Test DB: localhost:5433, financeops_test / testpassword

FIXTURES — VERIFY BEFORE USING:
  rg "def db\|def tenant\|def tenant_a\|def tenant_b" tests/conftest.py
  Use only fixtures that exist. If a needed fixture is missing:
    Copy pattern from test_accounting_layer_journals.py — do not invent.

TEST STRUCTURE:
  class Test{ModuleName}:
    async def test_happy_path(self, db, tenant):
      # arrange: INSERT test data directly to DB (not via HTTP)
      # act: call service method directly (not HTTP client)
      # assert: exact Decimal values, not just status codes

    async def test_edge_case_zero(self, db, tenant): ...
    async def test_edge_case_decimal_precision(self, db, tenant): ...
    async def test_idempotency_same_input_same_output(self, db, tenant): ...
    async def test_rls_tenant_a_cannot_see_tenant_b_data(self, db, tenant_a, tenant_b): ...

PROCEDURE:
  1. Write all tests for this module
  2. Run: pytest tests/integration/test_{module}.py -v
  3. All must pass: 0 failures, 0 warnings, 0 skips
  4. Run: pytest --tb=short -q → full suite must still show 2527+ passed, 0 failed
  5. Only then declare this module complete

IF ANY TEST FAILS: fix the test or the service (do not skip).
IF YOU CANNOT COMPLETE THIS MODULE: (see Pattern B)
```

---

## Phase 8 — Indian Compliance + Final Cleanup
**Week 8 · Modules: All**

---

### 8.1 — Indian compliance rules

**TDS note:** Do not hardcode TDS slab rates without confirmation from the finance team. Use placeholder constants marked `# TODO: confirm with finance team for FY2025-26` and raise a `NotImplementedError` if called before they are filled in.

**Claude Code / Codex prompt:**

```
FINANCEOPS — INDIAN COMPLIANCE RULES

Repo: D:\finos\backend\

TASK 1 — Org Setup default timezone:
  In create_org_entity(), set default timezone = "Asia/Kolkata" not "UTC".
  Verify field exists: rg "timezone" financeops/db/models/org_setup.py
  Migration: Pattern D. Name: 0120_set_default_timezone_asia_kolkata.py
  SQL: ALTER TABLE org_entities ALTER COLUMN default_timezone SET DEFAULT 'Asia/Kolkata';

TASK 2 — GSTIN state code validation fix:
  In financeops/utils/gstin.py:
  Current regex may allow state code "00". Fix:
    # Valid state codes 01–38 (38 = Ladakh, added after 2019 J&K bifurcation)
  VALID_STATE_CODES = set(f"{i:02d}" for i in range(1, 39))  # 01-38
    def validate_gstin(gstin: str) -> bool:
        if not re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$', gstin):
            return False
        state_code = gstin[:2]
        return state_code in VALID_STATE_CODES
  Test: validate_gstin("00AAAAA0000A1Z5") → False
  Test: validate_gstin("29AAAAA0000A1Z5") → True (Karnataka)

TASK 3 — Payroll statutory deductions:
  Create financeops/modules/payroll_gl_norm/application/statutory_deduction_service.py:

  PF_EMPLOYER_RATE = Decimal("0.12")
  PF_EMPLOYEE_RATE = Decimal("0.12")
  PF_MONTHLY_CAP   = Decimal("1800.00")  # employer cap
  ESI_EMPLOYER_RATE = Decimal("0.0325")
  ESI_EMPLOYEE_RATE = Decimal("0.0075")
  ESI_APPLICABILITY_LIMIT = Decimal("21000.00")  # gross salary threshold

  # TDS slabs — verify with finance team before going live
  # TODO: confirm FY2025-26 slabs with finance team
  TDS_SLABS_FY2526: list[tuple[Decimal, Decimal, Decimal]] = [
      # (lower_bound, upper_bound, rate) — all Decimal
      (Decimal("0"),       Decimal("300000"),  Decimal("0")),     # nil
      (Decimal("300001"),  Decimal("700000"),  Decimal("0.05")),  # 5%
      (Decimal("700001"),  Decimal("1000000"), Decimal("0.10")),  # 10%
      (Decimal("1000001"), Decimal("1200000"), Decimal("0.15")),  # 15%
      (Decimal("1200001"), Decimal("1500000"), Decimal("0.20")),  # 20%
      (Decimal("1500001"), Decimal("9999999"), Decimal("0.30")),  # 30%
  ]
  # NOTE: These are placeholder slabs — replace with confirmed values from finance team.
  # Calling compute_tds() will raise NotImplementedError until confirmed = True is set.
  TDS_SLABS_CONFIRMED = False

  def compute_pf(basic_salary: Decimal) -> dict:
      employee = min(basic_salary * PF_EMPLOYEE_RATE, PF_MONTHLY_CAP)
      employer = min(basic_salary * PF_EMPLOYER_RATE, PF_MONTHLY_CAP)
      return {"employee": employee, "employer": employer}

  def compute_esi(gross_salary: Decimal) -> dict:
      if gross_salary > ESI_APPLICABILITY_LIMIT:
          return {"employee": Decimal("0"), "employer": Decimal("0")}
      return {
          "employee": (gross_salary * ESI_EMPLOYEE_RATE).quantize(Decimal("0.01")),
          "employer": (gross_salary * ESI_EMPLOYER_RATE).quantize(Decimal("0.01"))
      }

  def compute_tds(annual_income: Decimal) -> Decimal:
      if not TDS_SLABS_CONFIRMED:
          raise NotImplementedError(
              "TDS slabs not confirmed by finance team. "
              "Set TDS_SLABS_CONFIRMED = True after verifying FY2025-26 slabs."
          )
      # ... slab calculation

TASK 4 — Working Capital Indian financial year:
  Already done in Phase 3.4. Verify it is in place:
  rg "financial_year_start" financeops/modules/working_capital/application/wc_service.py
  If missing: add it now (same implementation as Phase 3.4 prompt).

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS:
  - test_gstin_state_code_00_rejected
  - test_gstin_state_code_29_karnataka_valid
  - test_gstin_state_code_38_ladakh_valid  (Ladakh is valid)
  - test_gstin_state_code_39_invalid  (39 does not exist)
  - test_pf_employer_capped_at_1800_not_higher
  - test_pf_employee_capped_at_1800
  - test_esi_applicable_at_21000
  - test_esi_not_applicable_at_21001
  - test_tds_raises_not_implemented_until_confirmed
  0 warnings, 0 skips.
```

---

### 8.2 — ERP Integration cleanup + permission matrix + indexes

**Claude Code / Codex prompt:**

```
FINANCEOPS — CLEANUP: ERP INTEGRATION + PERMISSION MATRIX + DB INDEXES

Repo: D:\finos\backend\

TASK 1 — ERP Integration module resolution:
  STEP A: rg -r "erp_integration" financeops/ --include="*.py" -l
  List all files that import from or reference erp_integration.
  STEP B:
    If only files within financeops/modules/erp_integration/ itself:
      → Safe to delete. Run: rm -rf financeops/modules/erp_integration/
      → Check if any migration applied its tables:
         rg "erp_integration\|erp_connector" alembic/versions/ --include="*.py"
         If found: create a drop-table migration (Pattern D, next sequential number).
    If other modules import from erp_integration:
      → DO NOT DELETE. Instead: merge unique logic into erp_sync module.
      → List the conflicts with erp_sync's ErpConnector schema.
      → Resolve the schema conflict (erp_integration's model likely duplicates erp_sync's).
      → Remove erp_integration module after merge.
  STEP C: rg "erp_integration" financeops/main.py
    If found: remove the router registration.

TASK 2 — Permission matrix startup validation:
  In financeops/modules/auth/application/permission_matrix.py, add:
  def validate_permission_matrix() -> None:
      seen_keys = set()
      for key, value in PERMISSION_MATRIX.items():
          if key in seen_keys:
              raise ValueError(f"Duplicate permission key: {key}")
          if value is None:
              raise ValueError(f"Permission key has None value: {key}")
          seen_keys.add(key)
      logger.info(f"Permission matrix validated: {len(PERMISSION_MATRIX)} permissions OK")

  In main.py lifespan (or startup event):
    validate_permission_matrix()

TASK 3 — DB indexes:
  Run against test DB:
  SELECT indexname, tablename FROM pg_indexes
  WHERE tablename IN ('journal_entries','recon_sessions','bank_transactions',
                      'gst_returns','audit_trail','erp_sync_jobs','iam_sessions')
  ORDER BY tablename, indexname;

  For any table missing a (tenant_id, created_at) composite index:
    Migration: Pattern D.
    CREATE INDEX CONCURRENTLY ON {table} (tenant_id, created_at DESC);
  Group all missing indexes into one migration file.

TASK 4 — Budget approval workflow:
  Verify BudgetVersion exists: rg "class BudgetVersion" financeops/db/models/
  Add status transitions:
    BudgetStatus enum: DRAFT, SUBMITTED, CFO_APPROVED, BOARD_APPROVED, SUPERSEDED
  Add routes:
    POST /budgets/{id}/submit   → transition DRAFT → SUBMITTED
    POST /budgets/{id}/approve  → transition SUBMITTED → CFO_APPROVED (or → BOARD_APPROVED)
    Requires: Permission.BUDGET_APPROVE
  Each transition: INSERT BudgetVersionStatusEvent (APPEND-ONLY).
  On approved: set previous version status to SUPERSEDED (new row, not UPDATE).

IF YOU CANNOT COMPLETE THIS TASK: (see Pattern B)
BEFORE DECLARING COMPLETE: (see Pattern C)

TESTS:
  - test_erp_integration_module_not_importable_after_cleanup
  - test_permission_matrix_validates_at_startup
  - test_duplicate_permission_key_raises_at_startup
  - test_budget_approval_workflow_draft_to_submitted
  - test_budget_approval_requires_budget_approve_permission
  - test_budget_previous_version_superseded_on_new_approval
  0 warnings, 0 skips.
```

---

## Pre-Launch Checklist

Every item must be GREEN before onboarding a real customer.

| # | Check | Verify with | Phase |
|---|---|---|---|
| 1 | Full pytest suite: 0 failures, 0 warnings, 0 skips | `pytest --tb=short -q` | All |
| 2 | Password change revokes all sessions | `test_password_change_revokes_old_refresh_token` | 1 |
| 3 | MFA enforced on all protected endpoints | `test_new_user_with_force_mfa_blocked_on_protected_route` | 1 |
| 4 | Forgot-password rate-limited | `test_forgot_password_rate_limited_after_3_requests` | 1 |
| 5 | Webhook deliveries signed with HMAC | `test_webhook_delivery_includes_x_finqor_signature_header` | 1 |
| 6 | COA confirm idempotent | `test_confirm_twice_returns_same_result_without_duplicate_rows` | 2 |
| 7 | ERP sync publish transactional | `test_publish_gl_entry_rollback_when_sync_run_update_fails` | 2 |
| 8 | Incomplete org blocked from financial modules | `test_incomplete_org_blocked_from_gl_recon_endpoint` | 2 |
| 9 | Bank recon GL matching works | `test_exact_match_same_day_same_amount` | 3 |
| 10 | GST ITC Rule 36 implemented | `test_itc_rule_36_invoice_not_in_2b_is_ineligible` | 3 |
| 11 | IT Act Section 32 depreciation works | `test_section_32_100_percent_in_acquisition_year_prorated` | 3 |
| 12 | Working Capital uses real GL data | `test_wc_raises_insufficient_data_error_for_new_tenant_no_gl` | 3 |
| 13 | All heavy compute modules have Celery tasks | `test_all_new_tasks_appear_in_celery_registered_tasks` | 4 |
| 14 | Audit trail writes on all mutations | `test_audit_middleware_writes_row_on_post_200` | 4 |
| 15 | Accounting beat tasks actually execute | `test_approval_reminder_task_sends_notification_for_pending_approval` | 4 |
| 16 | AI CFO calls LLM or is honestly labelled | `test_narrative_service_calls_claude_api_endpoint` | 5 |
| 17 | Board Pack exports real PDF | `test_pdf_export_returns_valid_pdf_bytes_not_empty` | 5 |
| 18 | Board Pack exports real Excel | `test_excel_export_returns_valid_xlsx_bytes` | 5 |
| 19 | User invite is async not blocking | `test_invite_user_triggers_async_notification_not_sync_smtp` | 6 |
| 20 | GSTIN state code 00 rejected | `test_gstin_state_code_00_rejected` | 8 |
| 21 | PF capped at ₹1800 employer | `test_pf_employer_capped_at_1800_not_higher` | 8 |
| 22 | TDS placeholder raises until confirmed | `test_tds_raises_not_implemented_until_confirmed` | 8 |
| 23 | ERP Integration conflict resolved | `test_erp_integration_module_not_importable_after_cleanup` | 8 |
| 24 | Permission matrix validates at startup | `test_permission_matrix_validates_at_startup` | 8 |

---

## Platform State: Baseline vs Target

| Metric | Current (v3.0.0) | Target (post all phases) |
|---|---|---|
| Git tag | v3.0.0 | v4.0.0 |
| Migration head | `0101_accounting_rbac_seed_final` | ~`0125` (+24 migrations) |
| Tests passing | 2,527 | 2,775+ (2527 + ~250 new) |
| P0 blockers | 21 | 0 |
| Modules complete | 5 of 26 | 22+ of 26 |
| Modules with 0 tests | 18 | 0 |
| Celery tasks (real) | ~4 | 20+ |
| LLM calls in AI layer | 0 | Wired or honestly labelled |
| Audit trail coverage | 1 module | All 26 via middleware |
| asyncio.sleep in routes | Present | Zero (all moved to tasks) |
| Hardcoded dummy data | Present (Working Capital) | Zero |

---

*Finqor (FinanceOps) — Implementation Plan v3.1 — April 2026*  
*`D:\finos\` · Python 3.11 · FastAPI · PostgreSQL 16 + RLS · CONFIDENTIAL*