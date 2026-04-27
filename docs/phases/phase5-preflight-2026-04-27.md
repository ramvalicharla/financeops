# Phase 5 Pre-flight Planning Document

**Date:** 2026-04-27
**Branch:** `chore/phase5-preflight` (off `main` at `62efa0e`)
**Investigator:** Claude Sonnet 4.6 (read-only Checkpoints 1–6, doc-write only)
**Phase:** Phase 5 — Global UX Polish
**Status:** Pre-flight complete — all OQs include recommendations; no blocking decision required before SP-5A

---

## 1. Baseline Verification

| Check | Value | Status |
|---|---|---|
| Branch | `chore/phase5-preflight` (off `main`) | ✓ |
| HEAD | `62efa0e` — docs: phase 4 close | ✓ |
| Tag at Phase 4 close | `frontend-phase-4` at `62efa0e` | ✓ (confirmed) |
| Working tree | Clean | ✓ |
| Frontend `npm run build` | ✓ — 129 routes, 0 errors | ✓ |
| Frontend `npm run lint` | ✓ — 0 warnings, 0 errors | ✓ |
| Frontend Vitest | **222/224** — FU-007 baseline preserved; 2 known failures unchanged | ✓ no regression |
| Backend pytest (unit + integration key suites) | 41/41 passed (`test_chain_hash`, `test_auth_service`, `test_health`, `test_auth_endpoints`) | ✓ |
| Alembic head | `0146_sidebar_collapsed` — SP-4B migration | ✓ |

**No baseline regressions. Phase 5 may proceed.**

Lint note: FU-004 ("11 pre-existing lint warnings") was filed as Open in `docs/follow-ups/INDEX.md`, but `npm run lint` returns 0 warnings on current `main`. The warnings were resolved during Phase execution but FU-004 was never closed. **Action: close FU-004 in INDEX.md — it is already resolved.**

---

## 2. Locked Findings Table

Findings from `docs/audits/finqor-shell-audit-2026-04-24.md` §3.3 Phase 5 that are not yet resolved and belong to this phase.

| Finding # | Area | Title | Current Status | Phase 5 SP |
|---|---|---|---|---|
| #18 | B | CommandPalette live search — 5 hardcoded nav items, no API search | ⚠️ Partially superseded — `components/search/CommandPalette.tsx` exists with live `searchGlobal()` wiring but is NOT the one rendered by `⌘K` in layout. Old hardcoded palette (`components/layout/_components/CommandPalette.tsx`) is ALSO mounted, causing dual ⌘K handlers (see S-001). | SP-5A |
| #29 | H | 15+ `.toFixed()` bypasses of `formatAmount` | ⚠️ 2 of 15+ fixed (QW-10). ~30 remaining instances across 13+ files. Percentage and file-size displays account for ~10 of these and are out of scope (semantically correct). ~12 financial-amount instances remain. | SP-5B |
| #33 | B | NotificationBell wiring + graceful degradation | ✅ **Resolved at pre-flight start.** Wired to `/api/v1/notifications` via `getUnreadNotificationCount()`. Error path sets count=0 (no badge on failure). `setInterval` at 30s, max 120 attempts. No outstanding work. | Closed |
| #25 | H | `generateMetadata` sweep (residual) | ✅ **Resolved in Phase 1 SP `feat/phase1-metadata-sweep`.** 163/165 pages have metadata; 2 `@modal` intercepts are intentional skips. No outstanding work. | Closed |

