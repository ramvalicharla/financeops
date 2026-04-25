# FU-003 — Entity endpoint org-scoping decision

**Date:** 2026-04-26
**Status:** Decided
**Decided by:** Pre-flight pass for BE-001
**Supersedes:** FU-003 in `docs/follow-ups/FU-003-entity-endpoint-org-scoping.md`

---

## Context

Phase 0 sub-prompt 0.3 wired the `EntitySwitcher` to `GET /api/v1/org-setup/entities`. That
endpoint is JWT-scoped: it calls `get_current_tenant` (deps.py:354), which reads `tenant_id`
from the JWT claim (deps.py:258–262) and uses PostgreSQL RLS to scope the query. No path
parameter is involved; the endpoint does not accept an `orgId` argument.

FU-003 was opened because the Phase 0.3 implementation brief had assumed a different endpoint
shape — `GET /api/v1/orgs/{orgId}/entities` with an explicit orgId path parameter — but the
implementation correctly used the JWT-scoped form instead. The question deferred to this
decision record is: **for Phase 2 multi-org switching, which shape is correct?**

This decision directly shapes two things: (1) whether the entity endpoint needs a new route
as part of BE-001 scope, and (2) whether the frontend Axios interceptor needs changes in
Phase 2 beyond what the existing switch-token mechanism already provides.

---

## Options considered

### Option A — orgId path parameter on the endpoint

**API contract:** Add a new endpoint `GET /api/v1/orgs/{orgId}/entities`. The frontend sends
the active orgId in the URL path. The JWT carries user identity only; `tenant_id` in the JWT
is the user's home org (login default), not necessarily the active org.

**JWT lifecycle:** The existing session JWT does not change on org switch. The frontend reads
the active orgId from `workspaceStore.orgId` and constructs the request URL with it. The switch
is a pure client-side store update; no new token is issued.

**Frontend Axios interceptor changes:** The interceptor currently sends `X-Tenant-ID` derived
from the switch token or the session JWT. Under Option A, the interceptor would additionally
need to read `workspaceStore.orgId` and inject it into the request URL for entity queries —
or entity-fetching hooks would need to read orgId from the store and pass it as a path
parameter. Either approach requires changes to the interceptor or to every hook that calls the
entity endpoint.

**BE-001 scope changes:** The entity endpoint itself becomes part of BE-001 scope. A new route
handler at `GET /api/v1/orgs/{orgId}/entities` must be created. The handler must validate that
the authenticated user has a membership row in `user_org_memberships` for the given `orgId`
before returning entities — adding a membership check on every entity query.

**Failure modes:** The `orgId` path parameter is client-controlled. A malicious or buggy client
can send any UUID. The backend must validate membership on every request, introducing per-request
DB overhead. If the membership check is absent or has a bug, any user can read any org's entities
by guessing a UUID. The attack surface is the orgId itself.

**Migration cost:** Medium. New route handler + membership guard + frontend hook changes across
all entity-fetching code. The existing endpoint at `/org-setup/entities` would need to be
retained for backward compatibility or redirected, since other parts of the system call it
(e.g., org-setup flow).

**Compatibility with future features:** Query cache keys that include orgId are natural under
this model — each URL is distinct. Token revocation is straightforward (standard session
invalidation). Audit logging gets orgId from the URL, which is explicit.

**Effort delta in BE-001:** +0.5–1 day for the new route and frontend hook updates.

---

### Option B — JWT rotation on org switch (recommended)

**API contract:** The existing `GET /api/v1/org-setup/entities` endpoint is unchanged. It
continues to use `get_current_tenant`, which reads `tenant_id` from the JWT. Switching org
means issuing a new JWT that carries the target org's `tenant_id`. The endpoint automatically
scopes to the new org because the JWT changed — no path parameter involved.

**JWT lifecycle:** The `POST /api/v1/users/me/orgs/{tenant_id}/switch` endpoint (part of
BE-001 scope) verifies the user has a membership in the target org, then calls
`create_access_token(user.id, target_tenant_id, user.role.value)` — the same function used
at login. The resulting JWT is indistinguishable in structure from a normal session token,
except `tenant_id` points to the switched-to org. The token lifetime matches the normal access
token, not the 15-minute admin switch token.

**Frontend Axios interceptor changes:** None. The interceptor already implements JWT rotation:
when `is_switched = true`, it substitutes `state.switch_token` as the Bearer token and
`state.switched_tenant_id` as `X-Tenant-ID` (client.ts:120–128). The existing admin switch
plumbing is reused exactly as described in the Gap 2 trace (Section 4, reuse note). The entity
endpoint receives the new JWT and automatically scopes to the new org.

**BE-001 scope changes:** The entity endpoint is not touched. BE-001's `/switch-org` endpoint
already issues the new JWT (this was already in the spec). No additional route work for entity
scoping. The only residual FU-003 task is ensuring TanStack Query cache keys include orgId so
that entity results for different orgs are not served from stale cache — but this is a Phase 2
frontend concern, not a BE-001 backend concern.

**Failure modes:** Authorization is enforced server-side at token issuance time. The switch
endpoint checks membership before issuing the JWT. Once issued, `tenant_id` in the JWT is
server-attested — not client-controlled. RLS in PostgreSQL also enforces tenant_id isolation.
A buggy client cannot fabricate a tenant_id that bypasses these controls.

**Migration cost:** Minimal. The entity endpoint is unchanged. The switch-org endpoint is
already in BE-001 scope. Frontend changes are limited to TQ cache key updates (Phase 2 scope,
not BE-001 scope).

**Compatibility with future features:** JWT rotation is the existing pattern for org context.
Token revocation (Phase 6) works by revoking the session — applies uniformly to all JWTs.
Session pinning works because each switch issues a fresh token that can be independently
tracked. Audit logging gets `tenant_id` from the JWT claims, which is server-attested.

