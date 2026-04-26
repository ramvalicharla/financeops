# Claude Code Prompt — Phase 1 Sub-Prompt 1.6: Route Migration + Team Consolidation

> **Context:** Phase 1 is tagged at `v4.3.0-phase1-complete` (`b8c3aa1`). The structural shell is done but 9 of 12 sidebar nav items point at `/dashboard` placeholders. This sub-prompt fixes the 7 items that have real routes available — 4 by moving existing routes to spec-correct paths, 3 by creating a consolidated `/settings/team` page from existing `/settings/users` + `/settings/groups`. The remaining 5 items (Today's focus, Period close, Approvals, Connectors, Compliance) genuinely require Phase 2/6 backend work and stay placeholdered.
>
> **Branch:** create `feat/phase1-route-migration` from `main`.
>
> **Expected scope:** ~15-20 files. Single branch, single merge.
>
> **Risk:** Medium-High. Route moves touch internal links, redirects, and tests. The /settings/team consolidation is genuinely new UI work.
>
> **Tag handling:** This sub-prompt does NOT modify the existing `v4.3.0-phase1-complete` tag. After 1.6 merges, a separate tagging step creates `v4.3.1` for the usable-routes milestone.
>
> **CRITICAL — INTERNAL CHECKPOINTS:** This prompt has 5 explicit STOP-AND-REPORT gates. After each gate, you (Claude Code) report back to the user, wait for "proceed" instruction, and only then continue. Do NOT plow through all 5 phases in one run.
>
> **Do NOT push. Do NOT merge.**

---

## Phase Plan

| Phase | Scope | Checkpoint after |
|---|---|---|
| 0 | Pre-flight + read existing routes | ✋ Checkpoint 1 |
| 1 | Move /modules → /settings/modules | ✋ Checkpoint 2 |
| 2 | Move /billing → /settings/billing AND /audit → /governance/audit | ✋ Checkpoint 3 |
| 3 | Build consolidated /settings/team page | ✋ Checkpoint 4 |
| 4 | Update nav-config.ts + verify everything builds clean | ✋ Checkpoint 5 |
| 5 | Final commit | (commit, then report) |

Each checkpoint expects a typecheck + lint + build pass before the next phase begins. Each checkpoint produces a small commit on the branch — we use the branch's commit history as the audit trail.

---

## Paste this into Claude Code

```
## Task: Sub-prompt 1.6 — Route migration + /settings/team consolidation

Read the entire prompt before starting. This is a long, multi-phase prompt
with internal checkpoints. Do NOT run end-to-end; STOP at each checkpoint
and report.

## Phase 0 — Pre-flight + reconnaissance

git status
git checkout main
git pull --ff-only
git log --oneline -3                           # confirm 1.5 exit-gate merge present
git tag --list "v4*"                            # confirm v4.3.0-phase1-complete present
git checkout -b feat/phase1-route-migration

## Phase 0.1 — Read source routes

For each of these existing routes that we'll be moving, view end-to-end and
record:

1. /modules
   - View frontend/app/(dashboard)/modules/ (entire directory)
   - List every file in the directory
   - Note: any subdirectories? any layout.tsx? any sub-pages? any components/
     directory specific to this route?
   - Note: is the page a Server or Client Component?

2. /billing
   - View frontend/app/(dashboard)/billing/ (entire directory)
   - Same questions as above

3. /audit
   - View frontend/app/(dashboard)/audit/ (entire directory)
   - Same questions as above

4. /settings/users
   - View frontend/app/(dashboard)/settings/users/ (entire directory)
   - Same questions as above
   - Particularly note: how is the page structured? PageClient pattern?
     Sub-routes for individual users?

5. /settings/groups
   - View frontend/app/(dashboard)/settings/groups/ (entire directory)
   - Same questions as above

## Phase 0.2 — Internal link audit

Find every place in the codebase that links to one of the 5 source routes:

grep -rn "href=\"/modules\b\|href='/modules\b" frontend/ 2>/dev/null | grep -v node_modules
grep -rn "href=\"/billing\b\|href='/billing\b" frontend/ 2>/dev/null | grep -v node_modules
grep -rn "href=\"/audit\b\|href='/audit\b" frontend/ 2>/dev/null | grep -v node_modules
grep -rn "href=\"/settings/users\b\|href='/settings/users\b" frontend/ 2>/dev/null | grep -v node_modules
grep -rn "href=\"/settings/groups\b\|href='/settings/groups\b" frontend/ 2>/dev/null | grep -v node_modules

# Also search for router.push and redirect calls
grep -rn "push(\"/modules\b\|push('/modules\b\|redirect(\"/modules\b\|redirect('/modules\b" frontend/ 2>/dev/null | grep -v node_modules
grep -rn "push(\"/billing\b\|push('/billing\b\|redirect(\"/billing\b\|redirect('/billing\b" frontend/ 2>/dev/null | grep -v node_modules
grep -rn "push(\"/audit\b\|push('/audit\b\|redirect(\"/audit\b\|redirect('/audit\b" frontend/ 2>/dev/null | grep -v node_modules
grep -rn "push(\"/settings/users\b\|push('/settings/users\b" frontend/ 2>/dev/null | grep -v node_modules
grep -rn "push(\"/settings/groups\b\|push('/settings/groups\b" frontend/ 2>/dev/null | grep -v node_modules

# Tests that hit these routes
grep -rn "modules\b\|billing\b\|audit\b" frontend/tests/ 2>/dev/null | grep -E "url|navigate|goto|page\." | head -30

Record the verbatim results. For each match, record:
- file:line
- whether it's a hardcoded href, push call, redirect, or test url
- whether the link target is the moving route or coincidentally similar (e.g., a JSX className containing "billing" is not a link)

## Phase 0.3 — Existing redirects audit

View frontend/next.config.js (or .mjs / .ts).

Are there any existing redirect rules? List them. We'll be adding new ones.

## Phase 0.4 — nav-config.ts current state

View frontend/components/layout/sidebar/nav-config.ts.

Quote the 7 items affected by this work:
- Modules (currently href: "/dashboard" with TODO comment)
- Billing · Credits (currently href: "/dashboard" with TODO comment)
- Audit trail (currently href: "/dashboard" with TODO comment)
- Team · RBAC (currently href: "/dashboard" with TODO comment)

After 1.6, these will become:
- Modules → "/settings/modules"
- Billing · Credits → "/settings/billing"
- Audit trail → "/governance/audit"
- Team · RBAC → "/settings/team"

✋ ============================================================
   CHECKPOINT 1 — STOP AND REPORT TO USER
   ============================================================

Report back:
1. Phase 0.1 — for each of the 5 source routes, the file inventory + structural
   summary
2. Phase 0.2 — full internal link audit (count of links per route, files
   touched)
3. Phase 0.3 — current redirect state in next.config.*
4. Phase 0.4 — nav-config.ts confirmation
5. Concerns or surprises:
   - Any source route that's structurally complex (sub-routes, dynamic
     segments, multiple layouts)?
   - Any /settings/users or /settings/groups detail that suggests the
     consolidation will be harder than expected?
   - Internal link counts — are they manageable (~20 each) or massive (~100)?
6. Recommendation: proceed with Phase 1, proceed with adjustments, or stop

DO NOT proceed to Phase 1 until the user explicitly says proceed.

============================================================

## Phase 1 — Move /modules → /settings/modules

(After user approves, proceed.)

## Phase 1.1 — File moves

Move every file under frontend/app/(dashboard)/modules/ to
frontend/app/(dashboard)/settings/modules/

Use git mv (NOT cp + rm) to preserve git's rename detection:

# Example pattern — adapt to actual files found in Phase 0.1
cd frontend
mkdir -p app/\(dashboard\)/settings/modules
git mv "app/(dashboard)/modules/page.tsx" "app/(dashboard)/settings/modules/page.tsx"
# Repeat for every file/subdirectory under modules/
# Then remove the now-empty modules directory:
rmdir "app/(dashboard)/modules"

If the page is a client component using PageClient pattern, move both files.
If there are dynamic sub-routes ([id]/page.tsx, etc.), move the entire
subtree.

## Phase 1.2 — Update internal links

For every file identified in Phase 0.2's audit referencing /modules:
- Update the href / push / redirect target to /settings/modules
- BUT NOT in nav-config.ts yet (we update that in Phase 4 — having the nav
  point at the new path while everything else still works keeps each phase
  reviewable)
- Skip the test files for now — those go in Phase 1.4

## Phase 1.3 — Add redirect to next.config

Edit frontend/next.config.js (or .mjs / .ts).

Add to the redirects() function (creating the function if it doesn't exist):

```js
async redirects() {
  return [
    {
      source: '/modules',
      destination: '/settings/modules',
      permanent: true,
    },
    {
      source: '/modules/:path*',
      destination: '/settings/modules/:path*',
      permanent: true,
    },
    // (other redirects from Phase 2 go here too — don't add them yet)
  ]
}
```

The :path* pattern handles deep links to sub-pages (e.g., /modules/123).

## Phase 1.4 — Update tests

For any test files that reference /modules:
- E2E tests: update the URL string to /settings/modules
- Unit tests: update expected paths
- Keep test logic identical; only paths change

## Phase 1.5 — Verify Phase 1

cd frontend
npm run typecheck                # 0 errors
npm run lint 2>&1 | tail -5      # 0 NEW errors
npm run test 2>&1 | tail -10     # baseline failures only (5 known)
npm run build 2>&1 | tail -20    # clean build

If typecheck or build fails, STOP. Most likely cause: a stale internal
link wasn't caught. Re-grep for /modules and fix.

Commit:
git add -A
git commit -m "refactor(routes): phase 1.6.1 — move /modules to /settings/modules

- All files in app/(dashboard)/modules/ moved to app/(dashboard)/settings/modules/
  via git mv (rename detection preserved)
- Internal links updated: {N} files
- Permanent redirect /modules → /settings/modules added in next.config
- Tests updated to use new path
- nav-config.ts deferred to Phase 4"

✋ ============================================================
   CHECKPOINT 2 — STOP AND REPORT TO USER
   ============================================================

Report:
1. Files moved (git diff main --stat | grep modules)
2. Internal links updated (file count + sample of 3)
3. next.config redirect added (quote it)
4. Test paths updated (file count)
5. typecheck / lint / build / test verbatim
6. Commit hash for Phase 1
7. Any surprises

DO NOT proceed to Phase 2 until user says proceed.

============================================================

## Phase 2 — Move /billing → /settings/billing AND /audit → /governance/audit

(After user approves, proceed.)

This phase combines two route moves because they're structurally identical
(simple path renames, no consolidation). Same pattern as Phase 1, repeated.

## Phase 2.1 — Move /billing → /settings/billing

Same pattern as Phase 1.1: git mv every file under app/(dashboard)/billing/
to app/(dashboard)/settings/billing/.

## Phase 2.2 — Move /audit → /governance/audit

Same pattern but creates a new /governance/ directory:

cd frontend
mkdir -p "app/(dashboard)/governance/audit"
git mv "app/(dashboard)/audit/page.tsx" "app/(dashboard)/governance/audit/page.tsx"
# Move any other files in audit/
rmdir "app/(dashboard)/audit"

## Phase 2.3 — Update internal links

Update all internal links to /billing and /audit per the Phase 0.2 audit.

## Phase 2.4 — Add redirects

Add to next.config redirects:

```js
{
  source: '/billing',
  destination: '/settings/billing',
  permanent: true,
},
{
  source: '/billing/:path*',
  destination: '/settings/billing/:path*',
  permanent: true,
},
{
  source: '/audit',
  destination: '/governance/audit',
  permanent: true,
},
{
  source: '/audit/:path*',
  destination: '/governance/audit/:path*',
  permanent: true,
},
```

## Phase 2.5 — Update tests

Per Phase 1.4 pattern.

## Phase 2.6 — Verify

cd frontend
npm run typecheck
npm run lint 2>&1 | tail -5
npm run test 2>&1 | tail -10
npm run build 2>&1 | tail -20

Commit:
git add -A
git commit -m "refactor(routes): phase 1.6.2 — move /billing and /audit to spec paths

- /billing → /settings/billing (full subtree)
- /audit → /governance/audit (creates new /governance/ directory)
- Internal links updated: {N} files
- Permanent redirects added in next.config
- Tests updated"

✋ ============================================================
   CHECKPOINT 3 — STOP AND REPORT TO USER
   ============================================================

Report same shape as Checkpoint 2. STOP until user approves.

============================================================

## Phase 3 — Build consolidated /settings/team page

(After user approves, proceed. This is the largest phase.)

## Phase 3.1 — Architecture decision

Read the existing /settings/users and /settings/groups page structures
(captured in Phase 0.1 reconnaissance).

For the consolidated /settings/team page, the architecture is:

```
app/(dashboard)/settings/team/
  page.tsx                    — Server Component, exports metadata, renders TeamPageClient
  TeamPageClient.tsx          — Client Component, renders Tabs + tab content
  _components/                — (optional) shared sub-components
```

Tab approach using shadcn Tabs:
- 2 tabs: "Users" and "Groups"
- Active tab driven by URL search param ?tab=users (default) or ?tab=groups
- Each tab renders the existing client component (UsersClient and GroupsClient,
  whatever they're actually named) UNCHANGED. We're composing, not rewriting.

The existing page.tsx files at /settings/users/ and /settings/groups/ become
redirect-only pages:

```tsx
// app/(dashboard)/settings/users/page.tsx
import { redirect } from "next/navigation"
export default function UsersPage() {
  redirect("/settings/team?tab=users")
}
```

This preserves backward compatibility for any bookmarks while moving the
canonical home to /settings/team. We could go pure-redirect via next.config,
but using Next's redirect() inside a page.tsx is more reliable for App Router
deep-linking and simpler than configuring intercepting redirects with query
params.

## Phase 3.2 — Extract existing user/group client components

If /settings/users currently has a structure like:
  page.tsx (Server, exports metadata, renders UsersPageClient)
  UsersPageClient.tsx (Client, all logic)

…then UsersPageClient.tsx is the component to compose. Move it under
the new team directory:

cd frontend
git mv "app/(dashboard)/settings/users/UsersPageClient.tsx" "app/(dashboard)/settings/team/_components/UsersPanel.tsx"

Rename the component class/function to UsersPanel for clarity (it's now a
panel inside Tabs, not a page).

Repeat for groups → GroupsPanel.tsx.

If the existing files use different naming patterns, ADAPT — don't force
the names UsersPanel/GroupsPanel if it creates more confusion than clarity.
Use whatever existing naming is in the codebase, just relocated.

## Phase 3.3 — Build the team page

Create app/(dashboard)/settings/team/page.tsx (Server Component):

```tsx
import type { Metadata } from "next"
import { TeamPageClient } from "./TeamPageClient"

export const metadata: Metadata = {
  title: "Team · Finqor",
  description: "Manage team members, roles, and groups for your organisation.",
}

interface PageProps {
  searchParams: { tab?: string }
}

export default function TeamPage({ searchParams }: PageProps) {
  return <TeamPageClient initialTab={searchParams.tab === "groups" ? "groups" : "users"} />
}
```

Create app/(dashboard)/settings/team/TeamPageClient.tsx:

```tsx
"use client"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { UsersPanel } from "./_components/UsersPanel"
import { GroupsPanel } from "./_components/GroupsPanel"

interface TeamPageClientProps {
  initialTab: "users" | "groups"
}

export function TeamPageClient({ initialTab }: TeamPageClientProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [tab, setTab] = useState<"users" | "groups">(initialTab)

  const handleTabChange = (next: string) => {
    if (next !== "users" && next !== "groups") return
    setTab(next)
    const params = new URLSearchParams(searchParams.toString())
    params.set("tab", next)
    router.replace(`${pathname}?${params.toString()}`, { scroll: false })
  }

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-border px-6 py-4">
        <h1 className="text-xl font-medium">Team</h1>
        <p className="text-sm text-muted-foreground">
          Manage team members, roles, and groups for your organisation.
        </p>
      </header>
      <Tabs value={tab} onValueChange={handleTabChange} className="flex flex-1 flex-col">
        <TabsList className="border-b border-border bg-transparent px-6 rounded-none h-10">
          <TabsTrigger
            value="users"
            className="data-[state=active]:border-b-2 data-[state=active]:border-[#185FA5] data-[state=active]:bg-transparent rounded-none"
          >
            Users
          </TabsTrigger>
          <TabsTrigger
            value="groups"
            className="data-[state=active]:border-b-2 data-[state=active]:border-[#185FA5] data-[state=active]:bg-transparent rounded-none"
          >
            Groups
          </TabsTrigger>
        </TabsList>
        <TabsContent value="users" className="flex-1 overflow-auto">
          <UsersPanel />
        </TabsContent>
        <TabsContent value="groups" className="flex-1 overflow-auto">
          <GroupsPanel />
        </TabsContent>
      </Tabs>
    </div>
  )
}
```

IMPORTANT: The tab styling above assumes shadcn's Tabs. If the codebase
already uses Tabs elsewhere (search components/ui/tabs.tsx and a usage
example), match THAT styling. The active border-b-2 with #185FA5 should
echo the ModuleTabs active style from sub-prompt 1.3 for visual consistency.

## Phase 3.4 — Replace old users/groups pages with redirects

Replace app/(dashboard)/settings/users/page.tsx with:

```tsx
import { redirect } from "next/navigation"

