# BE-001 Pre-Implementation Investigation Gate — Report

**Date:** 2026-04-26
**Branch:** feat/be001-user-org-memberships
**Ticket:** `docs/tickets/backend-user-org-memberships.md` (commit 3170898)
**Status:** Gate report — implementation paused pending review

---

## Investigation 0.1 — `scope` claim handling in auth path

### Files inspected

- `backend/financeops/api/deps.py:249–337` — `get_current_user`: the primary FastAPI dependency that decodes the JWT and loads the user. Contains the only conditional scope checks in the auth path.
- `backend/financeops/api/deps.py:354–375` — `get_current_tenant`: calls `get_current_user`, then resolves the `IamTenant`. No scope inspection.
- `backend/financeops/core/middleware.py:76–105` — `RLSMiddleware`: extracts `tenant_id` from JWT into `request.state`. No scope inspection at all.
- `backend/financeops/main.py:461–494` — Middleware registration. All 11 registered middleware checked; none are JWT-scope-aware beyond `RLSMiddleware` above.
- `backend/financeops/api/v1/auditor.py:38–213` — Uses a field named `scope` on `AuditorGrant` records (read-only/full access level). Entirely unrelated to JWT `scope` claims; confirmed by context.
- `backend/financeops/platform/api/v1/admin.py:519–558` — Admin switch endpoint (reference). SETS `scope: "platform_switch"` on the issued token. Does not REQUIRE callers to carry this scope.

### Findings

#### `deps.py:249–337` — `get_current_user` (authoritative source)

```python
# deps.py:255–313 (condensed to relevant lines)
payload = decode_token(token)
if payload.get("type") != "access":
    raise AuthenticationError("Invalid token type")       # type claim checked
tenant_id_str = payload.get("tenant_id")
if not tenant_id_str:
    raise AuthenticationError("Token missing tenant_id")  # tenant_id required
token_scope = payload.get("scope")                        # line 265 — scope READ, not asserted
user_id_str = payload.get("sub")
if not user_id_str:
    raise AuthenticationError("Token missing subject")    # sub required
# ... user loaded, is_active checked, tenant_id cross-validated ...

# Scope is only checked in two narrowly-scoped blocks (lines 304–313):
if token_scope == "mfa_setup_only":
    raise HTTPException(status_code=403, detail="MFA setup required ...")
if token_scope == "password_change_only":
    raise HTTPException(status_code=403, detail="Password change required ...")
```

**Analysis:** `scope` is extracted at line 265 via `payload.get("scope")` — a no-op if absent (returns `None`). The only subsequent use is two equality checks against `"mfa_setup_only"` and `"password_change_only"`. Neither check triggers on `None`, `"platform_switch"`, `"user_switch"`, or any other value. A token with no `scope` claim at all passes both checks and proceeds normally.

Required claims (that WILL raise if missing): `type == "access"`, `tenant_id`, `sub`.
Optional claims (present but not enforced): `scope`, `role`, `pwd_at`, `iat`.

#### `core/middleware.py:76–105` — `RLSMiddleware`

```python
payload = decode_token(token)
tenant_id = payload.get("tenant_id", "")
request.state.tenant_id = tenant_id
# No other payload fields inspected
```

**Analysis:** Only `tenant_id` is extracted. `scope` is not read.

#### `admin.py:535–541` — Admin switch token construction (reference)

```python
switch_token = create_access_token(
    user_id=user.id,
    tenant_id=tenant_id,
    role=user.role.value if hasattr(user.role, "value") else str(user.role),
    additional_claims={"scope": "platform_switch", "switched_by": str(user.id)},
    expires_delta=timedelta(minutes=15),
)
```

**Analysis:** The admin switch token SETS `scope: "platform_switch"`. There is no corresponding check elsewhere in the auth path that REQUIRES `scope: "platform_switch"` to be present. The `get_current_user` dependency does not look for `platform_switch`. This scope value is informational (and carried by the token into downstream audit logging) but is not a gate condition.

#### No other scope checks found

The grep `grep -rn "scope" backend/financeops/api/ --include="*.py"` returned only:
- `deps.py:265` — the `payload.get("scope")` read above
- `deps.py:582` — `context_scope={"tenant": ...}` in the RBAC evaluator (unrelated to JWT)
- `auditor.py:38,70,79,133,213` — application-level auditor grant `scope` field (unrelated to JWT)

No middleware, no decorator, no guard inspects the JWT `scope` claim beyond the two specific-value checks in `get_current_user`.

### Verdict

**VERDICT 0.1: Proceed as written.**

The existing auth path does not reject tokens that carry no `scope` claim. The user switch token defined in Section 4.2 of the ticket (which carries no `scope` claim) will pass through `get_current_user` and all registered middleware without issue. The only JWT claims that will be validated are `type == "access"`, `tenant_id` (valid UUID), and `sub` (valid UUID). All three will be correctly populated by `create_access_token`.

No ticket amendment is required for this investigation.

---

## Investigation 0.2 — `create_access_token` signature

### Files inspected

