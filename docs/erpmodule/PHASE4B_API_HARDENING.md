# FinanceOps — Phase 4B: API Hardening
## Claude Code Implementation Prompt — v1 (Final)

> Prerequisite: Phase 4A complete, zero test failures.
> Paste this entire prompt into Claude Code.
> Estimated time: 1–2 days. This phase changes API contracts — all test assertions
> for response shape will need updating. Scope that effort before starting.

---

## WHO YOU ARE AND WHERE YOU ARE

You are Claude Code working inside the FinanceOps repository at `D:\finos\`.

This prompt adds three cross-cutting API hardening layers to the platform before
the ERP Sync kernel is built. Building these now means the ERP Sync module (Phase 4C)
is built against the correct patterns from day one — rather than retrofitting later.

**What this phase builds:**
1. Standard `ApiResponse[T]` envelope — applied to all existing and future endpoints
2. Idempotency key support — applied to new ERP Sync endpoints now, retrofitted
   to existing critical financial POST endpoints
3. CSRF middleware — applied platform-wide

**Blast radius awareness:**
- The response envelope will change the shape of every API response
- Every existing test that asserts on response body shape will need updating
- Audit and scope this before starting — run `grep -r "response.json()" tests/` to
  count affected tests
- This is the reason this phase exists as a separate prompt — it deserves its own
  controlled execution window

---

## STEP 0 — READ AND SCOPE BEFORE WRITING

```bash
# Count how many test assertions will be affected by envelope change
grep -r "response\.json()\[" tests/ | wc -l
grep -r '"success"' tests/ | wc -l    # any already expect envelope?

# List all POST endpoints across the platform
grep -r "@router.post\|@app.post" financeops/ backend/ | grep -v ".pyc"
```

Read:
```
D:\finos\financeops\shared_kernel\
D:\finos\backend\main.py
D:\finos\financeops\modules\          ← all module api/ directories
D:\finos\tests\
```

After reading, explicitly state:
```
TOTAL ENDPOINTS (GET + POST)         : [count]
POST ENDPOINTS NEEDING IDEMPOTENCY   : [count — financial mutation endpoints]
TEST FILES AFFECTED BY ENVELOPE      : [count]
EXISTING SHARED KERNEL FILES         : [list]
```

Do not proceed until scoped.

---

## PART 1 — API RESPONSE ENVELOPE

### 1a — Create the envelope

Create `financeops/shared_kernel/response.py`:

```python
from __future__ import annotations
from typing import TypeVar, Generic
from pydantic import BaseModel
from datetime import datetime, timezone
import uuid

T = TypeVar("T")


class ResponseMeta(BaseModel):
    request_id: str
    timestamp: datetime
    api_version: str = "1.0"


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ErrorDetail | None = None
    meta: ResponseMeta

    class Config:
        # Allow Generic[T] to serialize correctly
        arbitrary_types_allowed = True


def ok(data: T, request_id: str | None = None) -> ApiResponse[T]:
    return ApiResponse(
        success=True,
        data=data,
        error=None,
        meta=ResponseMeta(
            request_id=request_id or str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
        ),
    )


def err(
    code: str,
    message: str,
    field: str | None = None,
    request_id: str | None = None,
) -> ApiResponse[None]:
    return ApiResponse(
        success=False,
        data=None,
        error=ErrorDetail(code=code, message=message, field=field),
        meta=ResponseMeta(
            request_id=request_id or str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
        ),
    )
```

### 1b — Request ID middleware

Add to `backend/main.py`:

```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestIDMiddleware)
```

### 1c — Apply envelope to all existing endpoints

Rules:
- Every endpoint that currently returns a raw Pydantic object → wrap with `ok(data, request.state.request_id)`
- Every endpoint that currently raises `HTTPException` → replace with `err(code, message)` and return HTTP 200 with `success=False`, OR keep HTTPException for auth/permission errors (401, 403, 404 are acceptable as HTTPExceptions — business logic errors use the envelope)
- Do NOT change any business logic — wrapping only
- Do NOT change URL paths, methods, or authentication

Specifically:
- 2xx responses: always `ApiResponse(success=True, data=...)`
- Validation errors (422): keep FastAPI default validation error format — do not wrap
- Auth errors (401, 403): keep HTTPException — do not wrap
- Not found (404): keep HTTPException — do not wrap
- Business logic errors (e.g. "sync already running", "period locked"): use `err()` envelope with HTTP 400

### 1d — Update all affected tests

For every test that asserts on response body shape:
```python
# Before:
assert response.json()["id"] == expected_id

# After:
body = response.json()
assert body["success"] is True
assert body["data"]["id"] == expected_id

# For error cases:
assert body["success"] is False
assert body["error"]["code"] == "EXPECTED_ERROR_CODE"
```

Run after every module update:
```bash
pytest tests/unit/[module]/ tests/integration/[module]/ -x -q
```

---

## PART 2 — IDEMPOTENCY KEY SUPPORT

### 2a — Create idempotency middleware

Create `financeops/shared_kernel/idempotency.py`:

```python
from __future__ import annotations
from fastapi import Request, HTTPException
from typing import Callable
import json

IDEMPOTENCY_HEADER = "Idempotency-Key"
IDEMPOTENCY_TTL_SECONDS = 86400     # 24 hours
IDEMPOTENCY_KEY_MAX_LEN = 128
IDEMPOTENCY_KEY_PREFIX = "idempotency:"


async def get_idempotency_key(request: Request) -> str | None:
    key = request.headers.get(IDEMPOTENCY_HEADER)
    if key is not None and len(key) > IDEMPOTENCY_KEY_MAX_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Idempotency-Key must be {IDEMPOTENCY_KEY_MAX_LEN} characters or fewer."
        )
    return key


