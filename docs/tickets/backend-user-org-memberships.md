# Backend Ticket — `feat(schema): add user_org_memberships table + backfill`

**Status:** Execution-ready (amended 2026-04-26)
**Amendments:** §4.3 added — auth path for switch tokens (Checkpoint 2 finding)
**Pre-flight completed:** 2026-04-26
**FU-003 decision:** Option B (JWT rotation on switch) — see
`docs/decisions/fu003-entity-endpoint-scoping-decision.md`
**Estimated effort:** 7–11 dev-days (original 6–10 + ~1 day for §4.3 auth path amendment + 2 new integration tests)
**Blocks:** Phase 2 frontend
**Does not block:** Sprint 1 / Sprint 2 frontend FU sweep

**Type:** Backend schema + API
**Priority:** High — prerequisite for Phase 2 frontend work
**Owner:** _[assign to backend]_

---

## Background

The Gap 2 OrgSwitcher trace (`docs/audits/gap2-orgswitcher-trace-2026-04-25.md`) discovered
that the current `OrgSwitcher.tsx` is a **platform admin impersonation tool**, not a
multi-org membership switcher for regular users. Phase 2 of the shell rebuild plans to expose
org switching to any user who belongs to 2+ orgs.

The follow-up schema check (Section 9 of the same document) confirmed that `IamUser` is
**single-org today**. Four independent signals:

| Layer | Evidence |
|---|---|
| Model docstring | `users.py:32` — "Belongs to exactly one tenant." |
| Schema | Single `tenant_id` FK column, `nullable=False`. No junction table spans tenants. |
| JWT construction | `auth_service.py:116–121` — `create_access_token(user.id, user.tenant_id, …)` — singular |
| Frontend types | `next-auth.d.ts` — `tenant_id: string` (not array) |

The two junction tables that exist (`cp_user_organisation_assignments`,
`cp_user_entity_assignments`) are within-tenant assignment tables — they manage which
orgs/entities a user can see inside their one tenant, not cross-tenant membership.

**Therefore:** Before Phase 2's frontend OrgSwitcher work can begin, the backend needs a
schema change and related API work so that a single user can belong to multiple tenants/orgs.

### FU-003 — entity endpoint scoping (resolved)

FU-003 asked whether `GET /api/v1/org-setup/entities` needs an `orgId` path parameter for
multi-org switching, or whether JWT rotation on switch is sufficient. The pre-flight pass
resolved this as **Option B (JWT rotation)**. The existing entity endpoint is unchanged; it
already scopes via `tenant_id` in the JWT. When the switch-org endpoint issues a new JWT
with the target `tenant_id`, the entity endpoint automatically returns that org's entities.
See `docs/decisions/fu003-entity-endpoint-scoping-decision.md` for full analysis.

---

## Goal

Enable a user to belong to multiple orgs (tenants), and expose the list of their memberships
at an API the frontend can read and switch between.

---

## 0. Pre-implementation investigation gate

Before writing any model, migration, or endpoint code, the backend agent must
complete and report on two investigations. Both are read-only. Neither
investigation modifies the codebase. Implementation proceeds only after both
are reported and any required ticket amendments are made.

### 0.1 — `scope` claim handling in the auth path

The admin impersonation flow (`admin.py:519–557`) issues a 900-second JWT with
`scope: "platform_switch"` and `switched_by` claims. The user switch token
defined in Section 4.2 carries **no** `scope` claim. Before implementing,
verify the existing auth path does not reject tokens for missing or
non-`platform_switch` scope claims.

Read and capture verbatim:
- `backend/financeops/api/deps.py` — `get_current_user`, `get_current_tenant`,
  and any related dependency functions
- Any middleware in `backend/financeops/main.py` or `backend/financeops/api/`
  that touches JWT validation
- Any decorator-based guard that inspects token claims

For each, report whether `scope` claims are: (a) ignored, (b) required to
match a specific value, (c) required to be absent, or (d) checked
conditionally. Cite file path and line number for every finding.

