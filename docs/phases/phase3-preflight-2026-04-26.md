# Phase 3 Pre-flight Planning Document

**Date:** 2026-04-26
**Branch:** `chore/phase3-preflight` (off `main` at `6201335`)
**Investigator:** Claude Sonnet 4.6 (read-only Sections 0–6, doc-write Section 7)
**Phase:** Phase 3 — Module System with Module Manager
**Status:** Pre-flight complete — awaiting user review before sub-prompt drafting

---

## 1. Working Tree State at Pre-flight Start

| Check | Value | Status |
|---|---|---|
| Branch | `main` | ✓ |
| HEAD | `6201335d2106bd0af782cf2b934fe0fdc7f5181b` | ✓ |
| Commits ahead of `origin/main` | 4 | ✓ |
| Working tree | Clean | ✓ |
| Active worktrees | `D:/finos` only | ✓ |
| Tag at Phase 2 close | `v4.5.0-phase2-complete` at `20985cf` | (context) |

**Phase history at pre-flight:** Pre-Phase-0 → Phase 0 → Phase 1 → Pre-Phase-2 → Phase 2 all complete. Phase 3 is next. The two most recent commits (outside Phase 2 delivery) were doc-only pre-Phase-3 housekeeping: Sprint 2 FU triage (`9451567`) and TD-016 Option A resolution + BE-002 + TD-018 filing (`6201335`).

---

## 2. Decision Log

Decisions confirmed or made during the investigation. These are NOT user decisions — they are factual resolutions from reading the codebase.

| # | Decision | Evidence | Impact |
|---|---|---|---|
| D-01 | Tab bar source is backend-driven via `workspace_tabs` from `/api/v1/platform/control-plane/context` | `ModuleTabs.tsx:23–30`, `ControlPlaneContext` type | Sub-prompts must not hardcode tab lists |
| D-02 | No frontend module registry exists beyond `MODULE_ICON_MAP` (icon-only, 7 keys) | `frontend/components/layout/tabs/module-icons.ts` | Module Manager modal is greenfield for enable/disable and ordering |
| D-03 | Per-user module ordering state does not exist anywhere | Zero results for `module_order`/`ordering` in frontend | Ordering state is fully greenfield; must be designed in SP-3A |
| D-04 | `@dnd-kit` is not installed (none of the 4 packages) | `frontend/package.json` | SP-3B must install `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/modifiers`, `@dnd-kit/utilities` |
| D-05 | Dialog.tsx and tabs.tsx exist and are usable for the modal shell | `frontend/components/ui/Dialog.tsx`, `tabs.tsx` | SP-3A can use existing primitives |
| D-06 | `country_code` already on `OrgEntityResponse` and `OrgEntity` frontend type | `org_setup/api/schemas.py:156`, `orgSetup.ts:87` | BE-002 AC-4 (jurisdiction) already met; no backend change needed for tax relabeling |
| D-07 | `is_consolidation_parent` does NOT exist on the entity response | `OrgEntityResponse` schema confirmed | BE-002 AC-3 is the live "add it" path; must be implemented before SP-2E |
| D-08 | `module.manage` is absent from frontend PERMISSIONS and from the codebase | Zero grep results; `permission-matrix.ts` confirmed | Speculative-with-TODO approach is safe (returns false for all users until backend lands) |
| D-09 | `canPerformAction` accepts loose `string` — no compile error for unknown permissions | `ui-access.ts:98` type signature | Speculative use of `"module.manage"` is type-safe |
| D-10 | No `<PermissionGate>` component exists — inline pattern is canonical | Codebase survey | SP-3A uses inline `canPerformAction(...)` + conditional render |
| D-11 | Consolidation and tax pages exist but are NOT workspace tabs | `navigation.ts` sidebar items; `MODULE_ICON_MAP` 7-key; `_WORKSPACE_DEFINITIONS` 7 entries | Phase 3 must not assume consolidation/tax tabs until BE-002 lands |
| D-12 | `GET /api/v1/billing/module-pricing` does not exist in frontend or backend | Zero grep results | New backend ticket required alongside `module.manage` |
| D-13 | `control_plane_shell.test.tsx` imports `ModuleTabs` | File header confirmed | FU-019 naturally pairs with SP-3A (ModuleTabs will be modified) |
| D-14 | 15 E2E specs exist (prompt said 14 — 1-file count discrepancy) | `git ls-files frontend/tests/e2e/*.spec.ts` | FU-008 scope is 15 specs, not 14 |
| D-15 | `auditor` role maps to `tenant_viewer` in ROLE_ALIASES; no PERMISSIONS entry permits write for `tenant_viewer` | `permission-matrix.ts:32` | Auditor sidebar uses role-check, not a new permission key |

