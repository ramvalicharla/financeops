# Runbook: Auth Incident

**Last updated:** 2026-04-07
**Service:** JWT auth + MFA (FastAPI backend + Supabase)
**Severity:** P1 (all users locked out) / P2 (subset of users, one symptom)

---

## Table of Contents

1. [Symptom: Users Cannot Log In](#1-symptom-users-cannot-log-in)
2. [Symptom: MFA Codes Rejected](#2-symptom-mfa-codes-rejected)
3. [Symptom: Sessions Expiring Too Fast](#3-symptom-sessions-expiring-too-fast)
4. [Symptom: platform_owner Locked Out Completely](#4-symptom-platform_owner-locked-out-completely)
5. [Emergency: Disable force_mfa_setup for a User](#5-emergency-disable-force_mfa_setup-for-a-user)
6. [JWT Secret Rotation](#6-jwt-secret-rotation)
7. [Verify Auth Is Healthy](#7-verify-auth-is-healthy)
8. [Escalation](#8-escalation)

---

## 1. Symptom: Users Cannot Log In

**Presentation:** POST `/api/v1/auth/login` returns 401 or 500; users report "invalid credentials".

### Likely causes and diagnostics

#### Cause A: Wrong password / account locked

```bash
# Check if the user exists and is active
# Run in Supabase SQL Editor
SELECT id, email, is_active, failed_login_attempts, locked_until
FROM iam_users
WHERE email = 'user@example.com';
```

**Resolution:**
```sql
-- Unlock a locked account
UPDATE iam_users
SET failed_login_attempts = 0, locked_until = NULL
WHERE email = 'user@example.com';
```

#### Cause B: Backend crash-looping (migration failure or config error)

```bash
curl -sf https://api.financeops.app/api/v1/health | jq .
# If 502/503, the backend itself is down — see rollback-backend.md
```

#### Cause C: JWT_SECRET changed or missing

```bash
# Check Render env vars
render env get --service financeops-api JWT_SECRET
# Should be a non-empty 32+ byte hex string
```

If blank or recently changed, see [Section 6: JWT Secret Rotation](#6-jwt-secret-rotation).

#### Cause D: Database connection failure

```bash
# Check backend logs for asyncpg connection errors
render logs --service financeops-api --tail 50 | grep -i "asyncpg\|database\|connect"
```

If DB is unreachable, see `db-migration-failure.md` and check Supabase status.

### Verify it worked

```bash
curl -sf -X POST https://api.financeops.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"known-good@example.com","password":"TestPass123!"}' \
  | jq .success
# Expected: true
```

---

## 2. Symptom: MFA Codes Rejected

**Presentation:** Valid TOTP code from authenticator app returns 401 "invalid_mfa_code".

### Likely causes and diagnostics

#### Cause A: Clock skew — server and user device time are out of sync

TOTP codes are time-based and valid for a 30-second window (±1 window). If the server clock drifts >60 seconds from the user's device, codes will always fail.

```bash
# Check server time (from Render shell)
date -u

# Compare to user's device time
# If difference > 60s, the server clock is the problem
```

Render runs NTP-synced containers — clock drift is rare but possible after a restart.

**Resolution:** Render containers auto-sync on restart. Restart the service:
```bash
render restart --service financeops-api
```

#### Cause B: User's MFA secret is corrupted or re-enrolled incorrectly

```sql
-- Check if the user has an MFA secret recorded
SELECT id, email, mfa_enabled, mfa_secret IS NOT NULL AS has_secret
FROM iam_users
WHERE email = 'user@example.com';
```

If `mfa_enabled = true` but `has_secret = false`, the MFA setup record is broken.

**Resolution:** Reset MFA for the user (forces them through setup again):
```sql
-- Reset MFA — user will be prompted to re-enroll
UPDATE iam_users
SET mfa_enabled = false,
    mfa_secret = NULL,
    force_mfa_setup = true
WHERE email = 'user@example.com';
```

> This is a mutable operation on a non-financial table and is permitted.

#### Cause C: Hard MFA enforcement blocking platform roles

If the user is `platform_owner` or `platform_admin` with `mfa_enabled = false`, the hard policy in `deps.py` will return 403 on all endpoints. See [Section 4](#4-symptom-platform_owner-locked-out-completely).

### Verify it worked

Ask the user to:
1. Open their authenticator app.
2. Wait for the code to refresh (new 30-second window).
3. Attempt login again.

---

## 3. Symptom: Sessions Expiring Too Fast

**Presentation:** Users are logged out after < 15 minutes, or refresh token is rejected.

### Likely causes and diagnostics

#### Cause A: JWT config values too short

```bash
render env get --service financeops-api JWT_ACCESS_TOKEN_EXPIRE_MINUTES
# Expected: 15
render env get --service financeops-api JWT_REFRESH_TOKEN_EXPIRE_DAYS
# Expected: 7
```

If these are missing or set to `0`, all tokens expire immediately.

**Resolution:** Set correct values in Render dashboard → Environment:
```
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
```
Then redeploy.

#### Cause B: JWT_SECRET was rotated (hard rotation invalidates all sessions)

If JWT_SECRET was recently changed, all existing tokens are invalid. Users must log in again.

This is expected after a hard rotation — communicate it to users.

#### Cause C: Session record deleted or expired in the database

```sql
-- Check if the user's session still exists
SELECT id, user_id, expires_at, is_active
FROM iam_sessions
WHERE user_id = (SELECT id FROM iam_users WHERE email = 'user@example.com')
ORDER BY created_at DESC
LIMIT 5;
```

If `is_active = false` or `expires_at < NOW()`, the session is legitimately expired.

#### Cause D: Server clock skew (JWT `exp` claim miscalculated)

```bash
# Check server time
render logs --service financeops-api --tail 5
# Look for the `timestamp` field in JSON logs — compare to UTC
```

### Verify it worked

```bash
# Login and check token expiry
RESPONSE=$(curl -sf -X POST https://api.financeops.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}')

TOKEN=$(echo $RESPONSE | jq -r .data.access_token)

# Decode JWT payload (no verification needed for debug)
echo $TOKEN | cut -d. -f2 | base64 -d 2>/dev/null | jq .exp
# exp should be ~900 seconds (15 min) from now
```

---

## 4. Symptom: platform_owner Locked Out Completely

**Presentation:** `platform_owner` user gets 403 "MFA is required for this role" on all endpoints.

This is the **hard MFA enforcement policy** — `platform_owner` and `platform_admin` roles must have MFA enabled. The policy fires unconditionally regardless of `force_mfa_setup` flag.

### Diagnostic

```sql
SELECT id, email, role, mfa_enabled, force_mfa_setup
FROM iam_users
WHERE role IN ('platform_owner', 'platform_admin')
ORDER BY role;
```

If `mfa_enabled = false` for a `platform_owner`, they are locked out of everything **except** these bypass paths:
- `POST /api/v1/auth/mfa/setup`
- `POST /api/v1/auth/mfa/verify-setup`
- `POST /api/v1/auth/mfa/verify`
- `POST /api/v1/auth/me`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/refresh`

### Resolution — guide the user through MFA setup

1. User logs in — receives access token.
2. User calls `GET /api/v1/auth/me` to confirm identity (bypass path).
3. User calls `POST /api/v1/auth/mfa/setup` to get a TOTP QR code.
4. User scans QR code with authenticator app.
5. User calls `POST /api/v1/auth/mfa/verify-setup` with the 6-digit code.
6. `mfa_enabled` is set to `true` — lockout is lifted immediately.

### Emergency: force-enable MFA bypass via SQL (last resort)

Only use this if the user genuinely cannot complete MFA setup (lost device, no authenticator app).

See [Section 5](#5-emergency-disable-force_mfa_setup-for-a-user) for the SQL.

After granting access, the user **must** enroll MFA before the bypass is removed.

---

## 5. Emergency: Disable force_mfa_setup for a User

> **P1 use only.** This bypasses a security control. Log the action with a reason.

### Via Supabase SQL Editor

1. Open [supabase.com](https://supabase.com) → your project → **SQL Editor**.

**Clear `force_mfa_setup` flag** (allows login without completing MFA setup):

```sql
-- Targeted: single user by email
UPDATE iam_users
SET force_mfa_setup = false
WHERE email = 'locked-out-user@example.com';

-- Confirm the change
SELECT id, email, role, mfa_enabled, force_mfa_setup
FROM iam_users
WHERE email = 'locked-out-user@example.com';
```

> **Note:** This does NOT bypass the hard MFA enforcement for `platform_owner`/`platform_admin` roles. If the user is a platform role, you must also set `mfa_enabled = true` temporarily and ensure they enroll properly.

**Temporary emergency access for a platform_owner (max 1 hour)**:

```sql
-- EMERGENCY ONLY — document why in your incident log
-- This allows login but MFA is still required for the role policy
-- Re-enrollment via the MFA setup flow must follow immediately
UPDATE iam_users
SET mfa_enabled = true,
    force_mfa_setup = true   -- forces re-enrollment after login
WHERE email = 'locked-out-owner@example.com'
  AND role = 'platform_owner';

-- Confirm
SELECT id, email, role, mfa_enabled, force_mfa_setup
FROM iam_users
WHERE email = 'locked-out-owner@example.com';
```

After the user completes MFA re-enrollment, `force_mfa_setup` is automatically cleared.

---

## 6. JWT Secret Rotation

### Option A: Grace-period rotation (no forced logout)

Use this when rotating due to a planned security review. Users stay logged in.

1. Add a new env var `JWT_SECRET_PREVIOUS` in Render with the old value of `JWT_SECRET`.
2. Update `financeops/core/security.py` to try both secrets when verifying tokens:
   ```python
   # Pseudo-code — implement in verify_token()
   for secret in [settings.JWT_SECRET, settings.JWT_SECRET_PREVIOUS]:
       try:
           payload = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
           return payload
       except JWTError:
           continue
   raise credentials_exception
   ```
3. Set a new `JWT_SECRET` in Render and redeploy.
4. After all access tokens expire (15 minutes) and users refresh with new tokens, remove `JWT_SECRET_PREVIOUS`.
5. Redeploy again to drop the fallback.

> **Rollout window:** 15 minutes for access tokens, up to 7 days for refresh tokens.

### Option B: Hard rotation (all sessions invalidated)

Use this when `JWT_SECRET` is believed to be compromised. All users are immediately logged out.

1. Generate a new secret:
   ```bash
   openssl rand -hex 32
   ```
2. Update `JWT_SECRET` in Render → Environment Variables.
3. Redeploy the backend.
4. All existing tokens are instantly invalid — users must log in again.
5. Communicate to users: "Security maintenance — please log in again."

> After a hard rotation, also consider rotating `FIELD_ENCRYPTION_KEY` and `SECRET_KEY` if the compromise may have been broader.

---

## 7. Verify Auth Is Healthy

Run this sequence after any auth incident is resolved:

**Step 1 — Health check**

```bash
curl -sf https://api.financeops.app/api/v1/health | jq .
# Expected: {"status": "healthy", "database": "connected", ...}
```

**Step 2 — Login flow**

```bash
RESPONSE=$(curl -sf -X POST https://api.financeops.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke@test.local","password":"SmokePass123!"}')
echo $RESPONSE | jq .success
# Expected: true
```

**Step 3 — Token validity**

```bash
TOKEN=$(echo $RESPONSE | jq -r .data.access_token)
curl -sf https://api.financeops.app/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq .data.email
# Expected: "smoke@test.local"
```

**Step 4 — Refresh token works**

```bash
REFRESH=$(echo $RESPONSE | jq -r .data.refresh_token)
curl -sf -X POST https://api.financeops.app/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH\"}" | jq .success
# Expected: true
```

**Step 5 — Check Sentry**

- No `JWTError`, `AuthenticationError`, or `credentials_exception` events in last 15 minutes.
- Login error rate back to baseline.

---

## 8. Escalation

| Who | When to escalate |
|-----|-----------------|
| On-call engineer | Immediately for P1 (all users locked out) |
| Backend lead | MFA bypass needed and you're unsure of the SQL impact |
| Security lead | JWT_SECRET believed compromised — requires hard rotation + audit |
| Supabase support ([supabase.com/support](https://supabase.com/support)) | Cannot connect to DB to run emergency SQL |

**Supabase status page:** [status.supabase.com](https://status.supabase.com)
