# Finqor Frontend Tech-Debt Audit — Pre-Onboarding

**Date:** 2026-04-25  
**Commit:** `6afac67` (Merge branch 'feat/phase1-sidebar-structure' into main)  
**Tag:** `v4.2.0-phase0-complete` + 3 commits  
**Auditor:** Claude Code (read-only, evidence-based)  
**Mode:** All findings are evidence-based; speculation is labeled as such.

---

## Executive Summary

| Severity | Count | Examples |
|---|---|---|
| Critical | 0 | — |
| Major | 8 | Test colocation 4%, deprecated store fields in prod-path code, 80% client components, 7 oversized page components |
| Minor | 7 | 6 pages missing metadata, 4 inline query keys, no AbortController, 94 hardcoded hrefs |
| Info | 5 | Build 282 kB max, staleTime 10 s, sonner-only toast, 0 native `<img>` tags, 1 hydration suppression |

**Onboarding readiness: YELLOW**

The app compiles, typechecks, and builds cleanly — no hard blockers. Three Major items deserve attention before first real-user cohort: (1) test coverage is too thin to catch regressions confidently (4% component colocation, no coverage thresholds), (2) deprecated Zustand fields are still being written and read in the production API client path, and (3) the 80% client-component ratio will complicate bundle optimisation as the codebase grows. None of these would crash the app today, but they create significant risk surface as more code ships on top of them.

**Phase 1 plan:** Stands as-written. No scope changes needed. Two pre-onboarding hotfix items are identified at the bottom of this report.

---

## Findings by Dimension

---

### Dimension 1 — Build, Typecheck, Lint Health

#### 1.1 Typecheck — PASS
```
npx tsc --noEmit
exit code: 0
output: (none)
```
Zero TypeScript errors on `main` at commit `6afac67`.

#### 1.2 Lint — PASS (pre-existing warnings only)
```
npm run lint
Errors:   0
Warnings: 11
```
All 11 warnings are `react-hooks/exhaustive-deps`, all pre-existing (FU-004). The dominant pattern (7 of 11) is a logical expression used as a dependency of `useMemo`/`useEffect` that should itself be memoised first. Files:
- `board-pack/_hooks/useBoardPack.ts` — 3 warnings
- `reports/_hooks/useReports.ts` — 1
- `scheduled-delivery/_hooks/useDeliveries.ts` — 1
- `settings/cost-centres/PageClient.tsx` — 1
- `statutory/PageClient.tsx` — 1
- `control-plane/admin/tenants/[id]/PageClient.tsx` — 1
- `components/control-plane/pages/ControlPlaneIntentsPage.tsx` — 1
- `components/control-plane/pages/ControlPlaneJobsPage.tsx` — 1
- `components/layout/EntityLocationSelector.tsx` — 1

No new warnings were introduced by Phase 1 sub-prompt 1.1.

#### 1.3 Build Size and Bundle — PASS (within threshold)
```
✓ Compiled successfully
✓ Generating static pages (128/128)
Total routes: ~167 (128 static ○, 39+ dynamic ƒ)
Shared First Load JS: 87.7 kB
```

| Route | First Load JS |
|---|---|
| `/advisory/fdd/[id]/report` | 282 kB |
| `/forecast/[id]` | 271 kB |
| `/scenarios/[id]` | 269 kB |
| `/treasury/[id]` | 268 kB |
| `/budget/[year]` | 267 kB |
| `/working-capital` | 266 kB |

Maximum is 282 kB — below the 300 kB Major threshold. No "exceeds recommended size" warnings emitted by Next.js. The shared chunk (87.7 kB) is healthy.

#### 1.4 Dead Exports / Unused Code — Indeterminate
Neither `ts-prune` nor `knip` is installed. No dead-code analysis performed. **Recommended:** Add `knip` to devDependencies and run as part of CI in Phase 5.

---

### Dimension 2 — Test Infrastructure

#### 2.1 Test Count — Info (tracking against baseline)
```
Unit test files (.test.ts / .test.tsx):  30
E2E spec files (.spec.ts):               16 (15 in tests/e2e/, 1 in tests/)
__tests__ directories:                    2
Total unit test cases:                  187 (182 pass, 5 fail — all known)
```
Phase 0 baseline per prompt: 178 unit test cases, 77 e2e test cases (cases, not files). Current unit count: 187 (+9 from Phase 1.1). E2E file count is 16; individual e2e test case count was not measured (requires Playwright — indeterminate here).

