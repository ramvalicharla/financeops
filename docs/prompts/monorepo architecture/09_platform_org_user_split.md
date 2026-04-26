# PROMPT 09 — SPLIT PlatformUser FROM OrgUser IDENTITY

**Sprint:** 4 (Architectural Hardening)
**Audit findings closed:** #8, partial #13
**Risk level:** HIGH (schema change, auth flow change, multi-day migration)
**Estimated effort:** L (3-6 weeks)
**Prerequisite:** Prompts 01-08 complete

---

## CONTEXT

Repo root: `D:\finos`
Target files (initial — there will be more):
- `D:\finos\backend\financeops\db\models\users.py` (around line 14)
- `D:\finos\backend\financeops\api\v1\platform_users.py` (around line 83)
- `D:\finos\frontend\lib\permission-matrix.ts` (around line 4)
- The auth/JWT issuance code

The audit found that platform users (Sentinel — internal Finqor staff) and tenant org users (CFOs, accountants, customers) share the same `IamUser` model. This is wrong for several reasons:
1. Platform users have global scope; org users are scoped to a tenant — different security model
2. Sentinel admin actions need a separate audit trail from tenant user actions
3. Enterprise SSO (next prompt cycle) needs different IdP configs per tenant — platform users are on Anthropic-equivalent identity, org users are on customer IdPs
4. Backend role enums and frontend permission-matrix names don't match (#13) — splitting forces alignment

This is a **multi-day, multi-PR effort.** Do NOT attempt in one commit. The prompt below structures it as five distinct phases with verification gates between.

---

## SCOPE — DO EXACTLY THIS

### PHASE A — Inventory and design (read-only, 1 day)

1. Map every consumer of `IamUser`:
   ```
   rg -n "IamUser" D:\finos\backend
   rg -n "user_id|created_by" D:\finos\backend\financeops\db\models | head -50
   ```
2. Identify every FK referencing the users table
3. Map permission-matrix divergence:
   - Read `D:\finos\backend\financeops\db\models\users.py` UserRole enum
   - Read `D:\finos\frontend\lib\permission-matrix.ts`
   - Document which roles are platform-only, which are tenant-only, which are duplicated
4. Output the design document `D:\finos\docs\architecture\PLATFORM_VS_ORG_USERS.md` covering:
   - New model layout: `PlatformUser` (no tenant_id) + `OrgUser` (tenant_id required)
   - Shared base or separate models? (recommend: separate, with a thin `IdentitySubject` interface for FK polymorphism)
   - JWT structure: `subject_type: "platform" | "org"` claim
   - Session/RLS context: `platform_user_id` vs `org_user_id` vs `tenant_id`
   - Audit trail FK: polymorphic via subject_type or dual columns?
   - Migration path: how do we move existing users?

**STOP at end of Phase A. Wait for user review and approval of the design.**

### PHASE B — Build new models alongside old (1-2 days)

After design approval:
1. Create new SQLAlchemy models: `PlatformUser`, `OrgUser` (in separate files)
2. Create migration that adds new tables WITHOUT dropping `IamUser`
3. Add `IdentitySubject` interface or type for code that needs to reference either
4. Ship to staging, verify dual-write works (no behavioral change yet)

### PHASE C — Migrate identity reads (3-5 days)

1. Update auth/JWT code to issue tokens with `subject_type` claim
2. Update session deps to populate either `platform_user` or `org_user` in request context
3. Update permission checks to be subject-type-aware
4. Update API endpoints — split `/v1/platform/users` from `/v1/org/users`
5. Update frontend permission matrix to mirror backend role names exactly

### PHASE D — Migrate data and FKs (2-3 days, requires maintenance window)

1. Backfill: copy `IamUser` rows where `is_platform_user=True` into `PlatformUser`, others into `OrgUser`
2. Update every FK pointing at `IamUser` to point at the new tables (polymorphic FK or dual nullable columns)
3. Verify referential integrity after migration
4. Mark `IamUser` as deprecated but keep the table for one release cycle

### PHASE E — Drop old model (1 day, in a later release)

After one full release cycle confirms stability:
1. Drop `IamUser` table
2. Remove deprecated code
3. Update docs

---

## DO NOT DO

- Do NOT do all five phases in one commit — each is its own PR
- Do NOT drop `IamUser` until at least one release cycle has passed with the new model live
- Do NOT change SSO / OAuth behavior in this prompt — that's a separate prompt
- Do NOT modify the audit trail schema in the same migration — keep concerns separate
- Do NOT auto-generate the migration via Alembic autogenerate without manual review — autogenerate often misses backfill steps

---

## VERIFICATION CHECKLIST (per phase)

**After Phase A:**
- [ ] Design doc reviewed and approved by user
- [ ] All FK consumers identified
- [ ] Role matrix divergence documented

**After Phase B:**
- [ ] New tables exist in staging
- [ ] Old code paths still work unchanged
- [ ] No new test failures

**After Phase C:**
- [ ] JWTs include `subject_type` claim
- [ ] Permission checks are subject-type-aware
- [ ] Frontend role names match backend exactly
- [ ] All auth tests pass
- [ ] Manual smoke test: platform user login + org user login both work

**After Phase D:**
- [ ] All `IamUser` rows migrated correctly (verify counts)
- [ ] FK referential integrity preserved
- [ ] No orphaned records
- [ ] Existing API tests pass

**After Phase E (later):**
- [ ] `IamUser` table dropped
- [ ] No code references the old model

---

## ROLLBACK PLAN

If Phase D fails:
1. The new tables coexist with `IamUser` — rollback is "stop using new tables, route reads back to old"
2. Do NOT delete the new tables yet — investigate the FK issue first
3. Worst case: revert Phase D migration, keep `IamUser` as source of truth, plan re-attempt

---

## COMMIT MESSAGE PATTERN (one per phase)

Phase A: `docs(arch): design split of PlatformUser from OrgUser identity (audit #8)`
Phase B: `feat(identity): introduce PlatformUser and OrgUser models alongside IamUser`
Phase C: `feat(identity): route auth and permission checks through new user models`
Phase D: `feat(identity): backfill PlatformUser/OrgUser, deprecate IamUser`
Phase E: `chore(identity): drop deprecated IamUser model`

Each phase closes a portion of finding #8.
Phase C closes finding #13 (frontend/backend role taxonomy alignment).
