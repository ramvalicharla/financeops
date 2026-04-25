# Claude Code Prompt — Phase 1 Sub-Prompt 1.4: Route Metadata Sweep

> **Context:** 1.1, 1.2, 1.3 merged. Sidebar, TopBar, ModuleTabs all conforming to spec. This sub-prompt addresses audit finding #25 (residual scope after the Tier 1 a11y sweep): ~9 pages under `app/(dashboard)/` lack `generateMetadata` or `export const metadata`.
>
> **Branch:** create `feat/phase1-metadata-sweep` from `main`.
>
> **Expected scope:** ~9 page files modified, no new files. Single commit.
>
> **Risk:** Low. Metadata is additive; cannot break runtime behavior.
>
> **Do NOT push. Do NOT merge.**

---

## Paste this into Claude Code

```
## Task: Sub-prompt 1.4 — Route metadata sweep

## Pre-flight

git status
git checkout main
git pull --ff-only
git log --oneline -3
git checkout -b feat/phase1-metadata-sweep

## Step 1 — Inventory

Find every page.tsx under frontend/app/(dashboard)/ that does NOT export
`metadata` or `generateMetadata`:

# All page.tsx files under (dashboard)
find frontend/app/\(dashboard\) -name "page.tsx" 2>/dev/null

# Per file, check whether metadata is exported
for f in $(find frontend/app/\(dashboard\) -name "page.tsx" 2>/dev/null); do
  if grep -qE "(export const metadata|generateMetadata)" "$f"; then
    echo "OK    $f"
  else
    echo "MISS  $f"
  fi
done

Report the verbatim output.

The audit said ~9 pages are missing metadata. The actual count may be lower
if other PRs since the audit added metadata; or higher if new pages were
added. Use the actual count from the inventory.

## Step 2 — Metadata strategy

For each page missing metadata, infer a sensible page title from:
- The route segment names (e.g., `app/(dashboard)/settings/team/page.tsx` → "Team")
- Any existing page heading inside the component (look for `<h1>` text)

Title format: `{Page Title} · Finqor`
Description format: a one-sentence description aligned with the page's purpose.

For pages that contain dynamic segments (e.g., `[entityId]`), use
`generateMetadata` with the dynamic param resolved (or a sensible static
fallback if resolving requires a fetch — note as TODO).

For static pages, use `export const metadata = { title, description }`.

## Step 3 — Apply metadata

For each page in the MISS list:

1. If the file is a Server Component: add `export const metadata: Metadata = { ... }` at the top, importing `Metadata` from `"next"`.

2. If the file is a Client Component (`"use client"` directive at top):
   metadata cannot be exported from client components. Two options:
   a. Convert to a thin Server Component wrapper that exports metadata and
      renders a client child.
   b. Use a parent layout or a sibling `head.tsx` to set metadata.

   For 1.4, prefer option (a) — extract the client logic into a child
   component named `{PageName}Client.tsx`, leave the page.tsx as a server
   component that exports metadata and renders the client child.

   If a page has complex client behavior (forms, hooks tied to the route),
   use option (b) with a `head.tsx` sibling instead.

   For each page edited, note in the commit body which option was chosen.

3. Verify the page still renders by typechecking. Do not run the dev server
   for each one — typecheck is sufficient.

## Step 4 — Verify

cd frontend
npm run typecheck                # 0 errors
npm run lint 2>&1 | tail -5      # 0 NEW errors
npm run build 2>&1 | tail -20    # clean build, route count matches

# Quick visual confirmation per page that metadata is now present
for f in $(find frontend/app/\(dashboard\) -name "page.tsx" 2>/dev/null); do
  if grep -qE "(export const metadata|generateMetadata)" "$f"; then
    echo "OK    $f"
  else
    echo "STILL MISSING  $f"
  fi
done

Report verbatim. Every page that was MISS in Step 1 should be OK now,
unless deliberately deferred (with reason in commit body).

## Step 5 — Commit

git add -A
git status

Expected diff:
- N page.tsx files modified
- possibly N {PageName}Client.tsx files added (for pages converted from
  client to server wrapper)
- possibly head.tsx files added (for pages that took option b)

git commit -m "feat(shell): phase 1.4 — route metadata on remaining ${N} pages

Adds export const metadata or generateMetadata to dashboard pages that
were missing route-level metadata.

Pages updated:
- {list each page and the strategy: 'static metadata', 'client→server
  wrapper', or 'head.tsx'}

Title format: {Page} · Finqor
Description: per-page one-line.

Resolves audit finding #25 (residual scope after Tier 1 a11y sweep).
Spec ref §1.8 item 6: route-level metadata required."

## Final report

1. Step 1 inventory output (OK / MISS list)
2. Number of pages updated
3. For each page: strategy chosen (static metadata, client→server wrapper, head.tsx)
4. Step 4 verification output (final OK list)
5. typecheck / lint / build verbatim
6. Files changed
7. Commit hash
8. git status clean, did NOT push

If a page resists metadata application (e.g., deeply nested client component
with no clean wrapping option), STOP that one page and report — do not force
a fragile change. The page can be deferred to a follow-up.
```

After done, run `phase1-1.4-merge.md`.
