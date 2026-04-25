# FU-016 — Backend dependency clarification

**Date:** 2026-04-26
**Status:** Decided
**Decided by:** Pre-flight investigation, Lane A.2

---

## Question

What backend does FU-016 (real user management on `/settings/team`) actually
depend on, and how does it interact with BE-001?

---

## Findings

### Existing user-management surface area

The backend already ships a complete user management API at `/api/v1/users*`,
registered in `backend/financeops/api/v1/router.py:98` (no prefix) and mounted
at `/api/v1` in `backend/financeops/main.py:629`.

Every operation FU-016 scoped is already implemented:

| Endpoint | File:Line | What it does |
|---|---|---|
| `GET /api/v1/users` | `users.py:300` | List all users in caller's tenant |
| `POST /api/v1/users` | `users.py:312` | Invite user — email, full_name, role, entity_ids — sends email notification |
| `GET /api/v1/users/{user_id}` | `users.py:392` | Fetch single user |
| `PATCH /api/v1/users/{user_id}/role` | `users.py:402` | Role assignment (validates against tenant-assignable roles) |
| `DELETE /api/v1/users/{user_id}` | `users.py:429` | Offboard user |
| `POST /api/v1/users/{user_id}/offboard` | `users.py:449` | Offboard with explicit reason string |

All six routes sit behind `tenant_user_manage_guard` (`deps.py:*`) which
requires `resource_type="tenant_user", action="manage"` or one of the fallback
roles (`super_admin`, `platform_owner`, `platform_admin`, `finance_leader`).

The invite flow (`POST /api/v1/users`) is fully wired: it creates an
`IamUser` with `is_active=False`, generates a secure invite token, assigns
`CpUserEntityAssignment` rows for requested entities, and sends a notification
via `send_notification`.

Per-user group assignment is not a separate endpoint on users. Groups are
managed from the groups side (`/api/v1/platform/org/groups`), which is already
used by `GroupsPanel.tsx`. FU-016's "per-user group assignment" item is
therefore a frontend cross-link to the groups tab — not a missing API.

Audit trail per user: the existing `/governance/audit` page is the canonical
audit destination. No new backend needed.

### What FU-016 needs (per the FU itself + the placeholder UI)

From `docs/follow-ups/FU-016-real-user-management-implementation.md`:

1. User list table
2. Add user / invite user modal
3. Per-user role assignment (depends on FU-012 RBAC behavioral wiring)
4. Per-user group assignment (cross-link with Groups tab)
5. User suspension / removal flows
6. Audit trail per user (cross-link with `/governance/audit`)

Current `UsersPanel.tsx` state (`_components/UsersPanel.tsx:1-15`):
a static div with the text "User and role management is available via the
platform users module." — zero API calls, no TODOs in the file itself.

The FU-016 doc calls out: "user CRUD endpoints likely exist for the platform
admin path — may need scoping/permission adjustments to expose to org admins."
The investigation confirms they exist and are already scoped to org admins
(the `tenant_user_manage_guard` is explicitly NOT a platform-admin-only gate).

### What BE-001 delivers vs what FU-016 needs

**BE-001** (`docs/tickets/backend-user-org-memberships.md`) is about one user
belonging to **multiple tenants/orgs**. It adds:

- A new `user_org_memberships` table (user × org × role × is_primary)
- `GET /api/v1/users/me/orgs` — a user's own cross-org memberships
- `POST /api/v1/users/me/switch-org` — issue a new JWT scoped to a different org

**FU-016** needs: list users, invite users, change roles, offboard users
**within** the caller's current org.

These are orthogonal concerns:

| Dimension | BE-001 | FU-016 needs |
|---|---|---|
| Subject | Which orgs does *this user* belong to? | Who are the users *in this org*? |
| New table | `user_org_memberships` | None — uses `iam_users` |
| New endpoints | `GET /me/orgs`, `POST /me/switch-org` | None — fully covered by existing `/users*` |
| Auth model | Any authenticated user listing own memberships | Org-admin gate via `tenant_user_manage_guard` |

BE-001 does NOT add user-listing, invite, role-change, or offboard endpoints.
It does NOT ship anything FU-016 needs. Conversely, FU-016 does not require
the `user_org_memberships` table that BE-001 creates.

---

