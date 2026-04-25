# Claude Code Prompt — Phase 1 Sub-Prompt 1.3: Module Icon Registry + 40px Tab Container

> **Context:** 1.1 and 1.2 merged. Sidebar at 220px with three groups; TopBar at 48px with FY chip; follow-ups filed. This sub-prompt addresses two ModuleTabs concerns:
>
> 1. Audit finding #20 (Major) — tab bar container has `py-3 pb-4` padding-based sizing instead of a fixed 40px height.
> 2. Audit Risk #3 (Unknown) — no `MODULE_ICON_MAP` exists. Tabs render module text but have no per-module icon registry. QW-1 added inline icon rendering as a stopgap; this sub-prompt makes it data-driven.
>
> **Branch:** create `feat/phase1-module-icons` from `main`.
>
> **Expected scope:** ~3 files. Single commit.
>
> **Risk:** Low-Medium. Visible to all users — broken icon rendering would be obvious. Verification step is a build + visual inspection of the tab bar.
>
> **Do NOT push. Do NOT merge.**

---

## Paste this into Claude Code

```
## Task: Sub-prompt 1.3 — module icon registry + 40px tab container

## Pre-flight

git status
git checkout main
git pull --ff-only
git log --oneline -3
git checkout -b feat/phase1-module-icons

## Step 1 — Read current state

Read end-to-end:
- frontend/components/layout/ModuleTabs.tsx
- frontend/lib/api/control-plane.ts (or wherever the workspace_tabs / module shape is defined)
- Search for any existing MODULE_ICON_MAP, moduleIcons, getModuleIcon — confirm none exists

Report:
1. The current container element of the tab strip (~ line 34) and its className. Confirm it uses `py-3 pb-4` or similar padding-based sizing.
2. The shape of a workspace_tab item — what fields are available? At minimum: workspace_key, workspace_name. Are there others (icon, slug, etc.)?
3. The list of distinct workspace_keys that could appear (look at backend module registry, seed data, or any existing tests).
4. Whether QW-1 added an inline icon — quote the icon rendering code from ModuleTabs.tsx.

## Step 2 — Create module-icons.ts

Path: frontend/components/layout/tabs/module-icons.ts

```ts
import type { LucideIcon } from "lucide-react"
import {
  LayoutDashboard,
  BookOpen,        // Financials / GL
  Building,        // FAR / Fixed Assets
  Globe,           // Consolidation
  FileText,        // Lease Accounting
  Wallet,          // Banking
  Receipt,         // Tax / GST
  TrendingUp,      // Budgeting / MIS
  Folder,          // Reports
  CircleDot,       // fallback
} from "lucide-react"

/**
 * Maps backend `workspace_key` → Lucide icon component.
 *
 * Keys must match backend Module Registry workspace_key values exactly
 * (case-sensitive). When the backend adds a new module, an entry must
 * be added here or the tab will fall back to CircleDot.
 *
 * Ref: spec §1.5 (icon + label per tab); audit Risk #3.
 */
export const MODULE_ICON_MAP: Record<string, LucideIcon> = {
  overview: LayoutDashboard,
  financials: BookOpen,
  far: Building,
  consolidation: Globe,
  lease: FileText,
  banking: Wallet,
  tax: Receipt,
  budgeting: TrendingUp,
  mis: TrendingUp,
  reports: Folder,
}

export const FALLBACK_MODULE_ICON: LucideIcon = CircleDot

export function getModuleIcon(workspaceKey: string | undefined | null): LucideIcon {
  if (!workspaceKey) return FALLBACK_MODULE_ICON
  return MODULE_ICON_MAP[workspaceKey.toLowerCase()] ?? FALLBACK_MODULE_ICON
}
```

Important: cross-check the keys against the actual backend module registry. If the backend uses different workspace_key values (e.g., `accounting_layer` instead of `financials`), update the map to match. Add a TODO comment noting any keys that are guesses.

## Step 3 — Wire ModuleTabs to the registry

Edit frontend/components/layout/ModuleTabs.tsx:

1. **40px container** — replace the padding-based sizing on the tab strip container with a fixed `h-10` (40px) class. Adjust internal padding so vertical centering of tab content still works (`flex items-center` should already do this; if not, add it).

2. **Use getModuleIcon** — replace any inline icon mapping logic that QW-1 added with `getModuleIcon(tab.workspace_key)`. Each tab renders `<Icon size={14} />` followed by the label.

3. **Active tab style** — verify QW-1's active-tab style is preserved: `border-b-2 border-[#185FA5] font-medium bg-transparent text-foreground rounded-none`. Do NOT change this.

4. **Tab dimensions** — each tab should be `h-full` (40px to match container), with horizontal padding sufficient to space icon+label comfortably (`px-3` or `px-4`).

5. **Horizontal scroll** — confirm the container has `overflow-x-auto` for tab overflow per spec. If missing, add it.

6. **Border-bottom** — the tab strip container should have a 0.5px or 1px border at the bottom that the active tab's underline visually merges with. If a border isn't there today, add `border-b border-[var(--color-border-tertiary)]`.

## Step 4 — Add tests

Create frontend/components/layout/tabs/__tests__/module-icons.test.ts:

- Test getModuleIcon returns the correct icon for each key in MODULE_ICON_MAP
- Test getModuleIcon returns FALLBACK_MODULE_ICON for undefined / null / unknown key
- Test getModuleIcon is case-insensitive (returns Wallet for "BANKING")

Update or extend ModuleTabs render test (if one exists) to:
- Verify tab strip container has h-10 class
- Verify each tab renders an icon (querySelector for svg or the Lucide component test ID)

## Step 5 — Verify

cd frontend
npm run typecheck                # 0 errors
npm run lint 2>&1 | tail -5      # 0 NEW errors
npm run test -- module-icons     # tests pass
npm run test -- ModuleTabs       # if a test exists; else skip
npm run build 2>&1 | tail -20    # clean build

Report verbatim outputs.

If `npm run dev` is feasible and it opens cleanly, take one screenshot of the
tab bar (or describe the rendered state) — does the tab bar look like
icon + label, 40px height, blue underline on active? This is a sanity check,
not a test gate.

## Step 6 — Commit

git add -A
git status

Expected diff:
- frontend/components/layout/ModuleTabs.tsx (modified)
- frontend/components/layout/tabs/module-icons.ts (new)
- frontend/components/layout/tabs/__tests__/module-icons.test.ts (new)
- possibly an existing ModuleTabs test (modified)

git commit -m "feat(shell): phase 1.3 — module icon registry + 40px tab container

- MODULE_ICON_MAP maps backend workspace_key → Lucide icon component
- getModuleIcon() with case-insensitive lookup + safe fallback
- Tab strip container: fixed h-10 (40px) instead of padding-based height
- ModuleTabs reads icons from registry instead of inline logic
- Active tab underline (#185FA5, 2px) preserved from QW-1

Resolves audit findings: #20 (40px container), Risk #3 (icon registry)
Tests: module-icons (4 cases) + ModuleTabs render extended.
Verified: typecheck 0 errors, build clean."

## Final report

1. Branch HEAD hash
2. Files changed
3. Step 1 findings (current container className, workspace_key list, QW-1 state)
4. Step 2 — any keys that were guesses (marked TODO)
5. typecheck / lint / test / build verbatim
6. Visual sanity check result if dev was run
7. git status clean, did NOT push

If at any point a deviation > 10% from this plan emerges, STOP and report.
```

After done, run `phase1-1.3-merge.md`.