export default function UsersPage() {
  redirect("/settings/team?tab=users")
}
```

Replace app/(dashboard)/settings/groups/page.tsx with:

```tsx
import { redirect } from "next/navigation"

export default function GroupsPage() {
  redirect("/settings/team?tab=groups")
}
```

These are minimal redirect pages. They preserve the URLs without breaking
existing bookmarks.

NOTE: Server-component redirect() in App Router does an HTTP 307. Combined
with the next.config redirects we'd need for deep links, the cleaner approach
might be to delete the old pages entirely and use only next.config redirects.
However, App Router's interaction with query-string redirects via next.config
is fiddly. Using page-level redirects is more robust for the ?tab=X case.

## Phase 3.5 — Internal links update

Update internal references to /settings/users and /settings/groups per
Phase 0.2 audit. Three patterns:

Pattern A — link to user list:
  /settings/users → /settings/team?tab=users
Pattern B — link to group list:
  /settings/groups → /settings/team?tab=groups
Pattern C — link to a specific user/group detail:
  /settings/users/[id] → unchanged for now (sub-routes still live under
  the redirect-page). The redirect catches the bare path; deep paths still
  work because they hit /settings/users/[id] directly without the redirect
  triggering. If the audit shows links to /settings/users/[id], leave them
  alone — they continue to work.

If Phase 0.1 reconnaissance found dynamic sub-routes under users/ or groups/
(e.g., users/[id]/page.tsx), those stay where they are. Only the bare
list-page is consolidated.

## Phase 3.6 — Tests

For tests that referenced /settings/users and /settings/groups:
- E2E: update to /settings/team?tab=users or ?tab=groups
- Unit: update expected paths
- If a test specifically tested the legacy URL behavior, update to test
  the redirect (expect a 307 → /settings/team?tab=users)

Add a new test for the team page:
- Renders both tabs
- Clicking tab updates URL search param
- Default tab is "users" when no search param present
- Tab is "groups" when URL has ?tab=groups

## Phase 3.7 — Verify

cd frontend
npm run typecheck
npm run lint 2>&1 | tail -5
npm run test 2>&1 | tail -10
npm run build 2>&1 | tail -20

Commit:
git add -A
git commit -m "feat(settings): phase 1.6.3 — consolidate /settings/users + /settings/groups into /settings/team

- New /settings/team page with shadcn Tabs (Users / Groups)
- URL state via ?tab= search param; default tab is users
- Existing UsersPageClient → UsersPanel (relocated, unchanged logic)
- Existing GroupsPageClient → GroupsPanel (relocated, unchanged logic)
- Old /settings/users and /settings/groups now redirect-only
- Active tab style matches ModuleTabs (#185FA5 2px underline)
- Tests added for tab behavior and URL state

Resolves spec §1.3 sidebar 'Team · RBAC' canonical path.
Old paths preserved via redirect() for bookmark compatibility."

✋ ============================================================
   CHECKPOINT 4 — STOP AND REPORT TO USER
   ============================================================

Report:
1. The file structure under app/(dashboard)/settings/team/ post-consolidation
2. Lines of code in TeamPageClient (sanity check it's not bloated)
3. The active-tab CSS — does it visually match ModuleTabs from sub-prompt 1.3?
4. Tests added (count + names)
5. Internal link updates count + samples
6. typecheck / lint / test / build verbatim
7. Commit hash
8. Any surprises (especially: did UsersPageClient or GroupsPageClient have
   unexpected dependencies or behaviors that complicated the move?)

DO NOT proceed to Phase 4 until user approves.

============================================================

## Phase 4 — Update nav-config.ts

(After user approves, proceed.)

This is the moment the sidebar starts pointing at the new paths. Until now
nav-config has been pointing at /dashboard placeholders. After Phase 4, the
4 nav items go live.

## Phase 4.1 — Edit nav-config.ts

Open frontend/components/layout/sidebar/nav-config.ts.

Update the 4 nav items:

BEFORE (current):
```ts
// TODO Phase 2: route does not exist yet
{ id: "modules", label: "Modules", href: "/dashboard", icon: LayoutGrid },
// TODO Phase 2: route does not exist yet
{ id: "billing", label: "Billing · Credits", href: "/dashboard", icon: CreditCard },
// TODO Phase 2: route does not exist yet
{ id: "audit-trail", label: "Audit trail", href: "/dashboard", icon: ScrollText },
// TODO Phase 2: route does not exist yet
{ id: "team-rbac", label: "Team · RBAC", href: "/dashboard", icon: Users },
```

AFTER:
```ts
{ id: "modules", label: "Modules", href: "/settings/modules", icon: LayoutGrid },
{ id: "billing", label: "Billing · Credits", href: "/settings/billing", icon: CreditCard },
{ id: "audit-trail", label: "Audit trail", href: "/governance/audit", icon: ScrollText },
{ id: "team-rbac", label: "Team · RBAC", href: "/settings/team", icon: Users },
```

Remove the // TODO Phase 2 comment from each.

Update the comment block at the top of NAV_GROUPS (which lists placeholder
routes) — remove these 4 from the placeholder list. The placeholder list
should now mention only 5 items (Today's focus, Period close, Approvals,
Connectors, Compliance).

## Phase 4.2 — Update nav-config tests

Open frontend/components/layout/sidebar/__tests__/nav-config.test.ts.

If tests assert on specific hrefs, update them. If tests just count items
or assert on labels, no change needed.

## Phase 4.3 — Verify

cd frontend
npm run typecheck
npm run lint 2>&1 | tail -5
npm run test -- nav-config       # nav-config tests pass
npm run test 2>&1 | tail -10     # full run; baseline failures only
npm run build 2>&1 | tail -20    # clean build

Commit:
git add -A
git commit -m "feat(shell): phase 1.6.4 — sidebar nav-config points at canonical paths

- Modules → /settings/modules
- Billing · Credits → /settings/billing
- Audit trail → /governance/audit
- Team · RBAC → /settings/team
- Removed 4 TODO Phase 2 comments
- Updated header comment block; placeholder count down from 9 to 5

These 4 items now point at real working routes (post-1.6.1, 1.6.2, 1.6.3).
The remaining 5 placeholders (Today's focus, Period close, Approvals,
Connectors, Compliance) still target /dashboard pending Phase 2/6 work."

✋ ============================================================
   CHECKPOINT 5 — STOP AND REPORT TO USER
   ============================================================

Report:
1. nav-config diff (verbatim before/after of the 4 items)
2. nav-config test changes
3. typecheck / lint / test / build verbatim
4. Commit hash
5. CONFIRM: clicking each of the 4 nav items in dev would now navigate to a
   real working page. (You don't need to actually run dev — just confirm
   the routes exist via find: 
     test -f frontend/app/\(dashboard\)/settings/modules/page.tsx && echo OK
     test -f frontend/app/\(dashboard\)/settings/billing/page.tsx && echo OK
     test -f frontend/app/\(dashboard\)/governance/audit/page.tsx && echo OK
     test -f frontend/app/\(dashboard\)/settings/team/page.tsx && echo OK
   )

DO NOT proceed to Phase 5 until user approves.

============================================================

## Phase 5 — Final consolidation commit + cleanup

(After user approves, proceed.)

## Phase 5.1 — Final verification

cd frontend
git log --oneline ^main feat/phase1-route-migration   # should show 4 commits
                                                       # (1.6.1, 1.6.2, 1.6.3, 1.6.4)

# Full reset and rebuild
rm -rf .next
npm run build 2>&1 | tail -25

# Inventory check — confirm no orphaned files in old route locations
test -d "app/(dashboard)/modules" && echo "WARN: /modules dir still exists" || echo "OK: /modules removed"
test -d "app/(dashboard)/billing" && echo "WARN: /billing dir still exists" || echo "OK: /billing removed"
test -d "app/(dashboard)/audit" && echo "WARN: /audit dir still exists" || echo "OK: /audit removed"

# Inventory check — confirm new routes exist
test -f "app/(dashboard)/settings/modules/page.tsx" && echo "OK"
test -f "app/(dashboard)/settings/billing/page.tsx" && echo "OK"
test -f "app/(dashboard)/governance/audit/page.tsx" && echo "OK"
test -f "app/(dashboard)/settings/team/page.tsx" && echo "OK"
test -f "app/(dashboard)/settings/team/TeamPageClient.tsx" && echo "OK"
test -f "app/(dashboard)/settings/users/page.tsx" && echo "OK (redirect page)"
test -f "app/(dashboard)/settings/groups/page.tsx" && echo "OK (redirect page)"

## Phase 5.2 — Verify dev mode (optional but useful)

If practical (no large dependency installs needed), start dev mode briefly:
npm run dev &
sleep 8
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/modules     # expect 307 (redirect)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/settings/modules  # expect 200 (or 307 to login if auth-gated)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/audit       # expect 307
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3000/governance/audit  # expect 200/307
kill %1

If dev mode is impractical (long install / port conflicts / etc.), skip
this and rely on the build verification.

## Phase 5.3 — No final commit needed

The 4 phase commits ARE the work. No additional final commit. The branch
holds its own history; the merge commit (separate prompt) is what lands
on main.

git log --oneline ^main feat/phase1-route-migration

Should show exactly 4 commits in reverse chronological order:
- phase 1.6.4 nav-config update
- phase 1.6.3 team consolidation
- phase 1.6.2 billing + audit moves
- phase 1.6.1 modules move

## Final report

Report:
1. Phase 5.1 inventory results (every OK / WARN line)
2. Phase 5.2 dev-mode HTTP codes if run, or "skipped"
3. Total branch stats:
   git log --oneline ^main feat/phase1-route-migration | wc -l    # should be 4
   git diff main feat/phase1-route-migration --stat | tail -1
4. List of all 4 commit hashes in order
5. Confirm: all tests still pass, baseline failures unchanged
6. Confirm: did NOT push, did NOT merge

Branch is ready for merge. Merge runs as a separate prompt.

If at any point ANY phase produces a deviation > 10%, STOP IMMEDIATELY. The
checkpoints exist precisely to catch this.
```

---

## After all 5 checkpoints clear

You'll have a branch with 4 well-scoped commits, each independently verifiable. The merge prompt (separate file) will run `--no-ff` to preserve all 4 on the branch lane in topology, then verify clean post-merge build.

After merge, a final tagging step creates `v4.3.1`.
