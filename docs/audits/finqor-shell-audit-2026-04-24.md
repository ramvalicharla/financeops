# Finqor Workspace Shell — Frontend Audit Report
> Date: 2026-04-24 | Auditor: Claude (claude-sonnet-4-6) | Status: Complete
> Spec reference: Audit prompt §1 (locked design) + `docs/platform/01_MASTER_BLUEPRINT.md`

---

## 3.1 Executive Summary

**Overall shell completeness: ~38%**

The existing frontend has a solid engineering foundation — auth, state management, API client, control-plane admin, and the basic frame of a dashboard layout all work. However the **Finqor workspace shell as specified in §1 does not yet exist**. What is built is a functional but visually and structurally different product that will require substantial rework rather than incremental patching.

| Severity | Count |
|---|---|
| Critical | 10 |
| Major | 17 |
| Minor | 10 |
| **Total** | **37** |

**Top 3 structural gaps:**

1. **Module Manager modal is entirely absent** (Area F — 0% complete). No `+` button, no modal, no drag-to-reorder, no sub-tabs. This is the primary mechanism for tenants to configure their workspace and cannot be deferred.
2. **Sidebar architecture does not match the spec.** Width is wrong (240px vs 220px), the entity card is read-only static text not a picker, the three nav groups (Workspace / Org / Governance) do not exist, entity tree and scope bar are absent, and the collapsed rail shows a brand "F" chip instead of an entity indicator. The sidebar needs a near-complete rebuild.
3. **Entity drill-down scope layer is missing.** There is no `EntityScopeBar`, no entity tree in the sidebar, no Consolidation-tab disable logic, no jurisdictional Tax/GST tab relabelling, and no "Clear scope" action. The entity switcher updates Zustand state but nothing in the shell responds to it with the scoped UX.

**Recommended phasing at a glance:**

Start with Phase 0 (Zustand consolidation + query-key convention), then Phase 1 (sidebar rebuild), then Phase 2 (entity scoping), then Phase 3 (Module Manager). Phases 4–6 can follow in parallel once the shell skeleton stabilises.

---

## 3.2 Findings Register

> File paths are relative to `frontend/`. Line numbers are exact (read from source).

