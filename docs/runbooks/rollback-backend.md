# Runbook: Backend Rollback (Render)

**Last updated:** 2026-04-07
**Service:** FastAPI backend on Render
**Severity:** P1 (production down) / P2 (degraded)

---

## Table of Contents

1. [Identifying a Bad Deploy](#1-identifying-a-bad-deploy)
2. [Roll Back via Render UI](#2-roll-back-via-render-ui)
3. [Roll Back via Render CLI](#3-roll-back-via-render-cli)
4. [Verify Rollback Succeeded](#4-verify-rollback-succeeded)
5. [Communicate the Rollback](#5-communicate-the-rollback)
6. [Roll Back vs Hotfix Decision](#6-roll-back-vs-hotfix-decision)
7. [Escalation](#7-escalation)

---

## 1. Identifying a Bad Deploy

### Signals — check these first

| Signal | Where to look | Bad threshold |
|--------|---------------|---------------|
| Health check failing | Render dashboard → service → Events | Red status / restarts |
| 5xx error rate spike | Sentry → Issues, or Render logs | >1% of requests |
| P99 latency spike | Render metrics | >3× baseline |
| Celery jobs stuck | Flower dashboard (`:5555`) | Queue depth growing |
| DB connection errors | Render log stream | Any `asyncpg` pool exhaustion |

### Diagnostic commands

```bash
# Tail live logs from Render CLI
render logs --service financeops-api --tail

# Health check (replace with your Render service URL)
curl -sf https://api.financeops.app/api/v1/health | jq .

# Check error counts in last 5 minutes
curl -s "https://api.financeops.app/api/v1/health/detailed" | jq .
```

### Expected healthy response

```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "version": "1.x.x"
}
```

If `status` is not `"healthy"` or the endpoint returns 5xx, treat as a **P1 incident**.

---

## 2. Roll Back via Render UI

> **P1 target time to rollback: < 5 minutes**

1. Open [dashboard.render.com](https://dashboard.render.com) and sign in.
2. Select the **financeops-api** service.
3. Click **Deploys** in the left sidebar.
4. Locate the last **green** (successful) deploy before the current one.
5. Click the three-dot menu (⋮) on that deploy row.
6. Select **Redeploy**.
7. Confirm in the dialog — Render will build and push the previous image.
8. Watch the **Events** tab; deploy typically completes in 2–4 minutes.

---

## 3. Roll Back via Render CLI

```bash
# Install CLI if not present
npm install -g @render-mgt/cli   # or: brew install render

# Authenticate
render login

# List recent deploys for the service (get deploy IDs)
render deploys list --service srv-XXXXXXXXXX

# Redeploy a specific previous deploy
render deploys rollback --service srv-XXXXXXXXXX --deploy-id dep-XXXXXXXXXX

# Watch deploy status
render deploys get --service srv-XXXXXXXXXX --deploy-id dep-XXXXXXXXXX
```

Replace `srv-XXXXXXXXXX` with the actual Render service ID (visible in the URL when viewing the service).

---

## 4. Verify Rollback Succeeded

Run these checks in order. Do **not** declare success until all pass.

**Step 1 — Health check**

```bash
curl -sf https://api.financeops.app/api/v1/health | jq .status
# Expected: "healthy"
```

**Step 2 — Auth smoke test**

```bash
curl -sf -X POST https://api.financeops.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke@test.local","password":"invalid"}' | jq .error.code
# Expected: "invalid_credentials" (not 500)
```

**Step 3 — Confirm deployed version**

```bash
curl -sf https://api.financeops.app/api/v1/health | jq .version
# Must NOT match the bad deploy's version
```

**Step 4 — Check Render Events tab**

- Deploy status shows green checkmark.
- No restart loops in the last 5 minutes.

**Step 5 — Check Sentry**

- Error rate returning to baseline (allow 2–3 minutes for traffic to normalise).

---

## 5. Communicate the Rollback

### Immediate (within 2 minutes of decision)

Post to the team channel (#incidents or equivalent):

```
[INCIDENT] Backend rollback in progress
- Detected: <what was observed, e.g. "5xx spike on /api/v1/accounting/journals">
- Bad deploy: <commit SHA or deploy ID>
- Rolling back to: <previous deploy ID / commit SHA>
- ETA: ~4 minutes
- Owner: @<your-name>
```

### Resolution (once verified)

```
[RESOLVED] Backend rollback complete
- Rolled back to: <deploy ID>
- Health check: passing
- Duration of incident: <X> minutes
- Root cause (preliminary): <brief note>
- Follow-up: <link to issue/ticket for post-mortem>
```

---

## 6. Roll Back vs Hotfix Decision

| Condition | Action |
|-----------|--------|
| Error rate >5% or health check down | **Roll back immediately**, investigate after |
| Error rate 1–5%, root cause known, fix is 1 line | Hotfix: push fix, monitor |
| Error rate 1–5%, root cause unknown | **Roll back**, investigate on a branch |
| Regression is non-critical (cosmetic, edge case) | Hotfix; no rollback needed |
| Migration was included in the bad deploy | See `db-migration-failure.md` before rolling back |

> **Rule of thumb:** When in doubt, roll back. A rollback is always faster than a hotfix under pressure.

---

## 7. Escalation

| Who | When to escalate |
|-----|-----------------|
| On-call engineer | Immediately for P1 |
| Backend lead | Rollback not completing after 10 minutes |
| Render support ([render.com/support](https://render.com/support)) | Render platform issue (deploy stuck, not redeployable) |
| Supabase support | If rollback reveals DB issue |

**Render status page:** [status.render.com](https://status.render.com)