#### 2.2 Test Pass Rate — PASS (all failures are known baseline)
```
Test Files:  4 failed | 26 passed (30)
Tests:       5 failed | 182 passed (187)
Runtime:     10.60 s
```
Failed tests:
| Test file | Failing test | Known? |
|---|---|---|
| `tests/unit/control_plane_shell.test.tsx` | renders shell context from backend-confirmed… | FU-010 |
| `tests/unit/control_plane_state.test.tsx` | keeps module visibility dependent on backend context | FU-010 |
| `tests/unit/control_plane_panels.test.tsx` | opens the job panel from the top bar and renders failed jobs | FU-010 |
| `tests/unit/onboarding_wizard.test.tsx` | moves through backend-driven onboarding steps | FU-007 |
| `tests/unit/onboarding_wizard.test.tsx` | does not mark uploaded data as admitted without… | FU-007 |

All 5 failures match the pre-existing FU-007 + FU-010 baseline. No new test failures introduced.

#### 2.3 Coverage — **MAJOR** (F1)
`vitest.config.ts` has a `test:coverage` script but no `coverage` block, no thresholds, and no provider configured. Running `npm run test:coverage` produces per-file line counts but **no threshold enforcement**. Any coverage percentage is accepted.

**Evidence:**
```ts
// vitest.config.ts — no coverage: {} block
test: {
  environment: "jsdom",
  globals: true,
  setupFiles: ["./vitest.setup.ts"],
  include: ["**/*.test.ts", "**/*.test.tsx"],
  ...
}
```
Without thresholds, coverage provides no safety net. A 20% regression would not fail CI.  
**Recommended phase:** Phase 1 or FU (low-effort config change).

#### 2.4 Test Colocation — **MAJOR** (F2)
```
Component .tsx files:              226
Component files with a test file:   ~9  (7 in components/ui/, 2 in components/layout/)
Colocation ratio:                    ~4%
```
The 50% target from this audit's criteria is not met. The well-tested areas are:
- `components/ui/`: 7 test files covering ConfirmDialog, Dialog, FormField, Sheet, SortableHeader, StatusBadge, StepIndicator
- `components/layout/`: 2 test files (Sidebar render + nav-config — both new from Phase 1.1)

Completely untested component directories: `admin/`, `advisory/`, `budget/`, `covenants/`, `forms/`, `journals/`, `mis/`, `onboarding/` (OnboardingWizard — 512 lines, no test), `sync/`, `working-capital/`, `white_label/`, and most of `control-plane/`.

**Recommended phase:** Ongoing; prioritise the business-critical components in Phase 3+.

---

### Dimension 3 — Accessibility

#### 3.1 Landmark Integrity — PASS
```
<main> occurrences: 6 locations, all in distinct layout files
  app/(dashboard)/layout.tsx:86         — dashboard shell
  app/(marketing)/layout.tsx:24         — marketing shell
  app/(org-setup)/layout.tsx:13         — onboarding shell
  app/not-found.tsx:5                   — 404 page
  app/page.tsx:56                       — landing page
  components/control-plane/ControlPlaneShell.tsx:63 — control-plane shell

<nav>    tags: 8    <header>  tags: 73    <aside>   tags: 7
```
Each `<main>` lives in a distinct layout — no page renders duplicate `<main>` elements. All `<main>` elements carry `id="main-content"` for skip-link compatibility. The 73 `<header>` count reflects card headers and section headers inside components, not `<header role="banner">` — no concern. Landmark structure is sound.

#### 3.2 Aria-label Coverage — Minor concern
```
aria-label occurrences:  72
<button> occurrences:    76
```
The near-parity is suspicious: buttons that contain only icon components (no visible text) require `aria-label`. The audit prompt's icon-only button scan found that most identified buttons do carry `aria-label` (collapse toggle, sign-out, settings, mobile actions). However the 4-label gap indicates a small number of unlabeled buttons remain. No Critical finding, but spot-checks revealed no systemic gap.

#### 3.3 Image Alt-Text — PASS
```
Native <img> tags:  0
Next/Image usages:  1
```
Zero native `<img>` elements. The single `<Image>` component should be verified for `alt` but is not a systemic gap.

