# Gap 2: OrgSwitcher Wiring Trace
**Date:** 2026-04-25  
**Type:** Read-only static analysis  
**Analyst:** Claude Code (claude-sonnet-4-6)

---

## 1. Executive Summary

**One-line answer:** Phase 2 OrgSwitcher work requires 1 new backend endpoint + a full frontend rewrite of the switcher concept, because the current mechanism is an admin impersonation tool, not a multi-org membership switcher.

**Top 3 findings:**

1. **The current OrgSwitcher is admin impersonation, not org membership switching.** It issues a short-lived 15-minute JWT that lets `platform_owner` / `super_admin` impersonate any tenant. Both backend endpoints (`GET /api/v1/platform/admin/tenants` and `POST /api/v1/platform/admin/tenants/{id}/switch`) are under the `/platform/admin/` prefix and are guarded by `require_platform_admin` / `require_platform_owner`. No regular user path exists today.

2. **Removing the role gate would immediately 403 on every API call.** The list endpoint returns all tenants in the system (not the user's orgs), and the switch endpoint requires `platform_owner` role in the JWT. A regular `finance_leader` who clicked OrgSwitcher would get a tenant list API 403 on popover open, and a switch API 403 on select.

3. **No TanStack Query is involved — org switch is pure Zustand + JWT swap.** The `is_switched` flag in `useTenantStore` causes the Axios interceptor to substitute the `switch_token` as the Bearer on every subsequent request. There is no query invalidation, no session refresh, and no page reload. The existing propagation model could be reused for Phase 2, but the token issuance path needs a new endpoint.

---

## 2. Current Wiring Diagram

```
User opens OrgSwitcher (frontend/components/layout/OrgSwitcher.tsx:22)
  → useSession() reads session.user.role via next-auth (line 24)
  → if role NOT in ['platform_owner', 'super_admin']:
      → return null                              (line 27-30)

  → OrgSwitcherInner renders (line 35)
      → useTenantStore reads:
          s.is_switched          (line 43)
          s.switched_tenant_name (line 44)
          s.tenant_id            (line 45)
          s.switched_tenant_id   (line 46)
          s.enterSwitchMode      (line 47)
              all from frontend/lib/store/tenant.ts

  → Popover opens (user clicks button):
      → useEffect fires on `open === true` (line 51)
      → adminListTenants({ limit: 200 })       (frontend/lib/api/admin.ts:11)
          → GET /api/v1/platform/admin/tenants
          → backend: platform/api/v1/admin.py:91
          → guard: require_platform_admin (deps.py:504)
               allows: super_admin, platform_owner, platform_admin
          → returns: { items: AdminTenantListItem[], total, limit, offset }
      → setTenants(res.items)

  → User selects a tenant:
      → handleSelect(tenant)                   (line 62)
      → switchToTenant(tenant.id)              (line 70)
          → POST /api/v1/platform/admin/tenants/{id}/switch
          → backend: platform/api/v1/admin.py:519
          → guard: require_platform_owner (deps.py:512)
               allows: super_admin, platform_owner ONLY
          → returns: { switch_token (JWT), tenant_id, tenant_name, expires_in_seconds: 900 }
      → enterSwitchMode({ switch_token, tenant_id, tenant_name })
          → Zustand set():
              is_switched = true
              switch_token = <JWT>
              switched_tenant_id = <target id>
              switched_tenant_name = <target name>
          → stored in sessionStorage (NOT localStorage)
          → switch_token field excluded from persistence

  → All subsequent API requests (frontend/lib/api/client.ts:116):
      → interceptor reads useTenantStore.getState().is_switched
      → if true: Authorization: Bearer <switch_token>
                 X-Tenant-ID: <switched_tenant_id>
      → if false: normal session token + real tenant_id

  → Token expires (15 min) → any request returns 401:
      → client.ts:181 detects 401 while is_switched === true
      → calls exitSwitchMode() → clears all switch state
      → window.location.assign('/dashboard?switch_expired=1')
```

---

## 3. File Inventory

| File | Role in OrgSwitcher flow | Lines of relevance | Needs Phase 2 change? |
|---|---|---|---|
| `frontend/components/layout/OrgSwitcher.tsx` | Component — renders picker, owns switch flow | 1–159 | Yes — full rework: new endpoint, new data shape, remove role gate, show only user's own orgs |
| `frontend/components/layout/Topbar.tsx` | Mount point — renders `<OrgSwitcher />` unconditionally | 18, 321 | No — OrgSwitcher self-gates; mount point is fine |
| `frontend/lib/store/tenant.ts` | Zustand store — holds `is_switched`, `switch_token`, org state | 9–127 | Partial — `enterSwitchMode` is reusable; may need new action for multi-org membership switch |
| `frontend/lib/api/admin.ts` | API wrappers — `adminListTenants`, `switchToTenant` | 11–102 | No — admin functions stay; Phase 2 adds new functions in a different file |
| `frontend/lib/api/client.ts` | Axios interceptor — substitutes Bearer + tenant header | 116–123, 181–188 | No — propagation model is reusable as-is |
| `frontend/lib/types/admin.ts` | Type — `AdminTenantListItem` | 8–18 | No — admin type stays; Phase 2 needs a new `UserOrgListItem` type |
| `frontend/lib/auth.ts` | Type — `UserRole` enum | 8–20 | No |
| `frontend/components/layout/ViewingAsBanner.tsx` | Banner shown while `is_switched === true` | 34–73 | Partial — may need label change from "Read-only · 15 min token" to reflect user context switch |
| `frontend/app/control-plane/admin/tenants/[id]/PageClient.tsx` | Alternate admin switch entry point (writes to sessionStorage directly) | 148–160 | No — admin path unrelated to Phase 2 |
| `backend/financeops/platform/api/v1/admin.py` | Backend handlers for list + switch endpoints | 91–141, 519–558 | No — admin endpoints stay; Phase 2 adds a separate user-scoped endpoint |
| `backend/financeops/api/deps.py` | Permission guards: `require_platform_admin`, `require_platform_owner` | 504–517, 53–78 | No — guards stay on admin endpoints; Phase 2 adds `get_current_user` gated endpoint |

---

## 4. Backend Surface

### Endpoint A — List Tenants

| Field | Value |
|---|---|
| Path | `GET /api/v1/platform/admin/tenants` |
| Handler | `backend/financeops/platform/api/v1/admin.py:91` |
| Permission guard | `require_platform_admin` (deps.py:504) |
| Allowed roles | `super_admin`, `platform_owner`, `platform_admin` |
| Response shape | `{ items: [{ id, name, slug, status, plan_tier, trial_end_date, credit_balance, user_count, created_at }], total, limit, offset }` |

**Problem for Phase 2:** Returns ALL tenants in the system. Regular users need only the orgs they belong to. A new endpoint scoped to `current_user.id` is required.

### Endpoint B — Switch Tenant

| Field | Value |
|---|---|
| Path | `POST /api/v1/platform/admin/tenants/{tenant_id}/switch` |
| Handler | `backend/financeops/platform/api/v1/admin.py:519` |
| Permission guard | `require_platform_owner` (deps.py:512) |
| Allowed roles | `super_admin`, `platform_owner` ONLY |
| Response shape | `{ switch_token (JWT), tenant_id, tenant_name, expires_in_seconds: 900 }` |
| Token details | JWT sub = platform owner's user_id; tenant_id = target; claims include `scope: "platform_switch"`, `switched_by: <admin_id>` |

**Problem for Phase 2:** Issues a token carrying the platform owner's identity. A regular user switching to their second org needs a token with their own `user_id` and the target `tenant_id` — a fundamentally different issuance path. The admin endpoint must NOT be repurposed.

### What allowing regular users looks like

A new endpoint is needed, not a permission relaxation on the existing ones. Specifically:

1. `GET /api/v1/users/me/orgs` — returns the list of tenants the authenticated user belongs to, scoped by `IamUser.tenant_id` memberships or a membership join table if multi-org membership is stored separately. Guard: `get_current_user` only (no role restriction). Response shape same as `AdminTenantListItem` minus admin-only fields (`credit_balance`, `user_count`).

2. `POST /api/v1/users/me/orgs/{tenant_id}/switch` — issues a new JWT for the same `user_id` but with `tenant_id` set to the target org. Must verify the user actually belongs to that org before issuing. Guard: `get_current_user`. Token should NOT carry `scope: platform_switch` or `switched_by` claims (those are admin-only semantics).

The existing client-side propagation (Zustand store + Axios interceptor) can reuse the same `enterSwitchMode` + `switch_token` pattern with no changes, because the interceptor just substitutes the Bearer token — it doesn't inspect the token's claims.

---

## 5. Org Switch Propagation Model

**What happens today when a user picks a new org:**

| Step | Mechanism | File:Line |
|---|---|---|
| 1. Select fires | `handleSelect(tenant)` called | OrgSwitcher.tsx:62 |
| 2. API call | `POST /platform/admin/tenants/{id}/switch` | admin.ts:97 |
| 3. Zustand update | `enterSwitchMode({ switch_token, tenant_id, tenant_name })` | tenant.ts:94 |
| 4. Store persisted | `sessionStorage` (not localStorage) | tenant.ts:114 |
| 5. Next request | Interceptor reads `is_switched`, swaps Bearer + X-Tenant-ID | client.ts:116 |
| 6. No invalidation | TanStack Query keys are NOT invalidated | — |
| 7. No reload | No `window.location.reload()`, no router.push | — |
| 8. Token expires | 401 → `exitSwitchMode()` → redirect `/dashboard?switch_expired=1` | client.ts:181 |

**Query invalidation:** None. Data shown after a switch is whatever the new Bearer token allows on next fetch. Stale data from the previous org could briefly appear in components that use cached TanStack Query results. This is a known gap — Phase 2 should consider whether to call `queryClient.clear()` inside `enterSwitchMode`.

**Session refresh:** None. The switch is purely a JWT swap in the Zustand store.

**Race condition to note:** If multiple requests fire in the instant between `enterSwitchMode()` setting `is_switched = true` and the interceptor reading the new value, there is no risk — Zustand writes are synchronous and the interceptor reads synchronously before each request. No race.

**Edge case:** The `PageClient.tsx:148` alternate admin switch path writes directly to `sessionStorage` and then does `router.push('/dashboard')` after a 800ms timeout. On dashboard load, something must read those sessionStorage keys and call `enterSwitchMode` — that initialization code was not located in this trace (flagged in Section 7).

---

## 6. Phase 2 Implications — Confirmed or Changed

The Phase 2 plan assumed ~8 days for Org + Entity Switching. Based on this trace:

| Phase 2 task | Status |
|---|---|
| OrgSwitcher for all users | **Larger than assumed.** Needs: (1) new `GET /users/me/orgs` endpoint, (2) new `POST /users/me/orgs/{id}/switch` endpoint, (3) OrgSwitcher full rewrite — data source, role gate removal, display name logic (currently shows "My Org" vs "Switched Org" — needs real org names for members). Est: **3–4 days** (was likely assumed at 1–2). |
| Entity card as picker | **Unchanged.** Depends on entity store, not org switcher. No backend blocker found. Est: 2 days. |
| EntityScopeBar component | **Unchanged.** Frontend-only. Est: 1 day. |
| Entity tree in sidebar | **Unknown.** Not traced — entity tree data source not examined. |
| `ViewingAsBanner` update | **Unplanned but needed.** Currently labels switched state as "Read-only · 15 min token" — this is admin semantics. For regular multi-org users, the banner label, read-only framing, and 15-min expiry text are all wrong. Est: 0.5 days. |
| TanStack Query invalidation on switch | **Unplanned gap.** No cache invalidation happens today. Should be added in `enterSwitchMode`. Est: 0.5 days. |

**Revised estimate:** 8 days is plausible if backend is unblocked first and the team accepts the ViewingAsBanner and cache invalidation items as in-scope. Backend ticket (Section 8) should be filed before frontend work starts.

---

## 7. Risks and Unknowns

1. **PageClient.tsx sessionStorage initialization path not located.** `frontend/app/control-plane/admin/tenants/[id]/PageClient.tsx:148` writes `platform_switch_token`, `platform_switch_tenant_id`, `platform_switch_tenant_name` to sessionStorage and then navigates to `/dashboard`. The code that reads these keys back and calls `enterSwitchMode` on dashboard load was not found in this trace. If it doesn't exist, the admin alternate-path switch is broken silently.

2. **Multi-org membership model not verified.** This trace assumes regular users can belong to multiple tenants. The schema (migration `0001_initial_schema.py`) was not read. If `IamUser` has a single `tenant_id` column with no membership join table, Phase 2 cannot ship until Phase 0/1 schema is extended. This must be verified before the backend ticket in Section 8 can be written as scoped.

3. **`org_admin` role.** The backend `UserRole` enum includes `org_admin` (users.py:21) but the frontend `UserRole` type (auth.ts:8) does not. If Phase 2 intends org admins to see the OrgSwitcher, this type mismatch is a bug waiting to happen.

4. **`expires_in_seconds` for user switches.** The current switch token is 15 minutes (hardcoded in admin.py:557). For regular user multi-org switching there is no reason to expire the token — it should match the normal session lifetime. The new endpoint should not inherit the 15-minute limit.

5. **`platform_switch` JWT scope claim.** The `scope: "platform_switch"` claim in the current switch token may be checked somewhere in the backend auth path (e.g., in `get_current_user`) to restrict what the switch token can access. This was not verified. If so, the new user-switch token must use a different scope (or no scope), or backend API calls made by regular users in their second org will 403.

---

## 8. Recommended Backend Ticket

**Title:** `feat(auth): add user multi-org switch endpoints (GET /users/me/orgs + POST /users/me/orgs/{id}/switch)`

**Description:**

Phase 2 frontend work requires two new endpoints to power OrgSwitcher for regular users. These must NOT reuse the existing `/platform/admin/tenants` endpoints, which are scoped to admin impersonation and guarded by `require_platform_owner`.

**Endpoint 1 — List user's orgs**

```
GET /api/v1/users/me/orgs
Auth: get_current_user (no role restriction)
Response: {
  items: [{ id, name, slug, status }],  // only orgs the authenticated user belongs to
  total: int
}
```

Implementation notes:
- Filter by user membership — either `IamUser.tenant_id` (if single-column) or a membership join table (if multi-org schema exists)
- Must verify the membership model supports multiple orgs before implementing; if not, schema migration is a prerequisite
- File to add handler: `backend/financeops/api/v1/` (user-scoped routes, not platform/admin)

**Endpoint 2 — Issue org-switch token**

```
POST /api/v1/users/me/orgs/{tenant_id}/switch
Auth: get_current_user (no role restriction)
Request body: (none)
Response: {
  switch_token: str,   // JWT: sub=user.id, tenant_id=target, role=user.role, NO platform_switch scope
  tenant_id: str,
  tenant_name: str,
  expires_in_seconds: int  // match normal session lifetime, NOT 15 minutes
}
```

Implementation notes:
- Verify user belongs to `tenant_id` before issuing — return 403 otherwise
- Do NOT add `scope: "platform_switch"` or `switched_by` claims — those are admin-only semantics
- Do NOT use `require_platform_owner`; this endpoint is for all authenticated users
- Audit log: recommended but optional for Phase 2
- File hint: `backend/financeops/api/v1/users.py` (new file or existing user routes)

**Acceptance criteria:**
- [ ] `GET /users/me/orgs` returns only orgs the calling user belongs to; returns `[]` if single-org user
- [ ] `POST /users/me/orgs/{id}/switch` returns a valid JWT for a tenant the user belongs to
- [ ] `POST /users/me/orgs/{id}/switch` returns 403 if user does not belong to `tenant_id`
- [ ] Neither endpoint is accessible without a valid session token
- [ ] Existing `/platform/admin/tenants` endpoints are unchanged and still require `platform_admin` / `platform_owner`
- [ ] Tests: unit test for 403 guard, integration test for happy path switch token issuance

---

## Section 9 — IamUser Multi-Org Schema Verification
**Date:** 2026-04-25  
**Type:** Read-only static analysis — follow-up to Section 7 unknown

### 1. The Answer

**NO — IamUser is single-org today. A schema migration is required before Phase 2 backend work can proceed.**

`IamUser` carries a single non-nullable `tenant_id` foreign key (`users.py:37`). The docstring on the class reads: *"Platform user. Belongs to exactly one tenant."* (`users.py:32`). No junction table exists that associates a user with more than one tenant. A `user_org_memberships` (or equivalent) table must be created and backfilled before the `GET /users/me/orgs` endpoint can return meaningful data.

---

### 2. Schema Evidence

**IamUser model** — `backend/financeops/db/models/users.py:30–102`

- Line 32: docstring — `"Platform user. Belongs to exactly one tenant."`
- Line 37–42: `tenant_id: Mapped[uuid.UUID]` — single FK to `iam_tenants.id`, `nullable=False`, `index=True`
- Line 43: `email: Mapped[str]` — `unique=True` globally (not tenant-scoped) — confirms one account, one tenant

**Junction tables that exist** — `backend/financeops/platform/db/models/user_membership.py:13–70`

Two tables were found but both are **within-tenant** assignment tables, not cross-tenant membership:

| Table | Unique constraint | What it does |
|---|---|---|
| `cp_user_organisation_assignments` | `(tenant_id, user_id, organisation_id, effective_from)` | Assigns a user to an org **within their tenant** |
| `cp_user_entity_assignments` | `(tenant_id, user_id, entity_id, effective_from)` | Assigns a user to an entity **within their tenant** |

Both tables include `tenant_id` in the unique key — they are scoped records inside a single tenant, not a bridge between tenants. Migration DDL confirmed at `backend/migrations/versions/0008_phase1e_platform_control_plane.py:147–164`.

**No table with `UNIQUE (user_id, tenant_id)` and no `tenant_id` scope filter was found anywhere in the schema.**

---

### 3. Application Code Evidence

**Auth service login** — `backend/financeops/services/auth_service.py:48–103`

- Accepts a single `IamUser` object already bound to one tenant
- Does not enumerate or query multiple tenants at any point
- Calls `_issue_session_tokens(session, user=user, …)` (line 103)

**JWT construction** — `backend/financeops/services/auth_service.py:105–172`

```python
access_token = create_access_token(
    user.id,
    user.tenant_id,          # singular — line 140 (approx)
    user.role.value,
    additional_claims=token_claims,
)
refresh_token = create_refresh_token(user.id, user.tenant_id)  # singular
```

JWT payload carries `tenant_id: string`. No `tenant_ids`, `orgs`, or `memberships` claim exists anywhere in `build_billing_token_claims` (lines 463–512).

**Frontend session type** — `frontend/types/next-auth.d.ts:1–62`

```typescript
interface Session {
  user: {
    tenant_id: string        // singular
    tenant_slug: string      // singular
    entity_roles: EntityRole[] // multiple entities, but all within one tenant
  }
}
```

Session callback in `frontend/lib/auth.ts:305–330` populates `tenant_id` from a single `meEnvelope.data.tenant` object — no array, no iteration over multiple tenants.

---

### 4. Migration History Relevance

150+ migration files reviewed. Key touchpoints on user-tenant identity:

| Migration | What it did |
|---|---|
| `0001_initial_schema.py` | Created `iam_users` with `tenant_id` FK (single-org from day one) |
| `0008_phase1e_platform_control_plane.py` | Added within-tenant `cp_user_organisation_assignments` and `cp_user_entity_assignments` |
| `0073_user_invite_tokens.py` | User invite flow — single-tenant only |
| `0120_normalize_iam_user_emails.py` | Email normalization — no structural change |
| `0130_iam_user_password_changed_at.py` | Added field — no structural change |

**No migration has ever added a cross-tenant user membership table.** The most recent migration touching identity schema is `0130_iam_user_password_changed_at.py` — it added a field, moved nothing toward multi-org.

---

### 5. Deferred Refactor Status

**Evidence found** — `docs/design/Backend_Auth_Users_Structure_Audit_2026-04-13.md:169–176`:

> *"Keep one `IamUser` table short-term, but create an explicit shared service for 'platform user vs org user' classification so it is not router-local. Optional long-term hard split into separate platform-user and org-user tables/models. Why optional: this is the only change that truly enforces the boundary at the data model itself."*

**Status: Acknowledged but deferred — no active work.**

The design doc (dated 2026-04-13) names the split as "optional long-term." No migration, no model file, no TODO comment in any `.py` file suggests active implementation. The thread is alive in design docs only.

---

### 6. What Phase 2 Actually Needs

The answer is **NO**, so the full migration shape is required:

**Step 1 — Create `user_org_memberships` table**
- Columns: `id` (UUID PK), `user_id` (FK → `iam_users.id`), `tenant_id` (FK → `iam_tenants.id`), `role` (UserRole), `is_active` (bool), standard audit columns
- Unique constraint: `(user_id, tenant_id)` — permits multi-org, one row per user-org pair
- RLS: rows visible only to the owning tenant or the user themselves

**Step 2 — Backfill from `IamUser.tenant_id`**
- Insert one row into `user_org_memberships` for every existing `IamUser` (user_id, tenant_id, role from IamUser.role)
- `IamUser.tenant_id` stays as the "primary / login tenant" — not removed

**Step 3 — Migrate login flow**
- After successful auth, look up `user_org_memberships` by `user_id` to determine which tenants the user can switch to
- No change to single-tenant login path; the membership table is only consulted for the switcher

**Step 4 — Add `GET /api/v1/users/me/orgs`**
- Returns rows from `user_org_memberships` for the calling user
- A single-org user gets a one-item list — no frontend special-casing needed

**Step 5 — Add `POST /api/v1/users/me/orgs/{tenant_id}/switch`**
- Verifies membership row exists and `is_active = true`
- Issues JWT with user's own `user_id` and target `tenant_id`

**Realistic estimate:**
- Schema + migration + backfill: **2 days**
- Login flow update + new endpoints + tests: **2 days**
- Frontend OrgSwitcher rewrite + banner update + cache invalidation: **3 days**
- Total Phase 2 Org Switching: **~7 days** (was estimated 8 — realistic if backend ships first)

---

### 7. Recommended Next Move

Phase 2 has a schema prerequisite. File a separate migration ticket — `feat(schema): add user_org_memberships table and backfill` — before any Phase 2 frontend work starts. The frontend OrgSwitcher rewrite cannot be tested end-to-end until `GET /users/me/orgs` returns real data, and that endpoint cannot exist until the membership table does. Backend ticket from Section 8 of this document should be updated to include Steps 1–4 above; the 8-day Phase 2 estimate remains roughly accurate if the migration ticket is filed and executed first.
