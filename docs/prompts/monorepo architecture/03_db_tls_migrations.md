# PROMPT 03 — RESTORE DB TLS VERIFICATION (MIGRATIONS)

**Sprint:** 1 (Security & Integrity)
**Audit findings closed:** #4
**Risk level:** LOW
**Estimated effort:** XS (<1 day)
**Prerequisite:** Prompt 02 must be complete

---

## CONTEXT

Repo root: `D:\finos`
Target file: `D:\finos\backend\migrations\env.py` (around line 61)

Same issue as prompt 02 but in the Alembic migration runner. Migrations connect to the DB using a separate code path with its own SSL configuration that also disables verification.

This is its own prompt (not bundled with 02) because:
1. Migration runs are sensitive — a misconfiguration here breaks all deploys
2. Verification is different (alembic-driven, not app-driven)
3. Clean rollback boundary if something goes wrong

---

## SCOPE — DO EXACTLY THIS

### Step 1 — Read the current state
1. Open `D:\finos\backend\migrations\env.py`
2. Find the SSL config (around line 61)
3. Quote the exact lines that disable verification
4. Note how `env.py` reads the connection string — does it pull from `settings`, env var, or `alembic.ini`?

### Step 2 — Confirm consistency with prompt 02
1. Verify that prompt 02 is committed (check git log for the prompt 02 commit message)
2. Confirm the same `sslmode` strategy is used (verify-full default) — migrations and runtime should match
3. Confirm `DB_SSL_MODE` env var is read from the same source

### Step 3 — Apply the fix
1. Modify `D:\finos\backend\migrations\env.py` to:
   - Remove the SSL disable code
   - Use the same SSL config as runtime (read from `settings.db_ssl_mode` or env var)
   - Keep the override capability — migrations sometimes need different SSL behavior in CI
2. If CI uses a non-TLS Postgres (likely — local container), allow `DB_SSL_MODE=disable` ONLY when explicitly set, never as a silent default

### Step 4 — Update CI config
Check `D:\finos\.github\workflows\ci.yml` for migration runs:
- If CI runs migrations against a local Postgres container, set `DB_SSL_MODE=disable` explicitly in the CI env, with a comment explaining why
- Production and staging Render env vars should NOT have this override

### Step 5 — Verify migration operability
After the fix:
1. Run `cd D:\finos\backend && alembic heads` — must complete without TLS errors
2. Run `alembic check` if available
3. Run `alembic history --verbose | head -20` to confirm history is readable

If `alembic heads` still fails, that's likely finding #6 (settings validation) — note it and stop. Prompt 05 handles that.

---

## DO NOT DO

- Do NOT modify any migration file content — only `env.py`
- Do NOT change the alembic version table or schema name
- Do NOT add new migrations
- Do NOT couple this fix to prompt 05 (alembic heads unblock) — they may both be needed but are separate root causes

---

## VERIFICATION CHECKLIST

- [ ] `D:\finos\backend\migrations\env.py` no longer disables TLS verification
- [ ] SSL mode is read from the same source as runtime (single source of truth)
- [ ] CI workflow has explicit `DB_SSL_MODE=disable` only for the local container step
- [ ] `alembic heads` runs cleanly OR fails for a reason other than TLS (note the reason for prompt 05)
- [ ] `alembic history` works
- [ ] Staging deploy migrations run cleanly (user confirms out-of-band)
- [ ] No new test skips

---

## ROLLBACK PLAN

If migrations fail in staging:
1. Check the actual error — is it cert chain, hostname mismatch, or something else?
2. Set `DB_SSL_MODE=require` as a temporary env var on Render
3. Do NOT revert to insecure mode — fix the cert chain

---

## COMMIT MESSAGE

```
fix(security): enforce DB TLS verification in migration runner

- migrations/env.py now reuses runtime SSL config
- DB_SSL_MODE override allowed in CI only (explicit env var)
- alembic heads operability verified

Closes audit finding #4 (CRITICAL).
Pairs with finding #3 fix (prompt 02).
```
