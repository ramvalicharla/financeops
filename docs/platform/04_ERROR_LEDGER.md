# FinanceOps Platform — Error & Update Ledger
> Auto-updated on every merged commit via GitHub Actions
> APPEND ONLY — never modify existing entries
> Format: newest entries at top

---

## How This Document Works

**Automatic:** GitHub Actions populates entries on every merge to `main`
**Manual:** Add known issues, resolutions, and learnings as you discover them
**Rule:** Never edit or delete an existing entry — only add new entries
**Purpose:** Future team members can understand exactly what was built, what broke, and how it was fixed

---

## Entry Format

```
### [{version}] {date} — {module} — {brief description}
**Type:** feat | fix | refactor | docs | security | performance
**Author:** {github username}
**Files Changed:**
  - {file path} (lines {start}-{end})
**What Changed:** {clear description of what was done}
**Why:** {reason for the change}
**Known Risks:** {what could go wrong}
**If It Breaks:** {exact steps to diagnose and fix}
**Rollback:** `git revert {commit hash}` then `{any additional steps}`
**Dependencies Affected:** {list of modules/services that may be affected}
**Tests Added:** {test file + test name}
---
```

---

## Entries

### [0.0.1] 2025-03-02 — PLATFORM — Initial repository created
**Type:** feat
**Author:** founder
**Files Changed:**
  - All files (initial commit)
**What Changed:** Repository created with monorepo structure, README, and this ledger
**Why:** Starting point for FinanceOps platform build
**Known Risks:** None — initial commit
**If It Breaks:** N/A
**Rollback:** N/A — initial commit
**Dependencies Affected:** None
**Tests Added:** None yet

---

## Error Reference Library

### Common Errors and Solutions

Track every error encountered during development here. Future developers will find solutions faster.

```
ERROR ID:     ERR-001
ERROR:        PostgreSQL RLS blocks query with "permission denied for table"
CAUSE:        Current DB user doesn't have the tenant_id setting configured
SOLUTION:     Ensure middleware sets: SET LOCAL app.current_tenant_id = '{tenant_id}'
              in every DB session before executing queries
CODE FIX:     In backend/db/session.py — add set_tenant_context() call after connection
PREVENTION:   Add integration test that verifies RLS blocks cross-tenant access
```

```
ERROR ID:     ERR-002
ERROR:        Celery worker not picking up tasks from queue
CAUSE:        Worker started before Redis connection was ready, or queue name mismatch
SOLUTION:     1. Check Redis connection: redis-cli ping
              2. Check worker is listening to correct queue: celery inspect active_queues
              3. Check task is routed to correct queue in celery config
CODE FIX:     Add Redis health check before worker starts in docker-compose
PREVENTION:   health_check in docker-compose for Redis dependency
```

```
ERROR ID:     ERR-003
ERROR:        Temporal workflow stuck in "Running" state indefinitely
CAUSE:        Activity timed out without proper error handling
SOLUTION:     1. Check Temporal UI for workflow history
              2. Look for "ActivityTaskTimedOut" event
              3. Terminate stuck workflow: temporal workflow terminate {id}
              4. Fix timeout value in activity definition
CODE FIX:     Add schedule_to_close_timeout to all activity definitions
PREVENTION:   Every activity MUST have explicit timeout defined
```

```
ERROR ID:     ERR-004
ERROR:        Chain hash verification fails on audit log
CAUSE:        Concurrent writes to audit table caused hash collision
SOLUTION:     1. Run: SELECT verify_audit_chain('audit_log', start_id, end_id)
              2. Find break point in chain
              3. Check for concurrent writes at that timestamp
              4. Rebuild chain from last known good entry (append correction record)
CODE FIX:     Add database-level row lock on chain hash computation
PREVENTION:   Use SELECT FOR UPDATE when computing chain hash
```

```
ERROR ID:     ERR-005
ERROR:        Ollama not responding — AI Gateway falls back to cloud
CAUSE:        Ollama process crashed or ran out of memory
SOLUTION:     1. Check: curl http://localhost:11434/api/tags
              2. Restart: ollama serve
              3. Check memory: free -h (phi3:mini needs ~2GB)
              4. If memory issue: restart Ollama and wait for model to load
CODE FIX:     Add Ollama health check in AI Gateway with automatic fallback logging
PREVENTION:   Monitor Ollama memory usage, alert at 80% memory
```

