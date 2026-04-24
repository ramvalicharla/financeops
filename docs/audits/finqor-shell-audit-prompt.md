# Finqor Workspace Shell — Line-by-Line Frontend Audit Prompt

> This is the canonical spec used to audit the Finqor workspace shell frontend. Contains 54 numbered checks across 10 areas (A–J). Used as input by the coverage matrix audit pass.

---

## 0. Context the agent needs before starting

You are auditing the **Finqor / FinanceOps** frontend codebase (Next.js 14 App Router + TypeScript + Tailwind + shadcn/ui + TanStack Query + Zustand). The goal is to verify whether the current frontend matches the locked workspace shell design described in Section 1 below, and to produce a gap list plus a phased implementation plan.

Read these before writing a single finding:

1. The Master Blueprint at `docs/platform/01_MASTER_BLUEPRINT.md`. Focus on sections 2 (Platform Philosophy), 3 (Module Register), 6 (Multi-Tenant Data Architecture), 15 (Platform Portals), and 17 (Module Register).
2. The entire `frontend/app/` directory tree.
3. All files under `frontend/components/layout/`.
4. The Zustand stores under `frontend/lib/store/`.
5. Any feature flag / module registry config — typically `frontend/lib/config/modules.ts`, `frontend/lib/modules/registry.ts`, or similar.
6. The routing layer — both `frontend/app/(dashboard)/layout.tsx` and any nested layouts.
7. The RBAC layer — `frontend/lib/auth/`, `frontend/lib/ui-access.ts`, `frontend/middleware.ts`.

If any of these paths don't exist, report that as a finding and search for the nearest equivalent. Do not fabricate file paths.

---

## 1. The locked design — this is what the frontend MUST match

### 1.1 Three-layer hierarchy

The platform model is **Org → Entities → Modules**. Each layer maps to a specific UI surface:

| Layer | UI surface | Changes how often |
|---|---|---|
| Org | Top-bar org switcher | Rarely (per session) |
| Entity | Left sidebar entity card + entity tree | Occasionally (per task) |
| Module | Top module tab bar | Frequently (within a task) |

Non-module surfaces (Settings, RBAC, Audit, Billing, Compliance, Connectors) live in the sidebar, not as tabs. Tabs are strictly for finance modules from the Module Register.

### 1.2 Top bar — persistent global layer

Height 48px. Contains, left to right:

- Finqor brand mark + wordmark
- Org switcher (dropdown) showing current org name + avatar chip
- Global ⌘K search (centered, max 380px, placeholder "Search entities, journals, tasks…")
- Fiscal year chip (e.g. "FY 25-26")
- Notification bell (with unread indicator)
- User avatar (opens menu: profile, account settings, sign out)

The org switcher is the only place org context changes. It must be present on every authenticated page.

### 1.3 Left sidebar — expanded state (220px)

Top to bottom:

1. Section label — "ACTIVE ENTITY" (10px uppercase, letter-spaced, tertiary colour).
2. Entity card — padded card in `--color-background-secondary`. Shows entity label, entity name with dropdown caret, meta line (e.g. "Holding + 6 subs · INR"). Clicking opens the entity picker.
3. Collapsible nav groups, each with a chevron header:
   - Workspace — Overview, Today's focus, Period close, Approvals (with badge count)
   - Org — Entities, Org settings, Connectors, Modules, Billing · Credits
   - Governance — Audit trail, Team · RBAC, Compliance
4. User footer (pinned to bottom, border-top above it) — avatar, name, role, settings cog.

Nav items are 12px, 7px vertical padding. Active state uses `--color-background-info` + `--color-text-info`.

### 1.4 Left sidebar — collapsed rail state (52px)

Icon-only rail. Vertical stack, centre-aligned:

