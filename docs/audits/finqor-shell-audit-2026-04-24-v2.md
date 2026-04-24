# Finqor Workspace Shell Frontend Audit V2 - 2026-04-24

## 3.1 Executive summary

- Overall shell completeness: 32%
- Total findings: 44 (Critical: 11, Major: 27, Minor: 6)
- Top 3 structural gaps:
  1. Workspace context is fragmented across tenant, UI, URL, location, and control-plane stores/queries instead of one Org -> Entity -> Module -> Period shell state model.
  2. The mounted dashboard shell exists, but the rendered surfaces do not match the locked shell: top-bar org switching is missing, sidebar entity card/tree is missing, and module tabs are not a 40px finance module strip.
  3. The Module Manager workflow is absent: no modal, no `+` button, no `module.manage`, no reorder dependency, no registry-level Overview enforcement, and no org-scoped module persistence endpoint.

Recommended phasing at a glance: start with Phase 0. The current app has enough persistent shell scaffolding to evolve, but the state, query key, module registry, and RBAC foundations need to be corrected before UI polish will stick.

Scope notes:

- Requested blueprint path `docs/01_MASTER_BLUEPRINT.md` does not exist. Nearest equivalent reviewed: `docs/platform/01_MASTER_BLUEPRINT.md`, including sections 2, 3, 6, 15, and 17.
- Requested directories `frontend/components/sidebar`, `frontend/components/topbar`, `frontend/components/nav`, `frontend/components/modules`, `frontend/components/org`, and `frontend/components/entity` do not exist. Nearest shell equivalents are under `frontend/components/layout`, `frontend/components/search`, and `frontend/components/control-plane`.
- Requested `frontend/stores`, `frontend/config/modules.ts`, and `frontend/lib/modules/registry.ts` do not exist. Nearest stores are under `frontend/lib/store`; nearest module API is `frontend/lib/api/modules.ts`; nearest module/tab data source is backend `workspace_tabs` from control-plane context.

## 3.2 Findings register

