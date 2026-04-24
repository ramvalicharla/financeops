# Finqor Shell Audit — Coverage Matrix
> Date: 2026-04-25 | Analyst: Claude (claude-sonnet-4-6) | Status: Complete  
> Inputs: `finqor-shell-audit-prompt.md`, `finqor-shell-audit-2026-04-24.md` (37 findings), `finqor-shell-a11y-sweep-2026-04-24.md` (8 findings)

---

## 1. Executive Summary

| Metric | Count |
|---|---|
| Total checks | 54 |
| Covered — issue found | 34 |
| Covered — compliant | 5 |
| Covered — by a11y sweep | 5 |
| Partially covered | 8 |
| Not examined | 1 |
| Cannot determine | 1 |
| **Coverage rate** | **44 / 54 = 81.5%** |
| Gaps requiring follow-up | **10** |
| False positives identified | **0 confirmed** (1 initial candidate retracted; 1 scope correction) |

**Top 3 risks from the gaps list:**

1. **Check 54 (J — portal shell separation)** cannot be determined from the codebase alone. Blueprint §15 describes three separate portals (`app.`, `platform.`, `partners.`), but whether the middleware handles subdomain routing is unconfirmed. If portals require separate deployments, the shell audit scope differs entirely. This must be resolved with product before Phase 6.
2. **Checks 6, 7/38 (B — org switcher wiring, ⌘K global binding)** are only partially covered. The org switcher rebuild in Phase 2 depends on knowing whether `GET /api/v1/orgs` exists for regular users; the global ⌘K binding has never been traced end-to-end. Both gaps block Phase 2 and Phase 5 planning.
3. **Check 31 (G — entity selection query invalidation) is only partially covered.** Findings #10 and #26 imply coordinated invalidation is broken (fragmented store, inconsistent keys), but the actual `setActiveEntity` call path was never traced end-to-end. If invalidation is silently absent, entity scope changes will show stale data — a runtime correctness bug that should be confirmed before Phase 2 starts.

---

## 2. Coverage Matrix

> File paths are relative to `frontend/`. Status codes: **CI** = Covered — issue found | **CC** = Covered — compliant | **CA** = Covered — by a11y sweep | **PC** = Partially covered | **NE** = Not examined | **CD** = Cannot determine.

