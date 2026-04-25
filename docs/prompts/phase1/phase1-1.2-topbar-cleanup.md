# Claude Code Prompt — Phase 1 Sub-Prompt 1.2: TopBar Verification + Landmark Cleanup + Follow-up Filing

> **Context:** 1.1 merged. Sidebar is 220px with three nav groups. This sub-prompt is the verification + cleanup pass for TopBar (most TopBar work was done by QW-3, QW-8) and a landmark sweep, plus filing FU-011 (brand mark) and FU-012 (sidebar behavioral wiring) so deferred work is tracked.
>
> **Branch:** create `feat/phase1-topbar-verify-cleanup` from `main`.
>
> **Expected scope:** Mostly verification, possibly 1–2 code changes if duplicate `<main>` landmarks are found, plus 2 new docs (FU-011, FU-012) and an update to `docs/follow-ups/INDEX.md`. ≤ 5 files.
>
> **Risk:** Low. Mostly reading and documenting.
>
> **Do NOT push. Do NOT merge.**

---

## Paste this into Claude Code

```
## Task: Sub-prompt 1.2 — TopBar verification, landmark cleanup, follow-up filing

## Pre-flight

git status
git checkout main
git pull --ff-only
git log --oneline -3                             # confirm 1.1 merge is at the top
git checkout -b feat/phase1-topbar-verify-cleanup

## Section A — TopBar verification (read only)

Read these files end-to-end:
- frontend/components/layout/Topbar.tsx
- frontend/app/(dashboard)/layout.tsx

Verify and report each of the following:

A1. Topbar height: Find the height class on both mobile (~ line 169) and desktop (~ line 299) topbar divs. Confirm both are `min-h-12` (48px). Quote the line.

A2. Fiscal year chip: Search Topbar.tsx for "FY". Confirm a chip rendering "FY YY-YY" is present, derived from active period in workspaceStore (post-Phase-0). Quote the JSX snippet.

A3. Brand mark: Search Topbar.tsx for any `<svg>` or brand-related className/text near the leftmost section. Report whether a Finqor brand mark/wordmark exists in the TopBar today (expected: NO — this is what FU-011 will track).

A4. Org switcher: Confirm OrgSwitcher.tsx is imported and rendered in Topbar.tsx. Confirm it currently still has the role gate (`platform_owner` / `super_admin`) — that gate is removed in Phase 2, not Phase 1.

A5. CommandPalette: Confirm CommandPalette is imported and rendered in Topbar.tsx (existence check only, not behavior).

A6. NotificationBell: Confirm NotificationBell is imported and rendered in Topbar.tsx (existence check only).

A7. User avatar / menu: Confirm a user avatar/dropdown is rendered.

If any of A1–A7 fail, STOP and report — these are quick-win deliverables that should already be in place.

## Section B — Duplicate <main> landmark check

This is audit residual work flagged in finding #25 / a11y sweep.

Run these checks and report verbatim:

# Find every <main> tag in pages and layouts
grep -rn "<main" frontend/app/ frontend/components/ 2>/dev/null | grep -v node_modules

# Specifically look in:
#   frontend/app/(dashboard)/layout.tsx
#   frontend/app/(auth)/layout.tsx
#   any page-level <main> usage

For each `<main>` occurrence found:
- File and line
- Whether it's in a layout or a page

Required state per WCAG / spec §1.8: exactly one `<main>` landmark per rendered page.

If a page has its own `<main>` AND its layout also wraps content in `<main>`, that page renders two `<main>` elements. Report each such case.

If you find duplicates:
- Remove the page-level `<main>` (the layout's `<main>` is the authoritative landmark)
- Replace with `<div>` or appropriate semantic element
- Note each fix in the Section B output

If you find none, report "no duplicates" and move on.

## Section C — File FU-011 (brand mark)

Create file: docs/follow-ups/FU-011-topbar-brand-mark.md

Content:

```markdown
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
```

## Section D — File FU-012 (sidebar behavioral wiring)

Create file: docs/follow-ups/FU-012-sidebar-behavioral-wiring.md

Content:

```markdown
# FU-012 — Sidebar behavioral wiring (badges, RBAC filter, real routes)

**Opened:** 2026-04-25
**Related to:** Phase 1 sub-prompt 1.1 (deferred behavioral concerns)
**Spec ref:** finqor-shell-audit-2026-04-24.md §1.3 items 3–4; findings #4, #28

## Background

Phase 1 sub-prompt 1.1 rebuilt the sidebar's structure (three groups, 220px,
12 items via nav-config.ts). The behavioral wiring was deliberately deferred
to keep the PR reviewable. Audit task list for Phase 1 included these
behavioral concerns; user direction was to ship structure first and capture
behavior as a follow-up.

## Scope (3 independent tracks; can be split into separate PRs)

### Track 1 — Approvals badge

- Wire the Approvals nav item's `badge.count` to a live endpoint. Likely
  `GET /api/v1/approvals?status=pending&limit=0` (count-only).