| # | Area | File | Line(s) | Finding | Severity | Spec ref | Effort (S/M/L) |
|---|---|---|---|---|---|---|---|
| 1 | A | `frontend/lib/store/tenant.ts` | 7-23 | No single `workspaceStore` exists. Org/tenant and entity state live here, while period/sidebar/module state live elsewhere; `moduleId` is absent. | Critical | §1.1, §1.7, Area I #46 | M |
| 2 | A | `frontend/lib/store/ui.ts` | 6-38 | `activePeriod`, `sidebarCollapsed`, pinned modules, notification count, and UI state are mixed in `useUIStore`, not a dedicated shell state slice. | Critical | §1.7, Area I #46 | M |
| 3 | I | `frontend/lib/query/controlPlane.ts` | 36-76 | A partial query key factory exists only for control-plane keys; app pages still use many ad hoc keys and no standard `['org', orgId, ...]` / `['entity', entityId, ...]` convention. | Critical | §1.7, Area I #47 | M |
| 4 | B | `frontend/components/layout/Topbar.tsx` | 297-365 | Desktop top bar does not render the locked six-element sequence: Finqor brand, org switcher, centered max-380px search, FY chip, notification bell, user avatar. | Critical | §1.2 | M |
| 5 | B | `frontend/components/layout/Topbar.tsx` | 87-91, 297-318 | Org context is display-only text derived from control-plane context; the top bar has no org switcher dropdown or org-change invalidation flow. | Critical | §1.2, Area B #6 | M |
| 6 | C | `frontend/components/layout/Sidebar.tsx` | 234-265 | Expanded sidebar shows an Organization/backend context card, not the required `ACTIVE ENTITY` label, entity card, entity name dropdown, and entity meta line. | Critical | §1.3 | M |
| 7 | E | `frontend/components/layout/ModuleTabs.tsx` | 34-75 | Module tab surface is a large descriptive backend-context block with rounded pills, not a 40px tab bar directly below top-bar/above content. | Critical | §1.5 | M |
| 8 | E | `frontend/components/layout/ModuleTabs.tsx` | 56-74 | Required dashed 24x24 `+` button is missing, so the Module Manager cannot be opened from the tab strip. | Critical | §1.5, §1.6 | L |
| 9 | F | `frontend/app/(dashboard)/modules/PageClient.tsx` | 14, 93-125 | `/modules` is a separate hard-coded table of industry modules, not the required Module Manager modal with Active, Available, Premium advisory, and Custom request tabs. | Critical | §1.6 | L |
| 10 | G | `frontend/components/layout/ContextBar.tsx` | 42-67 | Scope bar is always an "Active Context" strip; no conditional blue `EntityScopeBar`, no "Clear scope" action, and no single-entity messaging. | Critical | §1.7 | M |
| 11 | G | `frontend/components/layout/ModuleTabs.tsx` | 57-73 | Consolidation is always rendered as a normal link if present; it is not disabled with tooltip and blocked activation under single-entity scope. | Critical | §1.7 | M |
| 12 | A | `frontend/app/(dashboard)/layout.tsx` | 64-105 | A persistent dashboard layout exists and mounts shell components once for the dashboard segment. However, `ModuleTabs` is rendered before `ContextBar`, while the spec requires scope bar above module tabs. | Major | §1.5, §1.7 | S |
| 13 | A | `frontend/components/layout/DashboardShell.tsx` | 20-25 | Expanded/collapsed shell offsets are `md:pl-60` and `md:pl-14`, corresponding to 240px/56px rather than 220px/52px. | Major | §1.3, §1.4 | S |
| 14 | C | `frontend/components/layout/Sidebar.tsx` | 217-224 | Expanded sidebar width is `w-60` (240px), not exactly 220px. | Major | §1.3 | S |
| 15 | D | `frontend/components/layout/Sidebar.tsx` | 217-224 | Collapsed rail width is `md:w-14` (56px), not exactly 52px. | Major | §1.4 | S |
| 16 | C | `frontend/lib/config/navigation.ts` | 132-221 | Sidebar groups are `Financials`, `Assets & Leases`, `Consolidation`, `Tax & Compliance`, `Reporting`, `Integrations`, and `Admin`, not the required `Workspace`, `Org`, and `Governance` groups. | Major | §1.3 | M |
| 17 | C | `frontend/lib/config/navigation.ts` | 33-120 | Finance modules, admin, marketplace, billing, partner, audit, and settings surfaces are mixed in one nav list; non-module surfaces are not cleanly sidebar-only while tabs remain finance-only. | Major | §1.1, §1.3, §1.5 | M |
| 18 | C | `frontend/lib/config/navigation.ts` | 75-76, 119, 245-270 | Required sidebar items are incomplete/misaligned: no Today's focus, Approvals, Org settings, Connectors, Modules, Billing Credits, Team RBAC, or Compliance with exact labels and grouping. | Major | §1.3 | M |
| 19 | C | `frontend/components/layout/Sidebar.tsx` | 113-130, 124-140 | Nav filtering is entitlement/role based, but not permission-by-item for the locked Workspace/Org/Governance list. | Major | §1.3, Area J #50 | M |
| 20 | D | `frontend/components/layout/_components/SidebarNavItem.tsx` | 40-56 | Collapsed rail icons use only `title` and `aria-label`; they do not use the existing tooltip component and will not expose tooltip content on keyboard focus. | Major | §1.4 | S |
| 21 | D | `frontend/components/layout/Sidebar.tsx` | 227-232 | Collapsed rail top chip is a static Finqor `F`, not an aggregate/single-entity indicator chip. | Major | §1.4 | S |
| 22 | D | `frontend/lib/store/ui.ts` | 81-99 | Collapse state persists via localStorage only; no server-side user preference endpoint is wired. | Major | §1.4 | M |
| 23 | D | `frontend/components/layout/Sidebar.tsx` | 344-366 | Collapsed and expanded sidebar rendering preserves many app-specific groups rather than the required rail stacks separated as Workspace, Org, and Governance icon groups. | Major | §1.4 | M |
| 24 | E | `frontend/components/layout/ModuleTabs.tsx` | 15-24 | Tabs are read from `getControlPlaneContext().workspace_tabs`; there is no frontend tenant module registry/table config as the tab source of truth. | Major | §1.5, Area E #19 | L |
| 25 | E | `frontend/components/layout/ModuleTabs.tsx` | 63-68 | Active tab is a filled rounded pill; it does not use a 2px bottom border in Finqor blue `#185FA5`. | Major | §1.5 | S |
| 26 | E | `frontend/components/layout/ModuleTabs.tsx` | 24-31 | `Overview` is not enforced as required or first in a registry; component trusts backend tab order and current module data. | Major | §1.5 | M |
| 27 | E | `frontend/package.json` | 9-58 | `@dnd-kit` is not installed, and no equivalent sortable drag dependency is present for keyboard-accessible module reordering. | Major | §1.6 | S |
| 28 | F | `frontend/app/(dashboard)/modules/PageClient.tsx` | 21-27, 111-118 | Module management uses `tenant.modules.update` and a disabled table button, not the required `module.manage` permission gating the tab-bar `+` button. | Major | §1.6 | M |
| 29 | F | `frontend/lib/permission-matrix.ts` | 230-243 | Permissions define `tenant.modules.view/update`; `module.manage` is absent from the RBAC matrix. | Major | §1.6, Area J #51 | M |
| 30 | F | `frontend/lib/api/modules.ts` | 76-84 | Module enable/disable calls `/api/v1/modules/{module}/enable|disable`, not `POST /api/v1/orgs/{orgId}/modules`. | Major | §1.6 | M |
| 31 | F | `frontend/app/(dashboard)/modules/PageClient.tsx` | 49-56 | Module update flow refreshes after the backend call and does not optimistically update tab state. | Major | §1.6 | S |
| 32 | F | `frontend/app/(dashboard)/modules/PageClient.tsx` | 74-128 | No premium advisory credit-cost display and no Custom request intake form exist in the current module UI. | Major | §1.6 | M |
| 33 | G | `frontend/components/layout/EntitySwitcher.tsx` | 98-124 | Entity picker is a flat cmdk list from session `entityRoles`, not a searchable tree fetched from `/api/v1/orgs/{orgId}/entities`. | Major | §1.7 | M |
| 34 | G | `frontend/components/layout/EntitySwitcher.tsx` | 108-111 | Entity selection only calls `setActiveEntity`; it does not trigger one coordinated workspace update and query invalidation. | Major | §1.7 | M |
| 35 | G | `frontend/app/(dashboard)/[orgSlug]/[entitySlug]/layout.tsx` | 15-24 | URL slug hydration sets `entitySlug` directly as `active_entity_id`; org slug, period preservation, and query invalidation are not centralized. | Major | §1.7 | M |
| 36 | G | `frontend/components/layout/Sidebar.tsx` | 234-265 | Sidebar has no entity tree, blue selected-entity card state, or "Back to all entities" shortcut. | Major | §1.7 | M |
| 37 | G | `frontend/components/layout/ModuleTabs.tsx` | 57-73 | Tax/GST tab label is not dynamically relabeled by entity jurisdiction. | Major | §1.7 | M |
| 38 | G | `frontend/components/ui/Breadcrumb.tsx` | 166-183, 190-240 | Breadcrumb is built from URL segments and filters ID-like values; it does not read scope state to render Org -> Entity -> Page labels. | Major | §1.7 | S |
| 39 | H | `frontend/app/(dashboard)/layout.tsx` | 16-19, 77-104 | Dashboard layout mounts `SearchProvider` and also imports/renders a second `components/layout/_components/CommandPalette`, creating duplicate command palette paths. | Major | §1.8 | S |
| 40 | H | `frontend/components/search/CommandPalette.tsx` | 116-120 | Command palette placeholder is "Search modules or type a command..." rather than "Search entities, journals, tasks, modules". | Minor | §1.2, §1.8 | S |
| 41 | H | `frontend/lib/utils.ts` | 51-104, 155-214 | Shared `formatAmount()` exists, but the same util also exposes raw `.toFixed()` formatting; grep found additional component-level `.toFixed()` amount/metric formatting. | Major | §1.8 | M |
| 42 | H | `frontend/app/(dashboard)/search/page.tsx` | 18 | This dashboard page renders its own `<main id="main-content">` inside the dashboard layout, causing nested main landmarks for that route. | Major | §1.8 | S |
| 43 | H | `frontend/app/(dashboard)/settings/airlock/page.tsx`, `frontend/app/(dashboard)/settings/airlock/[id]/page.tsx`, `frontend/app/(dashboard)/settings/control-plane/page.tsx`, `frontend/app/(dashboard)/[orgSlug]/[entitySlug]/accounting/journals/@modal/(.)new/page.tsx`, `frontend/app/(dashboard)/[orgSlug]/[entitySlug]/accounting/journals/@modal/(.)[id]/page.tsx` | file-level scan | These dashboard pages do not export `metadata` or `generateMetadata`, unlike most other dashboard routes. | Minor | §1.8 | S |
| 44 | J | `frontend/middleware.ts` | 110-127, 205-225 | Middleware derives tenant slug generically and role-gates `/admin`, `/control-plane`, and `/trust`; it does not route `app.`, `platform.`, and `partners.` portal shells or apply portal-specific branding/nav separation. | Major | §1.1, Blueprint §15 | L |

