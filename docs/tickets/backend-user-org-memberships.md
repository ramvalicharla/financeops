# Backend Ticket — `feat(schema): add user_org_memberships table + backfill`

**Type:** Backend schema + API
**Priority:** High — prerequisite for Phase 2 frontend work
**Estimate:** 6–10 dev-days (range, not a point estimate — see rationale)
**Blocks:** Phase 2 (Org + Entity Switching)
**Does not block:** Phase 0, Phase 1 — can start in parallel with those
**Owner:** _[assign to backend]_

---

## Background

The Gap 2 OrgSwitcher trace (`docs/audits/gap2-orgswitcher-trace-2026-04-25.md`) discovered that the current `OrgSwitcher.tsx` is a **platform admin impersonation tool**, not a multi-org membership switcher for regular users. Phase 2 of the shell rebuild plans to expose org switching to any user who belongs to 2+ orgs.

The follow-up schema check (Section 9 of the same document) confirmed that `IamUser` is **single-org today**. Four independent signals:

| Layer | Evidence |
|---|---|
| Model docstring | `users.py:32` — "Belongs to exactly one tenant." |
| Schema | Single `tenant_id` FK column, `nullable=False`. No junction table spans tenants. |
| JWT construction | `auth_service.py:140` — `create_access_token(user.id, user.tenant_id, …)` — singular, always |
| Frontend types | `next-auth.d.ts` — `tenant_id: string` (not array) |

The two junction tables that exist (`cp_user_organisation_assignments`, `cp_user_entity_assignments`) are within-tenant assignment tables — they manage which orgs/entities a user can see inside their one tenant, not cross-tenant membership.

**Therefore:** Before Phase 2's frontend OrgSwitcher work can begin, the backend needs a schema change and related API work so that a single user can belong to multiple tenants/orgs.

---

## Goal

Enable a user to belong to multiple orgs (tenants), and expose the list of their memberships at an API the frontend can read.

---

## Scope

### 1. Design decision: migration strategy

Two possible approaches. The ticket owner must pick one before implementation.

**Approach A — Add membership table alongside `tenant_id` (dual source of truth temporarily)**

- Keep `IamUser.tenant_id` as the user's "primary / home org" column
- Add new `user_org_memberships` table: `(user_id, org_id, role, is_primary, joined_at, ...)`
- Backfill: for every existing `IamUser`, insert a row into `user_org_memberships` with `org_id = tenant_id, is_primary = True`
- Queries that need "all of user's orgs" go to `user_org_memberships`
- Queries that need "the user's current org context" continue to use whatever the session/JWT carries

Trade-offs:
- Pros: minimal disruption; existing queries keep working; rollback is drop the new table
- Cons: two sources of truth; future migration still needed to fully retire `tenant_id` as a user column
- Estimate: ~5 dev-days

**Approach B — Drop `tenant_id` from `IamUser`, membership table becomes sole source of truth**