**Effort delta in BE-001:** 0 additional days. The switch endpoint already needed to issue a
JWT; it continues to do so at normal session lifetime.

---

## Decision

**Chosen option: Option B — JWT rotation on org switch.**

### Three strongest reasons

1. **The existing entity endpoint already works this way, and it is already correct.**
   `GET /api/v1/org-setup/entities` uses `get_current_tenant`, which reads `tenant_id` from
   the JWT (deps.py:258–262). When the switch-org endpoint issues a new JWT with the target
   `tenant_id`, the entity endpoint automatically returns the new org's entities. No code
   change is needed in the entity endpoint. This is not architectural preference — it is the
   observation that the existing system already implements the right behaviour.

2. **The frontend already has JWT rotation plumbing, and it works.** The Axios interceptor
   (client.ts:120–128) already substitutes the switch token as the Bearer on every subsequent
   request when `is_switched = true`. The `enterSwitchMode` / `exitSwitchMode` Zustand actions
   are already wired. The Gap 2 trace explicitly confirmed this mechanism is reusable
   (Section 4: "The existing client-side propagation … can reuse the same enterSwitchMode +
   switch_token pattern with no changes"). BE-001 just needs to issue the right JWT.

3. **Authorization is enforced once at token issuance, not on every entity query.**
   Under Option B, the membership check happens exactly once — at the switch-org endpoint,
   before the JWT is issued. Under Option A, the backend must re-verify membership on every
   `GET /entities` call, adding latency, complexity, and a per-request attack surface. The
   JWT itself is server-attested proof of authorization; there is no reason to re-derive it
   from a client-controlled path parameter.

### Counter-arguments considered

**Counter 1: "Option A makes orgId explicit in the URL, which is easier to debug and audit."**
This does not override Option B because the JWT's `tenant_id` claim serves the same purpose.
The Axios interceptor already sends `X-Tenant-ID` as a header (client.ts:127), derived from
the switch token. Backend audit logs record `tenant_id` from the JWT on every request. The
orgId is not hidden — it is present in the token and in the header. An explicit path parameter
adds no audit or debug value that the existing claims don't already provide.

**Counter 2: "Option A avoids JWT proliferation — you don't need to issue a new token per switch."**
This argument is inapplicable because BE-001 already specifies a `POST /users/me/switch-org`
endpoint that issues a new JWT regardless of which option is chosen. The token is needed to
authenticate the user's identity to the backend after switching. Option B simply reuses this
already-mandatory token to carry the org context, rather than issuing a token *plus* adding
a path parameter.

---

## Consequences

### For BE-001 scope
- The entity endpoint `GET /api/v1/org-setup/entities` is **not** part of BE-001 scope. No
  new entity route is needed.
- The `POST /api/v1/users/me/orgs/{tenant_id}/switch` endpoint must issue a JWT with
  `tenant_id = target_tenant_id` and normal session lifetime (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`,
  not 900 seconds). It must not carry `scope: platform_switch` or `switched_by` claims.
- FU-003 tasks #1 (add `GET /api/v1/orgs/{orgId}/entities`), #2 (update frontend hook), and
  #3 (add `listOrgEntitiesForOrg` to API client) are **closed as not needed**.
- FU-003 task #4 (update query key to include orgId) is deferred to Phase 2 frontend and
  is not a BE-001 backend task.

### For the frontend Axios interceptor (Phase 2)
- No changes to `client.ts` are required for entity endpoint scoping. The interceptor already
  does the right thing.
- When implementing Phase 2 OrgSwitcher, the frontend must call `queryClient.clear()` (or
  invalidate workspace entity queries) inside `enterSwitchMode()` to prevent stale org data
  from appearing after a switch. This is already noted as an unplanned gap in the Gap 2 trace
  (Section 5). It is a Phase 2 frontend task, not BE-001.

### For audit logging
- `tenant_id` is already recorded in every audit trail event via `AuditEvent(tenant_id=...)`.
  Under Option B, the switched-org's `tenant_id` appears in the JWT and is therefore present
  in every audit event made during a switched session. No changes to audit logging are needed.

### For JWT lifecycle
- Switch tokens are standard access tokens (same claims, same lifetime, same validation path).
  They do not require special handling in `get_current_user`, refresh logic, or token revocation.
  The `scope: platform_switch` check used by admin endpoints does not apply to user switch tokens.

### For Phase 2 frontend prompts
- The Phase 2 OrgSwitcher implementation brief should assume: entity data is fetched from
  `GET /api/v1/org-setup/entities` (unchanged URL). After a switch, `queryClient.clear()`
  must be called to purge stale entity cache. The new JWT carries the switched org's
  `tenant_id`; no orgId parameter is needed in entity fetch hooks.
- The query key for entity queries should include orgId for cache isolation between org sessions
  (e.g. `['workspace', 'entities', orgId]`), even though the URL does not change. This prevents
  stale cross-org entity data in multi-org sessions.

---

## References

- BE-001 ticket: `docs/tickets/backend-user-org-memberships.md`
- Gap 2 trace: `docs/audits/gap2-orgswitcher-trace-2026-04-25.md`
- Original FU-003: `docs/follow-ups/FU-003-entity-endpoint-org-scoping.md`
- Entity endpoint handler: `backend/financeops/modules/org_setup/api/routes.py:467–474`
- Tenant dependency: `backend/financeops/api/deps.py:354–370`
- Axios interceptor: `frontend/lib/api/client.ts:119–129`
- Admin switch endpoint (reference pattern): `backend/financeops/platform/api/v1/admin.py:519–557`