**Summary: 2 open findings (#18, #29) + 2 already closed (#33, #25) at pre-flight start.**

Additional findings surfaced during this pre-flight walk (not in original audit doc) are captured in Section 4 (Polish-Gap Walk).

---

## 3. FU Carry-over Status

| FU | Title | Status | Phase 5 action |
|---|---|---|---|
| **FU-007** | Fix onboarding wizard test text mismatches | ⏸ **Unchanged** — 2 Vitest failures are the same FU-007 tests. Not a Phase 5 regression. Pre-existing since Phase 0. | Candidate for SP-5E. Small fix (~30 min), clears the red baseline. |
| **FU-005** | Remove deprecated fields from legacy Zustand stores | ⏸ Open, low priority | Not Phase 5 scope. Pair with any future store-touching sub-prompt. |
| **FU-004** | Address pre-existing lint warnings | ✅ **Already resolved** — `npm run lint` returns 0 warnings. FU-004 was never formally closed. | Close in INDEX.md (SP-5E housekeeping). |
| **FU-011** | TopBar Finqor brand mark + wordmark | ⏸ Open — Finding #15 from audit, deferred at Phase 1 | **Phase 5 candidate (SP-5D).** Frontend-only, UX polish, no backend prereqs. |
| **FU-012** | Sidebar behavioral wiring (badges, RBAC, real routes) | ⏸ Open — Phase 1 deferred | Not Phase 5 scope. RBAC touches belong to Phase 6. |
| **FU-019** | `control_plane_*.test.tsx` pre-existing failures | ⏸ Open | Phase 5 candidate for SP-5E if scope allows. Not blocking. |
| **FU-008** | E2E mockSession sweep (14 specs) | ⏸ Open | Not Phase 5 scope. Low priority. |
| **FU-009** | WebKit Playwright binary | ⏸ Open | Not a Claude task. Deferred indefinitely. |
| **FU-014** | Vitest coverage thresholds | ⏸ Open | Not Phase 5 scope. Deferred. |
| **FU-015** | Remaining `active_entity_id` writers | ⏸ Open | Not Phase 5 scope. Pair with store refactor. |
| **FU-016** | Real user management implementation | ⏸ Open | Not Phase 5 scope. |
| **RBAC alias audit** (`isTenantViewer()`) | Surfaced SP-4A — `"tenant_viewer"` not in `ROLE_ALIASES` as self-alias | ⏸ Low priority | Phase 6 RBAC scope per handoff. Not Phase 5. |

---

## 4. Polish-Gap Walk

Read-only walk of the frontend. Findings classified as ✅ / ⚠️ / 🔴.

### 4.1 Skeleton Loaders

**Dimension:** Consistency across routes, modules, modals. Same component? Flash of nothing?

**Current state:** Root `app/(dashboard)/loading.tsx` exists as a catch-all (shows generic 4-card + 2-column skeleton). 12 of ~40 dashboard route directories have route-specific `loading.tsx` files covering: `advisory`, `board-pack`, `expenses`, `forecast`, `gaap`, `notifications`, `reconciliation`, `reports`, `scenarios`, `scheduled-delivery`, `statutory`, `treasury`. Routes without dedicated loaders: `ai`, `anomalies`, `budget`, `close`, `consolidation`, `covenants`, `dashboard/kpis`, `director`, `erp`, `fixed-assets`, `fx`, `governance`, `invoice-classify`, `marketplace`, `mis`, `partner`, `prepaid`, `search`, `settings`, `signoff`, `sync`, `tax`, `transfer-pricing`, `trial-balance`, `trust`, `working-capital`.

**Gaps:** ~28 routes show the generic 4-card skeleton regardless of their actual content layout. High-traffic routes like `mis`, `trial-balance`, `budget`, `close`, and `consolidation` don't have shape-matched skeletons. A content-mismatch skeleton is better than nothing, but noticeable on slow connections.

**Status:** ⚠️ gap, propose for SP-5C

---

### 4.2 Error States

**Current state:** Root `app/error.tsx` and `app/not-found.tsx` exist. Root `app/(dashboard)/error.tsx` exists as catch-all. 13 route-level `error.tsx` files: `advisory`, `close`, `consolidation`, `expenses`, `fixed-assets`, `forecast`, `governance/audit`, `scenarios`, `statutory`, `tax`, `transfer-pricing`, `treasury`, `[orgSlug]/[entitySlug]/accounting`. All use Next.js `error.tsx` client boundary pattern.

**Gaps:** ~27 dashboard routes have no dedicated error boundary; they fall back to the root `(dashboard)/error.tsx`. For routes with async API calls (most of them), query-level error states depend on individual component handling. No audit of whether every `useQuery` has an error branch was done.

**Status:** ⚠️ gap — low severity since root error boundary catches all unhandled cases, but inconsistent. Not blocking for Phase 5. Log as discovery, propose SP-5C (optional).

---

### 4.3 Empty States

**Current state:** `components/ui/EmptyState.tsx` exists and is well-designed: `icon`, `title`, `description`, `action`, `role="status"`, branded card styling. Used in: `app/(dashboard)/reconciliation/gl-tb/PageClient.tsx`, `components/control-plane/bodies/TimelineBody.tsx`.

**Gaps:** Only 2 usages out of ~40 data-displaying routes. Most list/table pages handle empty state inline (ad-hoc `if (!data.length)` renders with plain text or nothing). No consistent empty-state treatment across modules.

**Status:** ⚠️ gap, propose for SP-5C (sweep of highest-traffic tables)

---

### 4.4 Toast / Notification UX

**Current state:** Sonner via `<Toaster position="bottom-right" richColors duration={4000} />` in root layout. `NotificationBell` polling at 30s intervals, 120-attempt max (60 min window). Error handling degrades to count=0 (no badge). `NotificationPanel` exists with unread count updates. 8 component-level toast invocations confirmed.

**Gaps:** No `aria-live="assertive"` or `role="alert"` on Sonner toasts from the app's wrapper perspective (Sonner uses its own ARIA region internally — acceptable). No SSE push for notification count. Polling strategy is simple and acceptable for current scale.

**Status:** ✅ no blocking gap. Sonner's built-in ARIA is sufficient. Polling is acceptable. SSE upgrade is an OQ (OQ-2).

---

### 4.5 Focus Management on Route Change

**Current state:** Skip-to-content link exists in `app/layout.tsx` — `<a href="#main-content" className="sr-only focus:not-sr-only ...">Skip to main content</a>`. `<main id="main-content">` exists in `app/(dashboard)/layout.tsx:91` inside DashboardShell. No explicit focus-move-to-main-content on client-side navigation (Next.js App Router does not auto-manage focus the same way React Router does).

**Gaps:** Client-side navigation does not programmatically move focus to `#main-content`. Screen readers may announce the full new page from top. This is a known App Router limitation; fixing requires a custom `RouteChangeAnnouncer` or similar pattern.

**Status:** ⚠️ gap — propose for SP-5C as a lightweight fix (add a `RouteAnnouncer` component that moves focus on `pathname` change).

---

### 4.6 Keyboard Shortcuts

**Current state:** `KeyboardShortcutsModal` exists, triggered by `?` key. Lists 4 shortcuts: `Ctrl+K` (palette), `Ctrl+N` (new entry), `Ctrl+/` (search), `?` (help modal). `components/search/CommandPalette.tsx` has live search and registers `Ctrl+K` via `SearchProvider`. `components/layout/_components/CommandPalette.tsx` **also** registers `Ctrl+K` independently — both are mounted simultaneously in `layout.tsx` (see S-001 below). This causes two concurrent `keydown` listeners on `Ctrl+K`.

**Gaps:** 
1. **Dual ⌘K handler conflict** — critical: two separate `CommandDialog` components compete for `Ctrl+K`. Whichever receives the event first opens its dialog; both dialogs try to open simultaneously. 
2. The `Ctrl+N` shortcut in the modal is not actually registered anywhere in code (not found in any `useEffect` / `keydown` listener). The modal advertises a shortcut that doesn't exist.
3. `Ctrl+/` ("search current view") is also not registered.

**Status:** 🔴 gap, blocking polish — SP-5A must fix the dual handler and reconcile the shortcut list.

---

### 4.7 Responsive Breakpoints

**Current state:** DashboardShell uses `md:pl-[52px]` / `md:pl-[220px]` for sidebar offset. Sidebar is fixed (`position: fixed`) at left inset. ModuleTabs uses `overflow-x-auto` for horizontal tab scrolling. Topbar uses `min-w-0` and flex truncation for content overflow. No explicit `min-width` on the shell.

**Gaps:** No minimum supported viewport width is enforced. On viewport widths below ~320px the sidebar and topbar may collide. The spec's minimum supported width was not confirmed in the audit doc. Mobile breakpoints are present (`md:` prefix) but no mobile-first sidebar off-canvas is implemented — at small viewports the sidebar overlaps content.

**Status:** ⚠️ gap — not a Phase 5 target (mobile nav is Phase 2/3 scope per the audit phasing). Log as out of scope.

---

### 4.8 Motion Preferences (`prefers-reduced-motion`)

**Current state:** `Sidebar.tsx` uses `transition-all duration-200` (expand/collapse animation). Multiple nav elements use `transition-colors`, `transition-opacity`, `transition-transform`. No `@media (prefers-reduced-motion: reduce)` block in `app/globals.css`. Tailwind's `motion-safe:` / `motion-reduce:` utility classes are not used. `animate-pulse` on loading skeletons is also not guarded.

**Gaps:** Users who have enabled "Reduce motion" in their OS will still see the sidebar animate in/out and skeleton pulse animations. This fails WCAG 2.1 SC 2.3.3 (Animation from Interactions, AAA) and is a quality bar gap even if not strictly AA.

**Status:** ⚠️ gap, propose for SP-5C — global fix in `globals.css` is one block.

---

### 4.9 Color Contrast

**Spot-check scope:** Brand blue `#185FA5` on card backgrounds (`bg-card`), disabled states, hover-on-hover surfaces, focus rings, muted-foreground text.

**Current state:** Design uses a dark-only theme. `text-muted-foreground` on `bg-card` is the main risk surface — these are typically neutral-600-equivalent tones on dark. `focus-visible:ring-2 focus-visible:ring-ring` focus rings are present on interactive elements. Disabled state uses `opacity-50`.

**Gaps:** Cannot perform pixel-level WCAG contrast check without a browser rendering. `text-muted-foreground` at approximately 60% opacity on dark cards is a known WCAG AA borderline. Flagged as requiring a DevTools pass during SP execution.

**Status:** ⚠️ flag for per-SP spot-check, not a standalone SP.

---

### 4.10 Form UX

**Current state:** `components/ui/FormField.tsx` is fully accessible: `htmlFor` label association, `aria-required`, `aria-invalid`, `aria-describedby` (hint + error), `role="alert"` on error paragraphs, required `*` (aria-hidden). Used in: settings/chart-of-accounts, settings/cost-centres, and a few others.

**Gaps:** Many forms across the app use inline labels without `FormField`. No audit of inline forms was done. Inline validation timing is not consistent — some forms validate on blur, others on submit only.

**Status:** ⚠️ low-severity gap, not a Phase 5 blocker. Recommend adding to SP-5E discovery list.

---

### 4.11 Dark Mode (Polish Dimensions in Dark)

**Current state:** `className="dark"` on `<html>` confirmed ✅. Tailwind dark mode is `class`-based. All CSS variables are dark-mode values only. System light-mode users get dark mode by class (no OS preference leakage).

**Gaps:** None observed.

**Status:** ✅ no gap.

---

### Gap Summary Table

| Dimension | Status | Proposed SP |
|---|---|---|
| Skeleton loaders | ⚠️ ~28 routes lack shape-matched skeletons | SP-5C |
| Error states | ⚠️ ~27 routes fall back to root error boundary | SP-5C (optional) |
| Empty states | ⚠️ `EmptyState` component used in 2 of ~40 routes | SP-5C |
| Toast / notification UX | ✅ Sonner + graceful degradation working | — |
| Focus management on route change | ⚠️ No `RouteAnnouncer` for App Router | SP-5C |
| Keyboard shortcuts (dual ⌘K) | 🔴 Dual handler — blocking polish | SP-5A |
| Keyboard shortcuts (advertised not wired) | ⚠️ `Ctrl+N`, `Ctrl+/` listed but not wired | SP-5A |
| Responsive breakpoints | ⚠️ No mobile nav — out of Phase 5 scope | Defer |
| Motion preferences | ⚠️ No `prefers-reduced-motion` in globals.css | SP-5C |
| Color contrast | ⚠️ Flag for per-SP spot-check | Ongoing |
| Form UX | ⚠️ Inline forms skip `FormField` | SP-5E discovery |
| Dark mode | ✅ Only mode, correctly forced | — |

---

## 5. Proposed Sub-prompt Structure

### SP-5A — CommandPalette Cleanup + ⌘K Reconciliation

**Goal:** Remove the legacy hardcoded `CommandPalette` and make the live-search palette the single ⌘K handler. Reconcile the keyboard shortcut list.

**Findings addressed:** #18 (live search), S-001 (dual handler), Keyboard shortcuts gap

**Files touched:**
- `app/(dashboard)/layout.tsx` — remove import of `components/layout/_components/CommandPalette` and its render; `<SearchProvider>` already provides the live palette
- `components/layout/_components/CommandPalette.tsx` — delete (or archive) this file
- `components/layout/Topbar.tsx` — wire the existing search button to `useSearch().openPalette()` (SearchContext is already in tree)
- `components/ui/KeyboardShortcutsModal.tsx` — remove `Ctrl+N` and `Ctrl+/` entries that are not wired; add `?` self-reference as confirmed entry; optionally add `Ctrl+N` wiring for journals/expenses new entry

**Out of scope:** SSE for notifications, new search backend endpoints (already exist), backend changes of any kind.

**Backend prereqs:** None. Backend search endpoint already registered at `GET /api/v1/search` (`financeops/modules/search/api/routes.py`).

**Day estimate:** 0.5 day

**Dependencies:** None — unblocked from Phase 4 close.

---

### SP-5B — formatAmount Sweep

**Goal:** Replace all financial-amount `.toFixed()` bypasses with `formatAmount()` / `useFormattedAmount()`.

**Findings addressed:** #29 (remaining ~12 financial instances after percentage exclusions)

**Files touched (financial amounts only — out of scope for percentage/file-size calls):**
- `components/covenants/CovenantGauge.tsx:61,64` — threshold/actual values are currency
- `components/admin/BenchmarkChart.tsx:72` — exclude if this is a percentage (spot-check at SP start)
- `components/admin/TaskRegistryTable.tsx:55` — percentage → exclude
- `components/backup/BackupRunTable.tsx:13,16` — file size bytes → exclude
- `components/budget/VarianceBadge.tsx:29` — variance percentage → exclude (percentage is correct)
- `components/mis/MISDashboard.tsx:86` — change percentage → exclude
- `components/statutory/RegisterTable.tsx:142` — currency amount → **include**
- `components/treasury/CashFlowGrid.tsx:131` — currency amount → **include** (CashFlowGrid:70 already fixed in QW-10)
- `app/(dashboard)/dashboard/variance/PageClient.tsx:76,89` — variance percentage → assess: if variance\_value is currency, include; if %, exclude
- `app/(dashboard)/[orgSlug]/[entitySlug]/accounting/journals/new/PageClient.tsx:433,434` — debit/credit totals → **include**
- `app/(dashboard)/trial-balance/PageClient.tsx:346` — net total → **include**
- `components/scenarios/ScenarioSlider.tsx:33,52` — percentage sliders → exclude
- `lib/api/reconciliation.ts:93` — `formatAmount` local shadow → assess: this is a local helper, may be intentional

**Out of scope:** `invoice-classify` confidence scores, `trust` coverage percentage, `scenarios` sliders, `partner/earnings` earnings (these are financial but rendering as plain decimals is intentional for their context), file-size helpers, `lib/utils.ts` internal utility functions.

**Backend prereqs:** None.

**Day estimate:** 1 day (includes verify-then-fix pattern at SP start)

**Dependencies:** None — can run in parallel with SP-5A.

---

### SP-5C — Motion + Skeleton + Focus + EmptyState Polish

**Goal:** Address four cross-cutting polish gaps surfaced by this pre-flight. All are CSS or component additions with no API dependencies.

**Findings addressed:** Motion preferences gap, skeleton coverage gap, focus management gap, empty state coverage gap

**Sub-tasks (all in one branch):**

1. **`prefers-reduced-motion` global** — add to `app/globals.css`:
   ```css
   @media (prefers-reduced-motion: reduce) {
     *, *::before, *::after {
       transition-duration: 0.01ms !important;
       animation-duration: 0.01ms !important;
       animation-iteration-count: 1 !important;
     }
   }
   ```

2. **Route-specific loading.tsx** — add shape-matched skeleton for the 8 highest-traffic routes without one: `mis`, `trial-balance`, `budget`, `close`, `consolidation`, `fixed-assets`, `governance`, `sync`. Each should match the actual page's rough content shape (table vs cards vs panels).

3. **RouteAnnouncer** — add a small client component that reads `usePathname()` and on change calls `document.getElementById('main-content')?.focus()` with `tabIndex={-1}` on the main element. Mounts once in dashboard layout.

4. **EmptyState sweep** — add `<EmptyState>` to the 5 most-visited list/table pages that currently show nothing on empty: `anomalies`, `notifications` list, `governance/audit`, `expenses`, `fixed-assets`.

**Out of scope:** Route-level error boundaries (low impact), form UX inline-label audit (Phase 6), mobile nav (Phase 2/3 carry-over).

**Backend prereqs:** None.

**Day estimate:** 1 day

**Dependencies:** None — can run in parallel with SP-5A and SP-5B.

---

### SP-5D — TopBar Brand Mark (FU-011)

**Goal:** Ship Finding #15 / FU-011 — Finqor SVG brand mark + wordmark as the leftmost element in the persistent TopBar.

**Findings addressed:** #15 (TopBar brand mark, deferred from Phase 1 `feat/phase1-topbar-verify-cleanup`)

**Files touched:**
- `components/layout/Topbar.tsx` — add `<FinqorLogo />` as leftmost element in desktop layout
- `components/ui/FinqorLogo.tsx` (new) — inline SVG with word mark; accept `className` for sizing

**Out of scope:** Mobile TopBar brand treatment (mobile layout already has separate condensed rendering), brand color theming.

**Backend prereqs:** None. No Alembic migration.

**Day estimate:** 0.5 day

**Dependencies:** None — can run in parallel with all other SPs.

---

### SP-5E — Test Cleanup + Housekeeping

**Goal:** Close pre-existing tracked items that are small and self-contained.

**Tasks:**
1. **FU-007 fix** — update `tests/unit/onboarding_wizard.test.tsx` string literals to match current component copy. Goal: 224/224 Vitest.
2. **FU-004 close** — confirm 0 lint warnings, update `docs/follow-ups/INDEX.md` to mark FU-004 closed.
3. **FU-019 assessment** — read `FU-019-control-plane-test-preexisting-failures.md`; if the fix is scoped to a TooltipProvider wrapper and < 2h, fix it; otherwise leave deferred.

**Out of scope:** FU-008 (E2E sweep), FU-009 (WebKit binary), FU-014 (coverage thresholds).

**Backend prereqs:** None.

**Day estimate:** 0.5 day

**Dependencies:** None — can run at any point.

---

## 6. Day Estimates and Dependency Map

| SP | Scope | Est. Days | Parallel? | Depends on |
|---|---|---|---|---|
| **SP-5A** | CommandPalette cleanup + ⌘K reconciliation | 0.5 | ✅ Standalone | Phase 4 done ✓ |
| **SP-5B** | `formatAmount` sweep | 1.0 | ✅ Standalone | Phase 4 done ✓ |
| **SP-5C** | Motion + skeleton + focus + empty states | 1.0 | ✅ Standalone | Phase 4 done ✓ |
| **SP-5D** | TopBar brand mark (FU-011) | 0.5 | ✅ Standalone | Phase 4 done ✓ |
| **SP-5E** | Test cleanup + FU housekeeping | 0.5 | ✅ Standalone | Phase 4 done ✓ |
| **Total** | | **3.5 days** | All can run in parallel | |

### Dependency Map

```
main (62efa0e, tag: frontend-phase-4)
│
├── feat/sp-5a-command-palette  (0.5 day)   ─── PARALLEL ──┐
├── feat/sp-5b-format-amount    (1.0 day)   ─── PARALLEL ──┤
├── feat/sp-5c-motion-polish    (1.0 day)   ─── PARALLEL ──┤
├── feat/sp-5d-topbar-brand     (0.5 day)   ─── PARALLEL ──┤
└── feat/sp-5e-test-cleanup     (0.5 day)   ─── PARALLEL ──┘
                                                             │
                              all --no-ff merge into main ──┘
                                                             │
                                         docs/phases/phase5-close-*.md
                                                tag: frontend-phase-5
```

**All 5 sub-prompts are independent and can be executed via git worktrees in parallel.** There is no intra-Phase-5 sequential dependency. Recommended merge order: SP-5E first (clears test baseline to 224/224), then SP-5A (clears the ⌘K blocker), then SP-5B, SP-5C, SP-5D in any order.

**No backend Alembic migration required for any Phase 5 SP.** The Alembic head remains `0146_sidebar_collapsed` throughout Phase 5.

---

## 7. Open Questions

### OQ-1 — CommandPalette: Delete old or archive?

**Context:** `components/layout/_components/CommandPalette.tsx` is the old hardcoded 5-item palette that is superseded by `components/search/CommandPalette.tsx`. SP-5A proposes removing the old file entirely.

**Why it matters:** If the old file is deleted and a future branch re-introduces a simpler palette for a different surface (e.g., mobile), starting fresh is fine. If it's kept as a "fallback" it will confuse future contributors who don't know which palette to edit.

**Options:**

- **Option A — Delete the old file entirely.** `SearchProvider` + `components/search/CommandPalette.tsx` is the single palette. Remove old file and its import from `layout.tsx`. Clean.
- **Option B — Keep old file, disable its ⌘K handler.** Remove only the `useEffect` that registers the keyboard listener, but keep the component. Less clean; creates dead code.

**Recommendation:** **Option A.** The live-search palette (`components/search/CommandPalette.tsx`) is strictly more capable. Dead code has maintenance cost. Delete with confidence; git history preserves it if needed.

---

### OQ-2 — NotificationBell: SSE push vs polling

**Context:** `NotificationBell` uses `setInterval` at 30s, max 120 attempts (~60 min). At this frequency, a user leaves the app open → 120 requests per session. The backend has a notifications module (`0056_notifications.py` migration, `getUnreadNotificationCount` wired to `/api/v1/notifications`). An SSE push endpoint (`GET /api/v1/notifications/stream`) would eliminate polling.

**Why it matters:** At low user counts polling is fine. At scale (100+ concurrent users), 30s polling generates measurable background load. SSE requires a backend route addition — would be the first Phase 5 Alembic-touching item (no migration needed, just a new route).

**Options:**

- **Option A — Leave polling as-is for Phase 5.** Current implementation is graceful, tested, and simple. SSE is a Phase 6 optimization.
- **Option B — Add SSE endpoint in SP-5A.** Add `GET /api/v1/notifications/stream` to the backend; switch `NotificationBell` to `EventSource`. Increases SP-5A scope by ~0.5 day.

**Recommendation:** **Option A.** 30s polling is acceptable for current product stage. The graceful degradation is already correct. SSE adds backend scope to an otherwise frontend-only phase — defer to Phase 6 or a standalone FU.

---

### OQ-3 — formatAmount scope: What counts as a "financial amount"?

**Context:** SP-5B proposes replacing `.toFixed()` with `formatAmount()` for financial currency amounts. The codebase has ~30 `.toFixed()` instances, but ~18 are on percentages (confidence scores, change percentages, ratio displays), file sizes, and scenario sliders. These are semantically correct as `.toFixed(2)` — they are not currency values and should not go through `formatAmount()` (which prepends `₹` / `$`).

**Why it matters:** If SP-5B includes percentage displays, it will break the visual format (e.g., "5.23%" becomes "₹5.23"). If it excludes them, scope is tighter and less risky.

**Options:**

- **Option A — Scope to currency amounts only.** Fix: `RegisterTable.tsx`, `CashFlowGrid.tsx:131`, `journals/new` debit/credit totals, `trial-balance` net total, `CovenantGauge.tsx` if covenant values are currency. Leave: all percentage displays, file sizes, scenario sliders, confidence scores.
- **Option B — Full sweep.** Replace every `.toFixed()` including percentages with appropriate helpers (`formatPercent` from `lib/utils.ts:155` exists). More comprehensive but higher risk.

**Recommendation:** **Option A.** Currency amounts are finding #29's original intent ("bypass `formatAmount`"). Percentage displays using `.toFixed(2)` are correct and a separate concern. `formatPercent()` already exists in `lib/utils.ts:155` — SP-5B can add a note to use it in a follow-up, but should not be in scope here. Scope discipline over comprehensiveness.

---

## 8. Recommended Phase 5 Entry Point

**Start with SP-5E** to clear the 2-failure Vitest baseline (FU-007 text fixes, FU-004 index cleanup). This turns the 222/224 baseline into 224/224 before any SP-5A–5D work begins, giving each subsequent SP a clean green test gate.

**Then run SP-5A, SP-5B, SP-5C, SP-5D in parallel** via git worktrees. SP-5A (⌘K conflict) is the only 🔴 gap and should be merged first once complete. All others can be merged in any order.

**Recommended merge sequence:**
1. SP-5E (test baseline → 224/224)
2. SP-5A (removes the 🔴 dual ⌘K blocker)
3. SP-5B, SP-5C, SP-5D (any order — no dependencies between them)

**Phase 5 verification checklist at close:**

- [ ] `npm run build` ✓ (0 errors)
- [ ] `npm run lint` ✓ (0 warnings)
- [ ] Vitest 224/224 (FU-007 resolved, no new failures)
- [ ] `Ctrl+K` opens exactly one dialog — the live-search palette with AI assist
- [ ] Financial currency amounts in RegisterTable, CashFlowGrid, trial-balance, journals render through `formatAmount`
- [ ] Sidebar expand/collapse animation does not play when OS "Reduce motion" is enabled
- [ ] Top 8 previously-skeleton-less routes show shape-matched loading skeletons
- [ ] Finqor wordmark visible in TopBar on all dashboard routes
- [ ] Skip-to-content focus moves to `#main-content` on route change

**No backend Alembic migration. No push after merge. Stop and report.**
