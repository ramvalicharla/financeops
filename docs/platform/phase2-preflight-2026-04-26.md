# Phase 2 Pre-Flight — Org + Entity Switching

**Date:** 2026-04-26
**Branch:** chore/phase2-preflight
**Pre-flight HEAD:** 14cb364
**Author:** Claude Code (read-only investigation)

---

## Executive Summary

Pre-flight cleared 6 of 8 deliverables for sub-prompt drafting. Two deliverables (Consolidation tab disable, Tax/GST relabel) are **blocked** by a structural mismatch: the locked design assumes standalone `consolidation` and `tax` workspace tabs that do not exist in the backend's `_WORKSPACE_DEFINITIONS`. Three surprises require immediate ticket amendments before SP-2A begins: the actual switch endpoint response shape diverges from both the ticket spec and the existing `enterSwitchMode` signature, the `ViewingAsBanner` has admin-impersonation copy baked in ("Read-only · 15 min token") that would display to regular users on org switch, and a `ContextBar` component already occupies the layout slot where `EntityScopeBar` must mount. The four cleared sub-prompts (SP-2A through SP-2D) can begin in parallel once these amendments are resolved.

---

## Section 1 — Reconciliation read findings

### 1.1 Locked design extract

**Source:** `docs/audits/finqor-shell-audit-2026-04-24.md`, §3.3 Phase 2

**8 deliverables (findings closed):**

| # | Deliverable | Findings | Files touched | Visible behavior |
|---|---|---|---|---|
| 1 | OrgSwitcher for all users | F-17 | `OrgSwitcher.tsx` | All auth users see org list; click switches org context |
| 2 | Entity card as picker | F-3 | `Sidebar.tsx` | Card becomes clickable; entity picker popover with tree; card turns blue on selection |
| 3 | Entity tree in sidebar | F-7 | `Sidebar.tsx` | Compact parent/sibling tree below card; "Back to all entities" link |
| 4 | EntityScopeBar | F-2, F-34 | `EntityScopeBar.tsx` (new), `layout.tsx` | Full-width `bg-[#E6F1FB]` strip below tabs when `entityId != null`; "Clear scope ✕" |
| 5 | Consolidation tab disable | F-8 | `ModuleTabs.tsx` | `opacity-50 pointer-events-none` + tooltip when `entityId != null` |
| 6 | Tax/GST jurisdictional relabel | F-9 | `ModuleTabs.tsx` | Tab label changes to "Tax / GST" (India), "Tax / US" etc based on entity country |
| 7 | Collapsed rail entity chip | F-13 | `Sidebar.tsx` | "F" chip replaced with "A7" (org initial + entity count) or single letter when entity scoped |
| 8 | Currency from entity | F-27 | `useFormattedAmount.ts`, `workspace.ts` | `formatAmount` uses entity's `functional_currency` not user pref currency |

**Invariants the design relies on:**
- `entityId = null` means "all entities" / consolidated view
- `EntityScopeBar` hidden when `entityId == null`
- Consolidation tab greyed (not hidden) when `entityId != null`
- Entity tree groups by org/parent structure from ownership API
- Currency from entity `functional_currency` field

---

### 1.2 BE-001 ticket as shipped

**Source:** `docs/tickets/backend-user-org-memberships.md` + source reads

**GET /users/me/orgs** (actual implementation at `backend/financeops/api/v1/users.py:420`):
```python
@router.get("/users/me/orgs", response_model=UserOrgsListResponse)
async def get_my_orgs(...)
```
Response shape (verbatim from models at lines 392–438):
```typescript
type UserOrgsListResponse = {
  items: UserOrgItem[]  // filtered: status == "active" only
  total: number         // len(items), NOT a DB count
}
type UserOrgItem = {
  org_id: string        // UUID
  org_name: string
  org_slug: string
  org_status: string    // "active" | "suspended" | "trial"
  role: string          // UserRole enum value
  is_primary: boolean
  joined_at: string     // ISO 8601
}
```
No pagination (returns all active memberships). Empty list returns `{ items: [], total: 0 }`, NOT 404.

**POST /users/me/orgs/{tenant_id}/switch** (actual implementation at lines 441–455):
```python
@router.post("/users/me/orgs/{tenant_id}/switch", response_model=SwitchOrgResponse)
```
**ACTUAL response shape** (lines 409–418):
```python
class SwitchTargetOrg(BaseModel):
    id: str
    name: str
    role: str

class SwitchOrgResponse(BaseModel):
    switch_token: str
    target_org: SwitchTargetOrg
```
Serialised: `{ switch_token: "...", target_org: { id: "...", name: "...", role: "..." } }`

**DIVERGES from ticket spec §4.2** which specified flat fields: `{ switch_token, tenant_id, tenant_name, tenant_slug, expires_in_seconds }`. Missing from actual response: `tenant_slug`, `expires_in_seconds`. Shape is nested, not flat.

