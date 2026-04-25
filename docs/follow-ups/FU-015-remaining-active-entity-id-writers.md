---
# FU-015 — Remaining writers of deprecated tenantStore.active_entity_id

**Opened:** 2026-04-25
**Related to:** Hotfix 1.1.5 (fix for the dangerous READs); extends FU-005
**Severity at audit:** Major (audit finding F5 second half)

## Background

Hotfix 1.1.5 fixed two production-path READs of `tenantStore.active_entity_id`:

1. `lib/api/client.ts` — 403/ORG_SETUP_REQUIRED recovery interceptor (line ~224)
2. `app/(org-setup)/org-setup/OrgSetupPageClient.tsx` — `finishSetup()` fallback
   (line ~115)

These were the dangerous ones: they sent stale entity context to the backend or
passed stale IDs downstream during auth/setup flows.

The deprecated field still has live WRITERS across multiple files. Each writer
populates `tenantStore.active_entity_id` to a value that nothing
production-critical reads anymore (post-hotfix). The writers are dead weight
that shipped before the workspaceStore migration completed.

## WRITE call sites identified by hotfix 1.1.5 Step 2 audit

| File | Line(s) | Pattern |
|------|---------|---------|
| `app/(auth)/login/PageClient.tsx` | 213, 301 | `active_entity_id: user.entity_roles.at(0)?.entity_id ?? null` |
| `app/(auth)/mfa/PageClient.tsx` | 114 | `active_entity_id: user.entity_roles.at(0)?.entity_id ?? null` |
| `app/(auth)/mfa/setup/PageClient.tsx` | 181 | `active_entity_id: user.entity_roles.at(0)?.entity_id ?? null` |
| `app/(org-setup)/org-setup/OrgSetupPageClient.tsx` | 122 | `active_entity_id: newEntityId` (write in setTenant payload) |
| `components/control-plane/ControlPlaneTenantBootstrap.tsx` | 33 | `active_entity_id: entityRoles.at(0)?.entity_id ?? null` |
| `components/layout/Sidebar.tsx` | 80 | `active_entity_id: entityRoles.at(0)?.entity_id ?? null` |

## Scope

For each call site, the change is:

1. Verify the call site does not READ `active_entity_id` later in the same
   function (hotfix 1.1.5 already eliminated all known READs, but verify).

2. Remove the `active_entity_id` field from the `setTenant({...})` call
   payload.

3. If `setTenant({...})` becomes empty after removal, remove the call entirely.

4. Verify `workspaceStore.setEntityId(...)` is being called somewhere on the
   same code path with the same value. If not, ADD it — workspaceStore is the
   source of truth.

## Acceptance criteria

- [ ] All identified writers either remove the deprecated field write or
      confirm `workspaceStore.setEntityId()` is called on the same path
- [ ] No production code path leaves `workspaceStore.entityId` unset where
      a value was previously set on `tenantStore.active_entity_id`
- [ ] Tests pass; login, MFA, and org-setup flows still set entity context
      correctly post-change
- [ ] `grep -rn "active_entity_id" frontend/` returns only TYPE and
      store-implementation lines (tenant.ts lines 14, 31, 53, 74, 82–83, 92, 124)

## Relationship to FU-005

FU-005 ("Remove deprecated fields from legacy stores") is the ultimate
cleanup. FU-015 is the prerequisite: ALL writers must stop writing the
field before FU-005 can safely remove it from the store schema.

Order of operations:
1. Hotfix 1.1.5 — fix the dangerous READs ✅
2. FU-015 — fix all writers (this ticket)
3. FU-005 — remove `active_entity_id` and `active_location_id` from tenant.ts
             and `activePeriod`/`sidebarCollapsed` from ui.ts

## Estimate

2–3 hours. Mostly mechanical edits + verification per file.
