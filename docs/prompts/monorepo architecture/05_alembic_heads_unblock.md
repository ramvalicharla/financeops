# PROMPT 05 — RESTORE alembic heads OPERABILITY

**Sprint:** 2 (Operational Unblock)
**Audit findings closed:** #6 (and partially #41)
**Risk level:** LOW
**Estimated effort:** XS (<1 day)
**Prerequisite:** Prompts 01-04 complete

---

## CONTEXT

Repo root: `D:\finos`
Target files:
- `D:\finos\backend\migrations\env.py` (around line 15, 80)
- `D:\finos\backend\financeops\config.py`

The audit found that `alembic heads` cannot complete because settings validation rejects `DEBUG='release'`. This means right now you cannot inspect migration state cleanly, which is operational risk for any future migration work.

The root cause is that `migrations/env.py` imports application settings at module load, which triggers full Pydantic validation including production-only checks.

---

## SCOPE — DO EXACTLY THIS

### Step 1 — Reproduce and diagnose
1. Run `cd D:\finos\backend && alembic heads` — capture the full error output
2. Read `D:\finos\backend\financeops\config.py`:
   - Find the `DEBUG` field validator
   - Quote the validator logic and the allowed values
3. Read `D:\finos\backend\migrations\env.py`:
   - Trace what it imports from `financeops` at module-load time
   - Identify which import triggers settings validation

### Step 2 — Decide the fix strategy
Pick ONE based on what step 1 revealed:

**Option A (preferred):** The `DEBUG='release'` validator is wrong — `release` is presumably a deployment mode, not a debug flag. Fix the validator to accept the actual valid values (`true`, `false`, possibly `dev`/`staging`/`production`).

**Option B:** The validator is correct but `migrations/env.py` is being run with the wrong env (e.g., a stale env var). Fix `env.py` to set required env vars at startup or to use a minimal config object.

**Option C:** Both — the validator needs cleanup AND `env.py` should use lighter imports.

**STOP here. Output the diagnosis and proposed option. Wait for user confirmation.**

### Step 3 — Apply the fix
After confirmation:

If Option A:
1. Update the validator in `config.py` to accept the correct values
2. Update `.env.example` files to show the correct format
3. Update any CI/Render env vars that currently set `DEBUG='release'` (note: agent should LIST these for the user to update manually — do not modify Render config from code)

If Option B:
1. Refactor `migrations/env.py` to import only what's needed for migrations
2. Decouple alembic from full app settings — alembic should only need `DATABASE_URL` and metadata
3. Use a minimal config class for migrations

### Step 4 — Verify alembic operability
After the fix:
- [ ] `alembic heads` returns exactly one head (note the revision ID)
- [ ] `alembic current` works
- [ ] `alembic history --verbose | head -30` works
- [ ] `alembic check` works (if installed)
- [ ] `alembic upgrade head --sql` works (dry-run, doesn't apply)

If `alembic heads` returns multiple heads, that's a separate issue — STOP and report. Do not auto-merge heads.

### Step 5 — Add a CI smoke test
Add a step to `D:\finos\.github\workflows\ci.yml`:
```yaml
- name: Verify alembic operability
  run: |
    cd backend
    alembic heads
    alembic check
```

This catches regressions where someone breaks alembic via a config change.

---

## DO NOT DO

- Do NOT auto-merge migration heads if multiple are found
- Do NOT modify any existing migration file
- Do NOT change the `DATABASE_URL` env var name
- Do NOT remove the validator entirely — fix it, don't delete it
- Do NOT modify Render or CI env vars from code (list them for the user instead)

---

## VERIFICATION CHECKLIST

- [ ] `alembic heads` returns exactly one head, no errors
- [ ] `alembic current` works in dev, CI, and staging
- [ ] CI now includes the alembic smoke step
- [ ] Settings validator is correct and documented
- [ ] No regression in app startup (run `pytest -k startup` or equivalent)

---

## COMMIT MESSAGE

```
fix(infra): restore alembic operability, decouple from full settings

- Fixed DEBUG validator to accept correct values (or: decoupled migrations/env.py from full app settings)
- Added CI smoke step running `alembic heads` and `alembic check`
- alembic heads now returns one head cleanly

Closes audit finding #6 (CRITICAL).
Partially addresses finding #41 (env.py fragility).
```