- `backend/financeops/core/security.py:50–69` — canonical `create_access_token` definition
- `backend/financeops/services/auth_service.py:116–121` — call site at login
- `backend/financeops/services/auth_service.py:420–425` — call site at token refresh
- `backend/financeops/api/v1/auth.py:179–185, 196–202` — two call sites (MFA setup token, password change token)
- `backend/financeops/platform/api/v1/admin.py:535–541` — call site in admin switch endpoint
- `backend/financeops/core/__init__.py:51–61` — legacy stub (see note below)

### Current signature

```python
# backend/financeops/core/security.py:50–69
def create_access_token(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    additional_claims: dict | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token (15 minutes by default)."""
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "type": "access",
    }
    if additional_claims:
        payload.update(additional_claims)
    return _make_token(
        payload,
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )
```

The `additional_claims` kwarg is present, typed `dict | None = None`, and its body is:
```python
if additional_claims:
    payload.update(additional_claims)
```

### Existing call sites

All callers import from `financeops.core.security` (not from `financeops.core`):

| File | Line | Invocation pattern |
|---|---|---|
| `services/auth_service.py` | 116–121 | `create_access_token(user.id, user.tenant_id, user.role.value, additional_claims=token_claims)` |
| `services/auth_service.py` | 420–425 | `create_access_token(user.id, user.tenant_id, user.role.value, additional_claims=token_claims)` |
| `api/v1/auth.py` | 179–185 | `create_access_token(user.id, user.tenant_id, user.role.value, additional_claims={"scope": "mfa_setup_only"}, expires_delta=timedelta(minutes=15))` |
| `api/v1/auth.py` | 196–202 | `create_access_token(user.id, user.tenant_id, user.role.value, additional_claims={"scope": "password_change_only"}, expires_delta=timedelta(minutes=15))` |
| `platform/api/v1/admin.py` | 535–541 | `create_access_token(user_id=user.id, tenant_id=tenant_id, role=user.role.value ..., additional_claims={"scope": "platform_switch", "switched_by": str(user.id)}, expires_delta=timedelta(minutes=15))` |

All 5 call sites use the `additional_claims` kwarg. No call site uses `**kwargs`.

### Findings

The ticket Section 4.2 line 260 assumes:
```python
create_access_token(user.id, target_tenant_id, membership.role.value, additional_claims={})
```

This is fully supported. `additional_claims={}` is valid (empty dict evaluates as falsy, so `payload.update({})` is not called — correct behaviour, no spurious claims added).

**Legacy stub note — `core/__init__.py:51`:**

`backend/financeops/core/__init__.py` contains a SECOND definition of `create_access_token` with a narrower signature (no `additional_claims`, no `expires_delta`):

```python
# core/__init__.py:51 — LEGACY STUB, do not use
def create_access_token(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str) -> str:
    ...
```

This stub is **not imported by any of the 5 call sites above** (all import `from financeops.core.security import create_access_token`). The BE-001 implementation must likewise import from `financeops.core.security`, which is already the established pattern. The stub in `core/__init__.py` should be noted as dead code but is not a blocker. If the BE-001 implementation mistakenly imports from `financeops.core` instead of `financeops.core.security`, passing `additional_claims={}` would raise `TypeError: create_access_token() got an unexpected keyword argument 'additional_claims'` — caught immediately by tests.

**Impact radius if `additional_claims` kwarg did not exist** (hypothetical — it does exist): 5 existing call sites would need updating. Not applicable — the kwarg exists.

### Verdict

**VERDICT 0.2: Proceed as written.**

`create_access_token` in `financeops.core.security` already accepts `additional_claims: dict | None = None` with exactly the signature the ticket assumes. No refactor is needed. The implementation engineer must import from `financeops.core.security` (consistent with all existing callers).

No ticket amendment is required for this investigation.

---

## Combined gate result

| Investigation | Verdict |
|---|---|
| 0.1 — `scope` claim handling in auth path | **Proceed as written** |
| 0.2 — `create_access_token` signature | **Proceed as written** |

**Overall: PROCEED**

Both investigations confirm the ticket as written is correct and implementable without amendment. Key facts locked in:

1. User switch tokens with no `scope` claim will pass `get_current_user` — the only scope-gated rejections are `mfa_setup_only` and `password_change_only`.
2. `create_access_token(user.id, target_tenant_id, membership.role.value, additional_claims={})` is a valid invocation — the kwarg exists and is used by 4 other existing callers already.
3. No middleware in the stack inspects the JWT `scope` claim.
4. Import path: `from financeops.core.security import create_access_token` (not `financeops.core`).

BE-001 implementation can begin from Section 1 (migration strategy) onward in a follow-up prompt after this gate report is reviewed.

---

## References

- Locked ticket: `docs/tickets/backend-user-org-memberships.md` (commit 3170898)
- FU-003 decision: `docs/decisions/fu003-entity-endpoint-scoping-decision.md`
- Gap 2 trace: `docs/audits/gap2-orgswitcher-trace-2026-04-25.md`
- `get_current_user` source: `backend/financeops/api/deps.py:249–337`
- `create_access_token` source: `backend/financeops/core/security.py:50–69`
- Admin switch reference: `backend/financeops/platform/api/v1/admin.py:519–558`