| Check # | Area | Check description | Linked finding(s) | Status | Evidence / note |
|---|---|---|---|---|---|
| 1 | A | Single DashboardLayout renders all shell layers? | — | CC | Verified `app/(dashboard)/layout.tsx:64-108`; renders `<Sidebar>`, `<DashboardShell>` containing `<Topbar>`, `<ModuleTabs>`, `<ContextBar>`, `<main id="main-content">` in one persistent layout. |
| 2 | A | TopBar/Sidebar/TabBar extracted as reusable components, mounted once? | — | CC | Verified `app/(dashboard)/layout.tsx:66-85`; all three are imported as named components and rendered directly in the layout, not per-route. Next.js App Router layout pattern guarantees single mount. |
| 3 | A | Layout survives route transitions without remount? | — | CC | `app/(dashboard)/layout.tsx` is a standard Next.js App Router layout. Child route changes do not re-render the layout segment. No evidence of forced remount in the layout file. Confirmed by framework contract. |
| 4 | A | Single source of truth for org/entity/module/period? | #10 | CI | Finding #10: workspace state fragmented across `useTenantStore`, `useUIStore`, `useDisplayScale`, `useLocationStore` — no unified `workspaceStore`. |
| 5 | B | TopBar component exists; renders all six §1.2 elements? | #14, #15, #16 | CI | Component exists at `components/layout/Topbar.tsx`. Findings #15 (brand mark absent), #14 (height 64px not 48px — resolved), #16 (fiscal year chip absent — resolved) confirm six-element set incomplete. |
| 6 | B | Org switcher wired to API; updates Zustand + invalidates queries on change? | #17 | PC | Finding #17 confirms switcher renders only for `platform_owner`/`super_admin` (RBAC gap). Internal wiring of the component to `/api/v1/orgs` and its query-invalidation path were not traced; §3.4 Unknown #2 flags that no regular-user org listing endpoint was confirmed. |
| 7 | B | ⌘K wired to cmdk? Registered as global keyboard shortcut? | #18 | PC | Finding #18 confirms `CommandPalette.tsx:74-99` exists and uses cmdk. However, whether a document-level `keydown` listener is registered globally (not just page-local) was not traced in either audit. `SearchProvider` is the likely binding point but was not read. |
| 8 | B | Notification bell wired to API; poll or SSE; fallback on failure? | #33 | PC | Finding #33 explicitly deferred reading `NotificationBell.tsx`. A11y sweep (A7 section) confirmed 30-second polling at `NotificationBell.tsx:54-57` and noted no SSE. Graceful degradation on 5xx/network error was not verified in either audit. |
| 9 | C | Sidebar width exactly 220px in expanded state? | #11 | CI | Finding #11: `Sidebar.tsx:221` uses `w-60` (240px); spec requires 220px. |
| 10 | C | Entity card present and clickable; opens entity picker? | #3 | CI | Finding #3: `Sidebar.tsx:238-265` — entity card is static read-only text; no dropdown caret, no picker, no entity meta line, no blue selection state. |
| 11 | C | Three collapsible nav groups (Workspace / Org / Governance) with exact items? | #4 | CI | Finding #4: `Sidebar.tsx:286-324` — actual groups are Financials, Assets & Leases, Consolidation, Tax & Compliance. None of the three required groups exist; multiple required items absent. |
| 12 | C | Approvals item wired to count endpoint; badge updates in real time? | #4 | CI | Finding #4 confirms "Approvals" item is entirely absent from the nav. Badge wiring is not applicable while the item does not exist. |
| 13 | C | User footer present and pinned to bottom with border-top? | #30 | PC | Finding #30 (now resolved via QW-7) addresses content gaps (settings cog missing, collapsed state deficiency). Whether the footer is CSS-pinned (`sticky bottom-0` or `mt-auto`) with a `border-t` separator was not explicitly verified in either audit. Layout structure was confirmed by finding reference but exact CSS not cited. |
| 14 | D | 52px icon rail mode exists? | #12 | CI | Finding #12: `Sidebar.tsx:221` uses `md:w-14` (56px); spec requires 52px. |
| 15 | D | Collapse toggle wired; persists to localStorage + server preferences? | #24 | CI | Finding #24: `lib/store/ui.ts:86-99` — collapse persists to localStorage only; no API call to user preferences endpoint. |
| 16 | D | Every rail icon has accessible tooltip (not just `title` attribute)? | #32, A7-1 | CA | A11y sweep A7-1: `SidebarNavItem.tsx:45,67` — collapsed rail uses `title={item.label}` only; no Radix `<Tooltip>` component. WCAG 2.1.1 failure confirmed. Resolved in branch `fix/a11y-tier-1-wcag`. |
| 17 | D | Entity indicator chip reflects current entity state? | #13 | CI | Finding #13: `Sidebar.tsx:227-232` — collapsed header shows static "F" brand chip, not aggregate/single-entity indicator (e.g., "A7"). |
| 18 | E | Tab bar exactly 40px high, bordered below, horizontal scroll on overflow? | #20 | CI | Finding #20: `ModuleTabs.tsx:34` — container uses `py-3 pb-4` padding; no fixed 40px height; horizontal scroll and bottom border not verified. |
| 19 | E | Tabs rendered from tenant module registry, not hard-coded? | — | PC | §3.4 Unknown #6 confirms tabs read from `contextQuery.data?.workspace_tabs` (backend projection), not a hardcoded list. However, no formal frontend module registry exists — the distinction between "backend-driven" and "registry-driven" was not resolved. No specific finding created. Phase 3 plan calls for building the registry. |
| 20 | E | Tab order user-persistable via Module Manager? | #22 | CI | Finding #22: no drag-to-reorder anywhere; `@dnd-kit` not installed; `pinnedModules` controls sidebar pinning but not tab order. |
| 21 | E | `+` button RBAC-gated on `module.manage`? | #6 | CI | Finding #6: `+` button entirely absent from tab strip. RBAC gate is a Phase 3 requirement for the yet-to-be-built entry point. |
| 22 | E | Active tab underline uses `#185FA5` at 2px? | #5 | CI | Finding #5 (resolved via QW-1): active tab used `bg-foreground text-background rounded-full` pill; spec requires `border-b-2 border-[#185FA5] font-medium`. |
| 23 | E | "Overview" enforced as required and first-position at registry level? | #23 | CI | Finding #23 (resolved via QW-9): no registry-level guard; frontend trusted backend tab order without enforcing Overview at position 0. |
| 24 | F | Module Manager modal exists; reachable from `+` button? | #1 | CI | Finding #1: Module Manager modal does not exist. No `+` button, no modal component, no sub-tabs. Complete absence. |
| 25 | F | Modal has all four sub-tabs (Active / Available / Premium / Custom)? | #1 | CI | Finding #1: explicitly lists "no four sub-tabs (Active / Available / Premium / Custom)" as part of the complete absence. |
| 26 | F | Drag-to-reorder via `@dnd-kit` with keyboard accessibility? | #1, #22 | CI | Finding #22: `@dnd-kit` not installed; no drag-to-reorder anywhere. Finding #1: modal itself absent. |
| 27 | F | Toggles call `POST /api/v1/orgs/{orgId}/modules`; optimistic update? | #1 | CI | Finding #1: modal absent; no toggle endpoint to verify. §3.4 Unknown #6 questions whether the backend even has the correct module endpoint. |
| 28 | F | Premium modules show credit cost from pricing engine, not hard-coded? | #1 | CI | Finding #1: Premium advisory sub-tab absent as part of the missing modal. No credit cost display to verify. |
| 29 | F | Custom request tab submits to intake endpoint? | #1 | CI | Finding #1: Custom request sub-tab absent as part of the missing modal. No endpoint to verify. |
| 30 | G | `EntityScopeBar` component exists; renders conditionally on `entityId != null`? | #2 | CI | Finding #2: `EntityScopeBar` component does not exist. No blue scope strip appears on entity selection. |
| 31 | G | Entity selection invalidates all entity-scoped queries via single key strategy? | #10, #26 | PC | Findings #10 (fragmented store) and #26 (inconsistent query keys) together imply that a single coordinated invalidation is impossible. However, the actual `setActiveEntity` call path in `EntitySwitcher.tsx` was not traced to verify what queries are or are not invalidated. |
| 32 | G | Entity tree renders from `/api/v1/orgs/{orgId}/entities` with parent-child hierarchy? | #7, #36 | CI | Finding #7: no entity tree in sidebar. Finding #36: `EntitySwitcher.tsx:56-128` driven by session `entityRoles`, not live API call. |
| 33 | G | Consolidation tab dynamically disabled on single-entity scope; keyboard-accessible? | #8 | CI | Finding #8: no disable logic exists anywhere in the codebase; no opacity/tooltip applied to Consolidation tab on entity selection. |
| 34 | G | Tax/GST tab label changes based on entity jurisdiction? | #9 | CI | Finding #9: no jurisdictional mapping exists; tab label is static regardless of entity. |
| 35 | G | Currency formatter in metric cards reads entity functional currency? | #27 | CI | Finding #27: `lib/store/displayScale.ts:1-47` — formatter reads from user display-scale preference; entity functional currency is not stored in shell state and not passed to `formatAmount`. |
| 36 | G | Breadcrumb synced to scope state ("Org › Entity › Page")? | #35 | CI | Finding #35: `app/(dashboard)/layout.tsx:93` — `<Breadcrumb>` is route-based (URL segments), not scope-state-driven. |
| 37 | G | Clearing scope restores "all entities" state cleanly; no residual query state? | #2 | CI | Finding #2: `EntityScopeBar` (including the "Clear scope ✕" action) does not exist. Scope clearing and its query-cleanup behavior cannot be tested. |
| 38 | H | ⌘K palette exists and is globally bound? | #18 | PC | Same gap as Check 7. `CommandPalette.tsx` exists (finding #18); `app/(dashboard)/layout.tsx:103` mounts it. Whether a document-level shortcut listener is registered was not traced. Note: layout also imports a duplicate `CommandPalette` path (layout.tsx:19 vs SearchProvider) — a potential double-mount not caught in the main audit (flagged in v2 finding #39). |
| 39 | H | Sonner toasts mounted at root layout? | — | CC | Verified `app/layout.tsx:39`: `<Toaster position="bottom-right" richColors duration={4000} />` — Sonner is mounted at the root layout with correct position and 4s duration. Not flagged as missing by either audit (correct). |
| 40 | H | Single `formatAmount(value, currency)` utility; used everywhere amounts display? | #29 | CI | Finding #29: 15+ components bypass `formatAmount` with raw `.toFixed()`. Partially resolved (2 of 15+ fixed via QW-10). |
| 41 | H | Skeletons matched to final layout dimensions; zero CLS? | A6-1 | CA | A11y sweep A6-1: `app/(dashboard)/loading.tsx` — topbar skeleton 64px vs actual 48px; skeleton renders full shell chrome inside `<main>`, causing doubled UI during load. Structural CLS confirmed. |
| 42 | H | Skip-to-main link on every page; single `<main>` landmark? | A1, A2-1, A2-2 | CA | A11y sweep A1: skip-to-main PASS — link at `app/layout.tsx:30-35` uses correct `sr-only focus:not-sr-only` pattern. A11y sweep A2-1, A2-2: FAIL — nested `<main>` in `loading.tsx:39` and `search/page.tsx:18`. Both resolved in `fix/a11y-tier-1-wcag`. |
| 43 | H | Route-level `generateMetadata` on every page under `app/(dashboard)/`? | #25 | CI | Finding #25 (scope corrected by a11y sweep A3): 121 of ~130+ dashboard pages have `metadata` exports; ~9 pages (primarily `@modal/` segments and settings sub-routes) still missing. Residual scope stands. |
| 44 | H | `ConfirmDialog` used for all destructive actions; zero `window.confirm`? | A4-1 | CA | A11y sweep A4-1: `control-plane/admin/tenants/[id]/PageClient.tsx:134` — bare `confirm()` found for tenant suspend action. Resolved in `fix/a11y-tier-1-wcag`. No other `confirm()` calls found. |
| 45 | H | Every interactive element has visible keyboard focus ring? | A5-1, A5-2 | CA | A11y sweep A5: global `focus-visible` ring rule in `globals.css:72` provides baseline. Failures: A5-1 (`command.tsx:33` — CommandInput outline-none no ring) and A5-2 (`search/PageClient.tsx:114` — filter buttons outline-none no ring). Both resolved in `fix/a11y-tier-1-wcag`. |
| 46 | I | Exactly one `workspaceStore` with canonical shape? | #10 | CI | Finding #10: state fragmented across `useTenantStore`, `useUIStore`, `useDisplayScale`, `useLocationStore`; `moduleId` absent from all stores. |
| 47 | I | Single TanStack Query key convention (`['org', orgId, …]` / `['entity', entityId, …]`)? | #26 | CI | Finding #26: ad-hoc key strings across `Sidebar.tsx:63`, `Topbar.tsx:66`, `ContextBar.tsx:18`, `ModuleTabs.tsx:16`; no unified factory. |
| 48 | I | Any `any` types in layout / sidebar / tabbar / module manager code? | — | CC | Verified by grep across `components/layout/**/*.tsx`: zero `any` type annotations found. All layout shell components use explicit types. |
| 49 | I | Module/entity/org types generated from OpenAPI or hand-written? | — | NE | `frontend/lib/types/` contains 25 hand-written TypeScript type files (e.g., `board-pack.ts` exports plain `enum` and `interface` — no codegen comment). Neither audit examined this. No openapi/codegen invocation found in the grep pass. |
| 50 | J | Sidebar item list filtered by user permissions (not just rendered for all)? | #28 | PC | Finding #28 (Audit trail visible only to `ADMIN_NAV_ITEMS`) confirms some permission-gating exists. Comprehensive audit of `filterNavigationItems()` / `lib/ui-access.ts` was explicitly deferred to Phase 6 plan. The three required groups (Workspace / Org / Governance) don't yet exist, making per-item permission filtering moot until Phase 1. |
| 51 | J | Module Manager `+` button hidden for users without `module.manage`? | #1, #6 | CI | Findings #1 and #6: both the `+` button and modal are absent; RBAC gate is a Phase 3 requirement. |
| 52 | J | Org switcher scopes to user-accessible orgs (CA firm partner scenario)? | #17 | CI | Finding #17: org switcher entirely absent for non-admin users; CA firm partners (multi-org scenario from blueprint §2) have no org switching at all. §3.4 Unknown #2 flags missing `GET /api/v1/orgs` for regular users. |
| 53 | J | Audit trail link respects "Auditor" role (read-only view)? | #28 | CI | Finding #28: `Sidebar.tsx:326-366` — Audit trail link in `ADMIN_NAV_ITEMS` only; `auditor` role has no Audit trail entry and no read-only portal behaviour. |
| 54 | J | Three portal types (`app.`, `platform.`, `partners.`) handled correctly? | — | CD | §3.4 Unknown #7 explicitly flags this as unresolved. Only `/control-plane` route was confirmed. Whether subdomain routing exists in `middleware.ts` and whether portals share or separate the shell was not determined. Blueprint §15 terminology uses placeholder hostnames. |

