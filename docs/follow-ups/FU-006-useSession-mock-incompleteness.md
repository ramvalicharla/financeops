---
id: FU-006
title: Add useSession mock to OrgSwitcher unit tests
opened: 2026-04-25
related_to: Phase 0 test gate (pre-existing)
status: closed
closed: 2026-04-26
resolution: resolved
---

---
**Status:** Closed 2026-04-26
**Resolution:** Resolved by SP-2A
**Reasoning:** OrgSwitcher.tsx was completely rewritten in SP-2A
(`fffc242` merged via `3a972f7`). The component no longer imports
`useSession` from `next-auth/react`. The original failing test file
(`frontend/tests/unit/org_switcher.test.tsx`) no longer exists in main.
The mock incompleteness issue documented in this FU is moot.

If unit tests for the rewritten OrgSwitcher are wanted, open a new FU
scoped to "Add unit tests for rewritten OrgSwitcher (useTenantStore /
listUserSwitchableOrgs mocking)". That is out of scope for this FU.
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