**If the existing auth path requires `scope: "platform_switch"`** for any
switch-flavored token, the ticket needs amendment — either issue the user
switch token with a new scope value (e.g. `scope: "user_switch"`) and update
the auth path to accept it, or restructure the check. Stop and request
ticket amendment before proceeding.

**If `scope` is ignored or optional**, the ticket as written is correct.
Proceed.

### 0.2 — `create_access_token` signature

Section 4.2 line 260 shows:
`create_access_token(user.id, target_tenant_id, membership.role.value, additional_claims={})`

The `additional_claims` kwarg may or may not exist on the current
implementation. Read `backend/financeops/core/security.py` and capture the
exact signature of `create_access_token`. Also capture the call site in
`backend/financeops/services/auth_service.py:116–121` for reference.

**If the kwarg exists or the function accepts `**kwargs`**, the ticket as
written is correct. Proceed.

**If the kwarg does not exist and there is no `**kwargs`**, the ticket needs
amendment — either add the kwarg to `create_access_token` (small refactor,
~30 minutes, and re-test all existing call sites), or change Section 4.2 to
construct the JWT inline rather than via `create_access_token`. Stop and
request ticket amendment before proceeding.

### Gate report

The agent must produce a short report (≤ 1 page) at the start of the BE-001
branch, committed as the first commit on that branch:

`docs/audits/be001-investigation-gate-YYYY-MM-DD.md`

The report has two sections (0.1 and 0.2), each ending with the verdict
"Proceed as written" or "Ticket amendment required: [specifics]".

If either verdict is "amendment required", the agent stops and requests the
amendment from the ticket owner before writing implementation code.

### 0.3 — Post-Checkpoint-2 amendment note

The original Section 0 gate investigated two axes: (0.1) scope-claim handling
in `get_current_user`, (0.2) `create_access_token` signature. Both gates
returned "Proceed as written."