**deps.py:281 amendment** (verified at lines 281–293):
```python
if user.tenant_id != jwt_tenant_id:
    if payload.get("scope") == "user_switch":
        membership_result = await session.execute(
            select(UserOrgMembership).where(
                UserOrgMembership.user_id == user.id,
                UserOrgMembership.tenant_id == jwt_tenant_id,
                UserOrgMembership.status == "active",
            )
        )
        if not membership_result.scalar_one_or_none():
            raise AuthenticationError("No active membership in target tenant")
    else:
        raise AuthenticationError("Token tenant mismatch")
```
Switch token has `scope: "user_switch"` claim. Non-switch tokens are unchanged. Membership revocation is checked on every request.

**Token lifetime:** Normal `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (NOT 900s). No `switched_by` or `platform_switch` scope.

---

### 1.3 Frontend OrgSwitcher / EntitySwitcher / workspaceStore state

**OrgSwitcher.tsx** (full read, 159 lines):
- Role gate at lines 28–30: `PLATFORM_OWNER_ROLES = ["platform_owner", "super_admin"]`. Regular users: returns null (invisible).
- Calls `adminListTenants({ limit: 200 })` — platform admin endpoint `GET /api/v1/platform/admin/tenants`.
- Calls `switchToTenant(tenant.id)` — alias for `adminSwitchTenant` at `lib/api/admin.ts:102`, hitting `POST /api/v1/platform/admin/tenants/{id}/switch`.
- `handleSelect` at lines 62–82 calls `enterSwitchMode({ switch_token: result.switch_token, tenant_id: result.tenant_id, tenant_name: result.tenant_name })`.
- `enterSwitchMode` signature in `tenant.ts:38–43` expects `{ switch_token, tenant_id, tenant_name, tenant_slug? }` — FLAT, not nested.

**EntitySwitcher.tsx** (full read, 128 lines):
- Takes `entityRoles: EntitySwitcherOption[]` as prop (already-resolved list).
- Calls `workspaceStore.switchEntity(entity.entity_id)` on selection.
- Does NOT call any API on selection — entity switch is purely Zustand state.
- Single-entity case: renders static text, no dropdown.
- No tree view — flat list in popover.

**useOrgEntities hook** (`hooks/useOrgEntities.ts`):
- Calls `listOrgEntities()` → `GET /api/v1/org-setup/entities` (live endpoint, from Phase 0 sub-prompt 0.3).
- Maps `OrgEntity` → `{ entity_id: e.id, entity_name: e.display_name ?? e.legal_name, role: null }` — **drops `country_code` and `functional_currency`**.
- Falls back to `useTenantStore.entity_roles` while loading or on error.

**workspaceStore** (`lib/store/workspace.ts`, full read):
```typescript
WorkspaceState = {
  orgId: string | null
  entityId: string | null
  moduleId: string | null
  period: string | null
  sidebarCollapsed: boolean
  switchOrg: (orgId) => void  // resets entityId, moduleId
  switchEntity: (entityId) => void  // preserves module, period
}
```
No `entityCurrency`, no `entityCountry` field. `switchOrg` resets downstream context.

**Axios interceptor** (`lib/api/client.ts:106–145`):
- Lines 120–122: when `is_switched && switch_token`, uses `switch_token` as Bearer and `switched_tenant_id` as `X-Tenant-ID`. Transparent to callers.
- Lines 185–191: on 401 while `is_switched`, exits switch mode and redirects to `/dashboard?switch_expired=1`.
- No cache invalidation inside the interceptor — that's the caller's responsibility.

**is_switched / ViewingAsBanner consumption** (verbatim, `ViewingAsBanner.tsx:59`):
```tsx
<span className="hidden sm:inline text-amber-300/60 text-xs font-normal">
  · Read-only · 15 min token
</span>
```
This text fires for ALL `is_switched` states. Admin impersonation is read-only; user-org switching is not.

---

### 1.4 Phase 1 shell mount points

**TopBar** (`Topbar.tsx:306–331`, desktop layout):
```
[BrandMark] [orgName pill] / [EntitySwitcher] [OrgSwitcher]   [title] [contextSummary]
                                                               [EntityLocationSelector] [ScaleSelector] [FY chip] [Search] [NotificationBell] [ProfileMenu]
```
OrgSwitcher is at line 324. EntitySwitcher is at line 321 (inside the org/entity breadcrumb area). Both exist in TopBar.

**Sidebar entity card** (`Sidebar.tsx:127–167`):
- Collapsed: `Sidebar.tsx:129–133` — 32px "F" brand chip (`bg-primary`, `text-primary-foreground`) — NOT entity indicator.
- Expanded: `Sidebar.tsx:135–167` — static card with "ACTIVE ENTITY" label, `contextQuery.data?.current_entity.entity_name`, "Backend" badge chip. No click handler, no dropdown caret.

**Nav groups** (`Sidebar.tsx:178–233`): Three collapsible groups (Workspace / Org / Governance) from `NAV_GROUPS` config. No entity tree section. No "entities" sub-section.

**Module tab bar** (`ModuleTabs.tsx:53–87`): `h-10` fixed container at `layout.tsx:84`. No scope/disable logic on any tab.

**ContextBar** (`layout.tsx:85`): Mounted between `<ModuleTabs />` and `<main>`. This is the existing stub that Phase 2's `EntityScopeBar` must replace.

**Dashboard layout mount order** (`app/(dashboard)/layout.tsx:84–96`):
```
<ModuleTabs />
<ContextBar tenantSlug={tenantSlug} />
<main>
  <DataActivationReminder />
  <Breadcrumb />
  {children}