```
ERROR ID:     ERR-006
ERROR:        CORS error in browser when calling API
CAUSE:        Frontend domain not in CORS allowed origins
SOLUTION:     1. Check CORS config in backend/core/config.py → ALLOWED_ORIGINS
              2. Add the frontend domain
              3. For local dev: ensure localhost:3000 is in allowed origins
CODE FIX:     Add domain to ALLOWED_ORIGINS environment variable
PREVENTION:   CORS config reads from environment — set correctly in Doppler
```

```
ERROR ID:     ERR-007
ERROR:        JWT token rejected — "Signature verification failed"
CAUSE:        JWT secret key changed or mismatch between environments
SOLUTION:     1. Check Doppler for JWT_SECRET_KEY — must be identical in API + workers
              2. Issue new tokens by logging out all users (clear refresh tokens in DB)
              3. Verify: all services use same secret
CODE FIX:     Rotate JWT secret via Doppler — automatically propagates to all services
PREVENTION:   Never hardcode JWT secret — always from Doppler
```

```
ERROR ID:     ERR-008
ERROR:        Excel export corrupted — cannot open in Excel
CAUSE:        openpyxl file written while still open, or incomplete write
SOLUTION:     1. Check worker logs for write errors
              2. Verify workbook.save() called after all writes complete
              3. Delete corrupted file from R2, re-generate
CODE FIX:     Use context manager: with openpyxl.load_workbook(...) as wb:
PREVENTION:   Always use context managers for file operations
```

```
ERROR ID:     ERR-009
ERROR:        ClamAV scan hangs on large file
CAUSE:        ClamAV daemon has file size limit or is overloaded
SOLUTION:     1. Check ClamAV daemon: systemctl status clamav-daemon
              2. Increase MaxFileSize in /etc/clamav/clamd.conf
              3. Restart daemon: systemctl restart clamav-daemon
CODE FIX:     Set Celery task timeout for file scan at 120 seconds
PREVENTION:   Enforce 50MB file size limit BEFORE sending to ClamAV
```

```
ERROR ID:     ERR-010
ERROR:        PostgreSQL connection pool exhausted
CAUSE:        Too many concurrent requests, not enough pool connections
SOLUTION:     1. Check: SELECT count(*) FROM pg_stat_activity
              2. Kill idle connections: SELECT pg_terminate_backend(pid) WHERE state='idle'
              3. Increase pool size in database config
              4. Check for connection leaks (connections not being returned to pool)
CODE FIX:     Ensure all DB sessions use async context managers (async with session:)
PREVENTION:   PgBouncer in front of PostgreSQL to manage connection pooling
```

---

## Performance Baselines

Track performance benchmarks here. Add new entries when you measure.

```
DATE          ENDPOINT                          P50     P95     P99
2025-03-02    GET /health                       12ms    18ms    25ms
              (add measurements as you go)
```

---

## Dependency Vulnerability Log

Track security vulnerabilities found and resolved.

```
DATE        PACKAGE           CVE             SEVERITY    RESOLVED
(populated by Dependabot + Snyk automatically)
```

---

## Architecture Decisions

Track why key decisions were made. Prevent future team from re-litigating settled decisions.

```
DECISION:   Use Temporal instead of pure Celery for multi-step workflows
DATE:       2025-03-02
CONTEXT:    Month-end close has 20+ steps, runs over hours, must survive crashes
OPTIONS:    1. Celery chains (rejected: state lost on crash)
            2. Database-backed state machine (rejected: complex, reinventing the wheel)
            3. Temporal (chosen: durable execution, built-in retry, great UI)
TRADE-OFFS: Temporal adds infrastructure complexity but is worth it for reliability
STATUS:     Decided — do not revisit without strong justification
```

```
DECISION:   phi3:mini as default local model (not Mistral)
DATE:       2025-03-02
CONTEXT:    Need fast, local inference for Stage 1 (prep) and Stage 5 (format)
OPTIONS:    1. Mistral 7B (slower, better quality)
            2. phi3:mini (faster, sufficient quality for prep/format tasks)
            3. DeepSeek 6.7B (good at code/structure, slower)
TRADE-OFFS: phi3:mini is 3-4x faster than Mistral for simple tasks
            Quality difference negligible for prep/format (not analysis)
STATUS:     Decided — phi3:mini for Stages 1 & 5, Mistral for Stage 2 local execution
```

