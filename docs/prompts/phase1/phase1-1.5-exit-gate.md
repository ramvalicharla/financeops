# Claude Code Prompt — Phase 1 Sub-Prompt 1.5: Phase 1 Exit Gate

> **Context:** 1.1, 1.2, 1.3, 1.4 all merged to main. Phase 1 visible deliverables are in. This sub-prompt is the exit gate: run the full test suite, verify no new regressions beyond the 5 known pre-existing failures (FU-007 onboarding text, FU-010 control-plane render harness), tag `v4.3.0-phase1-complete`, and decide whether to push.
>
> **Branch:** None — this is verification + tagging. No branch needed unless test failures require fixes.
>
> **Expected scope:** No code changes if tests pass with the known baseline. If new failures appear, STOP and surface for triage.
>
> **Do NOT push the tag without explicit instruction in the report.**

---

## Paste this into Claude Code

```
## Task: Phase 1 exit gate

## Pre-flight

git status                       # expect clean
git checkout main
git pull --ff-only
git log --oneline -5             # confirm 1.1, 1.2, 1.3, 1.4 merges all present
git tag --list "v4.*"            # confirm v4.2.0-phase0-complete is the latest

## Section A — Test infrastructure sanity check

Confirm test infra hasn't drifted since Phase 0:

cd frontend
test -f vitest.config.ts && echo "vitest config present" || echo "vitest config MISSING"
test -f playwright.config.ts && echo "playwright config present" || echo "playwright config MISSING"

# Test file count (Phase 0 baseline: 178 unit, 77 e2e)
echo "Unit test files: $(find . -type f \( -name "*.test.ts" -o -name "*.test.tsx" \) -not -path "*/node_modules/*" -not -path "*/.next/*" | wc -l)"
echo "E2E test files: $(find ./e2e -type f -name "*.spec.ts" 2>/dev/null | wc -l)"

Report counts. If they have CHANGED since Phase 0 (178 unit / 77 e2e), report
the delta — Phase 1 added some tests in 1.1 and 1.3, so unit count should be
slightly higher. If the count went DOWN, that's a regression — STOP and
investigate.

## Section B — Full unit test run

cd frontend
npm run test 2>&1 | tee /tmp/unit-test-output.log | tail -50

Report:
1. The verbatim "Test Files" + "Tests" summary lines from vitest
2. The list of FAILED test files (verbatim)
3. The list of FAILED test names (verbatim)

## Section C — Compare to known baseline

Phase 0 exit baseline failures (5 total):
- FU-007 onboarding wizard text mismatches (count: confirmed at Phase 0 exit)
- FU-010 control-plane test render harness (count: confirmed at Phase 0 exit)

For each FAILED test from Section B, classify:
- KNOWN — matches an existing FU-007 or FU-010 failure (test file path or
  test name matches the FU's recorded scope)
- NEW — does not match any known FU; this is a Phase 1 regression

If any tests are classified NEW, STOP and report:
- Which sub-prompt likely introduced the failure (1.1, 1.3 most likely)
- The test name, the failure message, the relevant component

Do NOT proceed to tagging if any NEW failures exist.

## Section D — E2E run (optional, time-permitting)

E2E is slow and Phase 0 baselined some failures here too (FU-008 e2e data
deps, FU-009 webkit binary). If you want to run E2E:

npm run test:e2e -- --project=chromium 2>&1 | tee /tmp/e2e-test-output.log | tail -50

Skip if it would block more than 15 minutes. E2E baseline can be re-confirmed
at any later point — it's not a hard exit gate.

## Section E — Build sanity

cd frontend
npm run typecheck
npm run lint 2>&1 | tail -5
npm run build 2>&1 | tail -20

Confirm: typecheck 0 errors, build clean, route count meets or exceeds
Phase 0 exit count.

## Section F — Tag (only if Sections B–C are clean)

If no NEW test failures and Section E is clean:

git tag -a v4.3.0-phase1-complete -m "Phase 1 — Shell skeleton complete

Sub-prompts merged:
- 1.1 Sidebar structural rebuild (220px, three nav groups, nav-config)
- 1.2 TopBar verification + landmark cleanup + FU-011, FU-012 filed
- 1.3 ModuleTabs 40px container + module icon registry
- 1.4 Route metadata sweep on remaining dashboard pages

User-visible changes:
- Sidebar shows Workspace / Org / Governance groups (collapsible)
- Sidebar width 220px; rail 52px; matches spec §1.3, §1.4
- TopBar 48px with FY chip
- Module tabs 40px with icon + label and 2px blue (#185FA5) underline
- All dashboard routes have distinct page titles in browser tab

Audit findings resolved this phase: #4, #11, #12, #20, #25
Risk #3 resolved (module icon registry).

Deferred to follow-ups: FU-011 (brand mark), FU-012 (sidebar behavioral
wiring — badges, RBAC filter, real routes).

Test baseline carried forward from Phase 0 exit:
- {N} known failures: FU-007 (onboarding), FU-010 (control-plane harness)
- 0 new failures introduced in Phase 1"

git tag --list "v4*"             # confirm tag now present
git log --oneline --graph -10 main

## Section G — Decision: push or hold

Phase 0 pushed at exit gate. Same option here. Two choices:
- Hold local until further direction (current Phase 0 default)
- Push main + tag

DO NOT PUSH automatically. Report tag created, await user instruction on
whether to `git push origin main` and `git push origin v4.3.0-phase1-complete`.

## Final report

1. Section A test infra counts (current vs Phase 0 baseline)
2. Section B test summary verbatim (Test Files / Tests lines)
3. Section C classification: KNOWN failures (count + list), NEW failures (count + list)
4. Section D E2E result if run, or "skipped"
5. Section E typecheck / lint / build verbatim
6. Section F tag created (verbatim git tag --list output)
7. Section G — confirm: did NOT push, awaiting user instruction
8. Phase 1 summary numbers:
   - Total commits between v4.2.0-phase0-complete and v4.3.0-phase1-complete
   - Total files changed (git diff v4.2.0-phase0-complete..v4.3.0-phase1-complete --stat | tail -1)
```

---

## After Claude Code reports done

Decide:
1. If NEW test failures: triage them. Phase 1 is not done until they're resolved.
2. If clean: review the summary, then choose whether to push immediately or wait.
3. Once pushed (or held), Phase 1 is officially closed. Move to Phase 2 planning — which depends on backend ticket BE-001 shipping.

Push commands (when ready):
```
git push origin main
git push origin v4.3.0-phase1-complete
```
