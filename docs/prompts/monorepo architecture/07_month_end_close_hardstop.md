# PROMPT 07 — MONTH-END CLOSE HARD-STOP ON STEP FAILURE

**Sprint:** 3 (Finance Correctness)
**Audit findings closed:** #29
**Risk level:** MEDIUM
**Estimated effort:** S-M (3-5 days)
**Prerequisite:** Prompts 01-06 complete

---

## CONTEXT

Repo root: `D:\finos`
Target files:
- `D:\finos\backend\financeops\workflows\month_end_close\workflow.py` (around lines 63, 109)
- Related: activity definitions, status models, notification logic

The audit found that the month-end close workflow continues after step failures and returns partial status. **For a finance platform, a partial close is worse than a failed close** — customers will believe their books are closed when they aren't. This must be a hard stop.

I'm explicitly promoting this finding from Codex's HIGH to CRITICAL-equivalent because the failure mode is silent financial misstatement. Other workflows can be retried; close cannot be retried after partial application.

---

## SCOPE — DO EXACTLY THIS

### Step 1 — Map the close workflow
1. Open `D:\finos\backend\financeops\workflows\month_end_close\workflow.py`
2. List every step (activity) the workflow executes, in order
3. For each step, document:
   - What it does (e.g., `accrual_calculation`, `revaluation`, `inventory_close`, `journal_posting`, `period_lock`)
   - What state it modifies (DB tables, audit trail entries)
   - Is it idempotent?
   - Is it reversible?
   - What happens currently when it fails?

### Step 2 — Classify failure modes
For each step, classify the failure:
- `RECOVERABLE` — transient (network blip, lock contention) → retry within workflow
- `HALT_SAFE` — workflow should stop, no rollback needed (state is consistent)
- `HALT_REQUIRES_ROLLBACK` — workflow stopped but partial state must be reverted
- `UNRECOVERABLE` — manual intervention required, no automated recovery possible

This classification drives the fix strategy.

### Step 3 — Design the hard-stop logic
Output a plan covering:
1. **Atomic phases** — group steps into phases where each phase is all-or-nothing. Define rollback for each phase.
2. **Status model** — replace any "partial success" status with explicit states: `PENDING`, `IN_PROGRESS`, `STEP_FAILED_HALTED`, `ROLLED_BACK`, `COMPLETE`. No `PARTIAL_COMPLETE` state.
3. **Period lock atomicity** — period must transition from `OPEN` → `CLOSING` → `CLOSED` only after the full workflow succeeds. If workflow halts, period stays `CLOSING` and requires manual unlock by an authorized role.
4. **Customer-visible status** — UI must show "Close in progress" / "Close failed — manual review required" / "Closed". Never "Partially closed".
5. **Notification policy** — close failure must page on-call (or, for self-service tier, alert the customer admin) immediately.

**STOP here. Output the plan with the step classification table. Wait for user confirmation.**

### Step 4 — Apply the fix
After confirmation:
1. Refactor `workflow.py`:
   - Each step wrapped in error handling that halts on failure
   - No `try/except` that swallows errors and continues
   - Use Temporal's `ApplicationError` (non-retryable) for halt cases
   - Use Temporal's retry policy ONLY for `RECOVERABLE` failures
2. Update the close status model — add the new states, deprecate `PARTIAL_COMPLETE` if it exists
3. Implement period lock state machine in `D:\finos\backend\financeops\modules\<close_module>\period_lock.py`
4. Add the failure notification activity
5. Update the close API endpoint to expose the explicit status

### Step 5 — Tests (this section is non-negotiable for this prompt)
Create `D:\finos\backend\tests\test_month_end_close_workflow.py`:
- `test_close_completes_when_all_steps_succeed`
- `test_close_halts_on_first_step_failure` — period stays CLOSING, no partial entries
- `test_close_halts_on_middle_step_failure` — earlier steps' state preserved or rolled back per classification
- `test_close_halts_on_last_step_failure` — even at the period_lock step, must halt cleanly
- `test_close_failure_triggers_notification`
- `test_period_lock_requires_manual_unlock_after_halt`
- `test_close_status_never_returns_partial_complete`
- `test_close_retry_only_works_after_manual_unlock` — prevents accidental re-runs

### Step 6 — Document the operational runbook
Create `D:\finos\docs\runbooks\MONTH_END_CLOSE_FAILURE.md`:
- What to do when close halts mid-workflow
- How to verify state consistency (which queries to run)
- How to manually unlock a period
- How to re-run a close after halt
- Escalation contacts

---

## DO NOT DO

- Do NOT introduce `PARTIAL_COMPLETE` or `PARTIALLY_CLOSED` states under any name
- Do NOT add a "skip failed step and continue" option
- Do NOT silently retry forever — bound retries explicitly
- Do NOT modify the chart of accounts or journal entry models in this prompt
- Do NOT touch other workflows (year-end, quarter-end) — they're separate prompts

---

## VERIFICATION CHECKLIST

- [ ] Close workflow halts on any step failure
- [ ] No status value implies "partial close"
- [ ] Period lock state machine prevents premature close
- [ ] All 8 test cases pass
- [ ] Failure notifications fire (verify in test with mocked notification activity)
- [ ] Runbook exists at `docs/runbooks/MONTH_END_CLOSE_FAILURE.md`
- [ ] Existing close-related tests still pass

---

## ROLLBACK PLAN

If a customer's close is in flight when this is deployed:
1. Wait for in-flight closes to complete OR halt them via existing mechanism BEFORE deploy
2. Coordinate deploy timing — month-end is a bad week to deploy this
3. Recommended deploy window: mid-month (15th-20th of any month)

---

## COMMIT MESSAGE

```
fix(finance): month-end close halts on step failure, no partial state

- Workflow now halts on any non-recoverable step failure
- New status model: PENDING, IN_PROGRESS, STEP_FAILED_HALTED, ROLLED_BACK, COMPLETE
- Period lock state machine: OPEN -> CLOSING -> CLOSED (no intermediate close)
- Failure notification activity fires immediately
- Operational runbook added

Closes audit finding #29.
Prevents silent partial close — books either close fully or not at all.
```
