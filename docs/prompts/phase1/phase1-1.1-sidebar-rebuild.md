# Claude Code Prompt — Phase 1 Sub-Prompt 1.1: Sidebar Structural Rebuild

> **Context:** Phase 0 complete (`v4.2.0-phase0-complete`, main HEAD `fa3a89a`). Phase 1 begins.
> This sub-prompt rebuilds the sidebar's structure to match the locked spec in `docs/audits/finqor-shell-audit-2026-04-24.md` §1.3 — width 220px, collapsed rail 52px, three nav groups (Workspace / Org / Governance) with collapsible chevron headers.
>
> **Branch:** create `feat/phase1-sidebar-structure` from `main`.
>
> **Expected scope:** ~5 files. Single commit unless Claude Code finds a concrete reason to split (e.g., the nav-config file ends up large enough to warrant a separate commit — fine, but call it out explicitly).
>
> **Risk:** Medium. The sidebar is a heavily-used component. Risk is that nav items present today get accidentally dropped from the rebuild, breaking navigation for some user role.
>
> **Do NOT push. Do NOT merge.** Stop after typecheck + lint + build pass and report back. Merge runs as a separate prompt.

---

## What this sub-prompt does NOT do

These are deliberately deferred to keep this PR reviewable. Do not implement any of them in 1.1:

