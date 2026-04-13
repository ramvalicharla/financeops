# Backend Implementation Prompts — Wave 3
## Data Integrity & Financial Correctness
**Gaps covered:** #13, #15, #16, #17, #18, #26, #28
**Estimated effort:** ~1 day
**Prerequisite:** Wave 2 complete and tests passing
**Run after each prompt:** `pytest --tb=short -q`

---

## Prompt 1 of 3 — #13 — Fix float() for financial amounts in CoA upload
**Priority:** P1 | **Effort:** XS | **Tool:** Codex or Claude Code

```
You are working in the Finqor backend codebase at D:\finos\backend.

TASK: Replace all float() calls for financial amounts in
financeops/modules/coa/application/coa_upload_service.py with Decimal.

STEP 1 — Read coa_upload_service.py lines 380-430.
Confirm 6 occurrences of float(row.get("debit") or 0) and float(row.get("credit") or 0)
at lines ~386, 387, 403, 404, 421, 422.

STEP 2 — Add imports if not present:
  from decimal import Decimal, ROUND_HALF_UP

STEP 3 — Replace each occurrence:

  BEFORE: float(row.get("debit") or 0)
  AFTER:  Decimal(str(row.get("debit") or "0")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

  BEFORE: float(row.get("credit") or 0)
  AFTER:  Decimal(str(row.get("credit") or "0")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

The str() wrapper is essential — Decimal(str(value)) is precise,
Decimal(float_value) inherits float precision errors.

STEP 4 — Check return type annotations of functions containing these lines.
Update any float type hints to Decimal.

STEP 5 — Add a test:
  row = {"debit": "1234567.89", "credit": "0"}
  result = parse_coa_row(row)  # use the actual function name
  assert isinstance(result["debit"], Decimal)
  assert result["debit"] == Decimal("1234567.8900")

STEP 6 — Run a project-wide grep to confirm no other float() calls on financial fields:
  grep -rn "float(" financeops/modules/ | grep -i "debit\|credit\|amount\|balance"
Report any found beyond these 6.

RULES:
- ROUND_HALF_UP is project standard — confirmed in quantization_policy.py
- Decimal("0.0001") = 4 decimal places — matches Numeric(20,4) DB columns
- str() wrapper mandatory when constructing Decimal from user input
```

---

## Prompt 2 of 3 — #16 + #18 — Call verify_rls_active() at startup + fix audit commit
**Priority:** P2 | **Effort:** S | **Tool:** Claude Code

```
You are working in the Finqor backend codebase at D:\finos\backend.

TASK: Wire verify_rls_active() into the startup lifespan and fix the audit commit bypass.

PART A — Wire verify_rls_active() at startup:

STEP 1 — Read financeops/db/rls.py lines 45-67.
Confirm exact signature of verify_rls_active(session, table_name: str) -> bool.

STEP 2 — Read financeops/main.py. Find the lifespan async context manager.
Find where the DB ping / startup health check happens.

STEP 3 — After the DB ping passes, add:

  CRITICAL_RLS_TABLES = [
      "accounting_jv_state_events",
      "gl_entries",
      "bank_transactions",
      "credit_ledger",
      "auditor_grants",
      "payroll_journal_lines",
      "consolidation_entries",
  ]
  async with AsyncSessionLocal() as rls_check_session:
      for table_name in CRITICAL_RLS_TABLES:
          rls_active = await verify_rls_active(rls_check_session, table_name)
          if not rls_active:
              startup_errors.append(f"CRITICAL: RLS not active on table {table_name}")
              logger.critical(f"RLS not active on {table_name} — data isolation at risk")

STEP 4 — Confirm exact __tablename__ values for the 7 tables by reading their model files.
Adjust any names that do not match exactly.

IMPORTANT: RLS startup check must NOT block startup when APP_ENV != "production".
In dev/test, log a WARNING instead of appending to startup_errors.
The AsyncSessionLocal used must have permissions to read pg_class.

PART B — Fix audit commit bypass:

STEP 5 — Find await session.commit() at line ~252 in user_service.py.
Confirm commit_session is already imported in the file.
Replace: await session.commit()
With:    await commit_session(session)

RULES:
- Python 3.11 only
- If verify_rls_active is async, await it; if sync, wrap with run_in_executor
- Check the function signature before calling
```

