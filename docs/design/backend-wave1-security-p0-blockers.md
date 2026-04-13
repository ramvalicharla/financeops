# Backend Implementation Prompts — Wave 1
## Security & P0 Blockers
**Gaps covered:** #1, #2, #3, #4, #5, #6, #8
**Estimated effort:** ~3 hours
**Run after:** Fresh `pytest --tb=short -q` baseline
**Run before proceeding to Wave 2:** `pytest --tb=short -q` — all existing tests must still pass

---

## Prompt 1 of 5 — #1 + #8 — Populate entity_roles in JWT and /me response
**Priority:** P0 | **Effort:** S | **Tool:** Claude Code

```
You are working in the Finqor backend codebase at D:\finos\backend.

TASK: Populate entity_roles in the JWT access token and the /me response so the frontend EntitySwitcher works for all users.

CONTEXT:
- get_entities_for_user() already exists in financeops/platform/services/tenancy/entity_access.py
- build_billing_token_claims() in financeops/services/auth_service.py:105 builds JWT claims but never calls get_entities_for_user()
- get_me() in financeops/api/v1/auth.py:668 returns /me response but omits entity_roles

STEP 1 — Read financeops/platform/services/tenancy/entity_access.py fully.
Confirm the exact signature of get_entities_for_user() and return type.
Note exact attribute names on returned objects (id vs entity_id, legal_name vs entity_name, base_currency vs currency).

STEP 2 — Open financeops/services/auth_service.py.
Find build_billing_token_claims() at line ~105.
Add user_id and user_role as parameters (both available at all call sites).
Add inside the function after existing billing claims:

  from financeops.platform.services.tenancy.entity_access import get_entities_for_user
  entities = await get_entities_for_user(
      session, tenant_id=tenant_id, user_id=user_id, user_role=user_role
  )
  claims["entity_roles"] = [
      {
          "entity_id": str(e.id),
          "entity_name": e.legal_name,
          "role": user_role.value if hasattr(user_role, "value") else str(user_role),
          "currency": e.base_currency,
      }
      for e in entities
  ]

Use exact attribute names confirmed in Step 1.

STEP 3 — Grep for all call sites of build_billing_token_claims() and pass user.id and user.role at each.

STEP 4 — Open financeops/api/v1/auth.py. Find get_me() at line ~668.
Add the same get_entities_for_user() call and append to the returned dict:

  entities = await get_entities_for_user(
      session, tenant_id=current_tenant.id,
      user_id=current_user.id, user_role=current_user.role
  )
  response_data["entity_roles"] = [
      {"entity_id": str(e.id), "entity_name": e.legal_name,
       "role": current_user.role.value, "currency": e.base_currency}
      for e in entities
  ]

STEP 5 — Add a unit test:
- Mock get_entities_for_user to return 2 fake entities
- Call build_billing_token_claims()
- Assert claims["entity_roles"] has length 2
- Assert each item has keys: entity_id, entity_name, role, currency

RULES:
- Python 3.11 only
- Do not change JWT token structure beyond adding entity_roles
- If get_entities_for_user is sync, use run_in_executor; match async patterns in the file
```

---

## Prompt 2 of 5 — #2 — Fix DELETE on auditor_grants in offboard_user()
**Priority:** P0 | **Effort:** XS | **Tool:** Claude Code

```
You are working in the Finqor backend codebase at D:\finos\backend.

TASK: Fix offboard_user() in financeops/services/user_service.py — replace DELETE on auditor_grants with the append-only revocation INSERT pattern.

STEP 1 — Read financeops/services/user_service.py lines 200-260 fully.
Read financeops/db/append_only.py to confirm AuditorGrant is in APPEND_ONLY_TABLES.
Read the AuditorGrant model — confirm it has is_active and effective_to columns.

STEP 2 — Replace lines 214-219:

REMOVE:
  await session.execute(
      delete(AuditorGrant).where(AuditorGrant.user_id == user_id).returning(AuditorGrant.id)
  )

REPLACE WITH:
  active_grants_result = await session.execute(
      select(AuditorGrant).where(
          AuditorGrant.user_id == user_id,
          AuditorGrant.is_active == True
      )
  )
  for grant in active_grants_result.scalars().all():
      await AuditWriter.insert_financial_record(
          session,
          model_class=AuditorGrant,
          data={
              **{c.name: getattr(grant, c.name) for c in grant.__table__.columns},
              "is_active": False,
              "effective_to": datetime.utcnow(),
              "id": uuid.uuid4(),
          },
          actor_id=actor_id,
      )

Adjust AuditWriter call to match the exact signature used elsewhere in the file.

STEP 3 — Fix line 252: replace await session.commit() with await commit_session(session).

STEP 4 — Fix lines 204-209: replace delete(IamSession) with revoke_all_sessions(session, user_id=user_id) imported from auth_service.py:508.

STEP 5 — Add a test: call offboard_user() for a user with an active AuditorGrant.
Assert no exception raised, new AuditorGrant row exists with is_active=False, original row still exists.

RULES:
- Never DELETE or UPDATE any table in APPEND_ONLY_TABLES
- Use datetime.utcnow() or datetime.now(UTC) — match existing pattern in the file
- uuid.uuid4() for new row id
```

