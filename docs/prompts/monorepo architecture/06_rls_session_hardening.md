# PROMPT 06 — HARDEN PUBLIC-ROUTE SESSION & RLS CONTEXT

**Sprint:** 2 (Operational Unblock)
**Audit findings closed:** #7
**Risk level:** MEDIUM (touches the auth/dependency boundary)
**Estimated effort:** S-M (3-5 days)
**Prerequisite:** Prompts 01-05 complete

---

## CONTEXT

Repo root: `D:\finos`
Target file: `D:\finos\backend\financeops\api\deps.py` (around line 128)

The audit found that public-route session handling skips RLS context and can silently return empty tenant-scoped results if misused. The risk: a future developer adds a new endpoint, uses the wrong session dependency, and the endpoint silently returns empty data instead of raising an error — masking what should be a tenant isolation failure.

This is the kind of bug that *doesn't* show up in tests (because tests usually run with full RLS context) but bites in production.

---

## SCOPE — DO EXACTLY THIS

### Step 1 — Map the dependency surface
1. Open `D:\finos\backend\financeops\api\deps.py`
2. List every session/dependency function it exports:
   - `get_db()` / `get_session()` / `get_public_session()` / etc.
3. For each, document:
   - Does it set `tenant_id` in the session context?
   - Does it require an authenticated user?
   - What happens if called without auth — error or silent empty?
4. Run `rg -n "Depends\(get_" D:\finos\backend\financeops\api` and tabulate which routers use which session dependency

### Step 2 — Identify the failure modes
Specifically test these scenarios (read-only — trace through the code):
- Anonymous request hits a tenant-scoped router using the public session → what happens?
- Authenticated request hits a public router using the tenant session → what happens?
- Authenticated request from tenant A hits an endpoint that mistakenly queries tenant B data → what happens?

For each, output: `RAISES` / `SILENTLY_EMPTY` / `LEAKS_DATA` / `OK`

### Step 3 — Design the hardening
Output a plan covering:
1. A clear naming convention: `get_authenticated_session()` (always tenant-scoped, requires auth) vs `get_anonymous_session()` (no tenant scope, only for truly public endpoints like signup/healthcheck)
2. An explicit guard in the public session that raises if it's accidentally used in a tenant-scoped query (e.g., a marker column check)
3. A type-system hint — separate types for `TenantSession` vs `PublicSession` so misuse is a type error, not a runtime silent failure
4. A startup audit that scans all routers and confirms each uses a session type matching its declared scope

**STOP here. Output the plan. Wait for user confirmation before applying.**

### Step 4 — Apply the hardening (after confirmation)
Implement the plan. Specifically:
1. Rename ambiguous dependencies to make scope explicit
2. Add type aliases: `TenantDB`, `PublicDB`
3. Add a runtime guard in the public session that prevents tenant-scoped queries
4. Add a startup-time validator that verifies router → session pairing
5. Update routers that use the wrong session — go ONE module at a time, do not batch

### Step 5 — Add comprehensive tests
Create `D:\finos\backend\tests\test_session_isolation.py`:
- `test_tenant_session_requires_auth` — anonymous request raises 401
- `test_tenant_session_sets_tenant_id_in_context` — confirms RLS context is set
- `test_public_session_blocks_tenant_queries` — using public session for tenant-scoped table raises explicit error
- `test_cross_tenant_query_blocked_by_rls` — tenant A cannot see tenant B data even with malformed query
- `test_router_session_pairing_validator_catches_mismatches` — startup validator flags misuse

---

## DO NOT DO

- Do NOT silently fall back to anonymous behavior
- Do NOT remove RLS — strengthen it
- Do NOT change the JWT/auth flow itself
- Do NOT batch-rename across all routers in one commit — go module by module
- Do NOT touch the database RLS policies in this prompt — that's a separate hardening

---

## VERIFICATION CHECKLIST

- [ ] All session dependencies are clearly named by scope
- [ ] Public session raises if used for tenant-scoped queries
- [ ] Type system distinguishes `TenantDB` from `PublicDB`
- [ ] Startup validator passes — no router uses the wrong session
- [ ] All 5 isolation tests pass
- [ ] Existing API tests still pass (full backend test suite green)
- [ ] No new test skips

---

## ROLLBACK PLAN

If the startup validator finds many existing mismatches:
1. Do NOT auto-fix all of them — that's a much bigger refactor
2. Add a temporary allowlist of known-mismatched routers with a `# TODO: prompt 06 follow-up` comment
3. Track the allowlist in `D:\finos\docs\engineering\SESSION_PAIRING_DEBT.md`
4. Plan a follow-up sprint to clear the allowlist

---

## COMMIT MESSAGE

```
fix(security): harden session/RLS context boundaries

- Renamed session dependencies for explicit scope (TenantDB vs PublicDB)
- Added runtime guard preventing public session from running tenant queries
- Added startup validator for router/session pairing
- Added isolation regression tests covering cross-tenant query attempts

Closes audit finding #7 (CRITICAL).
Prevents silent tenant data exposure from session misuse.
```