#### 3.4 Color Contrast — PASS
```
text-gray-400 / text-zinc-400 / text-neutral-400:  2 occurrences
```
Only 2 low-contrast class instances — well below the 20 threshold. Not a concern.

#### 3.5 Keyboard Navigation — Minor (F3, minor)
```
onKeyDown / onKeyPress handlers:  10
Positive tabIndex:                 3
```
Most interactive components (dialogs, dropdowns, tooltips, command palette) rely on Radix UI primitives that handle keyboard navigation internally. However, the custom sidebar group collapse buttons and the new collapsible group headers in Phase 1.1 do not have `onKeyDown` handlers for `Enter`/`Space` activation beyond the browser default for `<button>` elements (which is correct). The 10 explicit keyboard handlers are concentrated in `CommandPalette`, `EntityLocationSelector`, and `Topbar`. No systemic gap; Radix covers the critical surfaces.

#### 3.6 Focus Indicators — PASS
```
focus:ring / focus-visible occurrences: 13
focus:outline-none occurrences:          1
```
The single `focus:outline-none` at `SidebarNavItem.tsx:98` targets the star-pin button's `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring` pattern — it suppresses the outline but immediately replaces it with a ring. Net effect is correct.

---

### Dimension 4 — Performance

#### 4.1 Image Optimization — PASS
Zero native `<img>` elements in app/ or components/. No optimization gap.

#### 4.2 Server vs Client Component Balance — **MAJOR** (F4)
```
components/ directory:
  Total .tsx files:           226
  Files with "use client":    181  (80.1%)
  Files without (server):      45  (19.9%)

app/ directory:
  Total .tsx/.ts files:       369
  Files with "use client":    178  (48.2%)
```
80% of the `components/` directory is client-side. The threshold for Major is 80%; this is exactly at the boundary. Key observations:
- Shadcn primitives (`tooltip.tsx`, `skeleton.tsx`, `popover.tsx`, `table.tsx`, `input.tsx`) correctly have no `"use client"` — they're pure markup.
- The majority of client marking is legitimate: components that read from Zustand stores, use `usePathname`, or manage local state must be client components.
- A non-trivial number of components may be client-marked speculatively (not verified per file — indeterminate without per-file audit).
- This ratio makes Server Component adoption and bundle reduction harder in later phases.

**Recommended phase:** Phase 5 — audit `"use client"` usage as part of global UX polish.

#### 4.3 Heavy Imports — PASS
```
Moment.js: 0 imports
Lodash (whole-package): 0 imports
```
No heavy bundle imports found.

#### 4.4 React Query staleTime Defaults — Info
```
// app/providers.tsx:14-17
defaultOptions: {
  queries: {
    staleTime: 10_000,          // 10 seconds
    refetchOnWindowFocus: false,
    retry: shouldRetryQuery,
    retryDelay: queryRetryDelay,
  },
```
10 s staleTime with `refetchOnWindowFocus: false` is a reasonable default for a financial app where stale data is preferable to excessive API load. Several dashboard queries override this with 30 s or 60 s. No concern.

#### 4.5 Hydration Mismatches — PASS
```
suppressHydrationWarning occurrences: 1
  app/layout.tsx:28  →  <html lang="en" className="dark" suppressHydrationWarning>
```
The single instance is the canonical pattern for dark-mode class hydration. Legitimate; not a code smell.

---

### Dimension 5 — State Management Discipline

#### 5.1 Zustand Store Inventory

| Store file | Manages | Type | Status |
|---|---|---|---|
| `workspace.ts` | orgId, entityId, moduleId, period, sidebarCollapsed | Workspace | ✅ Canonical (Phase 0 goal) |
| `ui.ts` | sidebarOpen, density, notifications, billingWarning, pinnedModules | UI prefs | ⚠️ Contains deprecated fields (FU-005) |
| `tenant.ts` | tenant_id, tenant_slug, org_setup_complete, entity_roles | Identity/session | ⚠️ Contains deprecated fields (FU-005) |
| `controlPlane.ts` | Panel open/close state, intent state | Feature (admin) | ✅ Clean |
| `displayScale.ts` | Display scale preference, currency, locale | Display prefs | ✅ Clean |
| `location.ts` | active_location_id | Feature | ✅ Clean |
| `theme.ts` | theme: light/dark/system | Display prefs | ✅ Clean |

**`workspace.ts` is THE single workspace store** — Phase 0 goal achieved. No split-brain on the canonical path. ✅