---

## Prompt 3 of 5 — #3 — Rate limit /forgot-password and /reset-password
**Priority:** P1 | **Effort:** XS | **Tool:** Codex or Claude Code

```
You are working in the Finqor backend codebase at D:\finos\backend.

TASK: Add rate limiting to /forgot-password and /reset-password in financeops/api/v1/auth.py.

STEP 1 — Read financeops/api/v1/auth.py. Find forgot_password (~line 525) and reset_password (~line 545).
Find an existing rate-limited endpoint (e.g. /login) — note the exact @limiter.limit() decorator syntax and settings key used.

STEP 2 — Add to forgot_password:
1. Add @limiter.limit(settings.AUTH_LOGIN_RATE_LIMIT) decorator above @router.post
2. Add request: Request as the FIRST parameter of the function signature
3. Confirm imports: from slowapi import Limiter and from starlette.requests import Request are present

STEP 3 — Apply the same two changes to reset_password.

STEP 4 — Confirm AUTH_LOGIN_RATE_LIMIT is defined in financeops/config.py.
Use a more specific setting name if one exists (e.g. AUTH_FORGOT_PASSWORD_RATE_LIMIT).

STEP 5 — Add a test that hits /forgot-password above the rate limit threshold and asserts 429 response.

RULES:
- Do not change the business logic of either endpoint — only add decorator and request param
- request: Request must be the first positional parameter, before any Depends() params
- Match the exact decorator pattern used on /login
```

---

## Prompt 4 of 5 — #4 — Remove PII (email) from auth failure logs
**Priority:** P1 | **Effort:** XS | **Tool:** Codex or Claude Code

```
You are working in the Finqor backend codebase at D:\finos\backend.

TASK: Remove PII (email addresses) from production log output in financeops/api/v1/auth.py.

STEP 1 — Read financeops/api/v1/auth.py lines 420-455.
Find all log.info() calls containing email= or normalized_email (~lines 425, 438, 448).

STEP 2 — For each occurrence replace the email with a truncated hash:

  import hashlib  # add to imports if not present (stdlib, no install needed)
  email_ref = hashlib.sha256(normalized_email.encode()).hexdigest()[:8]
  log.info(f"Login rejected: ... email_ref={email_ref}")

This preserves correlation ability without exposing the address.

STEP 3 — Search the entire auth.py for any other normalized_email or email= inside log. calls at INFO or WARNING level and apply the same fix.

STEP 4 — Run: grep -rn "log.info.*email" financeops/
Report any similar PII log patterns found in other service files.
Fix any in auth-related files. List others for a follow-up task.

RULES:
- Do not change log.warning or log.error calls used for security audit purposes
- Do not remove the log calls entirely — they are useful for debugging
- hashlib is stdlib — no pip install needed
```

---

## Prompt 5 of 5 — #5 + #6 — Hide API docs in production + validate payment secrets at startup
**Priority:** P1 | **Effort:** XS | **Tool:** Codex or Claude Code

```
You are working in the Finqor backend codebase at D:\finos\backend.

TASK: Fix two security gaps — hide API docs in production and validate payment secrets at startup.

FIX 1 — Hide API docs in production (main.py lines 295-315):

STEP 1 — Read financeops/main.py. Find the FastAPI(...) constructor.

STEP 2 — Add before the constructor:
  is_prod = settings.APP_ENV.lower() == "production"

STEP 3 — Add to the FastAPI(...) constructor:
  docs_url=None if is_prod else "/docs",
  redoc_url=None if is_prod else "/redoc",
  openapi_url=None if is_prod else "/openapi.json",

Confirm the exact string used for production env (may be "production", "prod", or "PRODUCTION").

FIX 2 — Validate payment secrets at startup (config.py lines 229-268):

STEP 4 — Read financeops/config.py. Find validate_production_security_requirements().
Note the pattern used to check existing required values.

STEP 5 — Add to the required values check:
  "STRIPE_SECRET_KEY": str(self.STRIPE_SECRET_KEY),
  "RAZORPAY_WEBHOOK_SECRET": str(self.RAZORPAY_WEBHOOK_SECRET),

These should raise RuntimeError when APP_ENV == "production" and value is empty.

STEP 6 — Add a test: mock APP_ENV="production" and STRIPE_SECRET_KEY="" → assert RuntimeError raised.

RULES:
- Docs must remain accessible in development and staging — only suppress in production
- Do not change any other FastAPI constructor arguments
```

---

*Wave 1 complete. Run `pytest --tb=short -q` before proceeding to Wave 2.*
