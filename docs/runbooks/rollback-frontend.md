# Runbook: Frontend Rollback (Vercel)

**Last updated:** 2026-04-07
**Service:** Next.js frontend on Vercel
**Severity:** P1 (site down / blank screens) / P2 (JS errors, broken flows)

---

## Table of Contents

1. [Identifying a Bad Deploy](#1-identifying-a-bad-deploy)
2. [Roll Back via Vercel UI](#2-roll-back-via-vercel-ui)
3. [Roll Back via Vercel CLI](#3-roll-back-via-vercel-cli)
4. [Verify Rollback Succeeded](#4-verify-rollback-succeeded)
5. [Communicate the Rollback](#5-communicate-the-rollback)
6. [Roll Back vs Hotfix Decision](#6-roll-back-vs-hotfix-decision)
7. [Escalation](#7-escalation)

---

## 1. Identifying a Bad Deploy

### Signals — check these first

| Signal | Where to look | Bad threshold |
|--------|---------------|---------------|
| Blank white screen | Browser, user reports | Any |
| JS bundle error | Browser DevTools console | `ChunkLoadError`, `SyntaxError` |
| Sentry frontend errors | Sentry → Projects → financeops-frontend | Spike above baseline |
| Vercel build failed | Vercel → Deployments tab | Red status |
| Vercel Edge Runtime errors | Vercel → Functions tab | Any 5xx |
| User reports: "page won't load" | Support channel | 2+ reports same page |

### Quick diagnostics

```bash
# Check if the app loads at all
curl -sf -I https://app.financeops.app | head -5
# Expected: HTTP/2 200

# Check if JS bundles are served
curl -sf https://app.financeops.app/_next/static/chunks/main.js -o /dev/null -w "%{http_code}"
# Expected: 200
```

### Reading Vercel deployment logs

1. Open [vercel.com](https://vercel.com) → your project → **Deployments**.
2. Click the failing deployment.
3. Select **Build Logs** tab — look for TypeScript errors, missing exports, or failed `next build`.
4. Select **Runtime Logs** tab — look for Edge Function errors.

---

## 2. Roll Back via Vercel UI

> **P1 target time to rollback: < 3 minutes**

1. Open [vercel.com](https://vercel.com) and navigate to the **financeops** project.
2. Click **Deployments** in the top navigation.
3. Find the last **green** deployment before the current one.
   - The current (bad) production deployment has a **Production** badge.
   - Look for the previous one — it shows a timestamp and commit SHA.
4. Click the three-dot menu (⋮) on the previous good deployment.
5. Select **Promote to Production**.
6. Confirm in the dialog.
7. Vercel re-routes all traffic to the old deployment instantly (no rebuild).

> The promotion is **instant** — Vercel just updates the routing alias. No build occurs.

---

## 3. Roll Back via Vercel CLI

```bash
# Install CLI if not present
npm install -g vercel

# Authenticate
vercel login

# List recent deployments
vercel ls financeops --prod

# Promote a specific deployment URL to production
vercel promote https://financeops-abc123.vercel.app --scope your-team

# Verify the production URL now points to the old deployment
vercel inspect https://app.financeops.app
```

---

## 4. Verify Rollback Succeeded

**Step 1 — Confirm production URL**

```bash
curl -sf https://app.financeops.app | grep -o '"buildId":"[^"]*"'
# Note the buildId — it must differ from the bad deploy
```

**Step 2 — Page load test**

Open these URLs in an incognito window (bypass cache) and confirm no blank screen or console errors:

- `https://app.financeops.app/` (redirect to login)
- `https://app.financeops.app/auth/login`
- `https://app.financeops.app/dashboard`

**Step 3 — Sentry error rate**

- Open Sentry → financeops-frontend → Issues.
- Filter by "Last 15 minutes".
- Error rate should be returning to pre-incident baseline.
- Allow 2–3 minutes after rollback for traffic to drain.

**Step 4 — Vercel Deployments tab**

- The promoted old deployment now shows the **Production** badge.
- No function invocation errors in the Runtime Logs.

---

## 5. Communicate the Rollback

### Immediate (within 2 minutes of decision)

```
[INCIDENT] Frontend rollback in progress
- Detected: <e.g. "blank screen on /accounting/journals, ChunkLoadError in Sentry">
- Bad deploy: <commit SHA or Vercel deployment URL>
- Rolling back to: <previous deployment URL / commit SHA>
- ETA: ~1 minute (Vercel promote is instant)
- Owner: @<your-name>
```

### Resolution

```
[RESOLVED] Frontend rollback complete
- Rolled back to: <deployment URL>
- Pages verified: login, dashboard, accounting
- Duration of incident: <X> minutes
- Root cause (preliminary): <brief note, e.g. "bad import in PageClient.tsx">
- Follow-up: <link to issue>
```

---

## 6. Roll Back vs Hotfix Decision

| Condition | Action |
|-----------|--------|
| Blank screen / JS crash on any key page | **Roll back immediately** |
| Build failed on Vercel (deploy never went live) | Push a fix; no rollback needed |
| Visual regression only (spacing, colour) | Hotfix; no rollback |
| Broken form (data loss risk) | **Roll back immediately** |
| Single page broken, others fine, fix is obvious | Hotfix if fix < 15 min; else roll back |
| TypeScript error in build, caught pre-production | Fix and redeploy; no incident |

> Vercel rollback is **zero-downtime and instant**. The cost of a false-positive rollback is very low.

---

## 7. Escalation

| Who | When to escalate |
|-----|-----------------|
| On-call engineer | Immediately for P1 |
| Frontend lead | Rollback not resolving the issue |
| Vercel support ([vercel.com/support](https://vercel.com/support)) | Promotion button unavailable, Vercel platform issue |

**Vercel status page:** [vercel-status.com](https://www.vercel-status.com)