Checkpoint 2 integration surfaced a **third axis** that Section 0 did not
investigate: the `tenant_id` consistency check in `get_current_user`
(`deps.py:281`). That check enforces `user.tenant_id == jwt_tenant_id`.
Switch tokens carry `tenant_id = target_tenant_id`, which differs from
`IamUser.tenant_id` (the user's home org). Without amendment, every request
made with a switch token would fail with `AuthenticationError("Token tenant
mismatch")`.

The amended **Section 4.3** resolves this. Future tickets that issue tokens
with a non-home `tenant_id` should add investigation of all three axes to
their Section 0 gate: (a) scope-claim handling, (b) token-construction
signature, (c) tenant consistency checks in auth dependencies.

---

## Scope

### 1. Migration strategy

**Chosen: Approach A — add membership table alongside `tenant_id` (dual source of truth
temporarily).**

Rationale: minimal disruption; existing queries keep working; rollback is drop the new table.
Approach B (drop `tenant_id` from `IamUser`) is deferred as a follow-up ticket after Phase 2.

- Keep `IamUser.tenant_id` as the user's "primary / home org" column (unchanged).
- Add new `user_org_memberships` table (see Section 2).
- Backfill: for every existing `IamUser`, insert one row into `user_org_memberships` with
  `tenant_id = IamUser.tenant_id`, `is_primary = True`.
- Queries that need "all of user's orgs" go to `user_org_memberships`.
- Queries that need "the user's current org context" continue to use whatever the JWT carries.

### 2. Schema changes

New table `user_org_memberships`:

```sql
CREATE TABLE user_org_memberships (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NOT NULL REFERENCES iam_users(id)    ON DELETE CASCADE,
    tenant_id   UUID         NOT NULL REFERENCES iam_tenants(id)  ON DELETE CASCADE,
    role        user_role_enum NOT NULL,
    is_primary  BOOLEAN      NOT NULL DEFAULT FALSE,
    joined_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    invited_by  UUID         REFERENCES iam_users(id)             ON DELETE SET NULL,
    status      VARCHAR(20)  NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_org UNIQUE (user_id, tenant_id)
);

-- Exactly one primary per user (partial unique index)
CREATE UNIQUE INDEX uq_user_one_primary
    ON user_org_memberships (user_id)
    WHERE is_primary = TRUE;
```

**Column notes:**
- `role` uses the existing `user_role_enum` Postgres enum (defined in migration 0001).
- `status` values: `'active'` | `'invited'` | `'suspended'`.
- `is_primary` = True means "default org on login". Invariant: exactly one row per user.
- `invited_by` is nullable — self-signup or admin-provisioned users have no inviter.
- No `chain_hash` / `previous_hash` — this is a membership table, not a financial ledger.
  The existing financial integrity rules do not apply here.

**SQLAlchemy model** (create in `backend/financeops/db/models/users.py`):

```python
class UserOrgMembership(UUIDBase):
    """Cross-tenant membership. One row per (user, tenant) pair."""
    __tablename__ = "user_org_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_user_org"),
        Index("idx_uom_user_id", "user_id"),
        Index("idx_uom_tenant_id", "tenant_id"),
    )

    user_id:    Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                    ForeignKey("iam_users.id", ondelete="CASCADE"), nullable=False)
    tenant_id:  Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),
                    ForeignKey("iam_tenants.id", ondelete="CASCADE"), nullable=False)
    role:       Mapped[UserRole] = mapped_column(
                    Enum(UserRole, name="user_role_enum"), nullable=False)
    is_primary: Mapped[bool]     = mapped_column(Boolean, nullable=False, default=False)
    joined_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True),
                    nullable=False, server_default=func.now())
    invited_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True),
                    ForeignKey("iam_users.id", ondelete="SET NULL"), nullable=True)
    status:     Mapped[str]      = mapped_column(String(20), nullable=False, default="active")
```

Add a `memberships` relationship to `IamUser`:
```python
memberships: Mapped[list["UserOrgMembership"]] = relationship(
    "UserOrgMembership", foreign_keys="[UserOrgMembership.user_id]",
    back_populates="user", lazy="noload"
)
```

### 3. Alembic migration

Single migration file `0XXX_add_user_org_memberships.py`. The migration must:

1. Create the `user_org_memberships` table (DDL in Section 2).
2. Create the partial unique index enforcing one primary per user.
3. **Backfill** (data migration, not just DDL):
   ```sql
   INSERT INTO user_org_memberships
       (id, user_id, tenant_id, role, is_primary, joined_at, status, created_at)
   SELECT
       gen_random_uuid(),
       u.id,
       u.tenant_id,
       u.role,
       TRUE,
       COALESCE(u.created_at, NOW()),
       'active',
       NOW()
   FROM iam_users u
   ON CONFLICT (user_id, tenant_id) DO NOTHING;
   ```
4. **Integrity check** (assert, not just log):
   ```sql
   DO $$
   DECLARE mismatch int;
   BEGIN
     SELECT COUNT(*) INTO mismatch
     FROM iam_users u
     WHERE NOT EXISTS (
       SELECT 1 FROM user_org_memberships m
       WHERE m.user_id = u.id AND m.is_primary = TRUE
     );
     IF mismatch > 0 THEN
       RAISE EXCEPTION 'Backfill integrity check failed: % users missing primary membership', mismatch;
     END IF;
   END $$;
   ```
5. **Downgrade:** `DROP TABLE user_org_memberships CASCADE;`

Run on a disposable DB first (snapshot or test DB). Verify row counts match `SELECT COUNT(*) FROM iam_users`.

### 4. API endpoints

#### 4.1 — List user's orgs

```
GET /api/v1/users/me/orgs
Authorization: Bearer <access_token>
```

**Response 200:**
```typescript
type UserOrgListResponse = {
  items: UserOrgItem[]
  total: number
}

type UserOrgItem = {
  org_id:     string   // UUID — the tenant's id
  org_name:   string   // IamTenant.name
  org_slug:   string   // IamTenant.slug
  org_status: string   // IamTenant.status ("active" | "suspended" | "trial")
  role:       string   // UserRole enum value for this user in this org
  is_primary: boolean
  joined_at:  string   // ISO 8601
}
```

**Error responses:**
- `401` — no valid session token
- `400` — malformed token

**Auth:** `get_current_user` dependency only. No role restriction. Users can always list their
own memberships.

**Implementation:** Query `user_org_memberships JOIN iam_tenants ON tenant_id` filtered by
`user_id = current_user.id AND status = 'active'`. A single-org user returns a one-item list.
A user with zero active memberships returns `{ items: [], total: 0 }` (not an error).

**File:** Add handler to `backend/financeops/api/v1/users.py` (new file or existing user routes).
Router prefix: `/api/v1/users`.

---

#### 4.2 — Switch active org (issues new JWT)

```
POST /api/v1/users/me/orgs/{tenant_id}/switch
Authorization: Bearer <access_token>
```

No request body.

**Response 200:**
```typescript
type OrgSwitchResponse = {
  switch_token:       string   // JWT: sub=user.id, tenant_id=target_tenant_id, role=user.role
  tenant_id:          string   // UUID — the target org
  tenant_name:        string
  tenant_slug:        string
  expires_in_seconds: number   // matches JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60, NOT 900
}
```

**Error responses:**
- `403` — user has no active membership in `{tenant_id}`
- `400` — `{tenant_id}` is not a valid UUID or the org is suspended
- `401` — no valid session token

**Auth:** `get_current_user` dependency. No role restriction (this is for all authenticated users).

**JWT requirements for the issued token:**
- `sub`: `str(user.id)` — the calling user's own ID (not the admin's ID)
- `tenant_id`: `str(target_tenant_id)` — the switched-to org
- `role`: `user.role.value` — the user's role **in the target org** (from `user_org_memberships.role`)
- **Must NOT include** `scope: "platform_switch"` or `switched_by` claims (those are admin-only)
- **Token lifetime:** `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (normal session lifetime, not 900 seconds)
- Issue via: `create_access_token(user.id, target_tenant_id, membership.role.value, additional_claims={})`

**Membership check (required before issuing):**
```python
membership = await session.scalar(
    select(UserOrgMembership)
    .where(UserOrgMembership.user_id == current_user.id)
    .where(UserOrgMembership.tenant_id == target_tenant_id)
    .where(UserOrgMembership.status == "active")
)
if not membership:
    raise AuthorizationError("User does not have an active membership in this org")