## 3.3 Phased implementation plan

### Phase 0 — Foundation

- Findings to fix: #1, #2, #3, #24, #26, #29, #30, #41
- Total days: 7
- Parallelizable? yes
- Dependencies on other phases: none
- Verification checklist:
  - `workspaceStore` exists with `{ orgId, entityId, moduleId, period, sidebarCollapsed }`.
  - Store updates expose one `setScope()` or equivalent action that invalidates org/entity/module query keys in one place.
  - Query key factory supports `['org', orgId, ...]` and `['entity', entityId, ...]`.
  - Module registry config/API enforces Overview first and required.
  - `module.manage` exists in permission matrix.
  - Shared amount formatter is the only component-facing amount formatter.

### Phase 1 — Shell skeleton

- Findings to fix: #4, #6, #7, #12, #13, #14, #16, #17, #18, #25, #39, #40, #42, #43
- Total days: 8
- Parallelizable? yes
- Dependencies on other phases: Phase 0
- Verification checklist:
  - Dashboard layout renders TopBar, Sidebar, ScopeBar, TabBar, and one `<main>` in the required order.
  - Top bar is 48px and renders brand, org switcher shell, centered search, FY chip, bell, and avatar.
  - Expanded sidebar width is exactly 220px with Workspace/Org/Governance groups and exact labels.
  - Module tab bar is 40px and active state uses a 2px `#185FA5` underline.
  - No dashboard child page nests another `<main>`.
  - All dashboard pages export metadata or `generateMetadata`.

