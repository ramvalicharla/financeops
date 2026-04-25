# FU-004 — Address pre-existing lint warnings

**Opened:** 2026-04-25
**Related to:** Phase 0 (entire phase reported "11 pre-existing warnings, unchanged")
**Status:** Open
**Priority:** Low — non-blocking
**Estimated effort:** 1–2 hours, one Claude Code session.

## Context

Throughout Phase 0 (sub-prompts 0.1 through 0.4), `npm run lint` consistently reported 11 pre-existing warnings that pre-date this work. They were not introduced by Phase 0 and are not blocking, but they remain unaddressed.

## What to do when picked up

1. Run `npm run lint` and capture the full warning output.
2. For each warning, decide one of:
   - Fix the underlying code (preferred for actionable warnings like `react-hooks/exhaustive-deps`)
   - Suppress with a code comment if the warning is a false positive (with justification)
   - Update lint config if the rule itself is overly strict
3. Goal: 0 warnings on `npm run lint`.

## Files to investigate (starting points)

Run `npm run lint` to get the file list. The 11 warnings are likely concentrated in 5–8 files based on prior session reporting.

## Acceptance criteria

- `npm run lint` returns 0 errors and 0 warnings on `main`
- No new lint suppressions added without justification
- Lint config (`.eslintrc*`) unchanged unless a rule is being deliberately relaxed with team agreement