```

**FU-003 implication:** The existing `GET /api/v1/org-setup/entities` endpoint is **not
modified**. After the switch token is issued, the frontend Axios interceptor substitutes it
as the Bearer token; the entity endpoint reads `tenant_id` from the new JWT via
`get_current_tenant` and automatically returns the target org's entities. No path parameter
or new entity route is needed.

**File:** Same file as 4.1 (`backend/financeops/api/v1/users.py`).

---

### 4.3 — Auth path amendment for switch tokens

**Context:** Checkpoint 2 integration surfaced that `backend/financeops/api/deps.py:281`
enforces `user.tenant_id == jwt_tenant_id`. The user switch token issued by Section 4.2
carries `tenant_id = target_tenant_id`, but `IamUser.tenant_id` remains the user's home
org. Without this amendment, every request after a switch fails with
`AuthenticationError("Token tenant mismatch")`.

The Section 0 gate's Investigation 0.1 was scoped to the scope-claim axis (does the auth
path reject tokens missing a scope claim?). It did not investigate the tenant_id consistency
axis. This finding is recorded in Section 0.3; the amendment below resolves the issue.

**Amendment:** `get_current_user` in `backend/financeops/api/deps.py` is amended to handle
`scope: "user_switch"` tokens via a conditional branch. The switch endpoint (Section 4.2)
must issue tokens carrying `additional_claims={"scope": "user_switch"}` (updating Section 4.2
line: `create_access_token(user.id, target_tenant_id, membership.role.value, additional_claims={"scope": "user_switch"})`).

```python
# In get_current_user, replace the hard tenant consistency check with:
if user.tenant_id != jwt_tenant_id:
    if payload.get("scope") == "user_switch":
        # Switch token: verify active membership in the target tenant
        membership_result = await session.execute(
            select(UserOrgMembership)
            .where(
                UserOrgMembership.user_id == user.id,
                UserOrgMembership.tenant_id == jwt_tenant_id,
                UserOrgMembership.status == "active",
            )
        )
        if not membership_result.scalar_one_or_none():
            raise AuthenticationError("No active membership in target tenant")
    else:
        raise AuthenticationError("Token tenant mismatch")
