# Backend Implementation Prompts — Wave 4
## ERP, Celery & CI Hardening
**Gaps covered:** #19, #20, #21, #22, #23, #24, #25, #27, #29
**Estimated effort:** ~2 days
**Prerequisite:** Wave 3 complete and tests passing
**Note:** Prompts #20+#21+#22 (Celery chunking) are the largest changes in this wave.
Run them last. Use the feature flag — do not activate chunked tasks until staging is validated.

---

## Prompt 1 of 3 — #19 — Make test_connection() abstract in base connector
**Priority:** P2 | **Effort:** XS | **Tool:** Claude Code

```
You are working in the Finqor backend codebase at D:\finos\backend.

TASK: Make AbstractConnector.test_connection() abstract so connectors without an
override fail at import time rather than silently reporting healthy connections.

STEP 1 — Read financeops/modules/erp_sync/infrastructure/connectors/base.py fully.
Confirm AbstractConnector inherits from ABC.
Note current test_connection() at line ~33.
Check if it is sync or async — match the majority pattern across the 23 connectors.

STEP 2 — Replace the default implementation:

  BEFORE:
    def test_connection(self) -> dict:
        return {"ok": True}

  AFTER:
    @abstractmethod
    async def test_connection(self) -> dict:
        """
        Test connectivity to the ERP system.
        Returns {"ok": True, "latency_ms": int} on success.
        Returns {"ok": False, "error": str} on failure.
        Raises ConnectorAuthError if credentials are invalid.
        """
        ...

STEP 3 — Grep all 23 connectors for test_connection:
  grep -rn "def test_connection" financeops/modules/erp_sync/
List any connector that does NOT override it.

STEP 4 — For each connector missing the override, add a minimal implementation:

  async def test_connection(self) -> dict:
      try:
          await self._get_client()  # replace with actual connection method
          return {"ok": True, "latency_ms": 0}
      except Exception as e:
          return {"ok": False, "error": str(e)}

STEP 5 — Verify no import errors:
  python -c "from financeops.modules.erp_sync.infrastructure.connectors import registry"

RULES:
- If AbstractConnector does not currently inherit from ABC, add ABC to its base classes
  and add: from abc import ABC, abstractmethod
- Do not change the connector registry
```

---

## Prompt 2 of 3 — #23 + #24 + #25 + #27 + #29 — CI hardening (5 quick fixes)
**Priority:** P2 | **Effort:** XS | **Tool:** Codex or Claude Code
> Run locally first before pushing: check current pytest coverage and confirm float grep returns 0 matches after Wave 3.

```
You are working in the Finqor repository at D:\finos.

TASK: Fix 5 CI configuration gaps in .github/workflows/ci.yml.

STEP 1 — Read .github/workflows/ci.yml fully before making any changes.

FIX 1 — PostgreSQL version (#23, line ~27):
  BEFORE: image: pgvector/pgvector:pg15
  AFTER:  image: pgvector/pgvector:pg16
Apply to ALL service definitions referencing pg15.
NOTE: Run existing tests on pg16 locally first if possible to catch any
      RLS/JSONB behaviour differences before pushing.

FIX 2 — Coverage threshold (#24, line ~100-108):
Find the pytest invocation step. Change to:
  run: pytest --tb=short -q --cov=financeops --cov-report=xml --cov-fail-under=70

Check pyproject.toml [dev] for pytest-cov. If missing, add: pytest-cov>=4.0

Add a coverage upload step after tests:
  - name: Upload coverage report
    uses: actions/upload-artifact@v4
    with:
      name: coverage-report
      path: backend/coverage.xml

NOTE: Run pytest --cov=financeops --cov-report=term locally first to check current
      coverage. If below 70%, lower --cov-fail-under to (current_coverage - 5) to
      avoid immediately breaking CI.

FIX 3 — Dependency vulnerability scanning (#25):
Add step in backend job AFTER tests pass:
  - name: Dependency vulnerability scan
    working-directory: backend
    run: pip install pip-audit && pip-audit --desc on

FIX 4 — Float lint check for financial fields (#27):
Add step in backend job:
  - name: Check for float usage in financial fields
    working-directory: backend
    run: |
      if grep -rn "float(" financeops/modules/ \
          --include="*.py" \
          | grep -v "confidence\|probability\|score\|#" \
          | grep -i "debit\|credit\|amount\|balance\|total\|tax\|gst"; then
        echo "ERROR: float() used for financial amount — use Decimal instead"
        exit 1
      fi

NOTE: Run this grep locally after Wave 3 to confirm 0 matches before enabling in CI.

FIX 5 — Use uv for consistent dependency install (#29, line ~70-71):
  BEFORE: run: pip install -e ".[dev]"
  AFTER:
    run: |
      pip install uv
      uv sync --extra dev

IMPORTANT: Only apply Fix 5 if uv.lock exists in the backend directory.
If it does not exist, run uv lock locally and commit the lock file first.
If unsure, skip Fix 5 and add a TODO comment — do not break CI.

RULES:
- Make each fix a SEPARATE commit for easy rollback
- Never combine all 5 into one commit
- The float grep must produce 0 matches after Wave 3 CoA fix — verify locally first
```

---

