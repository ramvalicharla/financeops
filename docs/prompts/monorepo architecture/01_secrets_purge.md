# PROMPT 01 — SECRETS PURGE & ROTATION

**Sprint:** 1 (Security & Integrity)
**Audit findings closed:** #2
**Risk level:** HIGH (git history rewrite involved)
**Estimated effort:** S (1-3 days, mostly waiting on rotation)

---

## CONTEXT

Repo root: `D:\finos`
Backend: `D:\finos\backend`
Frontend: `D:\finos\frontend`

The audit found secret-bearing env files committed to the repo:
- `D:\finos\.env`
- `D:\finos\backend\.env`
- `D:\finos\railway.env.production`
- `D:\finos\frontend\.env.local`

These must be removed from the working tree, removed from git history, and any real secrets must be rotated.

---

## SCOPE — DO EXACTLY THIS

### Step 1 — Inventory (read-only)
1. List every `.env*` file in the repo (excluding `node_modules`, `.venv`, `.next`).
2. For each, classify each line as:
   - `REAL_SECRET` (looks like a real key/password/token)
   - `PLACEHOLDER` (e.g., `xxx`, `replace-me`, `your-key-here`)
   - `NON_SENSITIVE` (e.g., `DEBUG=true`, `PORT=8000`)
3. Output a classification table. **STOP here and wait for user confirmation** before deleting anything.

### Step 2 — Create `.env.example` files (after confirmation)
For every `.env*` file, create a sibling `.env.example` containing:
- Same keys
- All values replaced with safe placeholders (`<your-database-url>`, `<your-jwt-secret>`)
- Comments preserved
- A header line: `# Copy this file to .env and fill in real values. Never commit .env.`

### Step 3 — Remove from working tree
- Delete the four committed `.env*` files listed above
- Add them to `.gitignore` if not already present:
  ```
  .env
  .env.local
  .env.production
  .env.*.local
  *.env.production
  railway.env*
  ```
- Verify `.gitignore` already exists and append rather than overwrite

### Step 4 — Verify with `git status`
Show the user `git status` output. **DO NOT commit yet.** **DO NOT rewrite history yet.**

### Step 5 — Document the rotation list
Create `D:\finos\docs\security\SECRETS_ROTATION_2026.md` with:
- Each secret found in step 1 (REAL_SECRET only)
- Where it's used (Railway / Render / Vercel / local dev)
- Rotation owner: `<founder>`
- Rotation status: `PENDING`
- Rotation completion date: `<empty>`

---

## DO NOT DO

- Do NOT run `git filter-repo` or `git filter-branch` yet — history rewrite is a separate manual step the user must do interactively after rotation
- Do NOT push anything
- Do NOT delete `.env.example` files if they already exist
- Do NOT touch any `.env*` file outside `D:\finos\.env`, `D:\finos\backend\.env`, `D:\finos\railway.env.production`, `D:\finos\frontend\.env.local` without explicit user confirmation
- Do NOT modify application code that reads env vars

---

## VERIFICATION CHECKLIST

After execution, confirm all of these:

- [ ] Four target `.env*` files are deleted from working tree
- [ ] Matching `.env.example` files exist with placeholder values
- [ ] `.gitignore` includes patterns for all env file shapes
- [ ] `docs/security/SECRETS_ROTATION_2026.md` exists with the rotation inventory
- [ ] `git status` shows the deletions and new example files only — no other unintended changes
- [ ] Application starts locally with a fresh `.env` copied from `.env.example` and filled in (manual smoke test by user)

---

## MANUAL FOLLOW-UP (USER, NOT AGENT)

After the agent completes the above, the user must:

1. Rotate every `REAL_SECRET` listed in the rotation doc:
   - Database passwords (Render, Railway)
   - JWT secrets, encryption keys
   - Third-party API keys (Sentry, Stripe, etc.)
   - OAuth client secrets
2. Update Render/Vercel/Railway env vars with rotated values
3. Run `git filter-repo` to scrub the four files from history (separate operation)
4. Force-push to main and notify any collaborators to re-clone
5. Mark `SECRETS_ROTATION_2026.md` entries as `COMPLETE` with date

---

## COMMIT MESSAGE (after verification passes)

```
chore(security): remove committed env files, add .env.example templates

- Removed .env, backend/.env, railway.env.production, frontend/.env.local
- Added matching .env.example files with placeholder values
- Updated .gitignore patterns
- Added docs/security/SECRETS_ROTATION_2026.md tracking rotation status

Closes audit finding #2 (CRITICAL).
History rewrite and key rotation tracked separately.
```