- Entity indicator chip at the top (e.g. "A7" for Acme + 7 entities)
- Thin divider
- Workspace icons (Overview, Today's focus, Period close, Approvals — Approvals gets a red dot for pending)
- Divider
- Org icons (Entities, Connectors, Modules, Billing)
- Divider
- Governance icons (Audit trail, RBAC, Compliance)
- Expand button pinned to the bottom (`»`)

Every icon must have a tooltip (keyboard-accessible). Active icon uses `--color-background-info` fill. Collapse state persists per user (localStorage + server-side preference).

### 1.5 Module tab bar (40px, directly below top-bar)

Horizontal, scrollable if overflow. Tabs have icon + label. Active tab uses a 2px bottom border in Finqor blue (`#185FA5`) + font-weight: 500. At the end of the tab strip, a dashed `+` button (24×24) opens the Module Manager modal.

Tabs are user-reorderable by drag within the Module Manager. Non-admin users see the order set by the tenant admin. The "Overview" tab is required and cannot be disabled or reordered out of first position.

### 1.6 Module Manager modal (opens from the `+` button)

Modal dialog, max-width 640px. Four sub-tabs at the top:

1. **Active tabs** — currently-pinned modules with drag grips (`⋮⋮`) on the left. Each row: grip, icon, name, tier badge (Core / Add-on / Premium), description, toggle. "Overview" row is disabled (toggle locked on, grip hidden).
2. **Available** — modules from the blueprint's Module Register that aren't pinned. Each row has a toggle to add it to the tab bar.
3. **Premium advisory** — FDD, PPA, M&A Workspace. Shows credit cost.
4. **Custom request** — form for commissioning new modules from the platform team.

Footer: "Changes apply to all users in this org" + Cancel + Save buttons.

RBAC: only users with `module.manage` permission can open this modal. For others, the `+` button is hidden or shown with a lock icon + tooltip.

### 1.7 Entity drill-down state

When a single entity is selected:

1. Entity card turns blue — background `#E6F1FB`, border `#85B7EB`. Label changes to "Selected · {currency}". Meta line shows entity type + jurisdiction + GAAP.
2. Entity tree appears below the entity card in a compact tree view.
3. "Back to all entities" shortcut appears as an inline link.
4. Scope bar appears above the module tabs — full-width strip, blue background (`#E6F1FB`), blue 800 text. Reads: "Scoped to **{entity}** · {currency} · {GAAP} · consolidation eliminated" with "Clear scope ✕" on the right.
5. Consolidation tab is disabled (opacity 0.5, tooltip explains).
6. Tax/GST tab relabels based on jurisdiction — "Tax / US", "Tax / GST", "Tax / UK", etc.
7. All metrics re-compute in the entity's functional currency via TanStack Query refetch keyed on `entityId`.
8. Breadcrumb shows: Org › Entity › Page.
9. Period selector is preserved across scope changes.

All scope changes must trigger a single Zustand update and invalidate the relevant query keys.

### 1.8 Global UX standards

- ⌘K / Ctrl+K command palette (cmdk). Wired to search entities, journals, tasks, modules.
- Toasts via sonner, bottom-right, 4s auto-dismiss.
- Decimal-safe amount formatting via a single `formatAmount()` util. No raw `.toFixed()` in components.
- Skeleton placeholders match final layout dimensions — zero CLS.
- Responsive to 1280px minimum.
- All destructive actions go through `ConfirmDialog`.
- WCAG 2.1 AA baseline: skip-to-main link, single `<main>` landmark per page, route-level `generateMetadata`, keyboard-reachable everything, visible focus rings, 4.5:1 contrast on text.
- Dark mode only (per blueprint). Every colour via CSS variable or Tailwind token.

---

## 2. The 54 audit checks

For each area, produce a per-file findings table with columns: `File` | `Line(s)` | `Finding` | `Severity (Critical / Major / Minor)` | `Design spec reference`.

### Area A — Layout shell

1. Is there a single `DashboardLayout` or equivalent that renders TopBar + Sidebar + TabBar + Outlet? Where?
2. Are TopBar, Sidebar, TabBar extracted as reusable components? Are they mounted once per session, not per route?
3. Does the layout survive route transitions without remount?
4. Is there a single source of truth for the current org / entity / module / period?

### Area B — Top bar

5. Does the TopBar component exist at the expected path? Does it render all six elements from §1.2?
6. Is the org switcher wired to `/api/v1/orgs` and does it update the org Zustand slice + invalidate all org-scoped queries on change?
7. Is ⌘K wired to `cmdk`? Is it registered as a global keyboard shortcut (not just a page-local one)?
8. Is the notification bell wired to `/api/v1/notifications`? Does it poll or use SSE? Is there a fallback when the endpoint is down?

### Area C — Sidebar (expanded)

9. Is the sidebar width exactly 220px in expanded state?
10. Is the Entity card present and clickable? Does it open the entity picker?
11. Are the three collapsible nav groups (Workspace / Org / Governance) present with the exact items listed in §1.3?
12. Is the Approvals item wired to a real count endpoint? Does the badge update in real time or on interval?
13. Is the User footer present and pinned to the bottom with border-top?

### Area D — Sidebar (collapsed rail)

14. Does a 52px icon rail mode exist?
15. Is the collapse/expand toggle wired and does it persist per-user (localStorage + user preferences endpoint)?
16. Does every rail icon have an accessible tooltip (not just a `title` attribute)?
17. Does the entity indicator chip on the rail reflect the current entity state (aggregate vs single)?

### Area E — Module tab bar

18. Is the tab bar exactly 40px high, bordered below, with horizontal scroll on overflow?
19. Are tabs rendered from the tenant's module registry, not hard-coded?
20. Is the order user-persistable via the Module Manager?
21. Is the `+` button RBAC-gated on `module.manage`?
22. Does the active tab underline use Finqor blue `#185FA5` at 2px?
23. Is "Overview" enforced as required and first-position at the registry level?

### Area F — Module Manager modal

24. Does the modal exist? Is it reachable from the `+` button?
25. Does it have all four sub-tabs (Active / Available / Premium / Custom)?
26. Is drag-to-reorder implemented using `@dnd-kit` (or equivalent) with keyboard accessibility?
27. Do toggles call the correct backend endpoint (`POST /api/v1/orgs/{orgId}/modules`) and optimistic-update the tab bar?
28. Are premium modules showing credit cost from the pricing engine, not hard-coded?
29. Does the Custom request tab submit to a ticketing / intake endpoint?

### Area G — Entity drill-down

30. Is the scope bar a separate component (`EntityScopeBar`) that renders conditionally on `entityId != null`?
31. Does selecting an entity invalidate all entity-scoped queries via a single key strategy (`['entity', entityId, …]`)?
32. Does the entity tree render from `/api/v1/orgs/{orgId}/entities` with proper parent-child hierarchy?
33. Is the Consolidation tab dynamically disabled on single-entity scope? Is the disabled state keyboard-accessible?
34. Does the Tax/GST tab label change based on entity jurisdiction?
35. Does the currency formatter in metric cards read from entity functional currency, not org currency?
36. Is the breadcrumb synced to the scope state?
37. Does clearing the scope restore the "all entities" state cleanly without residual query state?

### Area H — Global UX standards

38. ⌘K palette exists and is globally bound?
39. Sonner (or equivalent) toasts mounted at the root layout?
40. Is there a single `formatAmount(value, currency)` utility, and is it used everywhere amounts display?
41. Are skeletons matched to final layout (no CLS)?
42. Skip-to-main link present on every page? Single `<main>` landmark enforced?
43. Route-level `generateMetadata` on every page under `app/(dashboard)/`?
44. Is ConfirmDialog used for all destructive actions (grep for `window.confirm` — should be zero results)?
45. Does every interactive element have a visible keyboard focus ring?

### Area I — State, data, and types

46. Is there exactly one Zustand slice for workspace shell state (`workspaceStore`) with shape `{ orgId, entityId, moduleId, period, sidebarCollapsed }`?
47. Is there a single TanStack Query key convention (`['org', orgId, …]`, `['entity', entityId, …]`)?
48. Any `any` types in the layout / sidebar / tabbar / module manager code?
49. Are module, entity, and org types generated from OpenAPI or hand-written?

### Area J — RBAC and blueprint alignment

50. Is the sidebar item list filtered by user permissions (not just rendered for everyone)?
51. Is the Module Manager `+` button hidden for users without `module.manage`?
52. Is the org switcher correctly scoping to orgs the user has access to (CA firm partner scenario per blueprint §2)?
53. Does the Audit trail link respect the "Auditor" role (read-only view for auditor portal)?
54. Are the three portal types (`app.`, `platform.`, `partners.` per blueprint §15) handled by the same shell or separate shells? If same, is the branding / nav filtered correctly?

---

## 3. Required output format

### 3.1 Executive summary (max 1 page)

- Overall shell completeness: X%
- Total findings: N (Critical: X, Major: Y, Minor: Z)
- Top 3 structural gaps
- Recommended phasing at a glance

### 3.2 Findings register

A single table, every finding in order of severity:

| # | Area | File | Line(s) | Finding | Severity | Spec ref | Effort (S/M/L) |
|---|---|---|---|---|---|---|---|

Effort guide: **S** = ≤ 4h, **M** = ½–2 days, **L** = 3+ days.

### 3.3 Phased implementation plan

Produce exactly these phases, each with a list of findings to fix (by `#`), estimated effort in days, and verification criteria:

- **Phase 0 — Foundation** (Zustand workspace store, query key strategy, formatAmount util, ConfirmDialog primitive, module registry config). Unblocks everything else.
- **Phase 1 — Shell skeleton** (DashboardLayout, TopBar, Sidebar expanded, TabBar, route-level metadata, skip-to-main, single `<main>` fix).
- **Phase 2 — Org + entity switching** (org switcher wiring, entity card + picker + tree, scope bar, Consolidation disable logic, Tax/GST jurisdictional label, currency re-scope).
- **Phase 3 — Module system** (module registry-driven tab bar, Module Manager modal with all 4 sub-tabs, drag reorder via @dnd-kit, RBAC gating, premium credit display).
- **Phase 4 — Collapsed rail** (52px rail, tooltips, persistence, keyboard accessibility).
- **Phase 5 — Global UX polish** (⌘K palette wiring, sonner toasts, skeleton parity, focus rings, WCAG cleanup).
- **Phase 6 — RBAC + portal alignment** (sidebar permission filtering, Module Manager gate, auditor read-only, platform/partner portal shell separation if needed).

For each phase: total days, parallelizable? (yes/no), dependencies on other phases, verification checklist.

### 3.4 Risks and unknowns

A short list of things you could not determine from the codebase alone and need clarification on.

### 3.5 Quick wins

A list of 5–10 findings that are ≤ 4h each and can ship independently of the phased plan.

---

## 4. Rules of engagement

1. **Read before writing.** Do not produce any finding without reading the referenced file. If you cite line numbers, they must be real.
2. **No assumptions.** If a file is missing, say so. If a behaviour is unclear, list it in §3.4.
3. **No code changes in this pass.** This is an audit, not an implementation.
4. **Cite the spec.** Every finding references a section of §1 above.
5. **Be specific.** "Sidebar looks off" is not a finding. "Sidebar width is 240px at `components/layout/Sidebar.tsx:12`, spec §1.3 requires 220px" is a finding.
6. **Finish the whole audit.** Do not stop early.

---

## 5. When you finish

Produce the audit report at `docs/audits/finqor-shell-audit-YYYY-MM-DD.md`. Summarize in the terminal: total findings by severity, total estimated effort in days, which phase should start first, any blocking unknowns.