</main>
```
EntityScopeBar replaces `<ContextBar>` at this slot.

**Sidebar dimensions** (verified): width 220px (`style={{ width: sidebarCollapsed ? "52px" : "220px" }}`), collapsed 52px — both Phase 1 targets already hit.

---

### 1.5 Module registry / consolidation

**Backend `_WORKSPACE_DEFINITIONS`** (`backend/financeops/platform/api/v1/control_plane.py:44–99`), full extract:

| workspace_key | workspace_name | href | module_codes |
|---|---|---|---|
| dashboard | Dashboard | /dashboard | [] |
| erp | ERP | /erp/sync | [erp_sync] |
| accounting | Accounting | /accounting/journals | [accounting_layer, fixed_assets, prepaid, **gst**] |
| reconciliation | Reconciliation | /reconciliation/gl-tb | [reconciliation_bridge, payroll_gl_normalization, bank_reconciliation] |
| close | Close | /close/checklist | [monthend, **multi_entity_consolidation**, closing_checklist] |
| reports | Reports | /reports | [custom_report_builder, board_pack_generator, ...] |
| settings | Settings | /settings | [] |

**Critical:** There is NO `consolidation` workspace tab. Consolidation (`multi_entity_consolidation`) is a module_code INSIDE the `close` workspace. There is NO `tax` or `gst` workspace tab. GST is a module_code INSIDE the `accounting` workspace.

**Frontend MODULE_ICON_MAP** (`components/layout/tabs/module-icons.ts`): 7 entries matching all 7 workspace keys exactly (`dashboard, erp, accounting, reconciliation, close, reports, settings`). No per-module scope/consolidation flag.

No "requires_all_entities" or "single_entity_valid" field exists on workspace definitions anywhere.

---

### 1.6 Currency formatting

**`formatAmount`** (`lib/utils.ts:51–80`):
```typescript
export function formatAmount(
  amount: number | string | null | undefined,
  scale: DisplayScale = "LAKHS",
  currency: string = "₹",   // ₹ default
  options: { showLabel?, showCurrency?, decimalPlaces?, compact? } = {},
): string
```
Currency is a third parameter. Already accepts override. Default is `₹`.

**`useFormattedAmount`** (`hooks/useFormattedAmount.ts`):
```typescript
const { scale, currency } = useDisplayScale()  // user preference store
// ...
fmt: (amount, overrideScale?) => formatAmount(amount, overrideScale ?? scale, currency)
```
Currency comes from `useDisplayScale` (user-level preference, persisted to localStorage). NOT entity-specific.

**`displayScale` store** (`lib/store/displayScale.ts`): `{ scale: "INR", currency: "₹", locale: "en-IN" }` — user display pref, NOT org/entity context.

**`OrgEntity` type** (`lib/api/orgSetup.ts:87,89`):
```typescript
export interface OrgEntity {
  // ...
  country_code: string        // line 87
  functional_currency: string // line 89
}
```
Both fields ARE present on the entity type and in the backend response (confirmed at `backend/financeops/modules/org_setup/api/schemas.py:148,150`).

**Gap**: `useOrgEntities.ts:23–28` maps `OrgEntity → { entity_id, entity_name, role }`, dropping `country_code` and `functional_currency`. There is zero data path from entity's `functional_currency` to `formatAmount`.

**Existing call sites** (sampled):
- `hooks/useFormattedAmount.ts` — hook; currency comes from displayScale ✗
- `app/(dashboard)/.../revaluation/PageClient.tsx:81` — displays `runMutation.data.functional_currency` as a DD label (read-only display, not formatAmount)
- No call site passes entity functional_currency to `formatAmount` today

---

### 1.7 FU overlaps

**FU-005** (Remove deprecated fields from legacy Zustand stores):
- `active_entity_id` — on `tenantStore`, `@deprecated`, still has readers in `OrgSetupPageClient.tsx` (now via workspaceStore — HOTFIX 1.1.5 addressed read sites, FU-015 tracks write sites)
- `entity_roles` — still on `tenantStore`, used as fallback in `useOrgEntities.ts:32`
- Phase 2 OrgSwitcher sub-prompt touches `tenantStore` and potentially introduces a new `enterUserSwitchMode` action — FU-005 can fold into SP-2A (same file, same session) but only the OrgSwitcher-adjacent cleanup, not the full FU-005 scope.

**FU-012** (Sidebar behavioral wiring — badges, RBAC, real routes):
- Track 1 (Approvals badge): independent of Phase 2
- Track 2 (RBAC filter): overlaps with Phase 2 if SP-2A introduces role-based OrgSwitcher visibility logic. Recommend keeping RBAC filter in FU-012; SP-2A only removes the hard platform-admin gate, not adds per-item RBAC.
- Track 3 (real routes for placeholder items): "Today's focus", "Period close", "Approvals" — may overlap with Phase 2 sidebar navigation work. Keep separate; do not fold.

**FU-018** (Invite modal entity-fetch warning):
- Target file: `frontend/app/(dashboard)/settings/team/_components/UsersPanel.tsx`
- Zero overlap with Phase 2 files
- ~30 min effort; can run as a parallel quick task alongside any Phase 2 SP

---

## Section 2 — Decision log

### Decision 2.1 — OrgSwitcher: repurpose in place or fork?

**Recommendation: Option A — Repurpose in place.**

**Evidence:**
1. `OrgSwitcher.tsx` has 3 consumers: itself, `Topbar.tsx:324`, `lib/api/admin.ts` (named alias `switchToTenant`).
2. The platform admin impersonation flow (`control-plane/admin/tenants/[id]/PageClient.tsx:151–155`) does NOT use `OrgSwitcher` — it writes directly to `sessionStorage` and handles its own switch independently.
3. `OrgSwitcher.tsx` is therefore not shared with admin impersonation in practice; it is purely a TopBar control.
4. The component already has the Popover + Command list structure that works for user-facing switching.

**Plan:** Remove `PLATFORM_OWNER_ROLES` gate, replace `adminListTenants()` call with new `listUserOrgs()` function hitting `GET /users/me/orgs`, replace `switchToTenant()` call with new `switchUserOrg(tenantId)` function hitting `POST /users/me/orgs/{id}/switch`. Adapt `handleSelect` to the nested `target_org` response shape (see S-001). The admin impersonation path is unaffected because it lives in a separate component.

**Impact on sub-prompt count:** SP-2A covers OrgSwitcher + the API adaptation. No fork sub-prompt needed.

---

### Decision 2.2 — Switch token frontend handling

**PARTIALLY OPEN** due to S-001 (nested response) and S-003 (banner semantics). The recommended sequence once S-001 is resolved:

1. User opens OrgSwitcher, selects an org
2. `POST /users/me/orgs/{tenant_id}/switch` → response: `{ switch_token, target_org: { id, name, role } }`
3. Call `enterSwitchMode({ switch_token: res.switch_token, tenant_id: res.target_org.id, tenant_name: res.target_org.name })` (tenant store, lines 96–103)
4. Call `workspaceStore.switchOrg(res.target_org.id)` to reset entityId, moduleId downstream
5. Call `queryClient.clear()` to invalidate ALL caches — org-scoped entity queries, module queries, context queries are all stale after org change
6. Close the popover; the Axios interceptor picks up `switch_token` automatically on all subsequent requests

**Open issue (S-003):** `enterSwitchMode` sets `is_switched = true`. `ViewingAsBanner` renders "Read-only · 15 min token" for all `is_switched` states. This copy is wrong for user-to-own-org switching.

**Decision needed:** Add a `switch_mode: "admin" | "user"` field to `enterSwitchMode` params and to `TenantState`. `ViewingAsBanner` conditionally shows the "Read-only" label only for `switch_mode === "admin"`. User-mode could show: "Viewing: [Org Name]" with a simpler banner (or no banner if the TopBar already reflects the org name). This is a low-effort amendment to SP-2A.

**Cache invalidation scope:** `queryClient.clear()` is the correct choice — all queries must invalidate because entity lists, module config, and data are all org-scoped.

**workspaceStore.switchOrg already handles downstream reset** — it resets `entityId` and `moduleId` (workspace.ts:53–61).

---

### Decision 2.3 — Entity card vs entity tree picker shape

**Recommendation:** Sidebar card = primary interactive picker; TopBar EntitySwitcher = secondary (remains flat list, no tree).

The sidebar entity card (`Sidebar.tsx:139–166`) is currently a static div. Phase 2 makes it clickable: add a `cursor-pointer` and a click handler that opens a `Popover` or `Sheet`. Inside: entity search input + flat list (or tree if ownership data is available).

**Tree depth question (OPEN for product):** The locked design says "Org → Entity → Module hierarchy made visual." But:
- Module hierarchy in the entity tree introduces complexity (modules change per user's tab config).
- The spec text for Phase 2 Task 3 says only "entity tree" not "entity-module tree."
- Recommendation: Show Org → Entity tree only (not modules). Modules are already in the tab bar. See Section 5 open question OQ-1.

**TopBar EntitySwitcher:** Remains as-is (flat list, no tree). Phase 2 does not touch it beyond ensuring it uses the correct data source (already wired via `useOrgEntities`).

**Empty state** (one org, one entity): Both sidebar card and TopBar EntitySwitcher already handle single-entity gracefully (shows name, no dropdown). No change needed for empty state.

---

### Decision 2.4 — EntityScopeBar mount point and visibility rules

**Mount point:** Replace `<ContextBar>` at `app/(dashboard)/layout.tsx:85`. The ContextBar already occupies this slot — it renders unconditionally between ModuleTabs and main. Phase 2's SP-2C either replaces ContextBar entirely with EntityScopeBar or converts ContextBar into EntityScopeBar (rename + restyle). Recommend full replacement: ContextBar serves a different design (always-on breadcrumb strip) while EntityScopeBar is conditional and styled differently.

**Visibility trigger:** `entityId !== null` in `workspaceStore`. Confirmed by locked design invariant and Phase 2 task 4 spec: "Render conditionally on `entityId != null`."

**What it shows:**
- Entity name
- `functional_currency` (if carried through after SP-2D)
- "Clear scope ✕" → `workspaceStore.switchEntity(null)` + `queryClient.invalidateQueries(['workspace'])`
- GAAP and "consolidation eliminated" mentioned in design — data source TBD (see OQ-3)

**Interactive:** Yes — "Clear scope ✕" is a click action. Entity name may also be clickable (opens picker). Not purely read-only.

---

### Decision 2.5 — Sidebar entity tree

**Recommendation:** Compact flat list below entity card (not parent/sibling tree), unless ownership-tree data is readily available.

The spec mentions "compact parent/sibling/selected-entity tree." The ownership tree API (`GET /api/v1/org-setup/ownership-tree`) exists and is already called in some components (`lib/api/orgSetup.ts:383`). If the tree is fetchable cheaply, use it. If it adds a blocking extra request to sidebar load, fall back to flat list with depth indicators (indent by parent level).

**Click behavior:** Clicking entity in sidebar tree = same as `workspaceStore.switchEntity(entityId)`. Entity picker and sidebar tree share the same action.

**"Back to all entities":** A small `← All entities` link that calls `workspaceStore.switchEntity(null)`.

**Active entity highlight:** The entity whose `entity_id === workspaceStore.entityId` gets `bg-accent` or `text-primary` treatment.

**Collapsed rail chip:** Replace the "F" brand chip (`Sidebar.tsx:130–133`) with entity chip: when `entityId != null`, show first letter of entity name; when all-entities, show org initial + entity count. The chip click in collapsed state opens the full sidebar (existing collapse toggle behavior) or opens a mini entity picker flyout.

---

### Decision 2.6 — Consolidation tab disable

**OPEN — requires product/design input.**

**Root cause (S-002):** There is no `consolidation` workspace tab in the backend. The `multi_entity_consolidation` module is grouped under the `close` workspace ("Close" tab, `workspace_key: "close"`).

Three options:
- **Option A (Backend change):** Add a new `workspace_key: "consolidation"` to `_WORKSPACE_DEFINITIONS`, move `multi_entity_consolidation` out of `close`. This is a backend+migration change before SP-2E can proceed.
- **Option B (Disable the Close tab):** Disable/warn the `close` tab (not a `consolidation` tab) when `entityId != null`. This is technically correct (consolidation lives under Close) but heavy — it also disables Month-End Checklist, which IS valid per-entity.
- **Option C (Route-level disable):** Instead of disabling a tab, detect when the user navigates to consolidation routes (`/close/consolidation`, `/consolidation`) with `entityId != null` and show an in-page banner/redirect, not a tab-level disable.

**Default assumption to unblock (see OQ-2):** Option C — route-level warning — has the lowest risk and no backend change. SP-2E is drafted for Option C unless product overrides.

---

### Decision 2.7 — Tax/GST jurisdictional relabel

**OPEN — requires product/design input.**

**Root cause (S-002):** There is no `tax` or `gst` workspace tab. Tax/GST (`gst` module code) is inside the `accounting` workspace (`workspace_key: "accounting"`, `workspace_name: "Accounting"`).

Options:
- **Option A (Backend change):** Add `workspace_key: "tax"` to `_WORKSPACE_DEFINITIONS`, split GST out of accounting.
- **Option B (Frontend label override):** When `entityId != null` and entity `country_code == "IN"`, dynamically override `workspace_name` for `accounting` to "Accounting · GST". Technically doable in `ModuleTabs.tsx`, but semantically wrong (the tab has much more than GST).
- **Option C (Route-level label):** Apply jurisdictional label inside the accounting pages themselves (breadcrumb, page title) based on entity country, not the module tab.

**Default assumption to unblock (OQ-2):** Option C for now. SP-2E deferred until clarified.

---

### Decision 2.8 — Currency from entity functional currency

**Recommendation: Extend `useOrgEntities` to carry `functional_currency`, store in `workspaceStore`, update `useFormattedAmount`.**

**Evidence:** `OrgEntity.functional_currency` is already in the API response and frontend type (confirmed at `lib/api/orgSetup.ts:89`). The fix path:

1. In `useOrgEntities.ts:23–28`: extend `toSwitcherItem` to also return `functional_currency`.
2. Add `entityCurrency: string | null` to `WorkspaceState` in `workspace.ts`.
3. In `switchEntity` action: update `entityCurrency` from the resolved entity (either lookup in query cache or pass from caller).
4. In `useFormattedAmount.ts`: read `entityCurrency` from `workspaceStore` when `entityId != null`; fall back to `displayScale.currency` when `entityId == null` (all-entities view).

**All-entities view:** Use `displayScale.currency` (user preference / org default) when no entity is selected. No "Mixed" display — just falls back to default.

**Impact on callers:** `useFormattedAmount()` is the hook; `formatAmount()` is the pure util that already accepts currency as 3rd arg. No call site changes needed — they call `fmt()` from the hook, which will now pass the right currency internally.

**Effort estimate:** Small (~2h). Does NOT require new endpoints. Smaller than the locked design implies.

---

## Section 3 — Surprises register

| ID | Source | Locked design says | Reality says | Impact on Phase 2 | Recommended action |
|---|---|---|---|---|---|
| S-001 | `backend/financeops/api/v1/users.py:415–418` | Switch endpoint returns flat `{ switch_token, tenant_id, tenant_name, tenant_slug, expires_in_seconds }` (ticket §4.2) | Backend returns nested: `{ switch_token, target_org: { id, name, role } }`. `tenant_slug` and `expires_in_seconds` absent | SP-2A's `handleSelect` will fail — `result.tenant_id` and `result.tenant_name` are undefined on the actual response | **Before SP-2A begins:** decide whether (a) frontend adapts to nested shape or (b) backend amends to flat shape. Option (a) is the lower-effort path. |
| S-002 | `backend/financeops/platform/api/v1/control_plane.py:44–99` | Deliverables 5 (Consolidation tab disable) and 6 (Tax/GST relabel) target standalone `consolidation` and `tax` module tabs | No such tabs exist. Consolidation is a module_code under `close`; GST is a module_code under `accounting`. 7 tabs total, none named Consolidation or Tax | Deliverables 5 and 6 cannot be implemented as specified. SP-2E is blocked | **Escalate to product/design (OQ-2).** Clarify target surface before drafting SP-2E. |
| S-003 | `frontend/components/layout/ViewingAsBanner.tsx:59` | Phase 2 reuses `enterSwitchMode` and `is_switched` infrastructure (intended design) | `ViewingAsBanner` hardcodes "Read-only · 15 min token" for ALL `is_switched=true` states — including the future user-org switch | Regular users switching between their own orgs will see "Read-only · 15 min token" banner, which is semantically wrong and alarming | SP-2A must add `switch_mode: "admin" \| "user"` field and update `ViewingAsBanner` to conditionally render admin copy. Low effort but must not be skipped. |
| S-004 | `frontend/lib/api/orgSetup.ts:87,89`, `hooks/useOrgEntities.ts:23–28` | Deliverable 8 requires "entity functional currency" as a new data fetch | `OrgEntity.functional_currency` is already in the API response and frontend type. `useOrgEntities` drops it during mapping | Deliverable 8 is smaller than specified — no new endpoint needed. But requires extending the mapping hook. | SP-2D: extend `toSwitcherItem` to carry `functional_currency`; add `entityCurrency` to `workspaceStore`. ~2h total. |
| S-005 | `frontend/components/layout/Topbar.tsx:321`, `Sidebar.tsx:139–166` | "Entity card as picker" (Deliverable 2) | TopBar already has a live `EntitySwitcher` (flat list, no tree). Sidebar card is a separate static component. Design says "entity card in Sidebar clickable" — these are two distinct components | Phase 2 Deliverable 2 targets only the sidebar card, not the TopBar switcher. Spec was ambiguous. | Clarify in SP-2B prompt that TopBar EntitySwitcher is untouched; sidebar card becomes the interactive picker. |
| S-006 | `frontend/app/(dashboard)/layout.tsx:85` | EntityScopeBar mounts "below module tabs" | `<ContextBar>` already occupies this exact slot and renders unconditionally | SP-2C must remove/replace ContextBar. If ContextBar has any value not covered by EntityScopeBar, those must be migrated first. | Read `ContextBar.tsx` in SP-2C gate. If it's a thin wrapper with no unique logic, delete it and mount `EntityScopeBar` at `layout.tsx:85`. |

---

## Section 4 — Sub-prompt dependency map

| ID | Sub-prompt title | Depends on | Touches files | Rough size | Can parallel with |
|---|---|---|---|---|---|
| SP-2A | OrgSwitcher wiring + switch token infra | None (but see S-001 resolution note) | `OrgSwitcher.tsx`, `lib/api/orgs.ts` (new), `lib/store/tenant.ts`, `ViewingAsBanner.tsx` | M (1–2 days) | SP-2C, SP-2D |
| SP-2B | Sidebar entity card as picker + entity tree + collapsed rail chip | SP-2A (tenant store switch_mode field must exist) | `Sidebar.tsx`, `EntityCardPicker.tsx` (new or inline) | M (2 days) | SP-2C, SP-2D after SP-2A merges |
| SP-2C | EntityScopeBar (replace ContextBar) | None | `EntityScopeBar.tsx` (new), `app/(dashboard)/layout.tsx`, `ContextBar.tsx` (remove) | S (1 day) | SP-2A, SP-2D |
| SP-2D | Currency from entity (useFormattedAmount + workspaceStore) | None | `hooks/useOrgEntities.ts`, `lib/store/workspace.ts`, `hooks/useFormattedAmount.ts` | S (<1 day) | SP-2A, SP-2C |
| SP-2E | Consolidation disable + Tax relabel | **BLOCKED** — S-002 must be resolved by product/design | `ModuleTabs.tsx`, possibly `control_plane.py` (backend) | Unknown | Cannot parallel anything until unblocked |
| SP-2F | FU-018 invite modal entity warning | None | `settings/team/_components/UsersPanel.tsx` | XS (30 min) | Any SP |

**FU fold decisions:**
- FU-005 (deprecated store fields): fold the `entity_roles` fallback question into SP-2A gate. Full FU-005 cleanup remains a separate session after Phase 2 ships.
- FU-012 Track 2 (RBAC filter): independent of Phase 2 — do NOT fold. Keep in its own FU-012 session.
- FU-012 Track 3 (real routes): keep separate.
- FU-018: fold into Phase 2 sprint as SP-2F, fully parallel.

**Section 0 gates required:**
- SP-2A: Before writing code, confirm S-001 resolution (backend amendment vs frontend adaptation). Also read `ContextBar.tsx` (verify it has no logic that should survive into EntityScopeBar).
- SP-2C: Read `ContextBar.tsx` in full — confirm it is safe to delete before removing.

**Parallel topology:**
```
          [SP-2A]──────────────────────────────────────→ [SP-2B]
         /
