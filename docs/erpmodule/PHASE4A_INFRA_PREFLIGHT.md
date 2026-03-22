# FinanceOps — Phase 4A: Infrastructure Pre-Flight
## Claude Code Implementation Prompt — v1 (Final)

> Paste this entire prompt into Claude Code.
> This is a narrow, zero-risk infrastructure pass. Estimated time: 2–4 hours.
> Complete all three fixes and reach zero test failures before opening Phase 4B.

---

## WHO YOU ARE AND WHERE YOU ARE

You are Claude Code working inside the FinanceOps repository at `D:\finos\`.

This prompt contains exactly three fixes. They are scoped to be surgical and low-risk:
- No business logic changes
- No new tables
- No new migrations
- No API contract changes
- No test assertion changes

If any fix requires touching more than what is described, stop and report before proceeding.

---

## STEP 0 — READ FIRST, CONFIRM BEFORE PROCEEDING

Read in this order:

```
D:\finos\AUDIT_REPORT.md
D:\finos\KNOWN_ISSUES.md
D:\finos\alembic\versions\          ← list all files, note the current head filename
D:\finos\backend\main.py            ← find the Alembic startup call
D:\finos\pyproject.toml             ← confirm Python version range
D:\finos\Dockerfile                 ← note current base image Python version
D:\finos\infra\.env                 ← note whether real credentials exist
D:\finos\.gitignore                 ← note whether .env is currently excluded
```

After reading, explicitly state all of the following before writing a single line of code:

```
CURRENT ALEMBIC HEAD       : [e.g. 0025_some_migration_name.py]
NEXT MIGRATION NUMBER      : [head + 1, e.g. 0026]
DOCKERFILE PYTHON VERSION  : [e.g. python:3.12-slim]
PYPROJECT PYTHON RANGE     : [e.g. >=3.11,<3.13]
ENV FILE TRACKED BY GIT    : [YES / NO]
ENV FILE HAS REAL CREDS    : [YES / NO / UNKNOWN]
ALEMBIC STARTUP METHOD     : [subprocess / other — describe what is in main.py]
```

Do not proceed past Step 0 until all seven items are confirmed.

---

## FIX 1 — ALEMBIC STARTUP RACE CONDITION

**Problem:** `main.py` invokes `alembic upgrade head` via `subprocess` at startup. On
multi-worker deployments (Gunicorn, Uvicorn with multiple workers) every worker races
to run migrations simultaneously. This causes intermittent `DuplicateTable` or
`LockNotAvailable` errors in production.

**Scope:** One function change in `backend/main.py`. One new dependency.

### Implementation

Add `filelock` to `pyproject.toml` dependencies:
```toml
filelock = ">=3.12,<4.0"
```

Replace the subprocess Alembic call in `backend/main.py` with:

```python
import os
import filelock
from alembic.config import Config
from alembic import command

def run_migrations_with_lock() -> None:
    """
    Run Alembic migrations at startup with an exclusive file lock.
    Only one worker will execute migrations. Others wait up to 60 seconds
    and then proceed (assuming migrations already ran).
    """
    lock_path = os.environ.get("MIGRATION_LOCK_PATH", "/tmp/financeops_migration.lock")
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))

    try:
        with filelock.FileLock(lock_path, timeout=60):
            command.upgrade(alembic_cfg, "head")
    except filelock.Timeout:
        # Another worker holds the lock for > 60s — something is wrong.
        raise RuntimeError(
            "Migration lock timeout after 60 seconds. "
            "Check for a stuck migration process or a failed migration."
        )
```

Call `run_migrations_with_lock()` inside the FastAPI `lifespan` startup event, not at
module level. If migration raises any exception, the application must NOT start — let
the exception propagate and kill the worker process.

Log migration start and completion:
```python
import logging
logger = logging.getLogger(__name__)

# inside lifespan startup:
logger.info("Running database migrations...")
run_migrations_with_lock()
logger.info("Database migrations complete.")
```

**Verify:**
```bash
pip install filelock --break-system-packages
pytest tests/ -x -q
# Must show zero failures
```

---

## FIX 2 — CREDENTIALS IN .ENV / GIT HISTORY

**Problem:** Real credentials may be committed in `infra/.env` or `.env` and tracked in
git history. This is a security P1 — credentials in version history cannot be
revoked by simply deleting the file.

**Scope:** Git history rewrite + `.gitignore` update. No code changes.

### Step 2a — Verify what is tracked

```bash
git log --all --full-history -- "infra/.env"
git log --all --full-history -- ".env"
git log --all --full-history -- "**/.env"
```

If output is empty for all three: `.env` files are not tracked. Skip to Step 2c.

### Step 2b — Remove from git history (only if tracked)

```bash
pip install git-filter-repo --break-system-packages

