# FU-003 — Add org-scoped entity endpoint for Phase 2

## Status
Open

## Opened
2026-04-25

## Related to
Phase 0 sub-prompt 0.3 (EntitySwitcher live data wiring)

## Background
During Phase 0 sub-prompt 0.3, the implementation brief assumed a
`GET /api/v1/orgs/{orgId}/entities` endpoint scoped by organisation. The
endpoint does not exist. The wired implementation instead uses
`GET /api/v1/org-setup/entities`, which is JWT-scoped (derives tenant from
token) and returns all entities for the caller's tenant.

This is correct for single-org tenants. For Phase 2 (multi-org support),
where a user may belong to multiple organisations, the switcher must be
scoped to the currently active org.

## Required work (Phase 2)

1. **Backend**: Add `GET /api/v1/orgs/{orgId}/entities` route in
   `backend/financeops/modules/org_setup/api/routes.py`.
   - Path param: `orgId` (UUID)
   - Auth: verify the calling user has access to the org identified by
     `orgId` (not just any org in their tenant)
   - Response: same `list[OrgEntityResponse]` shape as the existing
     `/org-setup/entities` endpoint

2. **Frontend hook** (`frontend/hooks/useOrgEntities.ts`): Replace the
   `listOrgEntities()` call with a new `listOrgEntities(orgId)` call once
   the active org is available from the workspace store.

3. **API client** (`frontend/lib/api/orgSetup.ts`): Add
   `listOrgEntitiesForOrg(orgId: string): Promise<OrgEntity[]>` pointing
   at the new route.

4. **Query key**: Update `queryKeys.workspace.entities()` to accept an
   `orgId` parameter so cache entries are scoped per org.

## Do NOT change until Phase 2
- `useOrgEntities.ts` — current fallback logic is correct for Phase 1
- `queryKeys.workspace.entities()` — no-arg form stays until Phase 2 is
  scoped
- `EntitySwitcher.tsx` — pure presentational, no changes needed
