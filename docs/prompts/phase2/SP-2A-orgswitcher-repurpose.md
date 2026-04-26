# Claude Code Prompt — SP-2A: OrgSwitcher Repurpose + Switch Infrastructure

> **Purpose:** Repurpose `OrgSwitcher.tsx` for all-user org switching (removing the
> platform-admin-only gate), add `switch_mode` discriminator to tenant store, fix S-001
> nested response shape, wire post-switch flow per D2.2, and update `ViewingAsBanner`
> per S-003 + OQ-4 default.
>
> **Mode:** Code. Frontend-only.
>
> **Branch:** `feat/sp-2a-orgswitcher-repurpose` from `main`
>
> **Estimated runtime:** ~2 dev-days
>
> **Push:** NO. Local commit only.

---

## Background context

The Phase 2 pre-flight (`docs/platform/phase2-preflight-2026-04-26.md`) identified six
surprises and produced decisions for all non-deferred Phase 2 deliverables. This sub-prompt
implements the items assigned to SP-2A.

### Decision 2.1 — Repurpose in place (Option A)

`OrgSwitcher.tsx` has only one active consumer: `Topbar.tsx:324`. The platform-admin
impersonation flow (`control-plane/admin/tenants/[id]/PageClient.tsx:151–155`) writes
directly to `sessionStorage` and does **not** use `OrgSwitcher`. The component therefore
is safe to repurpose: it will serve both regular users (new path) and, once switch_mode is
wired, continue to work correctly for admin users landing on it.

**Plan:** Remove `PLATFORM_OWNER_ROLES` gate, replace `adminListTenants()` with a new
`listUserOrgs()` call → `GET /users/me/orgs`, replace `switchToTenant()` with a new
`switchUserOrg(id)` call → `POST /users/me/orgs/{id}/switch`.

### Decision 2.2 — Post-switch flow sequence

The verified sequence (pre-flight §2.2):

1. User selects org in OrgSwitcher
2. `POST /users/me/orgs/{tenant_id}/switch` → response: `{ switch_token, target_org: { id, name, role } }`
3. Call `enterSwitchMode({ switch_token: res.switch_token, tenant_id: res.target_org.id, tenant_name: res.target_org.name, switch_mode: "user" })`
4. Call `workspaceStore.switchOrg(res.target_org.id)` — resets `entityId`, `moduleId`
5. Call `queryClient.clear()` — invalidates all org-scoped caches
6. Close the popover; Axios interceptor auto-applies the new `switch_token` on all subsequent requests

### Surprise S-001 — Nested response shape

The backend endpoint `POST /users/me/orgs/{tenant_id}/switch` returns:
```json
{ "switch_token": "...", "target_org": { "id": "...", "name": "...", "role": "..." } }
```
The existing `enterSwitchMode` call site in `handleSelect` reads `result.tenant_id` and
`result.tenant_name` — both `undefined` on the actual response (they are at
`result.target_org.id` and `result.target_org.name`). Fix: update `handleSelect` to use
the nested shape.

### Surprise S-003 — `ViewingAsBanner` admin copy shown to all switch states

`ViewingAsBanner.tsx:59` hardcodes "Read-only · 15 min token" for ALL `is_switched === true`
states. Regular users switching their own orgs would see this alarming copy. Fix: add
`switch_mode: "admin" | "user"` to `TenantState`, set it in `enterSwitchMode`, and update
`ViewingAsBanner` to render "Read-only · 15 min token" only when `switch_mode === "admin"`.

### OQ-4 default — No banner for `switch_mode === "user"`

Per the pre-flight update (OQ-4): when `switch_mode === "user"`, show **no banner**. The
TopBar org name alone is sufficient to indicate the active org context. The admin impersonation
banner ("Read-only · 15 min token") is preserved for `switch_mode === "admin"`.

---

## Hard rules

1. No edits to backend files. Frontend-only.
2. The admin impersonation flow (`PageClient.tsx` in the control-plane) must remain unaffected.
3. `PLATFORM_OWNER_ROLES` gate removed entirely from `OrgSwitcher.tsx` — all authenticated
   users may use the switcher.
4. Do not add a new banner component for `switch_mode === "user"` — OQ-4 default is **no banner**.
5. `queryClient.clear()` (not selective invalidation) is the required cache strategy on org switch.
6. No TypeScript `any` casts. Type the new API response shapes explicitly.
7. Build, typecheck, and lint must pass clean before committing.

---

## Pre-flight (run before writing any code)