1. Real RBAC filtering of nav items by role (today's behavior of `filterNavigationItems()` is preserved as-is).
2. Real badge counts on Approvals (placeholder static `0` or no badge — wire to a real endpoint in Phase 2).
3. Real routes for Today's focus / Period close / Approvals — these point to `/dashboard` placeholders for now with a `// TODO Phase 2:` comment.
4. Entity card dropdown / picker behavior — entity card stays read-only as it is today (Finding #3 is Phase 2 work).
5. Entity tree below the entity card (Finding #7) — Phase 2.
6. Entity indicator chip in collapsed rail (Finding #13) — Phase 2.
7. Brand mark in TopBar — separate sub-prompt (1.2) and FU-011.

If any of these get pulled into the diff during implementation, **STOP and report the deviation** — do not silently expand scope.

---

## Paste this into Claude Code

```
## Task: Sub-prompt 1.1 — Sidebar structural rebuild (220px + three nav groups)

## Pre-flight

git status                                   # expect clean
git checkout main
git pull --ff-only
git log --oneline -1                         # expect fa3a89a or later (post-Phase-0)
git checkout -b feat/phase1-sidebar-structure

## Step 1 — Read current state

View these files end-to-end before changing anything:
- frontend/components/layout/Sidebar.tsx
- frontend/components/layout/_components/SidebarNavItem.tsx
- frontend/lib/ui-access.ts (look for filterNavigationItems and the existing nav config it consumes)

Report back BEFORE editing:
1. Current sidebar width class (the audit said `w-60` at line 221 — verify exact line and class name)
2. Current collapsed rail class (audit said `md:w-14` — verify)
3. Current grouping: list every group label and its items as they exist today
4. Whether any of the existing groups already match Workspace / Org / Governance, even partially
5. Where filterNavigationItems is defined and what shape of input it expects

Do NOT proceed past Step 1 until you have confirmed these five things.

## Step 2 — Create nav-config file

Path: frontend/components/layout/sidebar/nav-config.ts

This file is the single source of truth for the three nav groups. The Sidebar component imports from it.

Required exports:

```ts
import type { LucideIcon } from "lucide-react"
import {
  LayoutDashboard,
  Target,
  CalendarCheck,
  CheckSquare,
  Building2,
  Settings,
  Plug,
  LayoutGrid,
  CreditCard,
  ScrollText,
  Users,
  ShieldCheck,
} from "lucide-react"

export type NavGroupId = "workspace" | "org" | "governance"

export interface NavItem {
  id: string
  label: string
  href: string
  icon: LucideIcon
  badge?: { count: number; tone: "info" | "warning" | "danger" } | null
  // Phase 2/3 will add: requiredPermission?: string; requiredRole?: string[]
}

export interface NavGroup {
  id: NavGroupId
  label: string
  items: NavItem[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    id: "workspace",
    label: "Workspace",
    items: [
      { id: "overview", label: "Overview", href: "/dashboard", icon: LayoutDashboard },
      // TODO Phase 2: replace placeholder href with real /today route once endpoint ships
      { id: "today", label: "Today's focus", href: "/dashboard", icon: Target },
      // TODO Phase 2: replace placeholder href with real period-close route
      { id: "period-close", label: "Period close", href: "/dashboard", icon: CalendarCheck },
      // TODO Phase 2: wire badge.count to /api/v1/approvals?status=pending
      { id: "approvals", label: "Approvals", href: "/dashboard", icon: CheckSquare, badge: null },
    ],
  },
  {
    id: "org",
    label: "Org",
    items: [
      { id: "entities", label: "Entities", href: "/settings/entities", icon: Building2 },
      { id: "org-settings", label: "Org settings", href: "/settings", icon: Settings },
      { id: "connectors", label: "Connectors", href: "/settings/connectors", icon: Plug },
      { id: "modules", label: "Modules", href: "/settings/modules", icon: LayoutGrid },
      { id: "billing", label: "Billing · Credits", href: "/settings/billing", icon: CreditCard },
    ],
  },
  {
    id: "governance",
    label: "Governance",
    items: [
      { id: "audit-trail", label: "Audit trail", href: "/governance/audit", icon: ScrollText },
      { id: "team-rbac", label: "Team · RBAC", href: "/settings/team", icon: Users },
      { id: "compliance", label: "Compliance", href: "/governance/compliance", icon: ShieldCheck },
    ],
  },
]
```

IMPORTANT — verify the routes exist. For each item's `href`:
1. Check if a Next.js route exists at that path under `frontend/app/(dashboard)/`
2. If a route does NOT exist, set the href to `/dashboard` and add a `// TODO Phase 2: route does not exist yet` comment ABOVE the item

Report which routes existed and which did not.

## Step 3 — Rebuild Sidebar.tsx

Modify `frontend/components/layout/Sidebar.tsx`:

1. **Width** — change the expanded sidebar width from `w-60` (240px) to a fixed 220px. Use `style={{ width: "220px" }}` on the root sidebar element to be exact (Tailwind has no `w-[220px]` arbitrary class issue, but inline style is unambiguous and matches what the audit's verification checklist asks for: "DevTools shows 220px").

2. **Collapsed rail width** — change `md:w-14` (56px) to a fixed 52px via inline style on the same element when collapsed. Use the existing collapse state from workspaceStore.

3. **Three nav groups** — replace the existing nav rendering with rendering driven by `NAV_GROUPS` from the nav-config file:
   - Each group renders with a **collapsible chevron header** (label uppercase 11px tracking-wide, chevron icon rotates on collapse). Default state: all three groups expanded.
   - Group collapse state is local component state for now (useState). Phase 4 will move this to workspaceStore for persistence.
   - Items within a group render via the existing SidebarNavItem component (do not modify SidebarNavItem in this sub-prompt — its current props should still work).
   - Active item state must continue to use `--color-background-info` + `--color-text-info` (this is what SidebarNavItem already does — verify, do not change).
   - In collapsed rail mode, group headers do NOT render — only the items render as icons with thin dividers between groups (matching audit §1.4).

4. **Preserve filterNavigationItems** — the existing filterNavigationItems(nav, role) call must continue to work. If filterNavigationItems was applied to the old flat nav list, apply it to each group's items in turn (groups stay; items inside groups get filtered).

5. **Preserve the entity card section** — the static read-only entity card with "ACTIVE ENTITY" label (already correct from QW-2) stays exactly as it is today. Do not touch this section.

6. **Preserve the user footer** — already correct from QW-7. Do not touch.

7. **Remove the old groupings** — the old "Financials / Assets & Leases / Consolidation / Tax & Compliance / Trust / Advisory / Settings / Admin" structure is replaced wholesale by the three new groups. The old code paths producing that structure should be deleted, not commented out.

## Step 4 — Add tests

Create `frontend/components/layout/sidebar/__tests__/nav-config.test.ts`:

- Test that NAV_GROUPS contains exactly 3 groups
- Test that group ids are exactly ["workspace", "org", "governance"] in that order
- Test that the workspace group contains exactly 4 items
- Test that the org group contains exactly 5 items
- Test that the governance group contains exactly 3 items
- Test that no two items share the same id

Update or add a Sidebar render test to verify:
- All three group labels render in expanded mode
- Group headers do NOT render in collapsed (rail) mode
- All 12 nav items render under correct groups when not filtered

If existing Sidebar tests already cover some of this, extend rather than duplicate. If existing Sidebar tests would fail because they assert old group labels, update them — but only the assertions, not the test structure.

## Step 5 — Verify

cd frontend
npm run typecheck                     # 0 errors required
npm run lint                          # 0 NEW errors; pre-existing warnings can remain (FU-004)
npm run test -- nav-config            # nav-config tests pass
npm run test -- Sidebar               # Sidebar tests pass
npm run build 2>&1 | tail -20         # build clean

Report verbatim:
- typecheck output (full output if non-zero, "0 errors" line if clean)
- lint output summary (count of errors and warnings)
- test results (test count + pass count for each suite run)
- the route count line from build output

## Step 6 — Commit

git add -A
git status                            # confirm only intended files

Expected files in diff:
- frontend/components/layout/Sidebar.tsx              (modified)
- frontend/components/layout/sidebar/nav-config.ts    (new)
- frontend/components/layout/sidebar/__tests__/nav-config.test.ts  (new)
- frontend/components/layout/__tests__/Sidebar.test.tsx (possibly modified)

If anything else appears in the diff, STOP and report.

git commit -m "feat(shell): phase 1.1 — sidebar structural rebuild

- Width 220px (was 240px); collapsed rail 52px (was 56px) — matches spec §1.3, §1.4
- Three nav groups: Workspace / Org / Governance via nav-config.ts
- Workspace: Overview, Today's focus, Period close, Approvals
- Org: Entities, Org settings, Connectors, Modules, Billing · Credits
- Governance: Audit trail, Team · RBAC, Compliance
- Group headers collapsible (local state); not rendered in rail mode
- Placeholder hrefs for routes that don't yet exist, marked TODO Phase 2

Resolves audit findings: #4 (nav groups), #11 (sidebar width), #12 (rail width)
Deferred to follow-ups: Approvals badge wiring, RBAC filtering by role,
real Today's focus / Period close routes (FU-012 to be filed in 1.2)

Tests: nav-config (6 cases) + Sidebar render coverage extended.
Verified: typecheck 0 errors, build clean."

## Final report

1. Branch HEAD hash (git log --oneline -1)
2. Files changed (git diff main --stat)
3. Pre-flight + Step 1 findings (current state of sidebar before changes)
4. Step 2 routes audit — which hrefs existed, which were placeholdered
5. typecheck / lint / test / build verbatim outputs
6. Step 6 — git status clean, commit hash
7. Confirm: did NOT push, did NOT merge

If at any point a deviation > 10% from this plan emerges (extra files needed, scope expansion, unexpected coupling), STOP IMMEDIATELY and report. Do not silently expand.
```

---

## After Claude Code reports done

Review:
1. The list of routes that existed vs were placeholdered. If many are placeholdered, that's information for Phase 2 planning, not a problem with 1.1.
2. The verbatim build output — route count should match Phase 0's exit count (verify against the v4.2.0 build log).
3. The commit hash.

Then run the merge prompt (`phase1-1.1-merge.md`).