---

## 3. Surprises Register

| ID | Severity | Summary | Affected Sub-prompts | Recommended Resolution |
|---|---|---|---|---|
| S-001 | **HIGH — OPEN QUESTION** | `/settings/modules/PageClient.tsx` exists with old API endpoint pattern. Phase 3 must decide disposition before SP-3A. See full text below. | SP-3A | User decision required — see Open Questions §7 |
| S-002 | LOW | BE-002 filed 2026-04-26 (not implemented). `MODULE_ICON_MAP` needs `consolidation` + `tax` keys when BE-002 lands. | SP-3A icon map update | Add keys as a post-BE-002 coordinated change; no blocker for Phase 3 |
| S-003 | **HIGH — OPEN QUESTION** | Locked design Phase 3 Task 4 says `workspace_key !== 'overview'`; backend and frontend both use `"dashboard"`. Terminology error in the spec. | SP-3A | User confirms: treat locked design as containing a terminology error and use `"dashboard"`. See Open Questions §7 |
| S-004 | **HIGH — OPEN QUESTION** | Module Manager Available-tab vocabulary is a product decision. Two candidate architectures. Linked to S-001. | SP-3A | User decision required — see Open Questions §7 |

### S-001 full text

`frontend/app/(dashboard)/settings/modules/PageClient.tsx` — a live settings page with a hardcoded module list (`["LEASE", "REVENUE", "ASSETS", "PREPAID", "ACCRUAL", "SUBSCRIPTION"]`) using old endpoints (`GET /api/v1/modules`, `POST /api/v1/modules/{name}/enable|disable`). Three disposition options for the user:

- **Replace:** SP-3A ships the new Module Manager modal and removes or rewrites `PageClient.tsx` in the same sub-prompt.
- **Redirect:** SP-3A ships the modal and adds a redirect from `/settings/modules` to the modal entry point; page-as-shell remains for a later sub-prompt to remove.
- **Sunset:** A separate sub-prompt (SP-3X) removes the page entirely, sequenced before or after the modal lands.

**Semantic drift sub-finding:** The vocabulary in `/settings/modules/PageClient.tsx` is `LEASE/REVENUE/ASSETS/PREPAID/ACCRUAL/SUBSCRIPTION` (sub-module instruments). The `MODULE_ICON_MAP` vocabulary is `dashboard/erp/accounting/reconciliation/close/reports/settings` (workspace-level navigation keys). These two vocabularies do not overlap. The canonical vocabulary for Phase 3's Module Manager must be settled before SP-3A. This is linked to S-004.

**Backend endpoint status sub-finding:** Whether `/api/v1/modules/{name}/enable|disable` is still live, deprecated, or superseded is unverified from frontend-only investigation. Backend track must confirm before SP-3A is drafted.

**Sub-pages:** `settings/modules/assets/`, `settings/modules/lease/`, `settings/modules/prepaid/`, `settings/modules/revenue/` are instrument configuration forms (create leases, fixed assets, etc.), NOT part of the Module Manager modal concept. They are independent of the S-001 disposition.

### S-003 full text

The locked design Phase 3 Task 4 reads: "Frontend guard — if `workspace_tabs[0]?.workspace_key !== 'overview'` after API response, re-sort and log Sentry warning." And Task 1: `"Overview" row locked (toggle disabled, grip hidden)`.

The backend `_WORKSPACE_DEFINITIONS` (verified in `control_plane.py`) uses `workspace_key: "dashboard"` with `workspace_name: "Dashboard"`. The current `ModuleTabs.tsx:37` already checks for `workspace_key === "dashboard"`. The spec contains a terminology error — `"overview"` should read `"dashboard"`.