```bash
git status          # must be clean
git log --oneline -1  # confirm on main

git checkout -b feat/sp-2a-orgswitcher-repurpose
git branch --show-current

# Confirm the four files to be edited exist
ls frontend/components/layout/OrgSwitcher.tsx
ls frontend/lib/store/tenant.ts
ls frontend/components/layout/ViewingAsBanner.tsx

# Confirm lib/api/orgs.ts does NOT yet exist (SP-2A creates it)
ls frontend/lib/api/orgs.ts 2>/dev/null && echo "EXISTS — investigate" || echo "not found — create as new"

# Confirm the switch endpoint response shape has NOT changed since pre-flight
rg "SwitchOrgResponse|SwitchTargetOrg" backend/financeops/api/v1/users.py -n
# Expected: SwitchTargetOrg { id, name, role }, SwitchOrgResponse { switch_token, target_org }

# Confirm ViewingAsBanner copy is still the hardcoded admin text
rg "Read-only.*15 min" frontend/components/layout/ViewingAsBanner.tsx -n
# Expected: line ~59 with the hardcoded amber text

# Confirm enterSwitchMode signature in tenant store
rg "enterSwitchMode" frontend/lib/store/tenant.ts -n
# Expected: params { switch_token, tenant_id, tenant_name, tenant_slug? }
```

**STOP and report if:**
- The switch endpoint response shape has changed (new fields, flat shape, etc.)
- `ViewingAsBanner.tsx:59` no longer contains the hardcoded "Read-only · 15 min token" text
- `lib/api/orgs.ts` already exists with conflicting content

If all checks pass, proceed to Section 1.

---

## Section 1 — `switch_mode` discriminator in tenant store

**File:** `frontend/lib/store/tenant.ts`

1. Add `switch_mode: "admin" | "user" | null` to `TenantState` (alongside `is_switched`).
   Default value: `null`.
2. Update `enterSwitchMode` to accept an optional `switch_mode?: "admin" | "user"` parameter
   in its params object. Default to `"admin"` for backward compatibility (preserves current
   admin impersonation behavior exactly).
3. In the `enterSwitchMode` implementation, set `switch_mode` from params (or `"admin"` if
   omitted).
4. In `exitSwitchMode`, reset `switch_mode` to `null`.
5. Verify all existing callers of `enterSwitchMode` compile without error. The admin
   impersonation flow in the control-plane `PageClient` that calls this directly (if any)
   should continue to work because `switch_mode` defaults to `"admin"`.

**STOP checkpoint:** Confirm typecheck passes on `tenant.ts` and its callers before proceeding.

---

## Section 2 — S-001: New API module + response shape adapter

**File to create:** `frontend/lib/api/orgs.ts`

Create with two exports:

```typescript
import apiClient from "@/lib/api/client"

export interface UserOrgItem {
  org_id: string
  org_name: string
  org_slug: string
  org_status: string
  role: string
  is_primary: boolean
  joined_at: string
}

export interface UserOrgsListResponse {
  items: UserOrgItem[]
  total: number
}

export interface SwitchOrgTargetOrg {
  id: string
  name: string
  role: string
}

export interface SwitchOrgResponse {
  switch_token: string
  target_org: SwitchOrgTargetOrg
}

export async function listUserOrgs(): Promise<UserOrgsListResponse> {
  const res = await apiClient.get<UserOrgsListResponse>("/api/v1/users/me/orgs")
  return res.data
}

export async function switchUserOrg(tenantId: string): Promise<SwitchOrgResponse> {
  const res = await apiClient.post<SwitchOrgResponse>(
    `/api/v1/users/me/orgs/${tenantId}/switch`,
    {},
  )
  return res.data
}
```

Verify the response type shapes against `backend/financeops/api/v1/users.py` (pre-flight
Appendix A) before finalizing. No shape changes allowed without investigation.

---

## Section 3 — Repurpose `OrgSwitcher.tsx`

**File:** `frontend/components/layout/OrgSwitcher.tsx`

The component currently:
- Gates on `PLATFORM_OWNER_ROLES` at lines 28–30 (returns null for regular users)
- Calls `adminListTenants({ limit: 200 })` — platform admin endpoint
- Calls `switchToTenant(tenant.id)` — admin switch alias in `lib/api/admin.ts`
- `handleSelect` reads `result.tenant_id` and `result.tenant_name` (flat shape — WRONG for new endpoint)

Changes required:

1. **Remove** the `PLATFORM_OWNER_ROLES` constant and the role-gate early return. All
   authenticated users should see the switcher (assuming at least 2 active org memberships;
   the component already handles the single-org / empty case gracefully with the existing
   loading/empty states).

2. **Replace** `adminListTenants()` with `listUserOrgs()` from `lib/api/orgs.ts`. Update
   the query key and response field mappings:
   - `tenant.id` → `item.org_id`
   - `tenant.name` → `item.org_name`
   - `tenant.slug` → `item.org_slug`