```

**Behavior:**
- Non-switch tokens: existing behavior preserved exactly. `tenant_id` consistency
  enforced strictly.
- Switch tokens (`scope: "user_switch"`): tenant consistency is replaced by
  active-membership verification. If the user no longer has an active membership in the
  target tenant, the request is rejected immediately.

**Security implications:**
- Membership revocation takes effect on the next request after revocation. There is no
  in-flight session bypass.
- A forged switch token claiming a tenant the user is not a member of is rejected by the
  membership query.
- The home-org `IamUser.tenant_id` is never mutated — it remains the canonical reference
  for audit logging and identity.

**Performance implications:**
- Adds one indexed DB lookup per authenticated request when the token is a switch token.
  The lookup hits the existing `UNIQUE(user_id, tenant_id)` index — sub-millisecond.
- Non-switch tokens pay zero overhead (the `scope` check is a dict lookup, no DB call).
- If this becomes a hotspot at scale, the membership row can be cached in Redis or carried
  as additional JWT claims. Premature optimisation not warranted at this stage.

**File(s) modified in Checkpoint 3:**
- `backend/financeops/api/deps.py` — add conditional branch in `get_current_user` as shown
- `backend/financeops/api/v1/users.py` — update Section 4.2 `additional_claims` to include
  `scope: "user_switch"`
- `backend/tests/integration/test_user_orgs_endpoint.py` — add T7, T12, T13 integration
  tests exercising the amended auth path

---

### 5. JWT / session considerations

Under Approach A, `IamUser.tenant_id` stays — so existing JWTs continue to validate.
The `/switch-org` endpoint issues a new JWT similar to the login flow but for a different
tenant.

**Rollout:**
- Existing users: no forced logout. Their session continues with their primary org. When they
  explicitly use the switcher, they get a new token.
- New users: login flow issues JWT with `IamUser.tenant_id` (unchanged from today). After
  backfill, `user_org_memberships` also has a primary row for them.

**`platform_switch` scope check:** Verify in `get_current_user` (deps.py) whether the
`scope: "platform_switch"` claim is explicitly required or rejected anywhere. If present, the
user switch token (which carries no scope claim) must not be blocked. **Investigation required
before implementation.**

### 6. Impact on existing junction tables

`cp_user_organisation_assignments` and `cp_user_entity_assignments` remain within-tenant
assignment tables. No change to their semantics or queries. Their `tenant_id` scope filter
continues to work because the JWT `tenant_id` correctly reflects the active org.

### 7. Tests

Minimum test coverage required (add to `backend/tests/`):

**Unit tests:**
- `UserOrgMembership` model: create, unique constraint enforcement, cascade delete
- `is_primary` partial unique index: verify second `is_primary = TRUE` for the same user raises

**Integration tests:**
- `GET /users/me/orgs` — single-org user returns one item with `is_primary: true`
- `GET /users/me/orgs` — multi-org user returns all active memberships
- `GET /users/me/orgs` — user with no active memberships returns empty list (not 404/403)
- `POST /users/me/orgs/{id}/switch` — switch to an org the user belongs to → 200 + valid JWT
- `POST /users/me/orgs/{id}/switch` — switch to an org the user does NOT belong to → 403
- `POST /users/me/orgs/{id}/switch` — issued JWT carries `scope: "user_switch"` and no
  `scope: "platform_switch"` or `switched_by` claims (T8)
- `POST /users/me/orgs/{id}/switch` — issued token lifetime matches normal access token
  lifetime, not 900 seconds
- Switch token (`scope: "user_switch"`) used on protected endpoint — amended auth path
  membership-check branch exercises correctly; request succeeds (T7)
- Membership suspended after switch token issued — next request with that token returns 401
  "No active membership in target tenant" (T12)
- Forged switch token for tenant user is not a member of — rejected 401 (T13)
- Unauthenticated request to either endpoint → 401

**Migration / backfill tests:**
- After migration, every existing `IamUser` has exactly one membership row with
  `is_primary = True` in `user_org_memberships`
- Backfill count matches `SELECT COUNT(*) FROM iam_users`
- `alembic downgrade` removes `user_org_memberships` and its indexes cleanly

**Backwards compatibility:**
- Existing single-org users: token structure unchanged, no re-login required, all existing
  API calls continue to work

---

## Test plan

### Scenario matrix

| # | Scenario | Expected result |
|---|---|---|
| T1 | Single-org user (all existing pre-migration users) calls `GET /users/me/orgs` | Returns 1-item list, `is_primary: true` |
| T2 | Multi-org user (manually inserted second membership row) calls `GET /users/me/orgs` | Returns both orgs, correct `is_primary` on each |
| T3 | User switches to an org they belong to | 200, valid JWT, `tenant_id` = target org |
| T4 | User switches to an org they do NOT belong to | 403 |
| T5 | User switches to an org where their membership is `status = 'suspended'` | 403 |
| T6 | User with zero active memberships (all rows have `status != 'active'`) calls GET | 200, `items: []` |
| T7 | Switch token (`scope: "user_switch"`) accesses tenant-scoped endpoint | 200, amended auth path membership check passes; response scoped to target org |
| T8 | Issued switch token carries `scope: "user_switch"`, NOT `scope: "platform_switch"` | Assert `scope` claim equals `"user_switch"`; assert `switched_by` claim absent |
| T9 | Backfill: every `IamUser` has exactly one `is_primary = TRUE` membership row | Count assertion passes |
| T10 | Second `is_primary = TRUE` row for same user is rejected | DB-level unique constraint error |
| T11 | `alembic downgrade` from migration | Rolls back cleanly, no orphan objects |
| T12 | Membership revoked mid-session — next request with switch token returns 401 | First request 200; membership suspended; second request 401 "No active membership in target tenant" |
| T13 | Forged switch token for tenant user is NOT a member of — rejected | 401 "No active membership in target tenant" |
| T14 | Existing single-org user makes any existing API call after migration | Unchanged behavior |

---

## Rollout plan

### Migration ordering

1. **Deploy migration file** (table + indexes + backfill) to production during a maintenance
   window or zero-downtime slot:
   - The migration adds a new table — no existing table is altered. Safe for zero-downtime.
   - The backfill is an `INSERT … SELECT` — non-blocking on PostgreSQL with no locks on
     `iam_users` reads (only INSERTs into the new table).
   - Integrity check at end of migration (see Section 3, step 4) will surface any gap before
     the migration commits.

2. **Deploy BE-001 code** (new endpoints + `UserOrgMembership` model) once migration is applied
   and verified.
   - No feature flag needed — the new endpoints are additive and do not replace existing ones.
   - Existing `/platform/admin/tenants` endpoints are unchanged and continue to function.

3. **Dual-read window:** Not required. `IamUser.tenant_id` is preserved as the home org column.
   Existing queries that read `user.tenant_id` continue to work. The new endpoints are purely
   additive.

### Feature flag

Not required for backend. The new endpoints return empty data for single-org users; no
frontend can accidentally trigger multi-org switching until the Phase 2 frontend work ships.
If desired, a simple `MULTI_ORG_ENABLED` settings flag can gate `POST /switch-org` to prevent
early access, but this is optional.

### Frontend coordination

- **BE-001 is done when:** `GET /users/me/orgs` returns the calling user's memberships, and
  `POST /users/me/orgs/{id}/switch` issues a valid JWT, both verified by the integration tests.
- **Phase 2 frontend can begin** as soon as these two endpoints pass their acceptance criteria.
- Phase 2 frontend must: (a) rewrite `OrgSwitcher.tsx` to call `GET /users/me/orgs`; (b) call
  `enterSwitchMode({ switch_token, tenant_id, tenant_name })` with the response from
  `POST /switch-org`; (c) call `queryClient.clear()` inside `enterSwitchMode` to purge stale
  entity cache.
- The entity endpoint (`GET /api/v1/org-setup/entities`) is **not changed** as part of Phase 2.
  The JWT rotation already scopes it correctly.

### Rollback plan

If the migration needs to be rolled back:
1. `alembic downgrade -1` — drops `user_org_memberships` table and its indexes. No data loss
   on `iam_users` or any other existing table.
2. Re-deploy the previous backend image (without the `UserOrgMembership` model and new endpoints).
3. No forced re-login required. Existing JWTs remain valid.

---

## Acceptance criteria

- [ ] Migration runs clean on a disposable DB
- [ ] Migration reverts cleanly (`alembic downgrade`)
- [ ] Backfill verified: every existing `IamUser` has exactly one membership row with
      `is_primary = TRUE`
- [ ] `GET /api/v1/users/me/orgs` returns the logged-in user's memberships
- [ ] `POST /api/v1/users/me/orgs/{tenant_id}/switch` issues a new token scoped to the target org
- [ ] Issued switch token carries `tenant_id = target org`, normal lifetime, no platform_switch scope
- [ ] 403 returned for users trying to switch to an org they don't belong to (T4) or where their
      membership is suspended (T5)
- [ ] Entity endpoint `GET /api/v1/org-setup/entities` returns target org's entities when called
      with the switch token (T7)
- [ ] All existing tests still pass
- [ ] New tests cover all 12 scenarios in the test plan
- [ ] `platform_switch` scope claim verified absent from user switch token

---

## Estimate rationale

I've estimated this at 6–10 dev-days:

- Schema + migration + backfill + integrity check: ~2 days
- `GET /users/me/orgs` endpoint + service layer: ~1 day
- `POST /users/me/switch-org` endpoint + membership guard + JWT issuance: ~1–2 days
- Test coverage (all 12 T-scenarios): ~1–2 days
- Buffer for unexpected coupling with `cp_user_organisation_assignments` / `cp_user_entity_assignments`
  queries and `platform_switch` scope check (Section 5): ~1–2 days

FU-003 resolution to Option B removes ~0.5 days that would have been spent on the new entity
route and frontend hook changes.

---

## Related tickets

- Phase 2 frontend work (`feat(shell): phase 2 — OrgSwitcher for all users`) depends on this
  ticket
- Future ticket (post-Phase-2): `refactor(identity): retire IamUser.tenant_id column, complete
  Approach B migration`
- FU-003 (closed): `docs/decisions/fu003-entity-endpoint-scoping-decision.md`

---

## Notes for the engineer

1. The Gap 2 trace (`docs/audits/gap2-orgswitcher-trace-2026-04-25.md`) Sections 4–7 document
   the current admin impersonation flow in detail. The token-swap mechanism (Axios interceptor +
   Zustand `is_switched` flag) is reusable for the user-facing switch — the frontend already
   has the plumbing. The new endpoints just need to issue the right JWT.

2. Do NOT touch the existing admin impersonation endpoints
   (`/api/v1/platform/admin/tenants/...`). Those serve a separate use case and must remain
   as-is.

3. The `is_primary` flag's long-term purpose is "default workspace on login" — when a user
   logs in without specifying an org, they get their primary. This becomes user-configurable
   later (separate ticket).

4. Consider adding an `is_owner` boolean on `user_org_memberships` if you don't already have
   a role that captures org ownership (the user who created the org, for billing/deletion).
   If `UserRole.org_admin` already covers this semantically, skip it.

5. **Investigate before implementing (Section 5 flag):** Check whether `get_current_user` in
   deps.py or any middleware validates or rejects tokens based on the presence/absence of a
   `scope` claim. The admin switch token carries `scope: "platform_switch"` (admin.py:539).
   The new user switch token carries no scope claim. Verify this does not produce a mismatch
   or 403 in the existing auth path before implementing.
