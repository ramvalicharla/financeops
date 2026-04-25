# FU-011 — TopBar Finqor brand mark + wordmark

**Opened:** 2026-04-25
**Related to:** Phase 1 sub-prompt 1.2 (deferred from Phase 1 scope by user direction)
**Spec ref:** finqor-shell-audit-2026-04-24.md §1.2 item 1; finding #15 (Major)

## Background

Phase 1 sub-prompt 1.2 verified that the TopBar currently has no Finqor brand
mark or wordmark in its leftmost position. Audit finding #15 calls this out as
a Major gap against spec §1.2 item 1 ("Finqor brand mark + wordmark" is the
first item in the TopBar).

User direction during Phase 1 planning: skip the brand mark in Phase 1 in favor
of shipping 220px sidebar + 48px topbar + tab fixes first; defer the brand mark
to a polish PR.

## Scope

1. Source or commission a Finqor SVG brand mark + wordmark.
   - Working visual reference from prior design mockups: rounded square in
     `#185FA5` with "F" inside + "finqor" wordmark in tertiary text colour.
   - This reference is a placeholder — the real brand asset may differ.
2. Add the brand mark as the leftmost element of `Topbar.tsx`.
3. The brand mark links to `/dashboard` (workspace home).
4. The brand mark must scale appropriately at the 48px topbar height.
5. Add an `aria-label="Finqor"` for screen readers if the wordmark is not
   reproduced as text.

## Acceptance criteria

- Brand mark visible in TopBar on every authenticated page.
- Click navigates to `/dashboard`.
- WCAG: keyboard focusable, accessible name "Finqor".
- Visual matches the supplied brand asset (not the placeholder).
- No regression to TopBar height (must remain 48px).

## Out of scope

- Brand mark in auth pages (separate concern; auth pages have their own layout).
- Brand mark in collapsed-rail sidebar header (rail uses entity chip per spec
  §1.4 — not a brand mark slot).