### Phase 2 — Org + entity switching

- Findings to fix: #5, #10, #11, #33, #34, #35, #36, #37, #38
- Total days: 8
- Parallelizable? partially
- Dependencies on other phases: Phase 0, Phase 1
- Verification checklist:
  - Org switcher fetches accessible orgs and invalidates org-scoped queries once per change.
  - Entity picker fetches and renders parent-child hierarchy.
  - Single-entity scope shows blue entity card, tree, back shortcut, scope bar, and state-synced breadcrumb.
  - Consolidation tab is disabled with keyboard-reachable explanation in single-entity scope.
  - Tax label and metric currency derive from selected entity metadata.

### Phase 3 — Module system

- Findings to fix: #8, #9, #24, #26, #27, #28, #29, #30, #31, #32
- Total days: 11
- Parallelizable? yes
- Dependencies on other phases: Phase 0, Phase 1
- Verification checklist:
  - Tab bar renders from tenant module registry, not hard-coded UI.
  - `+` button is gated by `module.manage`.
  - Module Manager modal contains Active tabs, Available, Premium advisory, and Custom request tabs.
  - Reorder works by pointer and keyboard with `@dnd-kit` or equivalent.
  - Save calls the org modules endpoint and optimistically updates visible tabs.

### Phase 4 — Collapsed rail

- Findings to fix: #15, #20, #21, #22, #23
- Total days: 4
- Parallelizable? yes
- Dependencies on other phases: Phase 1, Phase 2
- Verification checklist:
  - Collapsed rail width is exactly 52px.
  - Entity indicator reflects aggregate vs single entity.
  - Workspace, Org, and Governance icon stacks are separated by dividers.
  - Every icon has a tooltip that works for hover and keyboard focus.
  - Collapse preference persists in localStorage and server-side user preferences.

### Phase 5 — Global UX polish

- Findings to fix: #39, #40, #41, #42, #43
- Total days: 4
- Parallelizable? yes
- Dependencies on other phases: Phase 0, Phase 1
- Verification checklist:
  - Cmd/Ctrl+K opens exactly one global command palette.
  - Palette searches entities, journals, tasks, and modules and uses locked placeholder.
  - Sonner remains root-mounted bottom-right with 4s duration.
  - Grep shows no raw amount `.toFixed()` in components.
  - Landmark and metadata checks pass for dashboard routes.

### Phase 6 — RBAC + portal alignment

- Findings to fix: #19, #28, #29, #44
- Total days: 6
- Parallelizable? partially
- Dependencies on other phases: Phase 0, Phase 3
- Verification checklist:
  - Sidebar item list is filtered by permissions, not only entitlements.
  - Module Manager gate uses `module.manage`.
  - Auditor role receives read-only audit portal behavior.
  - `app.`, `platform.`, and `partners.` route to separate or explicitly filtered shells.

## 3.4 Risks and unknowns

- Cannot confirm whether backend exposes `POST /api/v1/orgs/{orgId}/modules`; frontend currently uses `/api/v1/modules/{module}/enable|disable`.
- Cannot confirm whether `workspace_tabs` is intended as the future tenant module registry or only a temporary control-plane context projection.
- Cannot confirm whether entity tree pagination, lazy loading, or search indexing is required for large orgs.
- Cannot confirm server-side sidebar preference endpoint; only tenant display-preferences APIs and localStorage persistence were found.
- Cannot confirm exact portal hostnames for production Finqor domains; blueprint uses placeholder `app.yourplatform.com`, `platform.yourplatform.com`, and `partners.yourplatform.com`.

## 3.5 Quick wins

- #13: adjust `DashboardShell` offsets to 220px/52px.
- #14: set expanded sidebar width to 220px.
- #15: set collapsed rail width to 52px.
- #20: replace collapsed rail `title` attributes with the existing tooltip component.
- #21: replace static `F` rail chip with an entity-state chip.
- #25: update active module tab style to a 2px `#185FA5` underline.
- #39: remove the duplicate `components/layout/_components/CommandPalette` mount.
- #40: update command palette placeholder text.
- #42: remove the nested `<main>` from `app/(dashboard)/search/page.tsx`.
- #43: add metadata exports to the five dashboard routes missing them.
