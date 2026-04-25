---
id: FU-010
title: Control-plane test render harness incomplete
opened: 2026-04-25
related_to: Pre-existing test infrastructure (unmasked while resolving FU-006)
status: open
priority: medium
estimated_effort: 30–60 minutes
---

# FU-010 — Control-plane test render harness incomplete

**Opened:** 2026-04-25
**Related to:** Pre-existing test infrastructure (unmasked while resolving FU-006)
**Status:** Open
**Priority:** Medium — blocks 2 unit tests; affects confidence in shell-level rendering coverage
**Estimated effort:** 30–60 minutes, single Claude Code session

## Context

Two unit tests in the control-plane suite render `Topbar` and `Sidebar` components, which over time have accumulated dependencies on:

- `<TooltipProvider>` from Radix (required ancestor for `<Tooltip>`)
- `useSearchParams` from `next/navigation`
- `useSession` from `next-auth/react` (resolved in FU-006)
- Possibly other contexts/hooks not yet identified (only revealed by running)

The current test render helper (`renderWithQueryClient` or equivalent) only wraps in `QueryClientProvider`. As the rendered components have grown, the wrapper has not kept pace.

## Affected tests

- `tests/unit/control_plane_shell.test.tsx` > "renders shell context from backend-confirmed organization, entity, module, and period"
- `tests/unit/control_plane_panels.test.tsx` > "opens the job panel from the top bar and renders failed jobs"

Current errors after FU-006 useSession fix:

```
Error: `Tooltip` must be used within `TooltipProvider`
Error: [vitest] No "useSearchParams" export is defined on the "next/navigation" mock.
```

## Why a focused session

When FU-006 was patched, fixing the useSession crash unmasked these two additional errors. Patching the unmasked errors might unmask more. The right fix is a render-harness audit:

1. Read `Topbar.tsx` and `Sidebar.tsx` in full to enumerate every external dependency:
   - All hooks called (`useSession`, `useSearchParams`, etc.)
   - All providers required by rendered children (TooltipProvider, ThemeProvider, etc.)
   - Any Next.js utilities (`useParams`, `usePathname`, `useRouter`, etc.)
2. Build a shared `renderControlPlaneShell` helper in `frontend/tests/test-utils/` (or wherever test utilities live) that wraps in all required providers and provides all required mocks.
3. Update both affected tests to use the helper.
4. Run the full unit suite to confirm 175 passing.

## Acceptance criteria

- Both affected tests pass
- Render harness is centralized so future Topbar/Sidebar dependencies are easy to add to one place
- `npm test -- --run` shows 0 failures from FU-010 root cause
- No new failures introduced in other tests

## Files to touch (starting points)

- `frontend/tests/unit/control_plane_panels.test.tsx`
- `frontend/tests/unit/control_plane_shell.test.tsx`
- `frontend/components/layout/Topbar.tsx` (read only)
- `frontend/components/layout/Sidebar.tsx` (read only)
- New shared test utility (location TBD based on existing conventions)

## Related follow-ups

- FU-006 (resolved partially — useSession mock added)
- FU-007 (onboarding wizard text mismatches — separate issue)
