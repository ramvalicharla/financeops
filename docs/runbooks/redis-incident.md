# Runbook: Redis Incident

**Last updated:** 2026-04-07
**Service:** Redis on Upstash
**Severity:** P1 (Celery jobs completely stuck) / P2 (degraded job processing or rate limiting broken)

---

## Table of Contents

1. [What Redis Is Used For](#1-what-redis-is-used-for)
2. [Detecting Redis Is Down](#2-detecting-redis-is-down)
3. [Impact Assessment](#3-impact-assessment)
4. [Reconnect via Upstash Dashboard](#4-reconnect-via-upstash-dashboard)
5. [Flush Redis Safely](#5-flush-redis-safely)
6. [Drain and Restart Celery Workers After Recovery](#6-drain-and-restart-celery-workers-after-recovery)
7. [Prevention: Upstash Persistence Settings](#7-prevention-upstash-persistence-settings)
8. [Escalation](#8-escalation)

---

## 1. What Redis Is Used For

| Use case | Key pattern | Impact if lost |
|----------|-------------|----------------|
| Celery task queue | `celery` / `_kombu/*` | Background jobs stop processing |
| Celery results backend | `celery-task-meta-*` | Task status polling breaks |
| API rate limiting | `rl:{tenant_id}:{endpoint}` | Rate limits reset (security risk) |
| Session / JWT cache | `session:{user_id}` | Users may need to re-login |
| Credit reservation locks | `credit_lock:{tenant_id}` | Credit ops serialise via DB fallback |
| LLM circuit breaker state | `cb:{provider}` | Circuit breaker resets to closed |

---

## 2. Detecting Redis Is Down

### Automated signals

- Celery workers log: `redis.exceptions.ConnectionError` or `kombu.exceptions.OperationalError`
- API responses return `503` with body: `{"error": {"code": "service_unavailable"}}`
- Flower dashboard (`:5555`) shows all workers as offline or queue depth growing without drain
- Sentry alert: `redis.exceptions.ConnectionError` spike

### Manual health check

```bash
# From local machine (requires REDIS_URL from .env)
redis-cli -u "$REDIS_URL" ping
# Expected: PONG
# Bad: Could not connect to Redis / NOAUTH / timeout

# From Render shell (open via Render dashboard → Shell tab)
python -c "
import redis, os
r = redis.from_url(os.environ['REDIS_URL'])
print(r.ping())
"
```

### Check Celery worker status

```bash
# From Render shell
celery -A financeops.tasks.celery_app inspect ping

# Expected: one response per worker
# Bad: empty response or timeout after 30s
```

---

## 3. Impact Assessment

### What breaks without Redis

| Feature | Status |
|---------|--------|
| Background jobs (report generation, ERP sync, email ingestion) | **BROKEN** — jobs queue but don't process |
| Rate limiting | **BYPASSED** — all requests pass through (risk window) |
| LLM circuit breaker | **RESET** — may hit providers harder than intended |
| Session cache | Degraded — backend re-validates from DB each request (slower but works) |
| Real-time job status polling | **BROKEN** — `/api/v1/jobs/{id}/status` returns stale data |

### What keeps working without Redis

| Feature | Status |
|---------|--------|
| Login / logout | **OK** — auth reads from PostgreSQL |
| All read/write API endpoints | **OK** — DB is primary store |
| File uploads (airlock scan) | **OK** — ClamAV is a direct TCP call |
| MFA | **OK** — TOTP is stateless |
| Billing / accounting | **OK** — all data in PostgreSQL |

> Redis is a **best-effort** dependency for background processing. Core financial data is safe.

---

## 4. Reconnect via Upstash Dashboard

**Step 1 — Check Upstash status**

1. Open [console.upstash.com](https://console.upstash.com).
2. Navigate to your Redis database.
3. Check the **Metrics** tab for connection errors, latency spikes, or memory pressure.

**Step 2 — Test connectivity from Upstash console**

In the **CLI** tab of the Upstash console:

```
PING
# Expected: PONG
INFO server
# Check: uptime_in_seconds, redis_version
```

**Step 3 — Check if the connection URL is still valid**

```bash
# Upstash rotates credentials only if you manually reset them
# Confirm REDIS_URL in Render env vars matches Upstash → Details → Connection String
render env get --service financeops-api REDIS_URL
```

**Step 4 — Restart the Render services to force reconnection**

If Redis is back up but workers are stuck:

```bash
# Via Render UI: service → Settings → Restart service
# Or via CLI:
render restart --service financeops-celery-worker
render restart --service financeops-api
```

**Step 5 — Verify reconnection**

```bash
redis-cli -u "$REDIS_URL" ping
# Expected: PONG

# Check worker reconnected
celery -A financeops.tasks.celery_app inspect ping
```

---

## 5. Flush Redis Safely

> **WARNING:** Flushing Redis drops ALL queued jobs that haven't been picked up yet. Only do this if:
> - Jobs are poisoned (stuck in a loop, consuming all memory)
> - You are certain the queued jobs can be safely discarded or replayed

**Step 1 — Drain queues before flushing (preferred)**

```bash
# Revoke all pending tasks (they will not be executed)
celery -A financeops.tasks.celery_app purge

# Confirm queues are empty
celery -A financeops.tasks.celery_app inspect reserved
```

**Step 2 — If you must flush entirely**

```bash
# Flush ALL keys — use only in an emergency
redis-cli -u "$REDIS_URL" FLUSHALL ASYNC

# Or flush only the Celery namespace
redis-cli -u "$REDIS_URL" --scan --pattern "celery*" | xargs redis-cli -u "$REDIS_URL" DEL
redis-cli -u "$REDIS_URL" --scan --pattern "_kombu*" | xargs redis-cli -u "$REDIS_URL" DEL
```

**Step 3 — Verify flush**

```bash
redis-cli -u "$REDIS_URL" DBSIZE
# Should be near 0 or significantly reduced
```

---

## 6. Drain and Restart Celery Workers After Recovery

**Step 1 — Check what's in the queues**

```bash
# Count tasks by queue
celery -A financeops.tasks.celery_app inspect active_queues
redis-cli -u "$REDIS_URL" LLEN celery
```

**Step 2 — Warm restart (preferred — no task loss)**

```bash
# Send warm shutdown — workers finish current task then exit
celery -A financeops.tasks.celery_app control shutdown

# Wait for workers to drain (check Flower or the command below)
celery -A financeops.tasks.celery_app inspect active
# Expected: empty response (no active tasks)
```

**Step 3 — Restart workers via Render**

```bash
render restart --service financeops-celery-worker
```

Or via Render UI: select the Celery worker service → **Restart**.

**Step 4 — Verify workers are consuming**

```bash
# Workers should respond to ping
celery -A financeops.tasks.celery_app inspect ping

# Queue depth should be decreasing
watch -n 5 "redis-cli -u \"$REDIS_URL\" LLEN celery"
```

**Step 5 — Check Flower**

Open Flower dashboard (`:5555`):
- Workers tab: all workers show "Online"
- Tasks tab: tasks moving from "Received" → "Succeeded"

---

## 7. Prevention: Upstash Persistence Settings

Verify these settings in Upstash → your database → **Config**:

| Setting | Recommended value | Why |
|---------|-------------------|-----|
| Persistence | **Enabled (RDB + AOF)** | Survive Upstash node restart without data loss |
| AOF Sync | `everysec` | Balance between durability and performance |
| Max Memory Policy | `allkeys-lru` | Prevents OOM by evicting least-recently-used keys |
| TLS | **Enabled** | Encrypt data in transit |
| Eviction Notifications | Enabled | Alert when keys are being evicted (memory pressure) |

### Check current memory usage

```bash
redis-cli -u "$REDIS_URL" INFO memory | grep used_memory_human
# Alert if approaching the Upstash plan's max memory limit
```

### Check for unexpectedly large keys

```bash
redis-cli -u "$REDIS_URL" --bigkeys
# Anything >1MB is suspicious
```

---

## 8. Escalation

| Who | When to escalate |
|-----|-----------------|
| On-call engineer | Immediately if Celery has been stuck >10 minutes |
| Backend lead | Redis is up but workers won't reconnect after restart |
| Upstash support ([upstash.com/support](https://upstash.com/support)) | Redis data loss, unexpected eviction, plan limits hit |

**Upstash status page:** [status.upstash.com](https://status.upstash.com)