**Recommendation to user:** treat the locked design as containing a terminology error. Use `"dashboard"` as the locked-first-tab key in SP-3A. User confirms or overrides this recommendation before SP-3A is drafted.

### S-004 full text

The locked design describes an "Available" tab with "add toggles" but does not specify what the toggleable units are. Two architecturally different interpretations:

**Vocabulary A — workspace-level tabs** (7 keys: `dashboard/erp/accounting/reconciliation/close/reports/settings`):
- Module Manager manages the same surface as the tab bar.
- "Available" tab toggles which workspace tabs the user sees.
- Aligns with `MODULE_ICON_MAP` and `_WORKSPACE_DEFINITIONS`.
- Backend API would be a new `POST /api/v1/orgs/{orgId}/modules` endpoint that sets which `workspace_key` values are enabled for the tenant. The `workspace_tabs` response from `getControlPlaneContext` would then filter to only enabled workspaces.
- This interpretation makes the + button a shortcut to reconfigure the tab bar.

**Vocabulary B — sub-module instruments** (`LEASE/REVENUE/ASSETS/PREPAID/ACCRUAL/SUBSCRIPTION`, per the existing `/settings/modules` page):
- Module Manager manages accounting instruments inside (likely) the ERP or Accounting workspace.
- Backend API would be the existing (old) `/api/v1/modules/{name}/enable|disable` endpoints or a successor.
- This interpretation makes the Module Manager a rebrand/upgrade of the existing `/settings/modules` page.

**S-004 is linked to S-001:** Vocabulary B makes `/settings/modules` the legitimate ancestor (S-001 disposition = "inherit and upgrade" or "Replace"). Vocabulary A makes `/settings/modules` pure legacy with no vocabulary inheritance (S-001 disposition = "Replace" or "Sunset").

**User must decide before SP-3A can be drafted.**

---

## 4. Sub-prompt Dependency Map

### Proposed sub-prompt list

| ID | Scope | Files touched (tentative) | Dependencies | Backend tickets | Est. size | Parallel? |
|---|---|---|---|---|---|---|
| **SP-3A** | Module Manager modal shell — Active/Available/Premium tabs, + button wiring, Overview enforcement, module ordering state | `components/layout/ModuleTabs.tsx`, `components/modules/ModuleManager.tsx` (new), `lib/store/workspace.ts` (ordering state), `lib/api/modules.ts` or new `lib/api/workspaces.ts`, `lib/query/keys/` (new workspace-modules keys) | S-003 + S-004 resolved; Phase 1 (done) | `module.manage` permission, `GET /api/v1/billing/module-pricing`, `POST /api/v1/orgs/{orgId}/modules` | L (5–7 days) | Modal shell + Premium tab zero-state can partially proceed; Active tab drag integration waits for SP-3B |
| **SP-3B** | @dnd-kit install + drag-to-reorder in Active tab | `package.json`, `components/modules/ModuleManager.tsx` (Active tab section only) | SP-3A modal shell must exist first (or use git worktree parallel) | None | M (2–3 days) | Parallelizable with SP-3A shell via git worktree — install + reorder primitive is isolated |
| **SP-3C** | Auditor sidebar — add Governance nav group with Audit trail visible to `auditor` role | `lib/config/navigation.ts`, `lib/ui-access.ts` (possibly), `components/layout/Sidebar.tsx` | Phase 1 sidebar structure (done) | None (uses existing `auditor` role alias) | S (1–2 days) | Fully parallelizable with SP-3A/SP-3B via git worktree |
| **SP-3D** | Custom tab (Module Manager intake form) | `components/modules/ModuleManager.tsx` (Custom tab section) | SP-3A modal shell, backend `POST /api/v1/orgs/{orgId}/modules/custom-request` (or equivalent) | Custom request endpoint (unspecified) | Unknown — depends on spec | Cannot start until Custom tab spec is defined |
| **SP-2E** (carry-forward) | Consolidation tab disable + Tax/GST jurisdictional relabeling | `components/layout/ModuleTabs.tsx`, `components/layout/EntityScopeBar.tsx` | BE-002 (backend ticket — not yet implemented) | BE-002 (`is_consolidation_parent`, workspace tab promotion) | M (2–3 days) | After BE-002 lands |

