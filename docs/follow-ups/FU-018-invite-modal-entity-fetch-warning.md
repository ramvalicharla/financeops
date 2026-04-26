---
name: Invite modal — soft warning when entity fetch fails
description: Invite modal silently omits entity assignment when listOrgEntities() fails; should show a visible warning + retry so the inviter knows scope will be empty
type: project
---

# FU-018 — Invite modal: soft warning when entity fetch fails

**Opened:** 2026-04-26
**Related to:** FU-016 implementation (commit b368ac2)
**Estimate:** ~30 minutes (frontend-only)
**Priority:** Low — polish, does not block functionality

## Background

During FU-016 implementation of the Users tab on /settings/team, the invite
modal includes an optional entity assignment field. The entities list is
fetched from `/api/v1/org-setup/entities` via the existing `listOrgEntities()`
helper.

If the entity fetch fails (network error, backend error, slow response that
times out), the current behavior is to silently omit the entity section from
the modal. The user can still submit the invite, and the backend defaults
`entity_ids` to `[]`.

This is functionally safe — the backend default is correct and the invited
user still gets created. But a silent omission means the inviter doesn't know
that entity assignment was unavailable, and may submit with the expectation
that entity scope was set.

The silent omission was a documented judgment call in the FU-016 commit
message body ("non-fatal — matches the optional nature of `entity_ids: []`").
FU-018 upgrades it to a visible warning without changing the functional
fallback.

## Scope

When the entity fetch fails inside `InviteUserModal`:

1. The entity section is still rendered (not silently removed)
2. A soft in-modal warning replaces the entity selector — e.g.:
   *"Couldn't load entities. The user will be created without entity scope.
   You can assign entities later."*
3. A retry button next to the warning re-attempts the fetch without dismissing
   the modal
4. The submit button stays enabled (the invite is still allowed without entity
   scope)

Happy path (fetch succeeds) is unchanged — no warning is shown.

## Acceptance criteria

- [ ] Entity fetch failure in `InviteUserModal` shows a visible in-modal
      warning, not a silent omission
- [ ] Warning text clearly states what will happen on submit (no entity
      scope assigned; can be added later)
- [ ] Retry button re-fetches without dismissing or resetting the modal form
- [ ] Existing happy-path UX unchanged when fetch succeeds
- [ ] Existing fallback to empty `entity_ids: []` preserved on submit
- [ ] No new test failures

## Implementation notes

- Frontend-only change in
  `frontend/app/(dashboard)/settings/team/_components/UsersPanel.tsx`
- Backend behavior unchanged
- Sonner toast is too transient for this — needs a persistent in-modal
  indicator; match any existing inline error/warning banner pattern in the
  codebase
- TanStack Query's `isError`, `error`, and `refetch` from the
  `listOrgEntities()` call are already available — wire them to the warning
  UI rather than reaching outside the existing query state

## Closure

**Status:** Merged
**Branch:** `feat/sp-2f-fu018-invite-modal` (commit `47654df`)
**Merge commit:** `b0161e5` into `main` (2026-04-26)
**Sub-prompt:** SP-2F

All acceptance criteria met. Raw amber div used (no shared Alert component exists in
the team settings directory). Happy path and submit fallback unchanged. Build,
typecheck, and lint passed clean before and after merge.

## Out of scope

- Backend changes (entity endpoint, `entity_ids` defaulting) — already correct
- Any change to the happy path or the submit flow
- Styling beyond matching the existing in-modal pattern