# Remove each tracked env file from entire history
git filter-repo --path infra/.env --invert-paths --force
git filter-repo --path .env --invert-paths --force
```

After running: force-push to remote and coordinate with all team members to
re-clone. Document this in `KNOWN_ISSUES.md` with the date it was performed.

### Step 2c — Ensure .gitignore is correct

Verify `D:\finos\.gitignore` contains all of these (add any that are missing):

```gitignore
# Environment files — never commit real credentials
.env
.env.*
!.env.example
infra/.env
infra/.env.*
!infra/.env.example
*.env
```

### Step 2d — Verify .env.example files exist

Confirm these files exist and contain only placeholder values (no real credentials):
- `D:\finos\.env.example`
- `D:\finos\infra\.env.example`

If either is missing, create it with placeholder values matching the keys in the
real `.env` file. Example format:
```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/financeops
SECRET_KEY=your-secret-key-here
REDIS_URL=redis://localhost:6379/0
```

**Verify:**
```bash
git status
# .env files must NOT appear as tracked or modified
git check-ignore -v infra/.env
# Must show: .gitignore:N:infra/.env  infra/.env
```

---

## FIX 3 — DOCKERFILE PYTHON VERSION ALIGNMENT

**Problem:** `Dockerfile` uses a Python version that does not match the test environment.
Tests run on Python 3.11. `asyncpg` and `pydantic-core` have known behavioural
differences between minor Python versions. Mismatched versions cause hard-to-diagnose
CI/production discrepancies.

**Scope:** One line change in `Dockerfile`.

### Decision rule

- If `pyproject.toml` specifies `python_requires = ">=3.11,<3.13"` → use `python:3.11-slim`
- If tests are confirmed to run on 3.11 → use `python:3.11-slim`
- Do NOT change `pyproject.toml` — keep the version range as-is

### Implementation

In `D:\finos\Dockerfile`, change the base image line to:

```dockerfile
FROM python:3.11-slim
```

If there is a multi-stage build with multiple `FROM` lines, update every stage that
uses a Python base image.

**Verify:**
```bash
docker build -t financeops-preflight-check .
docker run --rm financeops-preflight-check python --version
# Must output: Python 3.11.x

pytest tests/ -x -q
# Must show zero failures
```

---

## FINAL VERIFICATION

After all three fixes:

```bash
# 1. Full test suite
pytest tests/ -x -q
# Required: zero failures

# 2. Migration function importable
python -c "from backend.main import run_migrations_with_lock; print('OK')"

# 3. .env not tracked
git ls-files | grep -i ".env"
# Required: empty output (no .env files tracked)

# 4. Docker version correct
docker run --rm $(docker build -q .) python --version
# Required: Python 3.11.x
```

---

## DEFINITION OF DONE

- [ ] `run_migrations_with_lock()` implemented using `filelock`
- [ ] `filelock` added to `pyproject.toml`
- [ ] Alembic called inside `lifespan` startup event, not subprocess, not module level
- [ ] Migration failure kills the worker — exception propagates, app does not start
- [ ] `.env` files removed from git history (or confirmed never tracked)
- [ ] `.gitignore` updated — no `.env` files tracked
- [ ] `.env.example` files exist with placeholder values only
- [ ] `KNOWN_ISSUES.md` updated noting the git history rewrite date (if performed)
- [ ] `Dockerfile` uses `python:3.11-slim`
- [ ] `docker build` succeeds
- [ ] `pytest tests/ -x -q` → zero failures
- [ ] All seven STEP 0 confirmation items documented in your output

---

## WHAT THIS PHASE DOES NOT TOUCH

- No API response contracts
- No endpoint return values
- No test assertions
- No idempotency logic
- No CSRF middleware
- No new database tables
- No new migrations
- No business logic of any kind

Those items are handled in Phase 4B (API Hardening).

---

## CRITICAL RULES

- Python 3.11 only
- No business logic changes
- No new migrations in this phase
- `WindowsSelectorEventLoopPolicy()` stays untouched in `main.py` and `conftest.py`
- `asyncio_default_test_loop_scope = "session"` stays untouched in `pyproject.toml`
- Run `pytest` after every fix — zero failures throughout

---

*Three fixes. Zero test failures. Then open Phase 4B.*