### Recommended execution order

```
SP-3C (standalone, 1–2 days)
  ↓ parallel with ↓
SP-3A (modal shell + Active/Available/Premium) — BLOCKED on S-003 + S-004 resolution
SP-3B (dnd-kit + drag) — parallelizable with SP-3A via git worktree once modal shell exists

SP-3D — deferred until Custom tab is specified
SP-2E — deferred until BE-002 lands
```

SP-3C can start immediately (no blockers, no open questions). SP-3A is the critical path blocker — S-003 and S-004 must be resolved first.

### S-001 disposition effect on SP-3A file-touch list

| S-001 option | Additional files in SP-3A |
|---|---|
| Replace | `frontend/app/(dashboard)/settings/modules/PageClient.tsx` (rewrite or remove) |
| Redirect | `frontend/app/(dashboard)/settings/modules/page.tsx` (add redirect) |
| Sunset (SP-3X) | No change to SP-3A; add SP-3X to sub-prompt list |

---

## 5. Backend Ticket Sharpening

### module.manage permission ticket

**What the frontend expects:**

- **Permission identifier string:** `"module.manage"`
- **Role mapping (tentative):** `tenant_admin` and `tenant_owner` permitted. `tenant_member`, `tenant_manager`, `tenant_viewer` (includes `auditor`) NOT permitted.
- **Frontend integration point:** a single entry added to `PERMISSIONS` in `frontend/lib/permission-matrix.ts`:
  ```ts
  "module.manage": {
    module: "workspace_modules",
    roles: ["tenant_admin", "tenant_owner"],
    entitlement_keys: [],   // or ["workspace_modules"] if plan-gated
    feature_flag: null,
    runtime_roles: [],
  }
  ```
- **Sequencing:** Phase 3 SP-3A ships `canPerformAction("module.manage", ...)` on the + button before this ticket lands. Until the ticket lands, all users see the gated zero-state (lock icon + "Ask your admin"). When the ticket lands, the coordinated frontend change is the single `PERMISSIONS` entry above — no other refactors required.
- **Acceptance criterion for the ticket:** the permission must be exposed via the same entitlements/role-check surface that `canPerformAction` reads from today (session role + `GET /api/v1/billing/entitlements/current`). Do NOT introduce a new permission delivery mechanism in this ticket.

### GET /api/v1/billing/module-pricing (new ticket to file)

**Context:** Phase 3 Premium tab requires per-module credit/pricing data. This endpoint does not exist in the frontend or backend.

**What the frontend expects:**

```ts
// Proposed response shape (to be confirmed by backend):
Array<{
  workspace_key: string         // matches MODULE_ICON_MAP keys
  workspace_name: string
  price_per_month: string       // Decimal-safe string, e.g. "29.00"
  currency: string              // ISO 4217, e.g. "USD"
  credits_per_month: number | null  // if priced in credits instead of / in addition to money
  is_free: boolean              // true for modules included in base plan
}>
```

**Sequencing:** SP-3A renders the Premium tab with skeleton/zero-state ("Pricing unavailable — loading") until this endpoint lands. The Premium tab zero-state is a valid Phase 3 MVP. This ticket can be drafted alongside `module.manage` and executed in parallel by the backend track.

### POST /api/v1/orgs/{orgId}/modules (new endpoint needed by SP-3A)

**Context:** Phase 3 Module Manager Save action calls this endpoint to update workspace-tab enablement and ordering. Depends on S-004 resolution (Vocabulary A vs B determines the request shape).

**What the frontend expects (Vocabulary A — workspace-level tabs):**

```ts
// Request body:
{
  enabled_workspace_keys: string[]   // ordered array of enabled workspace_key values
}
// Response: updated ControlPlaneContext.workspace_tabs (or 204 + client-side optimistic update)
```

**Vocabulary B shape would differ materially** — file after S-004 is resolved.

### BE-002 — entity model additions