Start ──<──[SP-2C]
         \
          [SP-2D]
          [SP-2F]  (anytime, standalone)

[SP-2E] = BLOCKED (do not draft)
```
SP-2A, SP-2C, SP-2D, SP-2F can all start in parallel on Day 1. SP-2B waits for SP-2A to merge (tenant store shape change needed).

---

## Section 5 — Open questions for product/design

**OQ-1 — Entity tree depth in sidebar picker**
- *Question:* Should the entity picker (sidebar card + EntityScopeBar) show Org → Entity only, or Org → Entity → Module hierarchy?
- *Why it matters:* Blocks SP-2B and SP-2C's UI spec. Module-in-tree requires additional data fetching and syncs with tab state.
- *Default to unblock:* Org → Entity only. Modules are already visible in the tab bar; duplicating them in the tree adds complexity without clear user benefit.
- *Cost of getting default wrong:* Re-rendering the picker to add module depth is additive work (~0.5 days), not destructive.

**OQ-2 — Target surface for Consolidation disable and Tax relabel (BLOCKING SP-2E)**
- *Question:* Given that there is no standalone `consolidation` or `tax/gst` workspace tab (they are sub-modules of `close` and `accounting` respectively), what is the intended behavior?
  - Option A: Add new backend workspace tabs (`consolidation`, `tax`) — backend ticket required.
  - Option B: Apply behavior to the `close` tab (Consolidation = Close tab disable when entity selected).
  - Option C: Apply behavior at the route/page level, not the tab bar.
  - Option D: Defer both deliverables to Phase 3 (when Module Manager ships and per-module scope flags can be added to `_WORKSPACE_DEFINITIONS`).
- *Why it matters:* Completely blocks SP-2E. The two deliverables (F-8, F-9) cannot be implemented as written.
- *Default to unblock SP-2E partially:* Option C (route-level in-page warning when navigating to consolidation with entity selected). Tab bar unchanged.
- *Cost of getting default wrong:* Option C is additive — adding tab-level disable later is non-destructive. If product wants Option A (backend tabs), it requires a backend sprint first.

**OQ-3 — EntityScopeBar data: GAAP and consolidation-eliminated fields**
- *Question:* The locked design says EntityScopeBar shows "entity name, currency, GAAP, consolidation eliminated." Where do GAAP standard and consolidation-eliminated status come from? Is there an API field for these on the entity or context query?
- *Why it matters:* SP-2C needs to know the data source before implementing the bar.
- *Default to unblock:* Ship EntityScopeBar with entity name + currency only (both confirmed available). Add GAAP/consolidation-status in a follow-up once the data source is confirmed.
- *Cost of getting default wrong:* Low — the bar is a new component, fields can be added incrementally.

**OQ-4 — Post-switch UX for user-org switching**
- *Question:* When a regular user switches between their own orgs (not admin impersonation), what UX confirms the switch? Options: (a) a subtle banner like "Now viewing: Acme Holdings" that auto-dismisses after 3s, (b) no banner (TopBar org name updates are sufficient), (c) a toast notification.
- *Why it matters:* SP-2A must implement the `switch_mode: "user"` branch in `ViewingAsBanner` (or a separate component). The copy and treatment affect the component design.
- *Default to unblock:* Option (a) — auto-dismissing banner showing "Now viewing: [Org Name]", 3s timeout, no "Read-only" copy. Matches existing infrastructure in `ViewingAsBanner`.
- *Cost of getting default wrong:* ViewingAsBanner is a small component; re-styling is 30 min.

**OQ-5 — "All entities" view treatment in EntityScopeBar**
- *Question:* When `entityId == null` (all-entities / consolidated view), EntityScopeBar is hidden. But should there be any visual indicator that the user is in "all entities" mode vs "no entity selected" error state?
- *Why it matters:* SP-2C's conditional rendering logic.
- *Default to unblock:* No bar when `entityId == null` (matches locked design exactly). All-entities mode is the default state, not a special mode that needs indication.
- *Cost of getting default wrong:* Adding a placeholder bar for all-entities is additive, not destructive.

---

## Appendix A — Verbatim file reads

**Backend switch endpoint response shape** (`backend/financeops/api/v1/users.py:409–455`):
```python
class SwitchTargetOrg(BaseModel):
    id: str
    name: str
    role: str

