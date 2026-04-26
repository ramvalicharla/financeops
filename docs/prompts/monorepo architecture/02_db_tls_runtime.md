# PROMPT 02 — RESTORE DB TLS VERIFICATION (RUNTIME)

**Sprint:** 1 (Security & Integrity)
**Audit findings closed:** #3
**Risk level:** LOW (small config change, easy rollback)
**Estimated effort:** XS (<1 day)

---

## CONTEXT

Repo root: `D:\finos`
Target file: `D:\finos\backend\financeops\db\session.py` (around line 49)

The audit found that runtime DB connections disable TLS certificate and hostname verification. This is a SOC 2 blocker and exposes the app to MITM attacks on the DB connection path.

---

## SCOPE — DO EXACTLY THIS

### Step 1 — Read the current state
1. Open `D:\finos\backend\financeops\db\session.py`
2. Find the engine/connect_args configuration (around line 49)
3. Quote the exact lines that disable verification (e.g., `ssl=False`, `verify_mode=ssl.CERT_NONE`, `check_hostname=False`)
4. Quote the surrounding context — show how the engine is built and what `connect_args` are passed

### Step 2 — Identify the DB provider
Check `D:\finos\backend\financeops\config.py` and `D:\finos\render.yaml` for the database URL pattern:
- Render Postgres → uses Render-managed cert, supports `sslmode=require` with verify
- Railway Postgres → similar
- Self-hosted → may need a custom CA bundle

Report which provider is in use before making changes.

### Step 3 — Plan the fix
Based on the provider, propose ONE of these approaches:
- **Option A (preferred):** Set `sslmode=verify-full` in the connection string and let the system CA bundle validate. Works for Render, AWS RDS, GCP Cloud SQL.
- **Option B:** Set `sslmode=verify-ca` with a provider-specific CA cert bundled in `D:\finos\backend\financeops\db\certs\` and referenced via `sslrootcert`.
- **Option C:** Provider explicitly does not support cert verification (rare; should not apply here) — document with a code comment + ADR.

**STOP here. Output the plan and wait for user confirmation before applying.**

### Step 4 — Apply the fix
After confirmation:
1. Modify `D:\finos\backend\financeops\db\session.py` to enable TLS verification per the chosen option
2. If Option B, add the CA cert file under `D:\finos\backend\financeops\db\certs\<provider>-ca.pem` and reference it via env var (do NOT hardcode the path)
3. Add a `DB_SSL_MODE` env var to `D:\finos\backend\.env.example` (default `verify-full`) so dev environments can override if needed
4. Add a startup log line: `logger.info("DB TLS mode: %s", settings.db_ssl_mode)` so it's visible in production logs

### Step 5 — Add a regression test
Create or update `D:\finos\backend\tests\test_db_tls_config.py`:
- Test that the engine's connect_args contain `sslmode` and that it is NOT `disable`, `allow`, or `prefer`
- Test that hostname verification is not disabled
- Mark the test in the existing test suite

---

## DO NOT DO

- Do NOT touch migration env (`D:\finos\backend\migrations\env.py`) — that's prompt 03
- Do NOT change the DB driver
- Do NOT modify the connection pool settings (separate finding, separate prompt)
- Do NOT hardcode CA cert paths
- Do NOT silently fall back to insecure mode if cert verification fails — it should raise

---

## VERIFICATION CHECKLIST

- [ ] `D:\finos\backend\financeops\db\session.py` no longer disables `sslmode`, `check_hostname`, or `verify_mode`
- [ ] `DB_SSL_MODE` env var exists in `.env.example` with default `verify-full`
- [ ] App starts locally with TLS verification enabled (smoke test: hit `/health`)
- [ ] App connects to staging/production DB cleanly (user must confirm out-of-band after deploy)
- [ ] New regression test passes
- [ ] `pytest D:\finos\backend\tests\test_db_tls_config.py -v` is green
- [ ] No new test skips, no new warnings

---

## ROLLBACK PLAN

If staging deploy fails after this change:
1. Set `DB_SSL_MODE=require` (no verify) as a temporary env var on Render
2. Investigate cert chain on the DB side
3. Do NOT revert to the original `verify=False` code — fix the cert config instead

---

## COMMIT MESSAGE

```
fix(security): enforce DB TLS verification at runtime

- session.py now uses sslmode=verify-full by default
- DB_SSL_MODE env var exposed for env-specific overrides
- Added regression test ensuring TLS verification is not disabled

Closes audit finding #3 (CRITICAL).
Required for SOC 2 readiness.
```