**AC-3 (is_consolidation_parent) — PENDING:** `OrgEntityResponse` does not yet have `is_consolidation_parent`. Backend must add a computed boolean field. The data for inference exists: `OrgOwnership` relationships (`parent_entity_id`, `child_entity_id`). Recommended implementation: calculated field on `OrgEntityResponse` returning `true` if the entity has any children in `entity_hierarchy`.

**AC-4 (country_code) — ALREADY MET:** `OrgEntityResponse.country_code: str` confirmed in `org_setup/api/schemas.py:156`. Frontend `OrgEntity.country_code: string` confirmed. No backend change needed for this criterion.

**Frontend impact when BE-002 lands:** Add `is_consolidation_parent: boolean` to `OrgEntity` type in `frontend/lib/api/orgSetup.ts`. The `useOrgEntities()` hook consumers (Sidebar, EntityScopeBar, EntityCardPicker) pick up the new field without hook rewrites. SP-2E uses it for consolidation tab gating logic.

---

## 6. Polish-Window Pairing Recommendations

| Deferred item | Status at pre-flight | Natural Phase 3 pairing |
|---|---|---|
| **FU-019** — control_plane TooltipProvider failures (3 tests) | Open, ~1–2h | Pair with SP-3A: `control_plane_shell.test.tsx` imports `ModuleTabs`; SP-3A modifies `ModuleTabs.tsx`. Fix FU-019 in the same sub-prompt or resolve it as a pre-SP-3A standalone step. |
| **FU-005** — deprecated `active_entity_id` + `pinnedModules` field removal | Open (writers cleared by FU-015; fields remain) | Pair with SP-3A if SP-3A adds module ordering state to `workspace.ts` (same store edit). Otherwise, standalone micro-sprint between SP-3A and SP-3B. |
| **TD-017** — `orgs.ts` endpoint duplication | Open, ~4h | No Phase 3 overlap confirmed. Standalone slot between phases or end-of-Phase-3 polish window. |
| **FU-008** — E2E spec mockSession sweep (15 specs, not 14) | Open, ~1–2h | No E2E spec tests workspace tab bar behavior. FU-008 is safe to run in parallel with any Phase 3 sub-prompt as a standalone task. |
| **FU-007** — Onboarding wizard test text mismatches | Open | No Phase 3 overlap. Run independently in polish window. |

---

## 7. Open Questions for User Decision

These items require user decisions before the affected sub-prompts can be drafted. **These are NOT agent recommendations to be accepted silently — they require explicit user choices.**

---

### OQ-1: S-001 — `/settings/modules/PageClient.tsx` disposition

The page exists with the old API pattern and a hardcoded instrument vocabulary. Phase 3 must decide what to do with it.

**Your options:**
1. **Replace** — SP-3A ships the new Module Manager modal and removes or rewrites `PageClient.tsx` in the same sub-prompt.
2. **Redirect** — SP-3A ships the modal and adds a redirect from `/settings/modules` → modal entry point. Page shell removed later.
3. **Sunset (SP-3X)** — A separate cleanup sub-prompt removes the page, sequenced separately.

Choosing between these also depends on OQ-3 (vocabulary). If you choose Vocabulary B (instruments), the page's concept survives in the modal. If you choose Vocabulary A (workspace tabs), the page is pure legacy.

---

### OQ-2: S-003 — "overview" vs "dashboard" workspace key

The locked design Phase 3 Task 4 references `workspace_key !== 'overview'`. The backend canonical key is `"dashboard"`. Current `ModuleTabs.tsx` already uses `"dashboard"`.

**Agent recommendation:** treat this as a terminology error in the locked design; use `"dashboard"` as the locked-first-tab key in SP-3A.

**Your choice:** confirm this recommendation, or override it (in which case, specify the correct key and whether the backend needs updating).

---

### OQ-3: S-004 — Module Manager Available-tab vocabulary (product decision)

The locked design does not specify what units the Available tab toggles.

**Vocabulary A — workspace-level tabs** (dashboard/erp/accounting/reconciliation/close/reports/settings):
- Module Manager reconfigures the tab bar.
- "Available" shows workspace tabs the user hasn't enabled yet.
- Aligns with `MODULE_ICON_MAP`. New backend endpoint controls which workspace tabs are active.

