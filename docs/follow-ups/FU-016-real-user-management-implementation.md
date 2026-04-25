---
name: Real user management implementation
description: Users tab in /settings/team is a placeholder stub — real user management UI needs to be built
type: project
---

# FU-016 — Real user management implementation

**Opened:** 2026-04-26
**Related to:** Phase 1 sub-prompt 1.6.3 (team consolidation)
**Spec ref:** Sidebar §1.3 Governance group "Team · RBAC"

## Background

Phase 1 sub-prompt 1.6.3 consolidated /settings/users + /settings/groups
into /settings/team with shadcn Tabs. The Groups tab renders the existing
functional groups management UI. The Users tab renders a placeholder stub
that was the original /settings/users page content — there has never been
a real user management UI in this codebase.

The consolidation is still useful because it creates the canonical URL
(/settings/team) and the tab structure ready for when real user management
lands. But the Users tab itself is a placeholder.

## Scope

Build a real user management UI in the Users tab. Likely components:

1. User list table (existing platform admin user management may have a
   reference implementation — check control-plane/admin/tenants/[id]/PageClient
   for pattern)
2. Add user / invite user modal
3. Per-user role assignment (depends on FU-012 RBAC behavioral wiring)
4. Per-user group assignment (cross-link with the existing Groups tab)
5. User suspension / removal flows
6. Audit trail per user (cross-link with /governance/audit)

## Dependencies

- FU-012 (sidebar behavioral wiring including RBAC) provides per-permission
  gating for these flows
- Backend: user CRUD endpoints likely exist for the platform admin path —
  may need scoping/permission adjustments to expose to org admins

## Estimate

Unknown — depends on backend availability and design decisions. Likely
1-3 days when the work is picked up.

## Out of scope

- The Groups tab — already functional from existing /settings/groups
- The /settings/team URL itself — created by 1.6.3
- Tabs UI shell — created by 1.6.3