- Add `user_org_memberships` table with same shape as Approach A
- Backfill from existing `IamUser.tenant_id`
- Remove `IamUser.tenant_id` column
- Update every query that referenced `user.tenant_id` to go through memberships
- JWT shape changes: carries `user_id` + `current_org_id` (user's active org selection), not `user_id` + `tenant_id`

Trade-offs:
- Pros: single source of truth; correct model long-term; no follow-up migration needed
- Cons: touches every query that uses `user.tenant_id`; larger rollout risk; requires forced re-login or backwards-compat JWT handling
- Estimate: ~9 dev-days

**Recommendation:** Approach A for this ticket. Schedule Approach B as a follow-up ticket for post-Phase-2. Approach A unblocks Phase 2 fastest and lets us validate the multi-org UX with real users before committing to the fuller refactor.

### 2. Schema changes (Approach A)

New table `user_org_memberships`:

```
user_id        UUID     FK → iam_users.id    NOT NULL
org_id         UUID     FK → orgs.id         NOT NULL
role           VARCHAR  NOT NULL             (member/admin/owner - or existing role enum)
is_primary     BOOLEAN  NOT NULL DEFAULT FALSE
joined_at      TIMESTAMP NOT NULL DEFAULT NOW()
invited_by     UUID     FK → iam_users.id    NULLABLE
status         VARCHAR  NOT NULL DEFAULT 'active'  (active/invited/suspended)

UNIQUE (user_id, org_id)
```

The `is_primary` flag replaces what `IamUser.tenant_id` previously meant — exactly one row per user has `is_primary = TRUE`. This invariant should be enforced either by a partial unique index or application-level logic.

### 3. Alembic migration

Single migration file. The migration must:

1. Create the `user_org_memberships` table
2. Backfill: `INSERT INTO user_org_memberships (user_id, org_id, role, is_primary, joined_at, status) SELECT id, tenant_id, role, TRUE, created_at, 'active' FROM iam_users` (adjust column names to actual schema)
3. Add the partial unique index enforcing one primary per user
4. Verify backfill integrity (every existing `IamUser` has exactly one `is_primary = TRUE` membership row)

Run on disposable DB first (as we did for migration 0066).

### 4. API endpoint

New endpoint:

```
GET /api/v1/users/me/orgs

Response:
[
  {
    "org_id": "uuid",
    "org_name": "Acme Inc",
    "role": "admin",
    "is_primary": true,
    "joined_at": "2024-01-15T10:00:00Z"
  },
  ...
]

Auth: any authenticated user
Permission: none (users can always list their own memberships)
```

Add a matching endpoint for switching the active org:

```
POST /api/v1/users/me/switch-org
Body: { "org_id": "uuid" }

Response: new access token scoped to the target org
Auth: authenticated, and user must have a membership in the target org_id
Error cases:
  - 403 if user has no membership in target org
  - 400 if target org is suspended/invalid
```

This endpoint issues a new JWT similar to the admin impersonation token flow today, but scoped to orgs the user actually belongs to.

### 5. JWT / session considerations

Under Approach A, `IamUser.tenant_id` stays — so existing JWTs continue to validate. The `/switch-org` endpoint issues a new JWT with a different `tenant_id`.

**Rollout:**
- Existing users: no forced logout. Their session continues with their primary org. When they explicitly use the switcher, they get a new session.
- New users: login flow looks up their primary membership and issues JWT with that `tenant_id`.

### 6. Impact on existing junction tables

`cp_user_organisation_assignments` and `cp_user_entity_assignments` remain within-tenant assignment tables. No change to their semantics. Their queries already filter on `tenant_id` inside the current org context, so they continue to work.

### 7. Tests

- Unit tests for `user_org_memberships` model
- Integration test: user with 2 memberships can list both
- Integration test: user can switch to their second org and access its data
- Integration test: user cannot switch to an org they don't have a membership in (expect 403)
- Migration test: backfill produces exactly one `is_primary = TRUE` per user
- Backwards compat: existing single-org users still work exactly as before

---

## Acceptance criteria

- [ ] Migration runs clean on a disposable DB
- [ ] Migration reverts cleanly (`alembic downgrade`)
- [ ] Backfill verified: every existing `IamUser` has exactly one membership row with `is_primary = TRUE`
- [ ] `GET /api/v1/users/me/orgs` returns the logged-in user's memberships
- [ ] `POST /api/v1/users/me/switch-org` issues a new token scoped to the target org
- [ ] 403 returned for users trying to switch to an org they don't belong to
- [ ] All existing tests still pass
- [ ] New tests added for the multi-org flow
- [ ] Frontend smoke test: existing single-org users experience no change

---

## Estimate rationale

I've estimated this at 6–10 dev-days rather than a point estimate because:

- The mechanical work (new table, backfill, endpoint) is ~3 days
- The JWT/token rollout design is ~1–2 days (decisions + implementation)
- Testing thoroughly across backwards-compat scenarios is ~1–2 days
- Buffer for unexpected coupling with `cp_user_organisation_assignments` / `cp_user_entity_assignments` queries: ~1–2 days

If this comes in under 6 days, great. If it runs to 10, that's still within plan.

---

## Related tickets

- Phase 2 frontend work (`feat(shell): phase 2 — OrgSwitcher for all users`) depends on this ticket
- Future ticket (post-Phase-2): `refactor(identity): retire IamUser.tenant_id column, complete Approach B migration`

---

## Notes for the engineer

1. The Gap 2 trace document (`docs/audits/gap2-orgswitcher-trace-2026-04-25.md`) Sections 4–7 document the current admin impersonation flow in detail. That flow's token-swap mechanism (Axios interceptor + Zustand `is_switched` flag) is reusable for the user-facing switch — the frontend already has the plumbing.

2. Do NOT touch the existing admin impersonation endpoints (`/api/v1/platform/admin/tenants/...`). Those serve a separate use case and should remain as-is.

3. The `is_primary` flag's long-term purpose is to support "default workspace on login" — when a user logs in without specifying an org, they get their primary. This becomes configurable in-app later (separate ticket).

4. Consider adding an `is_owner` boolean on `user_org_memberships` if you don't already have a role that captures org ownership (the user who created the org, for billing/deletion purposes). If `role` enum already includes `owner`, skip this.