**Vocabulary B — sub-module instruments** (LEASE/REVENUE/ASSETS/PREPAID/ACCRUAL/SUBSCRIPTION):
- Module Manager manages accounting instrument features inside specific workspaces.
- Conceptually continues the existing `/settings/modules` page.
- Calls the existing (or successor) `/api/v1/modules/{name}` endpoints.

**Note:** This decision also resolves OQ-1. Vocabulary A → S-001 disposition is Replace or Sunset (pure legacy). Vocabulary B → S-001 disposition is Replace (inherit and upgrade the concept).

---

### OQ-4: SP-3D Custom tab — defer or stub?

The locked design describes the Custom tab as an "intake form" with no further specification. No backend endpoint is visible.

**Your options:**
1. **Stub** — SP-3A includes the Custom tab as a placeholder ("Coming soon — contact your admin") with no functional form. No backend ticket needed yet.
2. **Defer** — Custom tab not implemented in Phase 3. Modal ships with 3 real tabs (Active/Available/Premium) and no Custom tab until the spec is written.
3. **Specify first** — define the intake form fields and submission endpoint before SP-3A, then implement in full.

---

### OQ-5: SP-3C auditor sidebar — Phase 3 or Phase 6?

The locked design places the auditor sidebar in Phase 3 (Task 6). Phase 6 is "RBAC + Portal Alignment" which also mentions auditor role verification.

**Your options:**
1. **Phase 3** — SP-3C runs alongside SP-3A/SP-3B as planned.
2. **Phase 6** — Move auditor sidebar to Phase 6 RBAC alignment. Keeps Phase 3 tighter.

SP-3C is small (~1–2 days, no backend dependency) and fully parallelizable — keeping it in Phase 3 costs little. Deferring avoids revisiting the sidebar twice.

---

### OQ-6: FU-019 pairing — pre-SP-3A or same-branch?

`control_plane_shell.test.tsx` imports `ModuleTabs` and is one of the 3 FU-019 failing tests. Phase 3 SP-3A modifies `ModuleTabs.tsx`.

**Your options:**
1. **Pre-SP-3A standalone** — Fix FU-019 (TooltipProvider in 3 test files, ~1–2h) as a standalone commit before SP-3A starts. Cleanest separation.
2. **Same SP-3A branch** — Include FU-019 fix in SP-3A's file-touch list. Saves a branch but mixes test-infra with feature work.

---

## Appendix A — Modal Infrastructure Notes

- `frontend/components/ui/Dialog.tsx` exists: custom portal-based implementation, not Radix UI Dialog. Supports size variants `sm/md/lg`.
- Size fit: locked design spec `max-w-[640px]`; `md` variant = `max-w-2xl` (672px). Delta: 32px.
- **Recommendation:** use inline `className` override on the Dialog instance (e.g. `className="max-w-[640px]"`). No new size variant needed unless 640px is referenced elsewhere in the design system.
- `frontend/components/ui/tabs.tsx` exists: Radix UI `@radix-ui/react-tabs`. Ready for the 4 sub-tabs.
- `components/modules/` directory does not exist — target path for `ModuleManager.tsx` is greenfield.

---

## Appendix B — Section 2 Territory Maps (for sub-prompt authors)

### TD-017 territory (do NOT touch in Phase 3 sub-prompts)
- `frontend/app/(auth)/orgs/PageClient.tsx`
- `frontend/components/layout/OrgSwitcher.tsx`
- `frontend/tests/unit/orgs_api.test.ts`

### TD-016 / BE-002 territory (do NOT assume these tabs exist until BE-002 lands)
- `frontend/app/(dashboard)/consolidation/PageClient.tsx` and sub-pages
- `frontend/app/(dashboard)/tax/PageClient.tsx` and sub-pages
- `frontend/lib/api/consolidation.ts`, `frontend/lib/api/tax.ts`
- `frontend/lib/config/navigation.ts` — has sidebar nav items for consolidation/tax; these are sidebar-only, NOT workspace tabs

When BE-002 lands, `MODULE_ICON_MAP` needs `consolidation` and `tax` keys added.

---

*Pre-flight investigation complete. Awaiting user review of this document and approval to begin sub-prompt drafting.*
