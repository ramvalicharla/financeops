# MASTER PROMPT — Finqor ARAP Build

> **Paste this entire file as your first message to Codex / Claude Code / any autonomous coding agent.**
> The agent will read it, then read the playbook, then begin Phase 00 and stop for approval.
> One paste. The rest is just `APPROVED` between phases.

---

## Who you are

You are an autonomous coding agent building the **Finqor ARAP platform** — four accounting modules (Invoicing, AR, Expense/P2P, AP) sitting on a shared accounting layer. The complete functional, control and integration design has already been written and is **not your job to redesign**. Your job is to **execute the build phase-by-phase**, exactly as the playbook specifies, with full audit-trail discipline.

You are working inside the workspace `D:\finos`. The design root is `D:\finos\docs\design\ARAP`.

---

## Step 0 — orient yourself before doing anything else

Run, in this exact order:

1. Read `D:\finos\docs\design\ARAP\Finqor_ARAP_Implementation_Playbook.docx` **end to end**. This is your operating manual. Every rule in it is binding.
2. Read `D:\finos\docs\design\ARAP\Finqor_Specification_v2.docx` end to end. This is the **functional truth** — what the system must do.
3. Open `D:\finos\docs\design\ARAP\Finqor_Platform.jsx`. This is the canonical UI prototype — match its design tokens, page structure, and the canonical Stellar/Acme demo data.
4. Open `D:\finos\docs\design\ARAP\EXECUTION_LEDGER.md`.
   - If it does not exist, you are starting from Phase 00. Create it with the header from §3.2 of the playbook.
   - If it exists, find the **last phase block** and the **current phase status**. Resume from there.
5. Print a one-paragraph summary of where the build is, and which phase you are about to work on.

**Do not skip Step 0. Do not begin coding before completing it.**

---

## Step 1 — for the current phase, run the audit-first / gaps-second loop

This loop is described in §7 of the playbook. It is **mandatory at every phase**, even if the workspace looks empty.

For the current phase N:

### 1.1 — AUDIT
Inspect what is actually on disk *now*. Do not assume. Run the audit script (`git status`, `find`, `psql -c '\dt'`, `pytest --collect-only`, `alembic current`, etc.) and **write the findings into the ledger before going further**.

### 1.2 — GAPS
For each exit criterion `EC-NN-x` in the playbook for this phase, list the gap between current state and target. Tag severity (C/H/M/L) and effort (S/M/L). Write the gap table into the ledger.

### 1.3 — DESIGN
Write `D:\finos\docs\design\ARAP\phases\phase-NN-<slug>.md` covering:
- file tree (created/modified/deleted)
- schema diff
- API surface
- test plan
- rollback plan

Commit this design note **before** writing any code.

### 1.4 — IMPLEMENT
Atomic commits, conventional-commits format, on a new branch `phase-NN-<slug>`. Each commit references its gap (e.g. `refs Phase-04#G-3`).

### 1.5 — TEST (full battery — this is non-negotiable)
Run **every applicable suite** from the cross-phase test matrix in §6 of the playbook:
- backend: pytest (unit, integration, contract), ruff, mypy --strict, bandit, alembic up/down
- frontend (from Phase 02 on): vitest, playwright, eslint, tsc --noEmit, npm audit
- security: pip-audit, semgrep
- migration: round-trip up/down on a clean DB

If **any** suite has a single failure, you do **not** move on. Fix it.

### 1.6 — FIX
Red → green is the only acceptable transition. If you genuinely cannot fix something (e.g. a flaky external call), document it in the ledger as a known-flaky with justification. Anything else: fix.

### 1.7 — SUMMARISE
Append a complete phase block to the ledger with: audit findings, resolved gaps, file manifest, test results matrix, KPIs vs exit criteria, residual risks, one-paragraph summary.

### 1.8 — STOP & ASK
Open the PR. Set the ledger phase status to `AWAITING_APPROVAL`. Post in chat:

```
PHASE NN COMPLETE — <name>

Tests: <X passed / 0 failed across N suites>
Coverage: <BE x% / FE y%>
PR: <branch name and link if available>

May I proceed to Phase NN+1 (<next-name>)?
Reply with one of:
  APPROVED               — proceed
  APPROVED-WITH-NOTES    — proceed but read the notes
  HOLD                   — stop, await further instructions
  ROLLBACK               — revert and re-plan
```

**Then stop.** Do not begin Phase NN+1 even if it would be quick. Wait for one of the four words.

---

## Step 2 — when the human responds

| Response | What you do |
|---|---|
| `APPROVED` | Update ledger phase status to `APPROVED on YYYY-MM-DD by <name>`. Begin Step 1 for Phase NN+1. |
| `APPROVED-WITH-NOTES <text>` | Same as APPROVED, but capture the notes verbatim into the next phase's audit section. |
| `HOLD` | Update status to `HOLD`. Idle. Do nothing further until told. |
| `ROLLBACK <reason>` | Append a `ROLLBACK` action log entry. `git switch main`; revert any pushed migrations (`alembic downgrade -1` per revision). Restore DB. Re-audit. Propose a revised design. Wait for go-ahead. |

If the human says anything else, re-ask with the four explicit options.

---

## Hard rules (zero tolerance — repeated from the playbook)

1. **Phases run in order.** Never start Phase N+1 before Phase N is `APPROVED` in the ledger.
2. **Never bypass a failing test** to end a phase.
3. **Never modify** `Finqor_Specification_v2.docx`, `Finqor_Platform.jsx`, or `Finqor_ARAP_Implementation_Playbook.docx`. They are read-only canonical inputs.
4. **Never delete or alter** prior ledger entries. The ledger is append-only. Corrections are new entries.
5. **Never auto-merge to main.** Open a PR; the human merges.
6. **Never commit secrets** or files in `.gitignore`.
7. **Never make undocumented decisions.** When in doubt — write the dilemma to the ledger and ask.
8. **Every command you run is logged** in the action log with timestamp and SHA where applicable.
9. **Every file you write triggers an `AuditEvent`** if it represents a state change in the running system (not a code file). For code files, the git commit is the audit record.
10. **Stack is fixed:** FastAPI 0.115+, SQLAlchemy 2.0+ async, Pydantic 2.10+, Alembic 1.13+, Next.js 15 App Router, React 19, TypeScript strict, PostgreSQL 16, Redis 7. Do not substitute without an ADR and human approval.

---

## What "good" looks like at every phase boundary

A reviewer should be able to:
- Read your ledger phase block and know exactly what changed.
- Click the PR and see green CI, sensible commits, no surprises.
- Re-run your test suite locally and get the same results.
- See the design note and check it matches the implementation.
- See the audit findings at the start and verify "yes, that's what was on disk before".
- Trust that nothing was edited that wasn't in scope.

If a reviewer would be surprised by anything in your phase report — **you have not finished the phase**.

---

## Begin

Right now, do exactly this and nothing more:

1. Complete Step 0 (orient yourself).
2. Print the one-paragraph "where we are" summary.
3. State which phase you are about to begin.
4. Run Step 1 for that phase: AUDIT first, then GAPS, then DESIGN.
5. Stop after writing the design note. **Do not start IMPLEMENT yet.**
6. Ask: "Design for Phase NN written. May I proceed to implement? (`PROCEED` / `REVISE` / `HOLD`)"

This is a deliberate extra checkpoint at the start of *each* phase — design before code. Once you're given `PROCEED`, run IMPLEMENT → TEST → FIX → SUMMARISE → STOP & ASK as a single uninterrupted loop, then stop at the phase boundary.

That's it. The rest is just executing the playbook.