async def check_idempotency_cache(
    redis_client,
    tenant_id: str,
    key: str,
) -> dict | None:
    """
    Returns the cached response dict if this key was already processed,
    otherwise returns None.
    """
    cache_key = f"{IDEMPOTENCY_KEY_PREFIX}{tenant_id}:{key}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    return None


async def store_idempotency_response(
    redis_client,
    tenant_id: str,
    key: str,
    response_body: dict,
) -> None:
    cache_key = f"{IDEMPOTENCY_KEY_PREFIX}{tenant_id}:{key}"
    await redis_client.setex(
        cache_key,
        IDEMPOTENCY_TTL_SECONDS,
        json.dumps(response_body),
    )
```

### 2b — Apply idempotency to financial POST endpoints

**Phase 0–3 existing endpoints — retrofit these (critical financial mutations only):**

For every existing `POST` endpoint that creates a financial record (journal entries,
recon runs, month-end checklists, audit access grants, IFRS run triggers, etc.):

1. Accept optional `Idempotency-Key` header
2. If key provided: check Redis cache for `{tenant_id}:{key}`
3. If cached: return cached `ApiResponse` immediately (HTTP 200), no re-execution
4. If not cached: execute, store response in Redis with 24h TTL, return response
5. If no key provided: execute normally (idempotency is optional for existing endpoints)

Do NOT make idempotency required on existing endpoints — only optional.

**New ERP Sync endpoints (Phase 4C and beyond) — make required on these:**
- `POST /erp-sync/connections` — required
- `POST /erp-sync/sync-runs` — required
- `POST /erp-sync/publish-events/{id}/approve` — required, and this endpoint is
  fully idempotent: calling approve twice returns the same approval response

### 2c — Add idempotency unit test

Create `tests/unit/shared_kernel/test_idempotency.py`:

```python
# Tests:
# - key too long → 400
# - key not provided → executes normally
# - same key second call → returns cached response
# - different tenant same key → different cache entries (isolation)
# - key expires after TTL → executes fresh
```

---

## PART 3 — CSRF MIDDLEWARE

### 3a — Install

Add to `pyproject.toml`:
```toml
starlette-csrf = ">=1.4,<2.0"
```

### 3b — Apply

Add to `backend/main.py` (after `RequestIDMiddleware`, before route registration):

```python
from starlette_csrf import CSRFMiddleware

app.add_middleware(
    CSRFMiddleware,
    secret=settings.SECRET_KEY,
    exempt_urls=[
        r"^/api/v1/auth/",           # auth endpoints use token not cookie
        r"^/health$",
        r"^/metrics$",
        r"^/erp-sync/webhooks/",     # webhook endpoints are exempt
    ],
    cookie_secure=settings.ENVIRONMENT == "production",
    cookie_samesite="strict",
    cookie_name="csrftoken",
    header_name="X-CSRFToken",
)
```

### 3c — Update test fixtures

Add CSRF token to all POST test requests that use session cookies.
API-key and JWT-based requests do not need CSRF tokens (CSRF only applies to
cookie-based sessions).

Check how existing tests authenticate:
```bash
grep -r "cookies\|session" tests/ | grep -v ".pyc"
```

If tests use JWT Bearer tokens only (likely) — no test changes needed.
If tests use cookies — add CSRF token to those fixtures.

---

## FINAL VERIFICATION

```bash
# Full test suite — zero failures
pytest tests/ -x -q

# Verify envelope shape on a known endpoint
curl -s http://localhost:8000/health | python -m json.tool
# Must contain: {"success": true, "data": ..., "meta": {"request_id": "...", ...}}

# Verify idempotency
curl -X POST http://localhost:8000/api/v1/[any-financial-endpoint] \
  -H "Idempotency-Key: test-key-001" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{}' | python -m json.tool
# Call again with same key — must return identical response

# Verify CSRF header present in response
curl -I http://localhost:8000/health
# Should see Set-Cookie: csrftoken=...
```

---

## DEFINITION OF DONE

- [ ] `financeops/shared_kernel/response.py` created with `ApiResponse[T]`, `ok()`, `err()`
- [ ] `RequestIDMiddleware` added — `X-Request-ID` on every response
- [ ] All existing endpoints return `ApiResponse[T]` envelope
- [ ] Auth/permission errors (401/403/404) still use `HTTPException` — not wrapped
- [ ] All affected test assertions updated for new envelope shape
- [ ] `financeops/shared_kernel/idempotency.py` created
- [ ] Idempotency optional on all existing Phase 0–3 financial POST endpoints
- [ ] Idempotency unit test file created and passing
- [ ] `starlette-csrf` added to `pyproject.toml`
- [ ] `CSRFMiddleware` active with correct exemptions
- [ ] JWT/Bearer-authenticated tests unaffected by CSRF (confirmed)
- [ ] `pytest tests/ -x -q` → zero failures
- [ ] `docker-compose ps` all healthy

---

## WHAT THIS PHASE DOES NOT TOUCH

- No database tables
- No migrations
- No business logic
- No connector code (Phase 4C)
- No canonical schemas (Phase 4C)

---

## CRITICAL RULES

- Python 3.11 only
- `async def` everywhere
- No UPDATE / DELETE on financial tables
- `WindowsSelectorEventLoopPolicy()` stays untouched
- `asyncio_default_test_loop_scope = "session"` stays untouched
- Run `pytest` after every part — zero failures throughout

---

*Envelope. Idempotency. CSRF. Zero business logic changes. Then open Phase 4C.*