---

## Prompt 3 of 3 — #15 + #17 + #26 + #28 — IamSession, JV doc, RLS test, public route guard
**Priority:** P2 | **Effort:** M | **Tool:** Claude Code

```
You are working in the Finqor backend codebase at D:\finos\backend.

TASK: Four data integrity fixes grouped together — IamSession audit history preservation,
JV mutable design documentation, tenant isolation integration test, and public route RLS comment.

FIX 1 — Preserve IamSession audit history (#15):

STEP 1 — Read user_service.py lines 200-215. Find delete(IamSession) at ~line 204.
STEP 2 — Read auth_service.py ~line 508. Find revoke_all_sessions().
Confirm its signature and that it does NOT issue a DELETE.
STEP 3 — Replace the delete(IamSession) block with:
  await revoke_all_sessions(session, user_id=user_id)
Import revoke_all_sessions from auth_service if not already imported.

FIX 2 — Document JV aggregate mutability (#17):

STEP 4 — Read db/models/accounting_jv.py lines 68-155.
Find the accounting_jv_aggregates model class.
STEP 5 — Add a comment block immediately above the class definition:
  # INTENTIONAL DESIGN NOTE: accounting_jv_aggregates is a MUTABLE state projection.
  # It is intentionally excluded from APPEND_ONLY_TABLES.
  # The immutable audit trail lives in accounting_jv_state_events (append-only).
  # This table tracks current JV state only — a read-optimised view of the event log.
  # Any JV status change MUST also insert a row in accounting_jv_state_events.
  # See docs/design/append-only-architecture.md for the full pattern rationale.
STEP 6 — Add a comment in db/append_only.py near where accounting_jv_aggregates
would appear (if it was included):
  # accounting_jv_aggregates intentionally EXCLUDED — mutable state projection.
  # See accounting_jv.py model docstring for rationale.

FIX 3 — RLS tenant isolation integration test (#26):

STEP 7 — Read tests/integration/ to understand existing patterns.
Note fixture names, session factories, and tenant creation helpers.
STEP 8 — Create tests/integration/test_rls_isolation.py:

  import pytest
  from financeops.db.rls import set_tenant_context
  from sqlalchemy import select

  @pytest.mark.asyncio
  async def test_tenant_a_cannot_read_tenant_b_data(async_session_factory, create_tenant):
      tenant_a = await create_tenant(slug="rls-test-tenant-a")
      tenant_b = await create_tenant(slug="rls-test-tenant-b")

      # Insert a GL entry under Tenant A context
      async with async_session_factory() as session_a:
          await set_tenant_context(session_a, tenant_id=tenant_a.id)
          entry = GLEntry(tenant_id=tenant_a.id)  # add minimum required fields
          session_a.add(entry)
          await session_a.commit()
          entry_id = entry.id

      # Query from Tenant B context — must return 0 rows
      async with async_session_factory() as session_b:
          await set_tenant_context(session_b, tenant_id=tenant_b.id)
          result = await session_b.execute(
              select(GLEntry).where(GLEntry.id == entry_id)
          )
          rows = result.scalars().all()
          assert len(rows) == 0, (
              f"RLS FAILURE: Tenant B can read Tenant A GL entry {entry_id}. "
              "Data isolation is broken."
          )

Use actual fixture names from existing integration tests.

FIX 4 — Document public route RLS assumption (#28):

STEP 9 — Read api/deps.py lines 97-108. Find get_async_session() and PUBLIC_ROUTE_PATHS.
STEP 10 — Add comment block:
  # PUBLIC ROUTE ASSUMPTION: Sessions for PUBLIC_ROUTE_PATHS have no RLS tenant context.
  # These sessions MUST NOT query financial tables without explicitly calling
  # set_tenant_context(session, tenant_id=...) first.
  # Violation results in empty result sets (not errors) — silent data access failure.

RULES:
- No schema or migration changes — documentation and test additions only for Fixes 2 and 4
- Integration test must run against test DB (localhost:5433, financeops_test)
- revoke_all_sessions must NOT issue a DELETE — verify the function body before calling it
```

---

*Wave 3 complete. Run `pytest --tb=short -q` before proceeding to Wave 4.*