class SwitchOrgResponse(BaseModel):
    switch_token: str
    target_org: SwitchTargetOrg

@router.post("/users/me/orgs/{tenant_id}/switch", response_model=SwitchOrgResponse)
async def switch_org(...) -> SwitchOrgResponse:
    result = await switch_user_to_org(session, user=current_user, target_tenant_id=tenant_id)
    return SwitchOrgResponse(
        switch_token=result["switch_token"],
        target_org=SwitchTargetOrg(
            id=result["target_tenant_id"],
            name=result["target_tenant_name"],
            role=result["role"],
        ),
    )
```

**Backend workspace definitions** (`control_plane.py:44–99`, 7 tabs, NO consolidation or tax):
```python
_WORKSPACE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    { "workspace_key": "dashboard", ... },
    { "workspace_key": "erp", ... },
    { "workspace_key": "accounting", "module_codes": ["accounting_layer", "fixed_assets", "prepaid", "gst"] },
    { "workspace_key": "reconciliation", ... },
    { "workspace_key": "close", "module_codes": ["monthend", "multi_entity_consolidation", "closing_checklist"] },
    { "workspace_key": "reports", ... },
    { "workspace_key": "settings", ... },
)
```

**ViewingAsBanner hardcoded admin copy** (`ViewingAsBanner.tsx:59`):
```tsx
<span className="hidden sm:inline text-amber-300/60 text-xs font-normal">
  · Read-only · 15 min token