**Deprecated fields still live — MAJOR (F5):**

`ui.ts` carries three fields marked `@deprecated` that still have live callers in production code:
```ts
// lib/store/ui.ts:8-11
/** @deprecated Read from useWorkspaceStore.sidebarCollapsed instead. */
sidebarCollapsed: boolean
/** @deprecated Read from useWorkspaceStore.period instead. */
activePeriod: string
/** @deprecated Call useWorkspaceStore.toggleSidebar instead. */
toggleSidebarCollapsed: () => void
```

`tenant.ts` carries two deprecated fields with callers across 5+ production files:
```ts
// lib/store/tenant.ts:13
/** @deprecated Read from useWorkspaceStore.entityId instead. */
active_entity_id: string | null
```

The critical call site is the **API client itself**:
```ts
// lib/api/client.ts:224
active_entity_id: tenantState.active_entity_id,
```
This reads the deprecated `active_entity_id` from `tenantStore` and passes it to the backend on every 400-triggered `setTenant` call. If `active_entity_id` diverges from `workspaceStore.entityId` (possible once Phase 2 ships multi-entity switching), this will silently send stale entity context to the backend.

**Other deprecated callers:**
- `app/(auth)/login/PageClient.tsx:213, 301`
- `app/(auth)/mfa/PageClient.tsx:114`
- `app/(auth)/mfa/setup/PageClient.tsx:181`
- `app/(org-setup)/org-setup/OrgSetupPageClient.tsx:115, 122`
- `components/control-plane/ControlPlaneTenantBootstrap.tsx:33`
- `components/layout/Sidebar.tsx:80`

These are all `setTenant(...)` calls that pass `active_entity_id` — writing the deprecated field, not reading it. The risk is lower here since writes just populate a field that may be stale; the dangerous pattern is the **read** in `client.ts`.

**Recommended phase:** FU-005 (already tracked). Prioritise the `client.ts` read as a pre-onboarding hotfix.

#### 5.2 Query Key Consistency — PASS
```
Inline queryKey literals (not using factory):  4
  hooks/useSync.ts:73   queryKey: ["sync-connections", version]
  hooks/useSync.ts:89   queryKey: ["sync-runs", connectionId, version]
  hooks/useSync.ts:121  queryKey: ["sync-run", id, version]
  hooks/useSync.ts:168  queryKey: ["sync-drift", syncRunId, version]
```
4 inline literals — well below the 15 Major threshold. All 4 are isolated in `hooks/useSync.ts`. Phase 0's query-key factory migration (194 sites) is holding. The 4 remaining literals are candidates for FU-001/002 cleanup.

#### 5.3 useState Counts — PASS
```
Top components by useState count:
  white_label/BrandingEditor.tsx:       6
  white_label/DomainConfig.tsx:         5
  components/layout/Topbar.tsx:         4 (profileOpen, mobileActionsOpen, etc.)
```
No component reaches the 8-useState threshold. No useReducer candidates identified.

---

### Dimension 6 — API Contract & Error Handling

#### 6.1 Error Boundaries — PASS (with minor gaps)
`app/(dashboard)/error.tsx` exists at the **root dashboard segment** — any uncaught render error in any dashboard route will be caught. Additionally, per-route error.tsx files exist for:
`advisory`, `audit`, `board-pack`, `close`, `consolidation`, `expenses`, `fixed-assets`, `forecast`, `reconciliation`, `reports`, `scenarios`, `scheduled-delivery`, `statutory`, `tax`, `transfer-pricing`, `treasury`.

**Minor gap:** No `error.tsx` in:
- `app/(dashboard)/settings/airlock/` — Airlock page errors would bubble to root dashboard boundary (acceptable but non-specific)
- `app/(dashboard)/settings/control-plane/` — same
- `@modal` parallel route pages — inherently hard to error-boundary separately

The root-level `app/(dashboard)/error.tsx` prevents white-screens. Granular error boundaries in the missing segments would improve user messaging but are not Critical.

