# Backend Implementation Prompts — Wave 2
## API Contract Fixes
**Gaps covered:** #7, #9, #10, #11, #12
**Estimated effort:** ~1.5 days
**Prerequisite:** Wave 1 complete and tests passing
**Run after each prompt:** `pytest --tb=short -q`

---

## Prompt 1 of 4 — #7 — Fix JournalStatus mismatch (backend + frontend)
**Priority:** P1 | **Effort:** S | **Tool:** Claude Code
> Note: This prompt touches BOTH repos. Open both D:\finos\backend and D:\finos\frontend in the same session.

```
You are working in BOTH D:\finos\backend AND D:\finos\frontend.

TASK: Create a canonical JournalStatus schema in the backend and align the frontend TypeScript type to all 12 values.

STEP 1 — Read financeops/db/models/accounting_jv.py lines 25-54.
Confirm all 12 JVStatus values:
DRAFT, SUBMITTED, PENDING_REVIEW, UNDER_REVIEW, APPROVED, RESUBMITTED,
REJECTED, PUSH_IN_PROGRESS, PUSHED, PUSH_FAILED, ESCALATED, VOIDED

STEP 2 — Create financeops/api/v1/schemas/journal_status.py:

  from typing import Literal
  from financeops.db.models.accounting_jv import JVStatus

  JournalStatusLiteral = Literal[
      "DRAFT", "SUBMITTED", "PENDING_REVIEW", "UNDER_REVIEW", "APPROVED",
      "RESUBMITTED", "REJECTED", "PUSH_IN_PROGRESS", "PUSHED",
      "PUSH_FAILED", "ESCALATED", "VOIDED"
  ]

  JOURNAL_STATUS_LABELS: dict[str, str] = {
      JVStatus.DRAFT: "Draft",
      JVStatus.SUBMITTED: "Submitted",
      JVStatus.PENDING_REVIEW: "Pending review",
      JVStatus.UNDER_REVIEW: "Under review",
      JVStatus.APPROVED: "Approved",
      JVStatus.RESUBMITTED: "Resubmitted",
      JVStatus.REJECTED: "Rejected",
      JVStatus.PUSH_IN_PROGRESS: "Posting",
      JVStatus.PUSHED: "Posted",
      JVStatus.PUSH_FAILED: "Post failed",
      JVStatus.ESCALATED: "Escalated",
      JVStatus.VOIDED: "Voided",
  }

STEP 3 — Find every Pydantic model with a journal status field (grep for JVStatus in api/v1/).
Update each to use JournalStatusLiteral instead of str.

STEP 4 — Open frontend file lib/api/accounting-journals.ts.
Replace JournalStatus type with full 12-value union:

  export type JournalStatus =
    | "DRAFT" | "SUBMITTED" | "PENDING_REVIEW" | "UNDER_REVIEW"
    | "APPROVED" | "RESUBMITTED" | "REJECTED" | "PUSH_IN_PROGRESS"
    | "PUSHED" | "PUSH_FAILED" | "ESCALATED" | "VOIDED"

STEP 5 — Search frontend for switch/case or if-else blocks handling old wrong values:
  "REVIEWED"  → "PENDING_REVIEW" or "UNDER_REVIEW" (check context)
  "POSTED"    → "PUSHED"
  "REVERSED"  → "VOIDED"
Fix unambiguous mappings. Flag unclear ones for manual review.

STEP 6 — Add status badge colour mapping for the 6 new statuses wherever journal
status badges are rendered in the frontend:
  PENDING_REVIEW   → amber
  UNDER_REVIEW     → amber
  PUSH_IN_PROGRESS → blue
  PUSHED           → green
  PUSH_FAILED      → red
  RESUBMITTED      → purple
  ESCALATED        → red
  VOIDED           → muted

RULES:
- JVStatus constants are source of truth — never hardcode strings independently
- Run tsc --noEmit after frontend changes and fix all TypeScript errors
```

---

## Prompt 2 of 4 — #9 — Install WebKit Playwright binary in CI
**Priority:** P1 | **Effort:** XS | **Tool:** Codex or Claude Code

```
You are working in the Finqor repository at D:\finos.

TASK: Add a Playwright browser install step to CI so WebKit (mobile Safari) tests pass.

STEP 1 — Read .github/workflows/ci.yml fully. Find the frontend job section (lines ~111-145).
Find the step that runs frontend tests.

STEP 2 — Add a new step BEFORE "Run frontend tests":

  - name: Install Playwright browsers
    working-directory: frontend
    run: npx playwright install --with-deps webkit

--with-deps installs system dependencies required by WebKit on Ubuntu CI runners.

STEP 3 — If npx playwright install already exists for other browsers, change it to:
    run: npx playwright install --with-deps
to install all browsers including webkit — do not add a duplicate step.

STEP 4 — Add a Playwright browser cache step if missing:

  - uses: actions/cache@v4
    with:
      path: ~/.cache/ms-playwright
      key: playwright-${{ hashFiles('frontend/package-lock.json') }}

STEP 5 — Check playwright.config.ts — confirm webkit is listed in the projects array
and not commented out.

RULES:
- Do not change any test files — CI infrastructure fix only
- Cache key must be separate from the node_modules cache
```