- Use TanStack Query with `queryKeys.workspace.approvalsCount(orgId)` (extend
  the query-key factory; this domain doesn't exist yet).
- Polling interval: 60s, or driven by SSE / WebSocket if those exist.
- Tone: warning when count > 0, none when count = 0.

Acceptance: open sidebar with pending approvals → badge shows count;
mark approval as resolved → badge updates within polling interval.

### Track 2 — RBAC filter at the item level

- Extend `NavItem` in nav-config.ts with optional `requiredPermission?: string`
  and `requiredRole?: string[]`.
- Update `filterNavigationItems()` (or its replacement) to filter items within
  groups based on the user's permissions and role.
- Audit trail item under Governance must be visible to `auditor` role
  (resolves audit finding #28).
- Modules item under Org must be gated on `module.manage` permission once
  that permission exists in backend (Phase 3 prerequisite).

Acceptance: log in as `auditor` → sees Audit trail; log in as `finance_team` →
no `+` button on tabs (separate concern, but RBAC plumbing shared); log in as
`viewer` → governance group only shows allowed items.

### Track 3 — Real routes for placeholder items

Today's placeholder hrefs (all → `/dashboard`):
- Today's focus
- Period close
- Approvals
- Possibly others (audit which routes were placeholdered in 1.1's report)

For each:
- Backend: confirm endpoint and route exists or file backend ticket.
- Frontend: create the page under `frontend/app/(dashboard)/{route}/page.tsx`.
- Update nav-config.ts to point at the real href; remove the
  `// TODO Phase 2` comment.

Acceptance: clicking each item navigates to the real page (not /dashboard).

## Dependencies

- Track 1 depends on backend confirming approvals endpoint shape.
- Track 2 depends on Phase 3 backend ticket `feat(rbac): add module.manage
  permission` and on existing role/permission data already on the JWT.
- Track 3 may overlap with Phase 2 (Today's focus and Period close are both
  natural Phase 2 surfaces).

## Out of scope

- Group collapse state persistence (separate concern; will be folded into the
  Phase 4 collapsed-rail server preferences work).
- Entity card behavior (Phase 2, finding #3).
- Entity tree (Phase 2, finding #7).
```

## Section E — Update follow-ups index

Modify `docs/follow-ups/INDEX.md`. Add two rows to the open follow-ups table,
in the format used for FU-001 through FU-010:

| FU-011 | [TopBar Finqor brand mark + wordmark](./FU-011-topbar-brand-mark.md) | 2026-04-25 | Phase 1 sub-prompt 1.2 |
| FU-012 | [Sidebar behavioral wiring (badges, RBAC, real routes)](./FU-012-sidebar-behavioral-wiring.md) | 2026-04-25 | Phase 1 sub-prompt 1.1 |

## Step F — Verify

cd frontend
npm run typecheck                # 0 errors
npm run lint 2>&1 | tail -5      # 0 NEW errors
npm run build 2>&1 | tail -20    # clean build

Report verbatim outputs.

## Step G — Commit

git add -A
git status                        # confirm only intended files

Expected diff:
- frontend/components/layout/Topbar.tsx (possibly modified — only if Section B found a duplicate <main>)
- frontend/app/(dashboard)/layout.tsx (possibly modified)
- frontend/app/.../page.tsx (possibly modified, only if duplicate <main> found there)
- docs/follow-ups/FU-011-topbar-brand-mark.md (new)
- docs/follow-ups/FU-012-sidebar-behavioral-wiring.md (new)
- docs/follow-ups/INDEX.md (modified)

If anything else appears in the diff, STOP and report.

If Section B found and fixed duplicate landmarks:
git commit -m "chore(shell): phase 1.2 — topbar verify, landmark cleanup, follow-up filing

Section A: TopBar verification — height (48px), FY chip, OrgSwitcher,
CommandPalette, NotificationBell, user avatar all confirmed in place.

Section B: Duplicate <main> landmark cleanup — fixed in {N} pages
(see commit body for list).

Sections C–E: FU-011 (brand mark deferred from Phase 1) and FU-012
(sidebar behavioral wiring deferred from 1.1) filed.

Resolves audit findings: #25 (residual ~9 page metadata is sub-prompt 1.4
scope, not 1.2)
No regression to test count or build."

If Section B found NO duplicates:
git commit -m "docs(shell): phase 1.2 — topbar verified, follow-ups FU-011 + FU-012 filed

Section A: TopBar verification — height (48px), FY chip, OrgSwitcher,
CommandPalette, NotificationBell, user avatar all confirmed in place;
no code changes needed.

Section B: Landmark sweep — no duplicate <main> elements found.

Sections C–E: FU-011 (brand mark) and FU-012 (sidebar behavioral wiring)
filed; INDEX updated.

No code changes; documentation and verification only."

## Final report

1. Section A: A1–A7 results (verbatim line quotes for each)
2. Section B: every <main> occurrence found, with file/line; whether duplicates were fixed
3. Section C, D, E: confirm files created and INDEX updated
4. typecheck / lint / build verbatim
5. Files changed (git diff main --stat)
6. Commit hash
7. Confirm: did NOT push, did NOT merge
```

---

## After Claude Code reports done

Review the Section A results. If any item is missing (i.e., a quick win regressed), pause Phase 1 and investigate. Otherwise run `phase1-1.2-merge.md`.