#### 6.2 Loading States — PASS
```
loading.tsx files: 15
  app/(auth)/loading.tsx
  app/(dashboard)/loading.tsx                     ← root dashboard
  app/(dashboard)/advisory/loading.tsx
  app/(dashboard)/board-pack/loading.tsx
  app/(dashboard)/expenses/loading.tsx
  app/(dashboard)/forecast/loading.tsx
  app/(dashboard)/gaap/loading.tsx
  app/(dashboard)/notifications/loading.tsx
  app/(dashboard)/reconciliation/loading.tsx
  app/(dashboard)/reports/loading.tsx
  app/(dashboard)/scenarios/loading.tsx
  app/(dashboard)/scheduled-delivery/loading.tsx
  app/(dashboard)/statutory/loading.tsx
  app/(dashboard)/treasury/loading.tsx
  + journals/loading.tsx
```
Root `app/(dashboard)/loading.tsx` covers all routes without a specific loading file. Coverage is adequate.

#### 6.3 Toast / Notification — PASS
```
Toast library: sonner (single library)
  toast() import: from "sonner" — consistent across all callers
  Toaster mount: app/layout.tsx:3
```
No mixed toast libraries. Sonner is the single implementation. ✅

#### 6.4 API Error Mapping — PASS (with a note)
`lib/api/client.ts` contains a typed `ApiValidationError` class and an Axios response interceptor that maps HTTP status codes (400, 403, 404, 422, 500+) to structured errors. The interceptor propagates errors via `Promise.reject` for all non-2xx cases.

`lib/api/auth-unauthorized.ts:46` has a bare `catch {}` block that silently swallows errors in the auth-recovery flow — this is intentional (best-effort recovery) but worth noting.

#### 6.5 Fetch Abort Handling — **Minor** (F6)
```
AbortController instances in lib/api/:  0
signal: parameter usages in lib/api/:  0
```
No API calls pass an `AbortSignal`. For short-lived queries this is acceptable, but several operations are long-running (consolidation runs, board-pack generation, AI narrative generation). Without abort signals:
- Navigating away from a consolidation page does not cancel the in-flight request
- Multiple rapid re-renders of a query component will accumulate stale responses

This is a Minor finding now but will become more visible in Phase 3+ when the module system drives more concurrent queries. Recommend wiring `signal` via TanStack Query's built-in `queryFn` `signal` parameter in Phase 5.

---

### Dimension 7 — Component Architecture

#### 7.1 Component Size Distribution — **MAJOR** (F7, 7 files)
```
Top 15 by line count (components/ and app/ combined):
  744  app/control-plane/admin/plans/PageClient.tsx         ← MAJOR (>500)
  661  app/(dashboard)/fixed-assets/PageClient.tsx          ← MAJOR (>500)
  627  app/(dashboard)/invoice-classify/PageClient.tsx      ← MAJOR (>500)
  576  app/control-plane/admin/credits/PageClient.tsx       ← MAJOR (>500)
  526  app/(auth)/login/PageClient.tsx                      ← MAJOR (>500)
  512  components/onboarding/OnboardingWizard.tsx           ← MAJOR (>500)
  511  components/control-plane/bodies/IntentBody.tsx       ← MAJOR (>500)
  489  app/(dashboard)/prepaid/PageClient.tsx
  483  tests/unit/onboarding_wizard.test.tsx  (test file — not a component concern)
  480  app/(dashboard)/settings/locations/PageClient.tsx
  475  components/control-plane/bodies/JobBody.tsx
  470  app/(dashboard)/settings/chart-of-accounts/PageClient.tsx
  462  app/(dashboard)/[orgSlug]/[entitySlug]/accounting/journals/new/PageClient.tsx
  456  app/(dashboard)/close/PageClient.tsx
  424  components/layout/Topbar.tsx
```

7 components exceed 500 lines. None exceed 1000 (the Critical threshold). All are `PageClient` components (collocated page-level client components) or wizard/panel bodies. Typical split: data-fetching + state + rendering in one file. None are architectural primitives, so the blast radius of a split is low.

**Notable:** `OnboardingWizard.tsx` at 512 lines is a component in `components/onboarding/` (not a page), making it the most in-need of extraction.

#### 7.2 Prop Drilling Depth — Pass (no concern identified)
Spot-check of `fixed-assets/PageClient.tsx` (661 lines): uses hooks directly (`useTenantStore`, `useWorkspaceStore`, `useQueryClient`) with no prop-passed state from parent. No prop-drilling chain observed for the largest files. Component isolation via hook consumption is the dominant pattern.

