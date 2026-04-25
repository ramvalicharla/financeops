---
id: FU-006
title: Add useSession mock to OrgSwitcher unit tests
opened: 2026-04-25
related_to: Phase 0 test gate (pre-existing)
status: open
---

# FU-006 — Add useSession mock to OrgSwitcher unit tests

## Problem

`frontend/tests/unit/org_switcher.test.tsx` (and any other tests that render `OrgSwitcher`) fails because `OrgSwitcher.tsx` calls `useSession()` from `next-auth/react` but the test file does not mock it.

`useSession` returns `{ data: undefined, status: "loading" }` in a non-provider context, which causes the component to render in an indeterminate state. The test assertion (`expect(screen.getByText(/acme group/i)).toBeInTheDocument()`) then fails.

## Attribution

Pre-existing. `OrgSwitcher.tsx` imported `useSession` in commit `bc8b583` ("PHASE 4B"), which predates the `v4.1.0` tag. No Phase 0 sub-prompt touched `OrgSwitcher.tsx`.

## Fix

In the test file(s) that render `OrgSwitcher`, add:

```typescript
vi.mock("next-auth/react", () => ({
  useSession: () => ({
    data: { user: { name: "Finance Leader", email: "leader@acme.test", role: "finance_leader" } },
    status: "authenticated",
  }),
  signOut: vi.fn(),
}))
```

Verify all assertions in the file pass after adding the mock.

## Scope

- `frontend/tests/unit/org_switcher.test.tsx` — add mock
- Any other unit test file that renders `OrgSwitcher` directly
- Do NOT change `OrgSwitcher.tsx` component code

## Out of scope

Removing `useSession` from `OrgSwitcher.tsx` is a separate concern (see `FU-005` for legacy store cleanup).