3. **Replace** `switchToTenant(tenant.id)` with `switchUserOrg(item.org_id)` from
   `lib/api/orgs.ts`.

4. **Update** `handleSelect` to read the nested response shape (S-001 fix):
   ```typescript
   const result = await switchUserOrg(item.org_id)
   enterSwitchMode({
     switch_token: result.switch_token,
     tenant_id: result.target_org.id,
     tenant_name: result.target_org.name,
     switch_mode: "user",                  // ← user-mode switch
   })
   workspaceStore.switchOrg(result.target_org.id)
   queryClient.clear()
   ```

5. Preserve the existing loading state, error state, and popover/command-list structure.

6. The `isSwitched` read at line 43 (`useTenantStore((s) => s.is_switched)`) may be used to
   highlight the active org or disable the current org in the list. Keep this behavior.

---

## Section 4 — Post-switch flow wiring

This is largely implemented in Section 3's `handleSelect`. Verify completeness:

- [ ] `POST /users/me/orgs/{id}/switch` is called via `switchUserOrg`
- [ ] `enterSwitchMode` is called with `switch_mode: "user"` and nested response fields
- [ ] `workspaceStore.switchOrg(result.target_org.id)` called — resets `entityId`, `moduleId`
- [ ] `queryClient.clear()` called — full cache invalidation
- [ ] Popover closes after selection (existing close behavior preserved)
- [ ] Axios interceptor picks up `switch_token` automatically on subsequent requests
  (this is existing behavior in `lib/api/client.ts:120–122` — no change needed)

Confirm by reading `lib/api/client.ts:106–145` to verify the interceptor behavior matches
the pre-flight's description at §1.3.

---

## Section 5 — `ViewingAsBanner` gate (S-003 fix + OQ-4)

**File:** `frontend/components/layout/ViewingAsBanner.tsx`

Current behavior: renders "Read-only · 15 min token" for ALL `is_switched === true` states.

Required behavior:
- `switch_mode === "admin"`: render the existing banner with "Read-only · 15 min token" copy (unchanged)
- `switch_mode === "user"` OR `switch_mode === null`: render **nothing**

Implementation:
1. Read `switch_mode` from `useTenantStore` alongside `is_switched`.
2. Change the component's render condition: only show the banner when
   `isSwitched && switchMode === "admin"`.
3. Do **not** add any new banner copy for `switch_mode === "user"` — OQ-4 default is no banner.
4. The existing amber banner JSX and the "Exit" button remain unchanged for admin mode.

---

## Verification

```bash
cd frontend

# Build
npm run build 2>&1 | tail -20
# Expected: no errors

# Typecheck
npx tsc --noEmit 2>&1 | tail -30
# Expected: no errors

# Lint
npm run lint 2>&1 | tail -20
# Expected: no warnings or errors

# If existing OrgSwitcher unit tests exist, run them
npx vitest run components/layout/OrgSwitcher 2>/dev/null || echo "no test file found"
```

Verify manually (or via existing tests):
- `enterSwitchMode` called with `switch_mode: "admin"` (old call sites) still sets `is_switched = true`
- `enterSwitchMode` called with `switch_mode: "user"` also sets `is_switched = true`
- `ViewingAsBanner` renders for `switch_mode === "admin"`, hidden for `switch_mode === "user"`

---

## Commit

```bash
git add frontend/components/layout/OrgSwitcher.tsx \
        frontend/lib/api/orgs.ts \
        frontend/lib/store/tenant.ts \
        frontend/components/layout/ViewingAsBanner.tsx
git status   # confirm only those 4 files staged

git commit -m "$(cat <<'EOF'
feat(phase2/sp-2a): repurpose OrgSwitcher for all-user org switching

- Remove PLATFORM_OWNER_ROLES gate; all authenticated users can switch orgs
- New lib/api/orgs.ts: listUserOrgs() + switchUserOrg() against BE-001 endpoints
- Fix S-001: handleSelect reads nested target_org response shape
- Add switch_mode: "admin" | "user" to TenantState + enterSwitchMode params
- Post-switch flow: enterSwitchMode → workspaceStore.switchOrg → queryClient.clear
- Fix S-003/OQ-4: ViewingAsBanner "Read-only" copy gated on switch_mode === "admin" only

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
git log --oneline -1
git status
```

**Do NOT push. Do NOT merge.**

---

## Report back

Report to the human:

1. Commit hash and branch name
2. Files changed with line counts
3. Confirmation that the admin impersonation path (control-plane `PageClient`) was not touched
4. Any deviations from the section specs and why
5. Whether any existing tests failed and how they were resolved
6. Whether any unexpected files were discovered during implementation that should be added to the file-touch list for a future sub-prompt
