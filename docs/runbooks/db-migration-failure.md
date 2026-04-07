# Runbook: Database Migration Failure

**Last updated:** 2026-04-07
**Service:** Alembic migrations on Supabase (PostgreSQL, aws-1-ap-southeast-2)
**Severity:** P1 (backend won't start) / P2 (partial data unavailable)

---

## Table of Contents

1. [How Migrations Run](#1-how-migrations-run)
2. [Detecting a Failed Migration](#2-detecting-a-failed-migration)
3. [Identify Which Migration Failed](#3-identify-which-migration-failed)
4. [Roll Back a Migration](#4-roll-back-a-migration)
5. [Fix and Re-run](#5-fix-and-re-run)
6. [Handle a Partially Applied Migration](#6-handle-a-partially-applied-migration)
7. [Emergency: Direct Supabase Access](#7-emergency-direct-supabase-access)
8. [Prevention Checklist](#8-prevention-checklist)
9. [Escalation](#9-escalation)

---

## 1. How Migrations Run

Migrations run **automatically on backend startup** via the FastAPI lifespan handler:

```python
# financeops/main.py — lifespan
await run_migrations()   # calls alembic upgrade head
```

- Migration files live in `backend/migrations/versions/`.
- Alembic tracks the current revision in the `alembic_version` table in the database.
- If `upgrade head` fails, the app process exits — Render restarts it, which re-attempts the migration.

> **Important:** Render will retry the failed start in a loop. You will see repeated crash-restart cycles in the Events tab.

---

## 2. Detecting a Failed Migration

### Render Events tab

Look for a pattern like:

```
Deploy live
Service starting
Error: Could not start service
Service restarting...
```

### Render log stream — tell-tale patterns

```
alembic.util.exc.CommandError: Can't locate revision identified by '...'
sqlalchemy.exc.ProgrammingError: column "xyz" of relation "abc" does not exist
sqlalchemy.exc.OperationalError: table "xyz" already exists
```

### Quick check via API

```bash
curl -sf https://api.financeops.app/api/v1/health
# Returns 502 Bad Gateway or connection refused if backend is crash-looping
```

---

## 3. Identify Which Migration Failed

**Step 1 — Read the full Render log**

```bash
render logs --service financeops-api --tail 200
```

Look for lines containing `Running upgrade` or the Alembic error. The revision ID will appear in the error.

**Step 2 — Check current DB state via Supabase SQL Editor**

```sql
-- What revision does Alembic think is applied?
SELECT version_num FROM alembic_version;

-- List all migration files and their IDs
-- (Do this locally to compare)
```

**Step 3 — Compare to local migrations**

```bash
cd backend
# List all known revisions in order
alembic history --verbose

# Show current head
alembic heads
```

The gap between the DB's `version_num` and the code's `head` points to the failing migration.

---

## 4. Roll Back a Migration

> **Only run downgrade if the migration has already partially or fully applied.**
> If the migration never ran (backend crashed before applying), skip to [Fix and Re-run](#5-fix-and-re-run).

**Step 1 — Stop the backend to prevent concurrent writes**

In Render: suspend the service (Settings → Suspend service) or scale to 0 replicas.

**Step 2 — Set the direct DB URL** (bypasses PgBouncer pooler for DDL)

```bash
export MIGRATION_DATABASE_URL="postgresql+asyncpg://postgres:<password>@db.<project>.supabase.co:5432/postgres"
```

Get this from Supabase → Project Settings → Database → Connection String → Direct.

**Step 3 — Downgrade one step**

```bash
cd backend
alembic -x db_url="$MIGRATION_DATABASE_URL" downgrade -1
```

**Step 4 — Confirm the DB is back to the previous revision**

```bash
alembic -x db_url="$MIGRATION_DATABASE_URL" current
```

**Step 5 — Verify the DB in Supabase SQL Editor**

```sql
-- Confirm alembic_version matches the expected previous revision
SELECT version_num FROM alembic_version;

-- Check the table/column that the bad migration touched still has the correct schema
\d table_name   -- in psql, or use Supabase Table Editor
```

---

## 5. Fix and Re-run

1. Fix the migration file in `backend/migrations/versions/`.
2. Test locally:
   ```bash
   # Apply to local test DB
   cd backend
   alembic upgrade head

   # Verify
   alembic current
   pytest tests/ -k "migration" -v
   ```
3. Push to `main` — Render will auto-deploy and re-run the migration on startup.
4. Watch Render Events tab for successful deploy.

---

## 6. Handle a Partially Applied Migration

A migration is "partial" when it ran some DDL statements but crashed mid-flight (e.g. added a column but didn't create the index).

### Detection

```sql
-- Check for expected table/column
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'your_table'
ORDER BY ordinal_position;

-- Check for expected index
SELECT indexname FROM pg_indexes WHERE tablename = 'your_table';

-- Check alembic_version — was the revision marked as applied?
SELECT version_num FROM alembic_version;
```

### If the revision IS in alembic_version (migration "succeeded" but is broken)

```sql
-- Manually remove the bad revision record so Alembic will re-run it
DELETE FROM alembic_version WHERE version_num = '<bad_revision_id>';
```

Then manually drop/fix the partial objects:

```sql
-- Example: remove a partially created column
ALTER TABLE your_table DROP COLUMN IF EXISTS bad_column;

-- Example: remove a partial index
DROP INDEX IF EXISTS ix_your_table_bad_column;
```

Then re-run:

```bash
alembic -x db_url="$MIGRATION_DATABASE_URL" upgrade head
```

### If the revision is NOT in alembic_version (migration failed before recording)

Clean up any partial objects manually (see above), then re-run upgrade.

---

## 7. Emergency: Direct Supabase Access

### Connect via Supabase SQL Editor

1. Go to [supabase.com](https://supabase.com) → your project → **SQL Editor**.
2. All SQL runs as the database owner — full DDL access.

### Connect via psql (direct, bypasses pooler)

```bash
# Get connection string from Supabase → Settings → Database → URI
psql "postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres"
```

### Useful emergency queries

```sql
-- Current migration state
SELECT version_num FROM alembic_version;

-- All tables (sanity check schema exists)
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;

-- Active connections (check for blocking locks)
SELECT pid, usename, application_name, state, query_start, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start;

-- Check for blocking locks
SELECT blocked_locks.pid AS blocked_pid,
       blocking_locks.pid AS blocking_pid,
       blocked_activity.query AS blocked_query,
       blocking_activity.query AS blocking_query
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_locks blocking_locks
  ON blocking_locks.locktype = blocked_locks.locktype
  AND blocking_locks.relation = blocked_locks.relation
  AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- Kill a blocking connection (use pid from above)
SELECT pg_terminate_backend(<pid>);
```

---

## 8. Prevention Checklist

Run this before every migration-containing PR is merged:

- [ ] Test migration locally: `alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head`
- [ ] Confirm the migration is reversible (has a proper `downgrade()` function)
- [ ] Run the full test suite: `pytest tests/ -v`
- [ ] For large tables: ensure `ALTER TABLE` uses `NOT NULL DEFAULT` or is done with a backfill migration
- [ ] Never add a `NOT NULL` column without a `server_default` in the same migration
- [ ] Append-only tables: verify no `UPDATE` or `DELETE` in migration DDL (violates immutability)
- [ ] Test on a copy of production schema if migration touches tables with >100k rows

---

## 9. Escalation

| Who | When to escalate |
|-----|-----------------|
| Backend lead | Can't identify which migration failed after 15 minutes |
| Database admin / DBA | Partial migration with data corruption risk |
| Supabase support ([supabase.com/support](https://supabase.com/support)) | DB unreachable, point-in-time recovery needed |

**Supabase status page:** [status.supabase.com](https://status.supabase.com)

> **Nuclear option:** Supabase supports Point-in-Time Recovery (PITR). If data corruption is confirmed, contact Supabase support immediately with a target restore timestamp *before* the bad migration ran.