## Decision

**Scenario: X**

FU-016's backend is already fully built and is entirely independent of BE-001.
The Users tab in `/settings/team` is a frontend-only task today.

**Reasoning:**

1. `GET /api/v1/users`, `POST /api/v1/users`, `PATCH /api/v1/users/{id}/role`,
   `DELETE /api/v1/users/{id}`, and `POST /api/v1/users/{id}/offboard` are all
   live, tested, and registered in the v1 router (`users.py:300–467`). Every
   operation in FU-016's scope maps directly to an existing endpoint.

2. The `tenant_user_manage_guard` already gates these routes at the org-admin
   level — not a platform-admin-only wall. The FU-016 doc's concern about
   "scoping/permission adjustments" is resolved: the endpoints already target
   the org-admin actor.

3. BE-001 solves a completely different problem (cross-org membership for the
   OrgSwitcher). FU-016's user management is entirely within a single org
   (`tenant_id`-scoped). No BE-001 deliverable is on FU-016's critical path.

4. The only FU-016 items without a dedicated API endpoint are the ones
   explicitly described as cross-links (audit trail → `/governance/audit`,
   group assignment → existing groups tab). These require zero new backend.

The "1–3 days depending on backend" estimate in the handoff was conservative
because the backend status was unknown at time of writing. Now that the backend
is confirmed complete, the remaining work is purely frontend UI: build the
users table, invite modal, role picker, and offboard flow against already-live
endpoints.

---

## Consequences

### Scenario X (confirmed)

- FU-016 is a **frontend-only task**: build `UsersPanel.tsx` against the live
  `/api/v1/users*` endpoints.
- No new backend ticket is needed.
- No dependency on BE-001. FU-016 can be drafted and shipped independent of
  the org-switching work.
- The one external dependency that remains is **FU-012** (sidebar behavioral
  wiring / RBAC permission gating). The invite and role-change flows should
  gate on the RBAC permission model FU-012 wires up. If FU-012 is deferred,
  FU-016 can ship with a simpler role-based guard (check `user.role ∈
  {finance_leader, platform_admin, …}`) and upgrade to fine-grained RBAC when
  FU-012 lands.
- The only reason not to ship FU-016 immediately is scheduling priority, not
  missing backend.

---

## Recommendation for sprint planning

- [x] **Sprint 1 (Lane B parallel polish, frontend-only because backend exists)**

FU-016 belongs in **Sprint 1 as a Lane B frontend-polish item**. The backend
is live. The estimate is 1–2 frontend dev-days:

- ~0.5 days: user list table (fetch `GET /api/v1/users`, render rows with role
  badge, status indicator, MFA status)
- ~0.5 days: invite modal (form → `POST /api/v1/users`, email + role + optional
  entity_ids)
- ~0.5 days: role change + offboard flows (inline actions on each row)
- ~0.25 days: wire FU-012 permission gate (or interim role check)

The fact that `GroupsPanel.tsx` already exists as a working reference
implementation (same file tree, same API client pattern, same shadcn Tabs
shell) further reduces ramp-up time.

If FU-012 is not ready in Sprint 1, ship FU-016 with the interim role check
and leave a `// TODO: upgrade to RBAC gate when FU-012 lands` comment on the
permission check only.

---

## References

- FU-016 follow-up: [docs/follow-ups/FU-016-real-user-management-implementation.md](../follow-ups/FU-016-real-user-management-implementation.md)
- BE-001 ticket: [docs/tickets/backend-user-org-memberships.md](../tickets/backend-user-org-memberships.md)
- Users API: [backend/financeops/api/v1/users.py](../../backend/financeops/api/v1/users.py)
- Router registration: [backend/financeops/api/v1/router.py:98](../../backend/financeops/api/v1/router.py#L98)
- Users tab stub: [frontend/app/(dashboard)/settings/team/_components/UsersPanel.tsx](../../frontend/app/(dashboard)/settings/team/_components/UsersPanel.tsx)
- Groups tab reference: [frontend/app/(dashboard)/settings/team/_components/GroupsPanel.tsx](../../frontend/app/(dashboard)/settings/team/_components/GroupsPanel.tsx)
- `/settings/team` consolidation context: Phase 1 sub-prompt 1.6.3, commit `fc6cdb6`