---

## Prompt 3 of 4 — #10 — Fix retry_failed_payments() to attempt actual charge
**Priority:** P1 | **Effort:** M | **Tool:** Claude Code

```
You are working in the Finqor backend codebase at D:\finos\backend.

TASK: Fix retry_failed_payments() in financeops/tasks/payment_tasks.py so it attempts
a real payment charge before marking a subscription ACTIVE.

STEP 1 — Read financeops/tasks/payment_tasks.py fully, especially retry_failed_payments()
at line ~228. Note how Stripe and Razorpay clients are initialised.
Read financeops/modules/payment/ to find existing charge/invoice payment functions.

STEP 2 — Rewrite retry_failed_payments() with this logic:

  For each PAST_DUE subscription:
    if subscription.payment_provider == "stripe":
      result = await stripe_service.retry_invoice_payment(subscription.stripe_subscription_id)
    elif subscription.payment_provider == "razorpay":
      result = await razorpay_service.retry_charge(subscription.razorpay_subscription_id)

    if result succeeded:
      update subscription to ACTIVE using append-only pattern
      log success at INFO level
    else:
      log failure at WARNING with error details
      increment retry_count if column exists
      if retry_count >= max_retries: update to CANCELLED via append-only pattern

STEP 3 — If retry_invoice_payment / retry_charge don't exist, create them:
  Stripe:   stripe.Invoice.pay(invoice_id) — retrieves latest invoice and pays it
  Razorpay: client.subscription.fetch(sub_id) then client.payment.capture(payment_id, amount)

STEP 4 — Add tests:
- Mock Stripe success → assert subscription becomes ACTIVE
- Mock Stripe failure → assert subscription stays PAST_DUE and retry_count increments
- Mock 3 consecutive failures → assert subscription moves to CANCELLED

RULES:
- All status changes via append-only pattern — no direct UPDATE on subscription rows
- Never charge an already ACTIVE or CANCELLED subscription
- Wrap entire retry loop in try/except — one failure must not stop retries for others
```

---

## Prompt 4 of 4 — #11 + #12 — Pydantic response models + /entity-roles endpoint
**Priority:** P2 | **Effort:** M | **Tool:** Claude Code
> Note: Run after Prompt 1 of Wave 1 (#1+#8) is complete so the entity_roles shape is confirmed.

```
You are working in the Finqor backend codebase at D:\finos\backend.

TASK: Add typed Pydantic response models to auth endpoints and create a /entity-roles endpoint.

PART A — Pydantic response models:

STEP 1 — Read financeops/api/v1/auth.py. List all endpoints currently returning -> dict:
/login, /me, /register, /mfa/verify, /refresh and any others.

STEP 2 — Create financeops/api/v1/schemas/auth_responses.py:

  from pydantic import BaseModel, EmailStr
  from typing import Optional

  class EntityRoleSchema(BaseModel):
      entity_id: str
      entity_name: str
      role: str
      currency: str

  class UserSchema(BaseModel):
      id: str
      email: EmailStr
      full_name: Optional[str]
      role: str
      is_active: bool
      mfa_enabled: bool

  class TenantSchema(BaseModel):
      id: str
      slug: str
      organisation_name: str
      subscription_tier: str

  class LoginResponse(BaseModel):
      access_token: str
      refresh_token: str
      token_type: str = "bearer"
      user: UserSchema
      tenant: TenantSchema
      entity_roles: list[EntityRoleSchema]

  class MeResponse(BaseModel):
      user: UserSchema
      tenant: TenantSchema
      entity_roles: list[EntityRoleSchema]
      billing: dict  # keep as dict — billing schema is complex

  class TokenPairResponse(BaseModel):
      access_token: str
      refresh_token: str
      token_type: str = "bearer"

STEP 3 — Add response_model= to each endpoint decorator and update return statements:

  @router.post("/login", response_model=LoginResponse)
  async def login(...) -> LoginResponse:
      return LoginResponse(**existing_return_dict)

Add model_config = ConfigDict(extra="ignore") to each schema if existing dicts have extra keys.

PART B — /entity-roles endpoint:

STEP 4 — In the most appropriate router file, add:

  @router.get("/entity-roles", response_model=list[EntityRoleSchema])
  async def get_my_entity_roles(
      current_user: User = Depends(get_current_user),
      current_tenant: Tenant = Depends(get_current_tenant),
      session: AsyncSession = Depends(get_async_session),
  ) -> list[EntityRoleSchema]:
      entities = await get_entities_for_user(
          session, tenant_id=current_tenant.id,
          user_id=current_user.id, user_role=current_user.role,
      )
      return [EntityRoleSchema(
          entity_id=str(e.id), entity_name=e.legal_name,
          role=current_user.role.value, currency=e.base_currency
      ) for e in entities]

STEP 5 — Register in financeops/api/v1/router.py if not auto-discovered.

RULES:
- Do not change any auth logic — only add type annotations and response_model decorators
- /entity-roles requires authentication — confirm Depends(get_current_user) is present
- Run tsc --noEmit on the frontend after this to confirm frontend types still match
```

---

*Wave 2 complete. Run `pytest --tb=short -q` before proceeding to Wave 3.*
