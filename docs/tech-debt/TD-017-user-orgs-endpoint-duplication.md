# TD-017 — User Orgs Endpoint Duplication

**Filed:** 2026-04-26  
**Filed by:** SP-2A (OrgSwitcher repurpose)  
**Area:** Frontend / API duplication  
**Severity:** Low  
**Effort to consolidate:** ~4h

---

## Problem

The backend exposes two endpoints that both return a user's org memberships:

| Endpoint | Response shape | Backend model |
|---|---|---|
| `GET /api/v1/user/tenants` | `list[UserTenantOut]` — flat: `{ id, slug, name, role, status, plan }` | `backend/financeops/api/v1/users.py:267` |
| `GET /api/v1/users/me/orgs` | `UserOrgsListResponse` — `{ items: UserOrgItem[], total }` where `UserOrgItem` has `org_id, org_name, org_slug, org_status, role, is_primary, joined_at` | `backend/financeops/api/v1/users.py:420` |

The frontend client module `frontend/lib/api/orgs.ts` wraps both under separate functions, which means:
- Two round-trips to different endpoints for the same logical resource
- Two diverging type surfaces (`OrgSummary` vs `UserOrgItem`)
- Two field-naming conventions (`tenant_id` / `display_name` vs `org_id` / `org_name`)

---

## Current consumers

### `/api/v1/user/tenants` — via `listUserOrgs()`
- **[frontend/app/(auth)/orgs/PageClient.tsx:9](../../frontend/app/(auth)/orgs/PageClient.tsx)** — renders the user's org list on the Orgs page; uses `OrgSummary` shape (`tenant_id`, `display_name`, `subscription_tier`, etc.)
- **[frontend/tests/unit/orgs_api.test.ts:2](../../frontend/tests/unit/orgs_api.test.ts)** — unit tests for `listUserOrgs()`

### `/api/v1/users/me/orgs` — via `listUserSwitchableOrgs()`
- **[frontend/components/layout/OrgSwitcher.tsx](../../frontend/components/layout/OrgSwitcher.tsx)** — popover that lets any authenticated user switch their active org; added in SP-2A

---

## Why they are separate today

SP-2A was assigned to repurpose `OrgSwitcher.tsx` to use the newer `/users/me/orgs` endpoint (which carries `role`, `is_primary`, and `joined_at` — richer data for the switcher UX). At the time SP-2A was written, `lib/api/orgs.ts` already contained `listUserOrgs()` targeting the older `/user/tenants` endpoint, with `PageClient.tsx` and its unit tests as live consumers. Replacing `listUserOrgs()` in-place would have broken `PageClient.tsx` and was classified as a scope deviation (>10% change outside the SP-2A file list). The additive Option A was chosen: keep `listUserOrgs()` unchanged, add `listUserSwitchableOrgs()` for the switcher.

---

## Migration path (if a future decision is to consolidate)

1. **Choose the canonical endpoint.** The newer `/users/me/orgs` shape is richer (`is_primary`, `joined_at`, `role`) and follows REST naming conventions. Recommend deprecating `/user/tenants`.

2. **Update `PageClient.tsx`** to call `listUserSwitchableOrgs()` (or a renamed `listUserOrgs()`) and remap field names:
   - `tenant_id` → `org_id`
   - `display_name` → `org_name`
   - `tenant_slug` → `org_slug`
   - `subscription_tier` — not in `UserOrgItem`; requires backend addition or a separate call to org details

3. **Update `OrgSummary`** type (or replace with `UserOrgItem`) in `PageClient.tsx` and its supporting components (`TierBadge`, `OrgCard`).

4. **Update `orgs_api.test.ts`** to mock the new endpoint and assert against `UserOrgItem` shape.

5. **Remove `/api/v1/user/tenants`** from the backend once no consumer remains.

6. **Remove `listUserOrgs()`** and the `OrgSummary` / `SubscriptionTier` / `UserTenantPayload` types from `lib/api/orgs.ts`.

Note: `subscription_tier` is computed client-side from `plan` in the current `listUserOrgs()` adapter. If `PageClient.tsx` needs tier data after migration, the backend `UserOrgItem` must be extended with a `plan` or `subscription_tier` field.

---

## Cross-references

- **SP-2A** — sub-prompt that introduced `listUserSwitchableOrgs()` and `switchUserOrg()`; see `docs/prompts/phase2/SP-2A-orgswitcher-repurpose.md`
- **TD-016** — related Phase 2 frontend tech-debt item