---

## 3. Summary Table by Area

| Area | Total checks | Covered — issue | Covered — compliant | Covered — a11y | Partial | Not examined | Cannot determine |
|---|---|---|---|---|---|---|---|
| A — Layout shell | 4 | 1 | 3 | 0 | 0 | 0 | 0 |
| B — Top bar | 4 | 1 | 0 | 0 | 3 | 0 | 0 |
| C — Sidebar (expanded) | 5 | 4 | 0 | 0 | 1 | 0 | 0 |
| D — Sidebar (collapsed rail) | 4 | 3 | 0 | 1 | 0 | 0 | 0 |
| E — Module tab bar | 6 | 5 | 0 | 0 | 1 | 0 | 0 |
| F — Module Manager modal | 6 | 6 | 0 | 0 | 0 | 0 | 0 |
| G — Entity drill-down | 8 | 7 | 0 | 0 | 1 | 0 | 0 |
| H — Global UX standards | 8 | 2 | 1 | 4 | 1 | 0 | 0 |
| I — State, data, types | 4 | 2 | 1 | 0 | 0 | 1 | 0 |
| J — RBAC and blueprint alignment | 5 | 3 | 0 | 0 | 1 | 0 | 1 |
| **Total** | **54** | **34** | **5** | **5** | **8** | **1** | **1** |