</span>
```

**enterSwitchMode signature** (`lib/store/tenant.ts:38–46`):
```typescript
enterSwitchMode: (params: {
  switch_token: string
  tenant_id: string
  tenant_name: string
  tenant_slug?: string
}) => void
```

**OrgSwitcher handleSelect** (`OrgSwitcher.tsx:62–82`):
```typescript
const handleSelect = async (tenant: AdminTenantListItem) => {
  const result = await switchToTenant(tenant.id)  // returns flat shape from admin endpoint
  enterSwitchMode({
    switch_token: result.switch_token,
    tenant_id: result.tenant_id,    // ← undefined on the new user endpoint
    tenant_name: result.tenant_name, // ← undefined on the new user endpoint
  })
}
```

**OrgEntity type** (`lib/api/orgSetup.ts:79,87,89`):
```typescript
export interface OrgEntity {
  // ...
  country_code: string        // present
  functional_currency: string // present
}
```

**useOrgEntities drops currency** (`hooks/useOrgEntities.ts:23–28`):
```typescript
function toSwitcherItem(e: OrgEntity): UseOrgEntitiesItem {
  return {
    entity_id: e.id,
    entity_name: e.display_name ?? e.legal_name,
    role: null,
    // country_code and functional_currency NOT carried through
  }
}
```

**Dashboard layout mount order** (`app/(dashboard)/layout.tsx:84–86`):
```tsx
<ModuleTabs />
<ContextBar tenantSlug={tenantSlug} />  ← EntityScopeBar replaces this
<main>
```

---

## Appendix B — Phase 2 readiness gate

| Gate | Status | Notes |
|---|---|---|
| BE-001 endpoints verified live on main | ✅ PASS | `/users/me/orgs` and `/users/me/orgs/{id}/switch` both present and registered at `api/v1/users.py:420,441` |
| Locked design read in full | ✅ PASS | All 8 deliverables extracted with finding IDs, files, behaviors |
| All 8 deliverables have decision recommendations | ⚠️ PARTIAL | D2.1–D2.5, D2.8 resolved; D2.6 and D2.7 are OPEN (S-002) |
| Surprises register populated | ✅ PASS | 6 surprises documented; 1 critical (S-002) blocks SP-2E |
| Sub-prompt dependency map produced | ✅ PASS | 6 sub-prompts (SP-2A through SP-2F); parallel topology defined |
| Open questions enumerated with defaults | ✅ PASS | 5 open questions with unblock defaults |

**Phase 2 sub-prompt drafting authorized? PARTIAL YES**

- **SP-2A, SP-2C, SP-2D, SP-2F:** YES — authorized to draft immediately. SP-2A requires S-001 to be resolved (frontend adaptation to nested shape is the recommended path, no backend amendment needed).
- **SP-2B:** YES — draft but mark as depending on SP-2A merge.
- **SP-2E:** NO — blocked until OQ-2 is answered by product/design. Do not draft SP-2E until the target surface (tab-level vs route-level) for Consolidation disable and Tax relabel is clarified.

**Primary blocker:** S-002 — two Phase 2 deliverables target UI surfaces that do not exist in the current workspace tab structure. Product must decide Option A/B/C/D before SP-2E can be scoped.

**Secondary pre-work for SP-2A:** Confirm frontend adapts to nested `target_org` response (recommended: update `handleSelect` to read `result.target_org.id` and `result.target_org.name`). This is a 15-minute frontend fix in SP-2A, no backend amendment needed.