#### 7.3 Duplicate Component Patterns — PASS
```
UI primitives in components/ui/:
  button.tsx       — 1 (shadcn)
  input.tsx        — 1 (shadcn)
  Dialog.tsx       — 1 (custom wrapper over shadcn Dialog)
  Sheet.tsx        — 1
  skeleton.tsx     — 1 (shadcn)
```
No duplicate Button/Input/Modal implementations found. The custom `Dialog.tsx` wraps Radix (not a duplicate of shadcn's dialog). ✅

#### 7.4 Inline Styles vs Tailwind — PASS
```
style={{ }} occurrences in components/:  11
```
11 is well below the 30 Minor threshold. Post-Phase-1.1 the sidebar uses intentional inline styles for pixel-exact widths (`style={{ width: sidebarCollapsed ? "52px" : "220px" }}`), which is the correct approach for the audit's requirement. No concern.

#### 7.5 Magic Hex Color Codes — **MAJOR** (F8)
```
6-digit hex codes in components/ + app/:  42
```
Sample of the 42 occurrences:
```tsx
// components/admin/BenchmarkChart.tsx:21
const COLORS = ["#60A5FA", "#34D399", "#F59E0B", "#A78BFA", "#FB7185"]

// components/covenants/CovenantGauge.tsx:26
status === "pass" ? "#22c55e" : status === "near_breach" ? "#f59e0b" : "#ef4444"

// components/advisory/ppa/AllocationWaterfall.tsx:31-35
{ fill: "#60A5FA" }, { fill: "#34D399" }, { fill: "#F59E0B" }, ...
```

The hex usage splits into two categories:
1. **Chart/visualization colors** (~35 instances) — hardcoded Recharts fill/stroke values. These are commonly hardcoded in chart libraries; mapping them to CSS variables requires custom Recharts configuration. Acceptable but non-ideal for theme consistency.
2. **Status/semantic colors** (~7 instances, e.g., `CovenantGauge.tsx`) — green/amber/red status colors that *should* be theme tokens (e.g., `text-green-500`, `hsl(var(--brand-success))`). These bypass the design system.

The semantic status colors are the Major concern; the chart fill arrays are Minor. Both should be addressed in Phase 5 (Global UX Polish).

---

### Dimension 8 — Routing & Information Architecture

#### 8.1 Route Inventory & Metadata — Minor (F9)
```
Total page.tsx files:          165
Pages with metadata:           159  (96.4%)
Pages missing metadata:          6
```
Missing metadata pages:
| Page | Reason / Note |
|---|---|
| `app/(dashboard)/settings/airlock/page.tsx` | Settings sub-route |
| `app/(dashboard)/settings/airlock/[id]/page.tsx` | Dynamic settings sub-route |
| `app/(dashboard)/settings/control-plane/page.tsx` | Admin settings sub-route |
| `app/(dashboard)/[orgSlug]/[entitySlug]/accounting/journals/@modal/(.)new/page.tsx` | Parallel route (modal intercept — metadata less relevant) |
| `app/(dashboard)/[orgSlug]/[entitySlug]/accounting/journals/@modal/(.)[id]/page.tsx` | Parallel route (modal intercept — metadata less relevant) |
| `app/control-plane/page.tsx` | Control-plane root |

The two `@modal` parallel route pages are intercepted routes; their metadata is effectively irrelevant (they render inside the parent page's tab/title context). The 4 real gaps are: `airlock`, `airlock/[id]`, `settings/control-plane`, and `control-plane` root. Minor; Phase 5.

#### 8.2 Orphaned Routes — Not fully measured
A systematic orphan-route analysis (grep for each of 165 routes across the codebase) was out of scope for a single audit pass. The Phase 1.1 nav-config introduces 6 placeholder routes (all pointing to `/dashboard`); those are intentional placeholders, not orphans. Full orphan analysis recommended for Phase 5.

#### 8.3 Hardcoded URLs — Minor (F10)
```
Hardcoded href="/..." occurrences in components/ + app/:  94
lib/routes.ts or lib/constants.ts:                        NOT FOUND
```
94 hardcoded path strings with no centralised route constants file. This is just below the 100 Major threshold. Most are in `nav-config.ts` (new), `Sidebar.tsx`, `Topbar.tsx`, and various page links — expected given the app's stage. Risk: renaming a route (e.g., `/audit` → `/governance/audit` in Phase 2) requires a multi-file grep/replace. A `lib/routes.ts` constants file would mitigate this.

**Recommended phase:** Phase 3 or FU (low-effort; file a FU before the first route rename in Phase 2).

#### 8.4 RBAC Route Protection — PASS (with a Phase 2 note)
```
// middleware.ts — server-side guards:
/admin/*        → platform_owner, platform_admin, super_admin, admin only
/control-plane/* → same
/trust/*        → finance_leader only
```
The most sensitive routes (`/admin`, `/control-plane`) are guarded at the **middleware level** — not client-side-only. An unauthenticated or under-privileged user hitting `/admin/rbac` directly will be redirected server-side before any React renders.

**Phase 2 note:** The Phase 1.1 nav items that will eventually resolve to `/governance/audit` and `/settings/team` do not yet have middleware guards. Since all those routes currently resolve to placeholder `/dashboard` hrefs, this is not a current gap — but it must be addressed when those routes are created in Phase 2/3.

---

## Triage Table

| ID | Sev | Dim | Title | Evidence | Recommended |
|---|---|---|---|---|---|
| F1 | Major | 2.3 | Coverage thresholds unconfigured | `vitest.config.ts` has no `coverage:` block | FU or Phase 1 (low-effort) |
| F2 | Major | 2.4 | Test colocation at 4% | 9 test files for 226 components | Ongoing — Phase 3+ priority |
| F3 | Minor | 3.5 | Low explicit keyboard handler count | 10 handlers for complex app | Phase 5 — verify Radix coverage |
| F4 | Major | 4.2 | 80% client component ratio | 181 of 226 components use client | Phase 5 audit |
| F5 | Major | 5.1 | Deprecated store fields in production-path code | `client.ts:224` reads `tenantStore.active_entity_id`; 8 files still write it | **Pre-onboarding hotfix** for `client.ts` read; FU-005 for writes |
| F6 | Minor | 6.5 | No AbortController in API layer | grep returns 0 in lib/api/ | Phase 5 |
| F7 | Major | 7.1 | 7 components > 500 lines | plans/PageClient 744 L, fixed-assets 661 L, invoice-classify 627 L, OnboardingWizard 512 L + 3 more | Phase 3/5 splits |
| F8 | Major | 7.5 | 42 hex literals; semantic status colors bypass tokens | CovenantGauge, BenchmarkChart, AllocationWaterfall | Phase 5 |
| F9 | Minor | 8.1 | 6 pages missing metadata | airlock, airlock/[id], settings/control-plane, @modal ×2, control-plane root | Phase 1 sub-prompt 1.4 or FU |
| F10 | Minor | 8.3 | 94 hardcoded hrefs; no lib/routes.ts | grep count; `ls lib/routes*` fails | Before first route rename in Phase 2 |
| F11 | Info | 1.3 | Max bundle 282 kB | build output | Monitor in Phase 3+ |
| F12 | Info | 4.4 | staleTime 10 s default | providers.tsx:16 | Acceptable for financial app |
| F13 | Info | 6.3 | Sonner-only toast | imports confirm single library | No action needed |
| F14 | Info | 3.3 | 0 native img tags | grep = 0 | No action needed |
| F15 | Info | 4.5 | 1 hydration suppression on html tag | app/layout.tsx:28 — legitimate dark-mode pattern | No action needed |

---

## Phase Plan Adjustments Recommended

**Phase 1 plan stands as-written.** No scope changes are warranted by this audit. All Critical slots are empty. The Major findings are either long-term debt (7.1, 7.5, 4.2, 2.4) or already-tracked FU items (5.1/FU-005, 2.3).

Specific observations for the current Phase 1 sub-prompts:

- **1.2 (TopBar):** No issues found in the TopBar that would change the planned work.
- **1.3 (ModuleTabs):** No issues found that affect scope.
- **1.4 (Metadata sweep):** F9 (6 pages missing metadata) is already in Phase 1's scope — the 4 real gaps (airlock, airlock/[id], settings/control-plane, control-plane root) should be included in 1.4's sweep.
- **1.5 (Exit gate):** The exit gate should verify F1 (coverage thresholds) is addressed before Phase 2 begins.

---

## Pre-Onboarding Hotfix Recommendations

These two items should be addressed before any real user touches the app, regardless of phase assignment:

### Hotfix 1 — Align `active_entity_id` read in API client (F5, risk: silent entity context mismatch)

**File:** `frontend/lib/api/client.ts:224`  
**Issue:** The Axios error interceptor reads `tenantStore.active_entity_id` (deprecated) when re-calling `setTenant` after an org-setup redirect. This field is populated at login and does not update when the user switches entities via `workspaceStore.switchEntity`. In Phase 2 (multi-entity switching), this will silently send stale entity IDs to the backend during error recovery.  
**Fix:** Replace `tenantState.active_entity_id` with `useWorkspaceStore.getState().entityId` at that call site.  
**Effort:** < 30 minutes.

### Hotfix 2 — Add coverage thresholds to vitest.config.ts (F1, risk: silent coverage regression)

**File:** `frontend/vitest.config.ts`  
**Issue:** `test:coverage` runs but enforces nothing. Any coverage regression would pass CI silently.  
**Fix:** Add a `coverage` block with minimum thresholds (suggested: statements 40%, branches 35%, lines 40%) as a floor, not a target. Run `npm run test:coverage` once to establish current baseline before setting thresholds.  
**Effort:** < 1 hour.

---

## Verbatim Outputs Appendix

### A1 — Git state
```
Branch: main
HEAD: 6afac67 Merge branch 'feat/phase1-sidebar-structure' into main
Tags: v4.0.0, v4.0.1-clean, v4.0.2-ca-fix, v4.0.3-pooler-tls-fix,
      v4.0.4-render-ssl-fix, v4.1.0, v4.2.0-phase0-complete
Working tree: clean
```

### A2 — Typecheck output
```
npx tsc --noEmit
(no output)
exit code: 0
```

### A3 — Lint output (condensed)
```
Errors:   0
Warnings: 11 (all react-hooks/exhaustive-deps, all pre-existing FU-004)
Files with warnings:
  app/(dashboard)/board-pack/_hooks/useBoardPack.ts (3)
  app/(dashboard)/reports/_hooks/useReports.ts (1)
  app/(dashboard)/scheduled-delivery/_hooks/useDeliveries.ts (1)
  app/(dashboard)/settings/cost-centres/PageClient.tsx (1)
  app/(dashboard)/statutory/PageClient.tsx (1)
  app/control-plane/admin/tenants/[id]/PageClient.tsx (1)
  components/control-plane/pages/ControlPlaneIntentsPage.tsx (1)
  components/control-plane/pages/ControlPlaneJobsPage.tsx (1)
  components/layout/EntityLocationSelector.tsx (1)
```

### A4 — Build output (relevant lines)
```
✓ Compiled successfully
✓ Generating static pages (128/128)
Route (app)                                          Size     First Load JS
+ First Load JS shared by all                        87.7 kB
  ├ chunks/2117-f83c949819615634.js                  31.9 kB
  ├ chunks/fd9d1056-def3aac4257a2603.js              53.6 kB
  └ other shared chunks (total)                       2.15 kB

Top 6 by First Load JS:
  /advisory/fdd/[id]/report    282 kB
  /forecast/[id]               271 kB
  /scenarios/[id]              269 kB
  /treasury/[id]               268 kB
  /budget/[year]               267 kB
  /working-capital             266 kB
```

### A5 — Test run output
```
Test Files:  4 failed | 26 passed (30)
Tests:       5 failed | 182 passed (187)
Start at:    21:40:20
Duration:    10.60s (transform 3.33s, setup 3.65s, import 17.13s,
                     tests 14.03s, environment 46.80s)

FAIL tests/unit/control_plane_panels.test.tsx   (FU-010)
FAIL tests/unit/control_plane_shell.test.tsx    (FU-010)
FAIL tests/unit/control_plane_state.test.tsx    (FU-010)
FAIL tests/unit/onboarding_wizard.test.tsx × 2  (FU-007)
```

### A6 — Key grep counts (reference)
```
"use client" in components/:         181 / 226 tsx files = 80.1%
aria-label occurrences:              72
<button> occurrences:                76
<main> occurrences:                   6 (all in distinct layouts)
Inline style={{ }} in components/:   11
Hex 6-digit literals:                42
Inline queryKey: [...] literals:      4 (all in hooks/useSync.ts)
suppressHydrationWarning:             1 (html tag, legitimate)
Native <img> tags:                    0
focus:ring / focus-visible:          13
focus:outline-none:                   1
Pages missing metadata:               6 of 165 (3.6%)
Hardcoded href="/...":               94
Deprecated store field callers:       8 files (across login, mfa, org-setup, Sidebar, client.ts)
```