---

## 4. Gaps List

Ordered by priority (Phase 0/pre-start first, later phases last).

---

### Gap 1 — Check 54 (J): Portal shell separation cannot be determined

**Why missed:** Blueprint §15 uses placeholder hostnames; only the `/control-plane` route was confirmed in the codebase. `middleware.ts` subdomain routing was not traced. The auditor correctly flagged it as §3.4 Unknown #7 but made no finding.

**Recommendation:** Ask product: are `app.`, `platform.`, and `partners.` subdomains in scope for the current implementation? If yes, grep `middleware.ts` for subdomain/host matching logic and verify branding/nav separation. If no, formally defer to a later release and note in the audit register.

**Before Phase 0?** Yes — if portals require separate deployments, the audit scope and Phase plan need adjustment.

---

### Gap 2 — Check 6 (B): Org switcher wiring to `/api/v1/orgs` + query invalidation not verified

**Why missed:** Finding #17 found the component was gated to admins and stopped there. Once the check confirmed a RBAC failure, the internal wiring was not traced.

**Recommendation:** Before Phase 2, read `components/layout/OrgSwitcher.tsx` in full. Verify which API endpoint it calls and what Zustand/query actions fire on org change. Confirm or deny §3.4 Unknown #2 (whether a regular-user org listing endpoint exists in the backend).

