# FU-019 — control_plane_*.test.tsx Pre-Existing Failures

**Status:** Open
**Filed:** 2026-04-26
**Source:** Phase 2 close — Step 11.5 useSearchParams fix surfaced hidden failures
**Severity:** Low (test infra; not user-visible)

## Summary

After fixing the Phase 2 regression in Step 11.5 (adding useSearchParams
to next/navigation vi.mock in 3 control_plane test files), three
pre-existing failures became visible. They were masked the whole time
by the useSearchParams undefined error firing first during component
import.

These are NOT Phase 2 regressions. They existed before Phase 2 started
and were misreported as "5 pre-existing failures" in pre-Phase-2 close
when the actual underlying breakage was different.

## The 3 pre-existing failures

1. control_plane_panels.test.tsx > "opens the job panel from the top
   bar and renders failed jobs" — Error: Tooltip must be used within
   TooltipProvider. The render harness needs to wrap the test with
   TooltipProvider.

2. control_plane_shell.test.tsx > "renders shell context from
   backend-confirmed organization, entity, module, and period" — same
   TooltipProvider error.

3. control_plane_state.test.tsx > "keeps module visibility dependent
   on backend context" — TestingLibraryElementError: Unable to find
   element with text /waiting for backend module context/i. Either the
   assertion is stale (component no longer renders this string) or the
   component behavior diverged. Needs investigation.

## Recommended fix scope

Test infra only, no production code changes:

- Items 1 and 2: wrap the affected test renders with TooltipProvider.
  Likely a 5-line shared test helper or per-test wrap. ~30 minutes.
- Item 3: read the test assertion against the current component
  behavior. Either update the assertion to match current behavior, or
  if the behavior is genuinely wrong, surface that as a separate
  finding. ~30-60 minutes.

## When to fix

Phase 3 polish window or any small open slot. Not blocking any phase.

## Cross-references

- Step 11.5 fix that unmasked these: commit 2571887 (merged at 9d40d56)
- Pre-Phase-2 close handoff misreported these as "5 pre-existing
  failures" when the symptom was useSearchParams (now fixed) rather
  than the underlying issues
- Onboarding wizard's 2 separate pre-existing failures (also reported
  in pre-Phase-2 close) are unrelated and remain open

---

## Resolution

**Closed:** SP-5E (Phase 5), 2026-04-27

All 3 documented failures verified passing on current `main` at SP-5E baseline (7/7 tests across `control_plane_panels.test.tsx`, `control_plane_shell.test.tsx`, `control_plane_state.test.tsx`). The fix landed silently between Phase 2 close (2026-04-26) and Phase 5 entry; the exact phase is not traceable from FU history but evidence-of-fix is the current green run. No further action required.
