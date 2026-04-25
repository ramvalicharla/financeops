# FU-012 — Sidebar behavioral wiring (badges, RBAC filter, real routes)

**Opened:** 2026-04-25
**Related to:** Phase 1 sub-prompt 1.1 (deferred behavioral concerns)
**Spec ref:** finqor-shell-audit-2026-04-24.md §1.3 items 3–4; findings #4, #28

## Background

Phase 1 sub-prompt 1.1 rebuilt the sidebar's structure (three groups, 220px,
12 items via nav-config.ts). The behavioral wiring was deliberately deferred
to keep the PR reviewable. Audit task list for Phase 1 included these
behavioral concerns; user direction was to ship structure first and capture
behavior as a follow-up.

## Scope (3 independent tracks; can be split into separate PRs)

### Track 1 — Approvals badge

- Wire the Approvals nav item's `badge.count` to a live endpoint. Likely
  `GET /api/v1/approvals?status=pending&limit=0` (count-only).
- Use TanStack Query with `queryKeys.workspace.approvalsCount(orgId)` (extend
  the query-key factory; this domain doesn't exist yet).
- Polling interval: 60s, or driven by SSE / WebSocket if those exist.
- Tone: warning when count > 0, none when count = 0.

Acceptance: open sidebar with pending approvals → badge shows count;
mark approval as resolved → badge updates within polling interval.

### Track 2 — RBAC filter at the item level

- Extend `NavItem` in nav-config.ts with optional `requiredPermission?: string`
  and `requiredRole?: string[]`.
- Update `filterNavigationItems()` (or its replacement) to filter items within
  groups based on the user's permissions and role.
- Audit trail item under Governance must be visible to `auditor` role
  (resolves audit finding #28).
- Modules item under Org must be gated on `module.manage` permission once
  that permission exists in backend (Phase 3 prerequisite).

Acceptance: log in as `auditor` → sees Audit trail; log in as `finance_team` →
no `+` button on tabs (separate concern, but RBAC plumbing shared); log in as
`viewer` → governance group only shows allowed items.

### Track 3 — Real routes for placeholder items

Today's placeholder hrefs (all → `/dashboard`):
- Today's focus
- Period close
- Approvals
- Possibly others (audit which routes were placeholdered in 1.1's report)

For each:
- Backend: confirm endpoint and route exists or file backend ticket.
- Frontend: create the page under `frontend/app/(dashboard)/{route}/page.tsx`.
- Update nav-config.ts to point at the real href; remove the
  `// TODO Phase 2` comment.

Acceptance: clicking each item navigates to the real page (not /dashboard).

## Dependencies

- Track 1 depends on backend confirming approvals endpoint shape.
- Track 2 depends on Phase 3 backend ticket `feat(rbac): add module.manage
  permission` and on existing role/permission data already on the JWT.
- Track 3 may overlap with Phase 2 (Today's focus and Period close are both
  natural Phase 2 surfaces).

## Out of scope

- Group collapse state persistence (separate concern; will be folded into the
  Phase 4 collapsed-rail server preferences work).
- Entity card behavior (Phase 2, finding #3).
- Entity tree (Phase 2, finding #7).
