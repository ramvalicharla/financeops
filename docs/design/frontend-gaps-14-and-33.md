# Frontend Implementation Prompts — Final 2 Gaps
## Gap #14 — Entity Tree Preview + Gap #33 — aria-live Loading States

**Prerequisite:** Backend entity_name field confirmed (entity_name is the real attribute, not legal_name)
**Run after each prompt:** `npx tsc --noEmit` and `npx playwright test --project=chromium`

---

## Prompt 1 of 2 — #14 — Live entity tree preview in onboarding step 2
**Priority:** P2 | **Effort:** M | **Tool:** Claude Code

```
You are working in the Finqor frontend codebase at D:\finos\frontend.

TASK: Add a live entity tree preview panel to onboarding step 2 (Entity structure)
that updates in real time as the user enters entities.

CONFIRMED FIELD NAME: The backend entity model uses entity_name (not legal_name).
Use entity_name throughout this implementation.

STEP 1 — Read components/org-setup/Step2Entities.tsx fully before writing anything. Note:
- The exact field names used in the form (name, type, parent fields)
- How entities are stored in react-hook-form state
- How the form array is structured (useFieldArray or similar)
- What entity type values are used (subsidiary, branch, holding, associate or similar)

STEP 2 — Create components/org-setup/EntityTreePreview.tsx:

interface EntityNode {
  id: string
  name: string
  type: string
  parentId?: string
}

interface EntityTreePreviewProps {
  entities: EntityNode[]
  orgName: string
}

The component:
- Builds a tree from the flat entities array using a recursive buildTree() function
- Renders as an indented list:
  Root node = orgName at top with a small building/org icon (use an SVG or lucide icon)
  Each entity = indented row with entity name + type badge
- Connecting lines: border-l border-border ml-4 pl-3 on the children container
- Type badge colours:
    subsidiary → bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300
    branch     → bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300
    holding    → bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300
    associate  → bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300
    default    → bg-muted text-muted-foreground
- Empty state: when entities array is empty or all names are blank, show:
    "Add your first entity to see the structure"
    in text-sm text-muted-foreground text-center py-8
- Purely derived from props — no API calls, no useEffect data fetching
- Updates on every keystroke via react-hook-form watch()

STEP 3 — Wire into Step2Entities.tsx:
Change the layout to a two-column grid on lg+:

  <div className="grid lg:grid-cols-[1fr_260px] gap-6 items-start">
    <div>{/* existing form JSX — unchanged */}</div>
    <div className="hidden lg:block sticky top-6">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
        Structure preview
      </p>
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <EntityTreePreview
          entities={watchedEntities}
          orgName={orgName}
        />
      </div>
    </div>
  </div>

watchedEntities: use react-hook-form watch() on the entity array field.
Map the watched values to EntityNode[] — use the actual field names from Step 1.

orgName: find how the org name is passed into or available in Step2Entities.
Check OrgSetupPageClient for how it passes data between steps.
If orgName is not directly available, use "Your organisation" as a fallback.

STEP 4 — Handle the case where entities have no parentId (flat list):
Render them all as direct children of the root org node.
Do not crash if parentId is undefined, null, or an empty string.

STEP 5 — Run npx tsc --noEmit and fix any TypeScript errors.

RULES:
- "use client" directive on EntityTreePreview.tsx — it reads from props derived from watch()
- The right panel is hidden on mobile (hidden lg:block) — must not affect mobile layout
- The existing form fields, validation, and mutation logic must not change at all
- EntityNode interface must match the actual form field shape — confirm field names in Step 1
- No new npm packages — use only what is already installed
```

---

## Prompt 2 of 2 — #33 — aria-live on loading states
**Priority:** P2 | **Effort:** S | **Tool:** Claude Code or Codex

```
You are working in the Finqor frontend codebase at D:\finos\frontend.

TASK: Add aria-live and aria-busy announcements to loading states across module pages
so screen readers announce when data is loading and when it has arrived.

STEP 1 — Read these files before making any changes:
- components/ui/TableSkeleton.tsx
- components/ui/EmptyState.tsx
- app/(dashboard)/mis/PageClient.tsx
- app/(dashboard)/reconciliation/gl-tb/PageClient.tsx
- app/(dashboard)/dashboard/kpis/PageClient.tsx
- app/(dashboard)/reconciliation/payroll/PageClient.tsx
- app/(dashboard)/dashboard/HomePageClient.tsx
- app/(auth)/orgs/PageClient.tsx

STEP 2 — Update components/ui/TableSkeleton.tsx:
Add a visually hidden screen-reader announcement as the first row inside the tbody:

  <tr className="sr-only">
    <td aria-live="polite" aria-atomic="true">Loading data, please wait.</td>
  </tr>

Confirm TableSkeleton already wraps output in <tbody> — if not, add it.

STEP 3 — Update components/ui/EmptyState.tsx:
Add role="status" to the outer div so screen readers announce when an empty state appears:

  <div role="status" className={cn("flex flex-col items-center ...", className)}>

STEP 4 — Apply aria-busy and aria-live to table wrapper divs in these files.
For each file, find the div that wraps the <table> element and add:

  <div
    role="region"
    aria-label="[descriptive label]"
    aria-busy={isLoading}
    aria-live="polite"
  >
    <table>...</table>
  </div>

Use these aria-label values:
- mis/PageClient.tsx            → aria-label="MIS report data"
- gl-tb/PageClient.tsx          → aria-label="GL/TB reconciliation data"
- kpis/PageClient.tsx           → aria-label="KPI data"
- payroll/PageClient.tsx        → aria-label="Payroll reconciliation data"

STEP 5 — Update app/(dashboard)/dashboard/HomePageClient.tsx:
The home screen has 3 independent metric card sections that load in parallel.
Add aria-busy={isLoading} independently to each section's wrapper div:
- Pending approvals section: aria-busy={approvalsQuery.isLoading} aria-live="polite"
- ERP sync section:          aria-busy={connectorsQuery.isLoading} aria-live="polite"
- Anomalies section:         aria-busy={anomaliesQuery.isLoading} aria-live="polite"

Use the actual query variable names from the file — confirm them in Step 1.

STEP 6 — Update app/(auth)/orgs/PageClient.tsx:
Find the skeleton grid. Change aria-busy="true" (hardcoded) to:
  aria-busy={loadState === "loading"}

Confirm the exact state variable name — it may be loadState, state, status, or similar.
Read the file in Step 1 and use the real variable name.

STEP 7 — Run npx tsc --noEmit and fix any TypeScript errors.
Run npx playwright test --project=chromium and confirm no regressions.

RULES:
- aria-live="polite" only — never "assertive" for data loading
- aria-busy must be a boolean expression, never the string "true" or "false"
- The sr-only row in TableSkeleton must be inside <tbody>
- Do not add aria-live to decorative skeleton divs — only table regions and status containers
- Do not change any visual styling — accessibility attributes only
```

---

*After both prompts are complete:*
*Run: `npx playwright test --project=chromium`*
*Then deploy to staging and run: `npx playwright test` (all 3 browsers)*
*The 52 backend-dependent tests should clear with a live backend.*