## Prompt 3 of 3 — #20 + #21 + #22 — Dead-letter queue + chunked tasks + asyncio.run() fix
**Priority:** P2 | **Effort:** L | **Tool:** Claude Code
> This is the largest change in the entire backend pass. Run last. Use the ENABLE_CHUNKED_TASKS feature flag throughout.

```
You are working in the Finqor backend codebase at D:\finos\backend.

TASK: Implement dead-letter queue for failed Celery sync tasks, chunk board pack and
consolidation into smaller tasks, and fix asyncio.run() pattern in payment tasks.

PART A — Dead-letter queue for failed sync tasks (#20):

STEP 1 — Read financeops/tasks/celery_app.py fully.
Note the 4 existing queues, failure signal handler, and Redis connection config.

STEP 2 — Add a "dead_letter" queue to task_queues in celery_app.py.

STEP 3 — In the task failure signal handler, add logic after max retries are exhausted:

  @task_failure.connect
  def on_task_failure(sender, task_id, exception, args, kwargs, traceback, einfo, **kw):
      if sender.request.retries >= sender.max_retries:
          import json
          from datetime import datetime
          redis_client.lpush("finqor:dead_letter", json.dumps({
              "task_name": sender.name,
              "task_id": str(task_id),
              "error": str(exception),
              "failed_at": datetime.utcnow().isoformat(),
          }))

STEP 4 — Add a Celery beat task to alert on stale dead-letter items:

  @celery_app.task
  def check_dead_letter_queue():
      from datetime import datetime, timedelta
      import json
      items = redis_client.lrange("finqor:dead_letter", 0, -1)
      for item in items:
          data = json.loads(item)
          failed_at = datetime.fromisoformat(data["failed_at"])
          if datetime.utcnow() - failed_at > timedelta(hours=24):
              logger.error(
                  f"Dead-letter item >24h old: {data['task_name']} — {data['error']}"
              )

STEP 5 — Add check_dead_letter_queue to the beat schedule with hourly interval.

---

PART B — Chunk board pack and consolidation tasks (#21):

STEP 6 — Add to financeops/config.py:
  ENABLE_CHUNKED_TASKS: bool = False

STEP 7 — Read the board pack task (search tasks/ for board_pack). Note current structure.

STEP 8 — Refactor with Celery Canvas chord behind the feature flag:

  from celery import chord

  @celery_app.task
  def generate_board_pack(pack_id: str):
      if not settings.ENABLE_CHUNKED_TASKS:
          return _generate_board_pack_monolithic(pack_id)  # existing logic, renamed

      pack = get_board_pack(pack_id)
      section_tasks = [generate_section.s(pack_id, s.id) for s in pack.sections]
      chord(section_tasks)(finalise_board_pack.s(pack_id))

  @celery_app.task(time_limit=120)  # per-section limit instead of global 600s
  def generate_section(pack_id: str, section_id: str):
      ...  # existing section generation logic

  @celery_app.task
  def finalise_board_pack(results, pack_id: str):
      ...  # assemble sections and mark pack complete

Apply the same chord pattern to consolidation tasks.

---

PART C — Fix asyncio.run() in sync Celery tasks (#22):

STEP 9 — Read tasks/payment_tasks.py lines ~86, 145, 214, 249.
Find all asyncio.run() patterns.

STEP 10 — Check Celery version in pyproject.toml.

If Celery >= 5.4, convert the tasks to native async tasks (preferred):
  BEFORE:
    @celery_app.task
    def some_task(arg):
        return asyncio.run(_async_impl(arg))

  AFTER:
    @celery_app.task
    async def some_task(arg):
        return await _async_impl(arg)

If Celery < 5.4, use anyio instead:
  BEFORE:
    @celery_app.task
    def some_task(arg):
        return asyncio.run(_async_impl(arg))

  AFTER:
    @celery_app.task
    def some_task(arg):
        import anyio
        return anyio.from_thread.run_sync(lambda: anyio.run(_async_impl, arg))

---

RULES:
- Python 3.11 only
- WindowsSelectorEventLoopPolicy() in main.py and conftest.py MUST NOT BE TOUCHED
- ENABLE_CHUNKED_TASKS must default to False — do not activate in production until staging validated
- The chord approach saves partial results — handle partial board pack state in the UI gracefully
- Make each part (A, B, C) a SEPARATE commit for easy rollback
```

---

*Wave 4 complete.*
*Run the full Playwright suite: `cd frontend && npx playwright test`*
*Target: all non-backend-dependent tests passing across all 3 browsers.*

---

## Summary — All Backend Waves

| Wave | Gaps | Effort | Status |
|------|------|--------|--------|
| Wave 1 — Security & P0 blockers | #1, #2, #3, #4, #5, #6, #8 | ~3 hrs | — |
| Wave 2 — API contract fixes | #7, #9, #10, #11, #12 | ~1.5 days | — |
| Wave 3 — Data integrity | #13, #15, #16, #17, #18, #26, #28 | ~1 day | — |
| Wave 4 — ERP, Celery & CI | #19, #20, #21, #22, #23, #24, #25, #27, #29 | ~2 days | — |

**Total: 29 gaps across 13 prompts.**
After all waves: run full pytest suite with live backend to clear the 52 backend-dependent Playwright tests.