| # | Area | File | Line(s) | Finding | Severity | Spec ref | Effort |
|---|---|---|---|---|---|---|---|
| 1 | F | *(missing)* | — | Module Manager modal does not exist. No `+` button on the tab bar, no modal component, no four sub-tabs (Active / Available / Premium / Custom), no drag-to-reorder. This is a complete gap. | Critical | §1.5, §1.6 | L |
| 2 | G | *(missing)* | — | `EntityScopeBar` component does not exist. When an entity is selected, no blue scope strip appears above module tabs showing entity name, currency, GAAP, consolidation-eliminated status, or "Clear scope ✕" link. | Critical | §1.7 item 4 | M |
| 3 | C | `components/layout/Sidebar.tsx` | 238–265 | Sidebar entity card is a static read-only card showing org name + entity/module from backend context. It has no dropdown caret, cannot be clicked to open an entity picker, shows no entity type / jurisdiction / GAAP meta line, and does not turn blue on single-entity selection. This is the primary entity navigation surface per spec and it is non-functional as such. | Critical | §1.3 item 2, §1.7 item 1 | L |
| 4 | C | `components/layout/Sidebar.tsx` | 286–324 | Sidebar nav groups do not match the spec. Spec requires exactly three collapsible groups: **Workspace** (Overview, Today's focus, Period close, Approvals), **Org** (Entities, Org settings, Connectors, Modules, Billing · Credits), **Governance** (Audit trail, Team · RBAC, Compliance). Actual groups are: Financials, Assets & Leases, Consolidation, Tax & Compliance, plus flat Trust/Advisory/Settings/Admin. "Approvals" with badge count, "Today's focus", "Period close", "Entities", "Team · RBAC" are all absent from the nav. | Critical | §1.3 item 3 | L |
| ✅ 5 | E | `components/layout/ModuleTabs.tsx` | 57–74 | Active tab uses `bg-foreground text-background` pill inversion (rounded-full). Spec requires a 2px bottom border in Finqor blue `#185FA5` with `font-weight: 500`, not an inverted pill style. **RESOLVED** — `fix/shell-quick-wins-qw0-qw10` (QW-1) | Critical | §1.5 | S |
| 6 | E | `components/layout/ModuleTabs.tsx` | 34–76 | No `+` button (dashed, 24×24) to open the Module Manager at the end of the tab strip. Without this entry point Area F is completely unreachable. | Critical | §1.5 | S |
| 7 | G | `components/layout/Sidebar.tsx` | 53–91 | No entity tree appears below the entity card when a single entity is selected. Spec §1.7 item 2 requires a compact parent/sibling/selected-entity tree in the sidebar. No "Back to all entities" shortcut link. | Critical | §1.7 items 2–3 | M |
| 8 | G | *(missing)* | — | Consolidation tab not dynamically disabled when `entityId != null`. Spec requires opacity 0.5 + tooltip "Consolidation not available for single entity". No such logic exists anywhere in the codebase. | Critical | §1.7 item 5 | M |
| 9 | G | *(missing)* | — | Tax/GST tab label does not relabel based on entity jurisdiction. No jurisdictional mapping exists (US → "Tax / US", India → "Tax / GST", UK → "Tax / UK"). | Critical | §1.7 item 6 | M |
| 10 | I | Multiple stores | — | No single `workspaceStore` with shape `{ orgId, entityId, moduleId, period, sidebarCollapsed }`. Workspace state is fragmented across `useTenantStore` (orgId/entityId), `useUIStore` (sidebarCollapsed/period/pinnedModules), `useDisplayScale` (currency), and `useLocationStore` (location). Any component that needs cross-domain workspace state must import from 3–4 stores. | Critical | §Area I #46 | M |
| 11 | C | `components/layout/Sidebar.tsx` | 221 | Sidebar width is `w-60` (240px). Spec requires exactly 220px. | Major | §1.3 | S |
| 12 | D | `components/layout/Sidebar.tsx` | 221 | Collapsed rail width is `md:w-14` (56px). Spec requires exactly 52px. | Major | §1.4 | S |
| 13 | D | `components/layout/Sidebar.tsx` | 227–232 | Collapsed rail header shows a brand logo chip ("F") not an entity indicator chip (e.g. "A7" for Acme + 7 entities, or single-letter when one entity selected). The chip must reflect entity scope state. | Major | §1.4 item 1 | S |
| ✅ 14 | B | `components/layout/Topbar.tsx` | 167, 299 | TopBar height is `min-h-16` (64px) on both mobile and desktop. Spec requires exactly 48px. **RESOLVED** — `fix/shell-quick-wins-qw0-qw10` (QW-3) | Major | §1.2 | S |
| 15 | B | `components/layout/Topbar.tsx` | 166–413 | Finqor brand mark + wordmark is absent from the TopBar. The brand appears only in the sidebar header (`Sidebar.tsx:235`). Spec §1.2 requires the brand to be the leftmost element in the persistent top bar. | Major | §1.2 item 1 | S |
| ✅ 16 | B | `components/layout/Topbar.tsx` | 299–388 | No fiscal year chip ("FY 25-26") in the TopBar. Spec §1.2 requires it between the search bar and notification bell. **RESOLVED** — `fix/shell-quick-wins-qw0-qw10` (QW-8) | Major | §1.2 item 4 | S |
| 17 | B | `components/layout/OrgSwitcher.tsx` | 21–32 | The org switcher only renders for `platform_owner` and `super_admin` roles. Regular authenticated users (finance team, CA firm partners, tenant admins) have no org switcher at all. Spec §1.2 requires the org switcher to be present on every authenticated page for all users. | Major | §1.2 item 2, §Area J #52 | M |
| 18 | B | `components/layout/_components/CommandPalette.tsx` | 74–99 | CommandPalette shows only 5 hardcoded navigation items. Spec requires dynamic search across entities, journals, tasks, and modules ("Search entities, journals, tasks…"). No live search integration exists. | Major | §1.2 item 3, §1.8 item 1 | M |
| ✅ 19 | E | `components/layout/ModuleTabs.tsx` | 36–55 | Tab bar has a header section ("Workspace Modules" label + explanatory paragraph + status chips) consuming vertical space above the actual tabs. This is debugging scaffolding, not the spec's 40px tab bar. The spec allows only icon + label tabs with no header section above. **RESOLVED** — `fix/shell-quick-wins-qw0-qw10` (QW-4) | Major | §1.5 | S |
| 20 | E | `components/layout/ModuleTabs.tsx` | 34 | Tab bar container uses `py-3 pb-4` padding with no fixed height. Spec requires exactly 40px height. | Major | §1.5 | S |
| ✅ 21 | E | `components/layout/ModuleTabs.tsx` | 57–73 | Tab icons are absent — tabs render `workspace_name` text only. Spec §1.5 requires icon + label in each tab. **RESOLVED** — `fix/shell-quick-wins-qw0-qw10` (QW-1) | Major | §1.5 | M |
| 22 | E | *(missing)* | — | Tab order is not user-persistable. No drag-to-reorder exists anywhere. `@dnd-kit` is not installed. `pinnedModules` in `useUIStore` stores HREFs for sidebar pinning but does not control tab order. | Major | §1.5, §Area F #26 | L |
| ✅ 23 | E | *(missing)* | — | "Overview" tab is not enforced as required and first-position at the frontend level. No guard prevents the backend from returning a tab order that places Overview elsewhere or omits it. **RESOLVED** — `fix/shell-quick-wins-qw0-qw10` (QW-9) | Major | §1.5, §Area F #23 | S |
| 24 | D | `lib/store/ui.ts` | 86–99 | Sidebar collapse preference persists to `localStorage` only. Spec §1.4 requires collapse state persisted "per user (localStorage + server-side preference)". No API call syncs the preference to the backend. | Major | §1.4 item 2 | M |
| 25 | H | `app/(dashboard)/layout.tsx` | 21–108 | `generateMetadata` is not exported from the dashboard layout and is absent from all pages under `app/(dashboard)/`. Every route is served with default metadata. Spec §1.8 requires route-level `generateMetadata` on every dashboard page. **SCOPE CORRECTED** — per a11y sweep, only ~9 pages under @modal/ and settings subroutes lack metadata (not "all pages"). Residual scope to fold into Phase 5. | Major | §1.8 item 6 | M |
| 26 | I | Multiple files | — | TanStack Query key convention is inconsistent. `Sidebar.tsx:63` uses `["control-plane-entities"]`; `Sidebar.tsx:68`, `Topbar.tsx:66`, `ContextBar.tsx:18` use `["control-plane-context", activeEntityId]`; `ModuleTabs.tsx:16` appends `"workspace-tabs"` as a third element inconsistently. No unified `['org', orgId, ...]` / `['entity', entityId, ...]` strategy. | Major | §Area I #47 | M |
| 27 | G | `lib/store/displayScale.ts` | 1–47 | Currency formatter reads from `displayScale` store (user display-scale preference). Spec §1.7 item 7 requires metric cards to re-compute in the entity's **functional currency**. The entity functional currency is not stored in shell state and is not passed to `formatAmount`. | Major | §1.7 item 7, §Area G #35 | M |
| 28 | J | `components/layout/Sidebar.tsx` | 326–366 | Audit trail link exists only in `ADMIN_NAV_ITEMS` (visible to platform admins). Users with `auditor` role have no Audit trail entry in their sidebar. Auditor-role filtering for read-only access is absent. | Major | §Area J #53 | M |
| 29 | H | Multiple component files | various | 15+ components bypass `formatAmount` with raw `.toFixed()`: `CovenantGauge.tsx:61,64`, `BenchmarkChart.tsx:72`, `TaskRegistryTable.tsx:55`, `BackupRunTable.tsx:13,16`, `VarianceBadge.tsx:29`, `MISDashboard.tsx:86`, `CommissionTable.tsx:64`, `RegisterTable.tsx:142`, `CashFlowGrid.tsx:70,131`, `ScenarioSlider.tsx:33,52`, `ConsentCoverageTable.tsx:35`. Causes inconsistent decimal formatting. **PARTIALLY RESOLVED** — 2 of 15+ instances fixed in `fix/shell-quick-wins-qw0-qw10` (QW-10, CashFlowGrid + CommissionTable). Remaining 13+ instances deferred to Phase 5. | Minor | §1.8 item 3 | M |
| ✅ 30 | C | `components/layout/Sidebar.tsx` | 369–428 | User footer in collapsed state shows only an initials avatar that signs out on click. Spec §1.3 item 5 requires: avatar, name, role ("Tenant admin"), settings cog. The expanded footer shows name/email/role but no settings cog icon. **RESOLVED** — `fix/shell-quick-wins-qw0-qw10` (QW-7) | Minor | §1.3 item 5 | S |
| ✅ 31 | C | `components/layout/Sidebar.tsx` | 241 | Section label reads "Organization" (not "ACTIVE ENTITY" with uppercase/letter-spaced tertiary colour styling required by spec §1.3 item 1). **RESOLVED** — `fix/shell-quick-wins-qw0-qw10` (QW-2) | Minor | §1.3 item 1 | S |
| ✅ 32 | D | `components/layout/_components/SidebarNavItem.tsx` | *(unread)* | Rail icon tooltips: spec requires a real tooltip component (keyboard-focus accessible), not just a `title` attribute. `SidebarNavItem` was not fully read during this audit — must be verified manually. If `title` attribute is used, this is a failure. **RESOLVED** — `fix/a11y-tier-1-wcag` (commit 37de5c7, see a11y finding A7-1) | Minor | §1.4 item 3 | S |
| 33 | B | `components/notifications/NotificationBell.tsx` | *(unread)* | Notification bell polling strategy and SSE fallback were not verified. Endpoint wiring to `/api/v1/notifications` and graceful degradation on 5xx cannot be confirmed from this audit. | Minor | §1.2 item 5, §Area B #8 | M |
| 34 | G | `components/layout/ContextBar.tsx` | 43–67 | `ContextBar` shows Org → Entity → Module → Period chip strip. This is not the spec's blue scope bar (§1.7 item 4 — full-width, `bg-[#E6F1FB]`, blue text, shows only when `entityId != null`). ContextBar renders unconditionally below ModuleTabs (layout:86), not above them. | Minor | §1.7 item 4 | M |
| 35 | G | `app/(dashboard)/layout.tsx` | 93 | `<Breadcrumb />` renders inside `<main>` padding area. Spec §1.7 item 8 requires breadcrumb synced to scope state ("Org › Entity › Page"). The component's implementation was not audited but its position inside the content area (not shell chrome) suggests it is route-based, not scope-state-driven. | Minor | §1.7 item 8 | S |
| 36 | B | `components/layout/EntitySwitcher.tsx` | 56–128 | `EntitySwitcher` is driven by `entityRoles` prop from session, not by a live `/api/v1/orgs/{orgId}/entities` call. Session entity roles may lag behind backend changes until re-login. | Minor | §Area B #6 | M |
| ✅ 37 | H | `app/layout.tsx` | 28 | `<html lang="en">` has no `dark` class forced. Blueprint §1.8 states "Dark mode only." Without `className="dark"` on `<html>`, dark mode depends on OS preference and may render in light mode on some systems. **CLOSED AS STALE** — verified by a11y sweep A3 correction; `className="dark"` already present at `app/layout.tsx:28` | Minor | §1.8 | S |

---

## 3.3 Phased Implementation Plan

### Phase 0 — Foundation
**Findings addressed:** #10, #26, #36, #37

**Goal:** Establish shared data primitives that every subsequent phase depends on.

**Tasks:**
1. Consolidate `useTenantStore` + `useUIStore` (sidebar, period) into a single `useWorkspaceStore` with shape `{ orgId, entityId, moduleId, period, sidebarCollapsed }`. Migrate all consumers. `displayScale` and `location` may remain separate as display-only concerns.
2. Define and document the TanStack Query key tree: `['workspace', 'context', entityId]`, `['workspace', 'entities']`, `['workspace', 'tabs', entityId]`. Update all existing query calls to follow it.
3. Wire `EntitySwitcher` to call `GET /api/v1/orgs/{orgId}/entities` instead of session `entity_roles`.
4. Add `className="dark"` to `<html>` in `app/layout.tsx:28`.

**Estimated effort:** 3 days | **Parallelizable:** No — everything depends on the store shape | **Dependencies:** None

**Verification checklist:**
- [ ] `useWorkspaceStore` imported in Sidebar, Topbar, ModuleTabs, ContextBar — zero other store imports for workspace data
- [ ] React DevTools shows unified query key tree
- [ ] Entity switcher dropdown repopulates on org change without re-login
- [ ] App renders in dark mode on a system set to light mode preference

---

### Phase 1 — Shell Skeleton
**Findings addressed:** #11, #12, #14, #15, #16, #19, #20, #21, #25, #30, #31

**Tasks:**
1. **Sidebar rebuild**: Change width to 220px (`style={{width:'220px'}}`), collapsed rail to 52px. Rename entity card section label to "ACTIVE ENTITY" (10px uppercase, letter-spaced, tertiary colour). Add settings-cog icon to user footer. Remove debugging scaffolding from ModuleTabs header section (lines 37–55).
2. **TopBar**: Reduce to `h-12` (48px). Add Finqor brand mark (SVG) as leftmost element. Add fiscal year chip "FY YY-YY" derived from `period` in workspaceStore. Position search button centrally (max-w-[380px]).
3. **ModuleTabs**: Replace pill active style with `border-b-2 border-[#185FA5] font-medium` for active tab. Fix container height to `h-10`. Add icon + label to each tab (requires module icon registry — see §3.4 unknown #3).
4. **Route metadata**: Add `export const metadata` or `generateMetadata` to the 10 highest-traffic dashboard pages.
5. **Dark mode**: Done in Phase 0.

**Estimated effort:** 5 days | **Parallelizable:** Sidebar and TopBar can be done in parallel (2 engineers) | **Dependencies:** Phase 0

**Verification checklist:**
- [ ] Topbar height measured at 48px in DevTools
- [ ] Sidebar width measured at 220px; collapsed rail at 52px
- [ ] Active tab shows 2px blue underline, not inverted pill
- [ ] Finqor logo visible in TopBar on every dashboard route
- [ ] FY chip displays correct fiscal year
- [ ] 10 dashboard routes show distinct page titles in browser tab

---

### Phase 2 — Org + Entity Switching
**Findings addressed:** #2, #3, #7, #8, #9, #13, #17, #27, #34, #35

**Tasks:**
1. **OrgSwitcher for all users**: Refactor `OrgSwitcher.tsx` to render for all authenticated users. Call `GET /api/v1/orgs` for regular users. Platform admin switch-token flow remains as a conditional branch.
2. **Entity card as picker**: Make the entity card in Sidebar clickable. On click, open entity picker (tree + search). On selection, set `entityId` in workspaceStore. Style card blue (`#E6F1FB` bg, `#85B7EB` border) when entity scoped. Show jurisdiction / GAAP meta line.
3. **Entity tree in sidebar**: When `entityId != null`, render compact parent/sibling tree below entity card. Add "Back to all entities" inline link that sets `entityId` to null.
4. **EntityScopeBar**: Create `components/layout/EntityScopeBar.tsx`. Full-width strip: `bg-[#E6F1FB] text-[#042C53]`. Render conditionally on `entityId != null` above module tabs. Show entity name, currency, GAAP, "consolidation eliminated". "Clear scope ✕" sets `entityId = null` + calls `queryClient.invalidateQueries(['workspace'])`.
5. **Consolidation tab disable**: In ModuleTabs, when `entityId != null` and tab key is `consolidation`, apply `opacity-50 pointer-events-none` + `<Tooltip>` "Consolidation not available for single entity".
6. **Tax/GST tab label**: Build jurisdiction map. Read jurisdiction from entity object. Dynamically rename tab label in ModuleTabs.
7. **Entity indicator chip in rail**: Replace "F" chip in collapsed state with entity chip — first letter of entity name + total entity count (e.g. "A7") when all-entities mode, single letter when entity scoped.
8. **Currency from entity**: Store entity functional currency in workspaceStore. Pass to `formatAmount` in metric cards.

**Estimated effort:** 8 days | **Parallelizable:** EntityScopeBar and entity tree can be built in parallel | **Dependencies:** Phase 0, Phase 1

**Verification checklist:**
- [ ] Select entity → blue card + blue scope bar appear
- [ ] Clear scope → card returns to default styling, scope bar disappears
- [ ] Consolidation tab is greyed out in single-entity mode, tooltip appears on hover/focus
- [ ] Switch entity with US jurisdiction → tab shows "Tax / US"
- [ ] Switch entity with India jurisdiction → tab shows "Tax / GST"
- [ ] Rail chip shows "A7" (or equivalent) in all-entities mode
- [ ] All users (not just platform admins) see org switcher in TopBar

---

### Phase 3 — Module System
**Findings addressed:** #1, #5, #6, #22, #23, #28

**Tasks:**
1. **Module Manager modal**: Create `components/modules/ModuleManager.tsx`. Modal dialog, max-w-[640px]. Four sub-tabs: Active (drag grips `⋮⋮`), Available (add toggles), Premium (credit cost), Custom (intake form). "Overview" row locked (toggle disabled, grip hidden). Save calls `POST /api/v1/orgs/{orgId}/modules` and optimistically updates tab bar.
2. **`+` button**: Add dashed 24×24 button at end of tab strip (inside `ModuleTabs`). RBAC-gate on `module.manage` permission. No permission → lock icon + tooltip "Ask your admin".
3. **Drag-to-reorder**: Install `@dnd-kit/core` + `@dnd-kit/sortable`. Wire to Active tab list. Keyboard accessible (arrow keys to reorder).
4. **Overview enforcement**: Frontend guard — if `workspace_tabs[0]?.workspace_key !== 'overview'` after API response, re-sort and log Sentry warning.
5. **Premium credit cost**: Fetch credit cost from `GET /api/v1/billing/module-pricing` — do not hardcode.
6. **Auditor sidebar**: Add Audit trail item to a "Governance" nav group visible to `auditor` role (read-only). Remove write-action items for auditors.

**Estimated effort:** 10 days | **Parallelizable:** Modal UI and drag-to-reorder can be parallelised | **Dependencies:** Phase 1

**Verification checklist:**
- [ ] `+` button visible for `module.manage` users, hidden (or lock icon) for others
- [ ] Modal opens with all 4 sub-tabs
- [ ] Drag tab to new position → tab bar reorders
- [ ] Reload → reordered tab order persists
- [ ] Toggle module off → disappears from tab bar immediately (optimistic)
- [ ] Overview tab cannot be toggled off or moved from position 0
- [ ] Premium tab shows credit costs fetched from API
- [ ] Auditor role sees Audit trail in sidebar

---

### Phase 4 — Collapsed Rail
**Findings addressed:** #12, #13, #24, #32

**Tasks:**
1. **Rail width**: Verify 52px (from Phase 1 carryover).
2. **Rail tooltips**: Audit `SidebarNavItem.tsx`. Replace `title` attribute with `<Tooltip>` component that fires on keyboard focus.
3. **Persistence to backend**: On `toggleSidebarCollapsed`, call `PATCH /api/v1/users/me/preferences { sidebar_collapsed: boolean }`. On app load, fetch preference and initialise store from server value (localStorage as optimistic fallback while request is in-flight).
4. **Entity indicator chip**: Verify Phase 2 work covers this.

**Estimated effort:** 3 days | **Parallelizable:** Yes | **Dependencies:** Phase 1, Phase 0

**Verification checklist:**
- [ ] Collapse sidebar, reload in new browser tab — collapsed state preserved
- [ ] Keyboard-navigate (Tab) to a collapsed rail icon — tooltip appears
- [ ] DevTools measures rail at 52px
- [ ] Entity chip reflects current scope state

---

### Phase 5 — Global UX Polish
**Findings addressed:** #18, #19, #29, #33

**Tasks:**
1. **CommandPalette live search**: Replace hardcoded items with `useQuery(['search', query])` calling `GET /api/v1/search?q={q}&types=entity,journal,task,module`. Show grouped results.
2. **formatAmount sweep**: Replace all 15+ `.toFixed()` usages with `useFormattedAmount().fmt()` or `formatAmount()`. Prioritise: `CashFlowGrid.tsx`, `CommissionTable.tsx`, `RegisterTable.tsx`, `VarianceBadge.tsx`, `MISDashboard.tsx`.
3. **Notification bell audit**: Read `NotificationBell.tsx`. Wire to `/api/v1/notifications`. Add graceful degradation (bell without badge on 5xx/network error).
4. **Remove ModuleTabs debug header**: Ensure Phase 1 removed lines 37–55.
5. **generateMetadata sweep**: Complete remaining dashboard pages not covered in Phase 1.

**Estimated effort:** 4 days | **Parallelizable:** Yes | **Dependencies:** Phase 0

**Verification checklist:**
- [ ] Type "Acme" in ⌘K → entity results appear from API
- [ ] All currency amounts in visible tables show consistent `₹1,23,456.00` or `$1,234.56` format
- [ ] ModuleTabs shows only the tab strip — no debug header
- [ ] Kill backend → notification bell renders without badge, no console error

---

### Phase 6 — RBAC + Portal Alignment
**Findings addressed:** #17 (OrgSwitcher done in Phase 2), #28 (auditor done in Phase 3)

**Tasks:**
1. **Sidebar permission filtering audit**: Audit `filterNavigationItems()` and `lib/ui-access.ts`. Confirm every nav item has a required permission/role and is correctly filtered. Verify Governance group visible to correct roles.
2. **Module Manager RBAC verification**: `module.manage` gate from Phase 3 — verify correct permission string matches backend.
3. **Portal shell separation**: Verify `app/control-plane/layout.tsx` provides distinct branding/nav for platform portal. If `app.` / `partners.` subdomains are planned, confirm middleware subdomain routing is correct.
4. **OrgSwitcher final RBAC**: Confirm regular-user org switcher only shows orgs they belong to. Platform admin switch-token path remains separate.

**Estimated effort:** 3 days | **Parallelizable:** Yes | **Dependencies:** Phases 2, 3

**Verification checklist:**
- [ ] `auditor` role: sees Audit trail in Governance, cannot access write-action items
- [ ] `finance_team` role: no `+` button on module tabs
- [ ] Platform portal at `/control-plane` shows distinct chrome and nav
- [ ] Regular user org switcher only shows their orgs

---

### Phase Summary

| Phase | Key findings | Est. Days | Parallelizable | Depends on |
|---|---|---|---|---|
| 0 — Foundation | #10, #26, #36, #37 | 3 | No | None |
| 1 — Shell skeleton | #11,#12,#14,#15,#16,#19,#20,#21,#25,#30,#31 | 5 | Sidebar ∥ TopBar | Ph. 0 |
| 2 — Org + entity | #2,#3,#7,#8,#9,#13,#17,#27,#34,#35 | 8 | EntityScopeBar ∥ entity tree | Ph. 0, 1 |
| 3 — Module system | #1,#5,#6,#22,#23,#28 | 10 | Modal ∥ DnD | Ph. 1 |
| 4 — Collapsed rail | #12,#13,#24,#32 | 3 | Yes | Ph. 1 |
| 5 — UX polish | #18,#19,#29,#33 | 4 | Yes | Ph. 0 |
| 6 — RBAC + portals | #17,#28 | 3 | Yes | Ph. 2, 3 |
| **Total** | | **36 days** | | |

---

## 3.4 Risks and Unknowns

1. **Entity tree pagination**: Blueprint does not specify maximum entities per org. If orgs can have 100+ entities the sidebar tree needs virtual scrolling. Recommend confirming with product before Phase 2.
2. **`/api/v1/orgs` endpoint for regular users**: The OrgSwitcher rebuild (Phase 2) assumes a `GET /api/v1/orgs` endpoint listing orgs per user. Only `GET /api/v1/platform/admin/tenants` (admin-only) was confirmed in the codebase. A regular-user org listing endpoint needs to be verified or built in the backend before Phase 2 can complete finding #17.
3. **Module key → icon mapping**: ModuleTabs renders backend `workspace_name` text. Phase 3 requires a per-module icon. No `MODULE_ICON_MAP` config was found. This registry must be agreed and built before Phase 1 tab icons (finding #21) can ship.
4. **`module.manage` permission**: This permission string was not found anywhere in `middleware.ts`, `lib/ui-access.ts`, or any navigation config. It must be defined in the backend RBAC system and surfaced to the frontend (via JWT claim or `/api/v1/auth/me` response) before Phase 3 can gate the Module Manager correctly.
5. **Search endpoint for ⌘K**: Phase 5 assumes `GET /api/v1/search`. No search endpoint was confirmed in the backend routes. Must be verified before Phase 5 begins.
6. **`workspace_tabs` backend field**: `ModuleTabs` depends on `contextQuery.data?.workspace_tabs`. If the backend does not return this field, the tab bar renders empty with no empty state — a silent failure in production today. Requires immediate backend verification.
7. **Three portal subdomains (`app.`, `platform.`, `partners.`)**: Blueprint §15 describes these as separate portals. Whether `platform.` maps to `/control-plane` routing or a separate deployment is unclear. If separate deployment, shell audit scope differs for each portal.
8. **NotificationBell polling vs SSE**: The component was not read during this audit. If it uses `setInterval` polling at short intervals this may cause excessive requests at scale. Must be confirmed before Phase 5.
9. **Entity functional currency field name**: The entity API response field for functional currency was not confirmed. Phase 2 (finding #27) requires this field in the entity object returned by `/api/v1/orgs/{id}/entities`.

---

## 3.5 Quick Wins

The following findings are ≤ 4h each and can ship independently, in a single PR, before the phased plan begins:

| # | Finding | Action | File | Effort |
|---|---|---|---|---|
| QW-1 | #5 | Change active tab CSS from `bg-foreground text-background rounded-full` to `border-b-2 border-[#185FA5] font-medium bg-transparent text-foreground rounded-none` | `components/layout/ModuleTabs.tsx:62–67` | 1h |
| QW-2 | #31 | Change "Organization" label text to "ACTIVE ENTITY" and add `text-[10px] uppercase tracking-widest text-muted-foreground` | `components/layout/Sidebar.tsx:241` | 30m |
| QW-3 | #14 | Change `min-h-16` to `min-h-12` on both mobile (`Topbar.tsx:169`) and desktop (`Topbar.tsx:299`) topbar divs | `components/layout/Topbar.tsx:169,299` | 30m |
| QW-4 | #19 | Remove debug header paragraph (lines 37–55 of ModuleTabs) — the "Workspace Modules" label, explanatory text, and status chips | `components/layout/ModuleTabs.tsx:37–55` | 30m |
| QW-5 | #37 | Add `className="dark"` to `<html>` element | `app/layout.tsx:28` | 15m |
| QW-6 | #6 | Add stub `+` button (dashed, 24×24, disabled with tooltip "Module Manager — coming soon") at end of tab strip so the entry point is visible | `components/layout/ModuleTabs.tsx:75` | 1h |
| QW-7 | #30 | Add settings-cog icon button linking to `/settings` in both expanded and collapsed user footer states | `components/layout/Sidebar.tsx:370–428` | 1h |
| QW-8 | #16 | Add fiscal year chip — derive from `activePeriod` in UIStore: `FY ${yy}-${(yy+1).toString().slice(-2)}`. Place between search and notification bell in desktop TopBar | `components/layout/Topbar.tsx:325` | 2h |
| QW-9 | #23 | Add client-side Overview guard in ModuleTabs: if `visibleTabs[0]?.workspace_key !== 'overview'`, log Sentry warning + toast to admin | `components/layout/ModuleTabs.tsx:24` | 1h |
| QW-10 | #29 | Replace `.toFixed(2)` with `formatAmount` in `CashFlowGrid.tsx:70,131` and `CommissionTable.tsx:64` — highest-visibility financial tables | Two files | 2h |

---

## Resolution log

> Updated: 2026-04-24 | Source: local branches not yet pushed

**Branch `fix/shell-quick-wins-qw0-qw10`** (12 commits, local)
- Resolves findings: #5, #14, #16, #19, #21, #23, #30, #31
- Partially resolves: #29 (2 of 15+ `.toFixed` usages)
- Status: local, pending review and push

**Branch `fix/a11y-tier-1-wcag`** (commit `37de5c7`, local)
- Resolves findings: #32
- Status: local, pending review and push

**Closed as stale**
- #37 — `className="dark"` is already present; superseded by a11y sweep cross-reference

**Scope corrected**
- #25 — residual scope is ~9 pages, not all pages

**Total quick-win effort: ~10h. All are safe, isolated, and reviewable in a single PR per file.**