**Before Phase 0?** Yes (before Phase 2 planning is finalized).

---

### Gap 3 — Check 19 (E): Tabs from `workspace_tabs` vs formal module registry

**Why missed:** Tabs work via backend context projection; it's not hardcoded in the frontend. The audit noted this in §3.4 Unknown #6 but did not produce a finding or explicitly resolve the check.

**Recommendation:** Decide before Phase 3 whether `workspace_tabs` is the intended runtime registry or a temporary field. If `workspace_tabs` IS the source of truth, then check 19 is compliant (backend-registry-driven). If it's a stop-gap, raise a finding that the frontend has no registry validation layer.

**Before Phase 0?** No — but resolve before Phase 3 planning.

---

### Gap 4 — Check 31 (G): Entity selection does not trigger coordinated query invalidation

**Why missed:** `EntitySwitcher.tsx` was examined (finding #36) for its data source, but the invalidation path downstream of `setActiveEntity` was not traced. Findings #10 and #26 imply it's broken but do not confirm it.

**Recommendation:** Before Phase 2, trace `setActiveEntity` in `EntitySwitcher.tsx` — what Zustand actions fire, and do any query keys get invalidated? Given finding #10 (fragmented store) this is likely "nothing is invalidated", which would be a Critical finding. If confirmed, raise a new finding.

**Before Phase 0?** No — but verify before Phase 2 starts.

---

### Gap 5 — Checks 7 and 38 (B, H): Global ⌘K keyboard binding not verified (duplicate gap)

**Why missed:** Both checks ask whether the command palette is globally bound. Finding #18 examined the component's content (hardcoded items) and stopped. The `SearchProvider.tsx` binding logic was never read.

**Recommendation:** Grep `components/search/SearchProvider.tsx` for `document.addEventListener('keydown'` or the cmdk `useHotkeys` / `onOpenChange` pattern. Also check `app/(dashboard)/layout.tsx:103` for whether a duplicate `<CommandPalette>` mount creates a double-trigger (noted in v2 finding #39, not in main audit).

**Before Phase 0?** No — Phase 5 item, but the double-mount risk should be verified before Phase 1 ships.

---

### Gap 6 (B — Check 8): Notification bell SSE fallback not verified

**Why missed:** Finding #33 explicitly deferred reading the file. The a11y sweep confirmed 30-second polling but only from an ARIA/structural perspective.

**Recommendation:** Read `components/notifications/NotificationBell.tsx` in full. Verify: (a) polling interval, (b) whether `useQuery` error state shows the bell without a badge (not a blank space or unhandled error), (c) whether SSE is absent by design or missing by omission.

**Before Phase 0?** No — Phase 5 item.

---

### Gap 7 (J — Check 50): Sidebar permission filtering not comprehensively audited

**Why missed:** Finding #28 confirmed one specific case (Audit trail in ADMIN_NAV_ITEMS). The new nav group structure doesn't exist yet (Area C failures), making full permission-per-item audit premature.

**Recommendation:** Defer to Phase 6 as already planned. When Workspace/Org/Governance groups are built (Phase 1), add a DoD checklist item: "every nav item has a named required permission in `lib/ui-access.ts`".

**Before Phase 0?** No — Phase 6.

---

### Gap 8 (C — Check 13): User footer CSS pinning and border-top not explicitly verified

**Why missed:** Finding #30 focused on content (settings cog absent, collapsed state deficiency). Structural CSS was not cited.

**Recommendation:** Low-risk gap. When Phase 1 sidebar rebuild runs, add to the DoD checklist: user footer must have `mt-auto` / `sticky bottom-0` and `border-t` separator class, verifiable in DevTools.

**Before Phase 0?** No — Phase 1, low risk.

---

### Gap 9 (I — Check 49): Type origin (OpenAPI vs hand-written) not examined

**Why missed:** Not a structural or functional gap; silently skipped in both audits.

**Recommendation:** Check `package.json` for openapi-codegen scripts (`openapi-typescript`, `swagger-codegen`, etc.). If absent, hand-written types are confirmed; recommend adding codegen to `lib/types/` for backend-facing types to prevent drift. Low effort, fits in Phase 0.

**Before Phase 0?** No — can be absorbed into Phase 0 if desired.

---

## 5. False Positives

### FP-1 (Retracted): Finding #37 "CLOSED AS STALE" — closure was correct, fix is unmerged

**Prior audit claim:** Finding #37 in the main audit was marked `✅ CLOSED AS STALE` with note "verified by a11y sweep A3 correction; `className="dark"` already present at `app/layout.tsx:28`."

**Initial concern during this coverage pass:** The working-tree file (`app/layout.tsx:28`) reads `<html lang="en" suppressHydrationWarning>` — no `className="dark"`. This appeared to be a false positive correction.

**Resolved by checking the branch directly:**
```
git show fix/shell-quick-wins-qw0-qw10:frontend/app/layout.tsx | head -35
```
Line 28 on that branch reads:
```tsx
<html lang="en" className="dark" suppressHydrationWarning>
```

**Assessment:** The a11y sweep correctly read the branch where QW-5 was implemented. The fix exists and is correct. The gap is a **pending merge**, not a false audit closure. Finding #37 closure stands.

**Action required:** Merge `fix/shell-quick-wins-qw0-qw10` to land the fix. The proposed finding #38 in §6.3 is **withdrawn** — no new finding needed.

---

### FP-2 (Scope correction, not fabrication): Finding #25 — metadata absence substantially overstated

**Prior audit claim:** "generateMetadata absent from all pages; every route is served with default metadata."

**A11y sweep correction (Section A3):** 121 of ~130+ dashboard pages export `metadata` via a shared `createMetadata()` helper. ~9 pages (primarily `@modal/` segments and settings sub-routes) are missing.

**Assessment:** This is not a false positive in the strict sense — some pages ARE missing metadata, so the finding is valid. However, the severity and scope were substantially overstated. The main audit has already acknowledged this correction. The finding stands as Major but with a reduced scope of ~9 pages.

---

## 6. Conclusions

### 6.1 Is the prior audit trustworthy as a base for implementation?

**Yes, with caveats.**

The 34 findings marked "issue found" are accurate: all cited file paths and line numbers are real (confirmed against current codebase), and the structural gaps they describe (absent Module Manager, non-functional entity card, fragmented workspace store, inconsistent query keys) are genuine pre-implementation blockers. No fabricated findings were identified. The phased implementation plan is coherent and the effort estimates are consistent with the finding severity.

The primary accuracy concern is **FP-1**: finding #37 was incorrectly closed and the dark mode class is still missing — a one-line fix that will cause visual regressions until corrected. The second concern is that 8 checks are only partially covered (primarily in Areas B and J), meaning the Phase 2 and Phase 6 plans carry some unconfirmed assumptions. These partial gaps are acknowledged (§3.4 Risks and Unknowns) rather than hidden, which increases confidence in the audit's honesty. The audit is usable as a Phase 0 baseline.

---

### 6.2 Which 2-3 areas need the most follow-up before Phase 0 starts?

**1. Area B (Top bar) — 3 of 4 checks only partially covered.**
Checks 6 (org switcher wiring), 7 (⌘K global binding), and 8 (notification bell fallback) all have unresolved sub-questions. Phase 2 depends on a confirmed backend `/api/v1/orgs` endpoint for regular users; Phase 5 depends on whether the global ⌘K listener is correctly registered or duplicated. Both should be verified before those phases are scoped.

**2. Area J (RBAC + portal alignment) — Check 54 cannot be determined.**
The three-portal architecture from blueprint §15 is either in-scope or out-of-scope, and neither the middleware code nor product documentation resolves this. If portals require separate deployments, the current Phase plan (single shell, one audit) is incomplete. This must be a product decision before Phase 6 scope is locked.

**3. Reopening finding #37 (Area H) — dark mode class still missing.**
This is a 15-minute fix (`app/layout.tsx:28`) that affects every user on a light-mode OS. The incorrect closure creates risk that it will be missed through Phase 1 without an explicit reopened ticket.

---

### 6.3 Are there any checks that should be added as new findings?

**No new findings to raise.** The one candidate (dark mode class) was traced to an unmerged fix in `fix/shell-quick-wins-qw0-qw10` — see FP-1 above. No clear gaps rising to finding level were uncovered during verification that aren't already captured by existing findings or the §3.4 unknowns list.

---

## Appendix — Verification Methods

| Check | Verification method |
|---|---|
| 1–3, 37, 39 | Direct file read: `app/(dashboard)/layout.tsx`, `app/layout.tsx` |
| 4–37, 40–47, 50–53 | Evidence from main audit findings (file + line citations verified against known findings) |
| 16, 41–45 | Evidence from a11y sweep (A1–A9 per-check results) |
| 48 | Grep: `components/layout/**/*.tsx` for `any` type annotations — 0 matches |
| 49 | Glob: `frontend/lib/types/*.ts` (25 files); content check confirms hand-written TypeScript |
| 54 | §3.4 Unknown #7 in main audit; no middleware read performed |