```
DECISION:   Append-only database with no UPDATE/DELETE on audit tables
DATE:       2025-03-02
CONTEXT:    SOC2, ISO, GDPR, and immutability requirements
OPTIONS:    1. Standard CRUD with soft delete (rejected: not truly immutable)
            2. Event sourcing (considered: too complex for initial build)
            3. Append-only with version columns (chosen: simple, auditable, correct)
TRADE-OFFS: Slightly more storage, simpler queries (always select WHERE is_superseded=false)
STATUS:     Decided — core architectural principle, non-negotiable
```

---

*End of Error & Update Ledger*
*This document is append-only — never modify existing entries*

---

## Severity Classification Guide

```
SEVERITY LEVELS — USE THESE CONSISTENTLY:

P0: Platform down or data at risk
    ├── All users affected
    ├── Data loss possible
    ├── Security breach
    └── SLA: acknowledge 5 min, resolve 60 min

P1: Major feature broken
    ├── >20% users affected
    ├── Core workflow blocked (cannot close month-end)
    ├── Authentication broken
    └── SLA: acknowledge 15 min, resolve 4 hours

P2: Feature degraded
    ├── <20% users affected
    ├── Workaround exists
    ├── Performance degraded but functional
    └── SLA: acknowledge 1 hour, resolve 8 hours

P3: Minor issue
    ├── Cosmetic problem
    ├── Edge case bug
    ├── Single user affected
    └── SLA: fix in next sprint

P4: Enhancement / no user impact
    ├── Improvement request
    ├── Technical debt
    ├── Documentation gap
    └── SLA: prioritise in backlog
```

---

## Root Cause Analysis Template (P0/P1 Required)

```
USE THIS FORMAT FOR ALL P0 AND P1 POST-MORTEMS:
Add as an entry in this ledger within 24 hours of resolution.

---
DATE: YYYY-MM-DD
INCIDENT ID: INC-NNNN
SEVERITY: P0/P1
DURATION: X hours Y minutes
USERS AFFECTED: estimated count / percentage
DETECTION METHOD: [PagerDuty alert / user report / monitoring]
DETECTION METRIC: [which Grafana panel / which alert fired]
TRACE ID: [correlation_id from logs for this incident]
DASHBOARD LINK: [direct link to Grafana timeframe]

TIMELINE:
  HH:MM UTC — [what happened]
  HH:MM UTC — [when detected]
  HH:MM UTC — [first action taken]
  HH:MM UTC — [resolution]

ROOT CAUSE (5 Whys):
  Why 1: [immediate cause]
  Why 2: [cause of why 1]
  Why 3: [cause of why 2]
  Why 4: [cause of why 3]
  Why 5: [root cause]

IMPACT:
  User impact: [what users experienced]
  Data impact: [any data affected — YES/NO + details]
  Revenue impact: [SLA credits due? estimate]

RESOLUTION:
  [what was done to fix it]

PREVENTION (action items):
  [ ] Action 1 — Owner — Due date
  [ ] Action 2 — Owner — Due date

BLAMELESS NOTE:
  [this is a systems problem, not a people problem]
---
```

---

## Known Workarounds

```
ACTIVE WORKAROUNDS (issues not yet fixed):
  None currently — add here as issues arise.

FORMAT:
  ISSUE: [brief description]
  AFFECTS: [which feature/module]
  WORKAROUND: [step by step]
  FIX ETA: [when permanent fix expected]
  ADDED: [date added]
```

---

## Performance Baselines

```
Establish these baselines after Phase 0 build.
Update after each major phase.

BASELINE AS OF: [date — fill after first build]

API Response Times (p50 / p95 / p99):
  GET /api/v1/health:              __ ms / __ ms / __ ms
  POST /api/v1/mis/upload:         __ ms / __ ms / __ ms
  GET /api/v1/mis/dashboard:       __ ms / __ ms / __ ms
  POST /api/v1/reconciliation/run: __ ms / __ ms / __ ms

Task Completion Times (median):
  MIS classification (100 rows):   __ seconds
  GL reconciliation (1000 entries): __ seconds
  Consolidation (3 entities):      __ seconds
  AI commentary generation:        __ seconds
  Report PDF generation:           __ seconds

Database:
  Avg query time:                  __ ms
  Slow queries (>1s) per hour:     __
  Connection pool utilisation:     __%

AI Pipeline:
  Stage 1 (prepare):               __ ms
  Stage 2 (execute):               __ ms
  Stage 3 (validate):              __ ms
  Total pipeline (no Stage 4):     __ seconds

Note: any regression >20% from these baselines = P2 investigation.
```
