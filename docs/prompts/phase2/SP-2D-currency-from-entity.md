# Claude Code Prompt — SP-2D: Currency from Entity Functional Currency

> **Purpose:** Wire entity `functional_currency` through the data path so that
> `useFormattedAmount` automatically uses the active entity's currency instead of the
> user-preference store. Implements Decision 2.8 and the OQ-5 all-entities fallback.
>
> **Mode:** Code. Frontend-only.
>
> **Branch:** `feat/sp-2d-currency-from-entity` from `main`
>
> **Estimated runtime:** ~2–4 hours (<1 dev-day)
>
> **Push:** NO. Local commit only.
>
> **Can run in parallel with:** SP-2A, SP-2C (disjoint file sets).

---

## Background context

The Phase 2 pre-flight (`docs/platform/phase2-preflight-2026-04-26.md`) covers this
sub-prompt through Decision 2.8 and Surprise S-004.

### Decision 2.8 — Extend data path, update hook

The recommended strategy (pre-flight §2.8, "util-resolves" variant):

1. **`hooks/useOrgEntities.ts`**: Extend `toSwitcherItem` to carry `functional_currency`
   (and `country_code`) from the `OrgEntity` type — both fields are already in the backend
   response and the frontend type at `lib/api/orgSetup.ts:87,89`.
2. **`lib/store/workspace.ts`**: Add `entityCurrency: string | null` to `WorkspaceState`.
   Update the `switchEntity` action to set `entityCurrency` from the resolved entity data.
3. **`hooks/useFormattedAmount.ts`**: Read `entityCurrency` from `workspaceStore` when
   `entityId !== null`. Fall back to `displayScale.currency` when `entityId === null`.

**Impact on callers:** Zero. `useFormattedAmount` exposes the `fmt()` function — callers
call `fmt(amount)` and get correct currency automatically. No call-site changes needed.

### Surprise S-004 — Field already present, mapping drops it

`OrgEntity.functional_currency` is in the API response and frontend type but is dropped in
`useOrgEntities.ts:23–28` during mapping. SP-2D extends the mapping — no new endpoint
needed.

### OQ-5 default — All-entities fallback

When `entityId === null` (all-entities view):
- `useFormattedAmount` falls back to `displayScale.currency` (user preference, currently `"₹"`)
- `workspaceStore.entityCurrency` is `null`
- No "Mixed" display — just the default currency

---

## Hard rules

1. No call-site changes to `formatAmount(...)` or `fmt(...)` callers — the change is
   entirely in the hook layer.
2. `formatAmount` in `lib/utils.ts` is a pure utility — do NOT modify it. It already
   accepts `currency` as its third parameter. Only the hook changes.
3. No new API endpoints. `functional_currency` is already in the existing
   `GET /api/v1/org-setup/entities` response.
4. Do not touch SP-2A files (`OrgSwitcher.tsx`, `lib/api/orgs.ts`, `lib/store/tenant.ts`,
   `ViewingAsBanner.tsx`) or SP-2C files (`EntityScopeBar.tsx`, `layout.tsx`,
   `ContextBar.tsx`).
5. Build, typecheck, and lint must pass clean before committing.

---

## Pre-flight (run before writing any code)

```bash
git status          # must be clean
git log --oneline main -1

git checkout -b feat/sp-2d-currency-from-entity
git branch --show-current

# Confirm useOrgEntities currently drops functional_currency
rg "toSwitcherItem\|functional_currency\|country_code" frontend/hooks/useOrgEntities.ts -n
# Expected: toSwitcherItem maps { entity_id, entity_name, role } — no functional_currency

# Confirm OrgEntity type has both fields
rg "functional_currency\|country_code" frontend/lib/api/orgSetup.ts -n | head -8
# Expected: both present on OrgEntity interface

# Confirm workspaceStore has NO entityCurrency today
rg "entityCurrency" frontend/lib/store/workspace.ts -n
# Expected: zero results — we are adding this field

# Confirm useFormattedAmount currently reads from displayScale only
rg "displayScale\|entityCurrency\|workspaceStore" frontend/hooks/useFormattedAmount.ts -n
# Expected: reads from useDisplayScale(), no workspaceStore reference yet

# Spot-check formatAmount call sites (to confirm no call-site changes needed)
rg "formatAmount\(" frontend/ -n | head -10
# Expected: callers use fmt() from the hook, not formatAmount directly (except lib internals)
```

**STOP if** `entityCurrency` already exists in `workspace.ts` (another sub-prompt may have
landed this change — investigate before proceeding).

---

## Section 1 — Extend `useOrgEntities` to carry `functional_currency`

**File:** `frontend/hooks/useOrgEntities.ts`

1. Locate `toSwitcherItem` (around lines 23–28).
2. Extend the return type to include `functional_currency: string` and
   `country_code: string`.
3. Map both fields from the `OrgEntity` source object:
   ```typescript
   function toSwitcherItem(e: OrgEntity): UseOrgEntitiesItem {
     return {
       entity_id: e.id,
       entity_name: e.display_name ?? e.legal_name,
       role: null,
       functional_currency: e.functional_currency,
       country_code: e.country_code,
     }
   }
   ```
4. Update the `UseOrgEntitiesItem` interface (or type) to include the two new fields.
5. Verify the existing fallback path (`useTenantStore.entity_roles` fallback) — if it
   returns items of the same type, add `functional_currency: ""` and `country_code: ""`
   as safe empty defaults to the fallback items.

**Note:** SP-2B and SP-2C (if already merged) will benefit from these new fields
automatically since they use `useOrgEntities()`. No changes needed in those components.

---

## Section 2 — Add `entityCurrency` to `workspaceStore`

**File:** `frontend/lib/store/workspace.ts`

1. Add `entityCurrency: string | null` to `WorkspaceState`. Default: `null`.
2. Update `switchEntity(entityId: string | null)` to also accept an optional
   `currency?: string` parameter (or resolve it from the entity list in the store):

   **Option A (simpler):** Add `entityCurrency` as an explicit second param to
   `switchEntity`:
   ```typescript
   switchEntity: (entityId: string | null, currency?: string | null) => void
   ```
   Callers that already call `switchEntity(id)` work as-is (currency defaults to undefined
   → sets `entityCurrency: null`).

   **Option B (no param change):** `switchEntity` stays single-param. `useFormattedAmount`
   resolves currency by looking up `entityId` in the `useOrgEntities` list at render time.

   **Choose Option B** if adding a param would require touching existing callers (check
   with `rg "switchEntity(" frontend/ -n`). Choose Option A only if no existing caller
   would break.

3. Include `entityCurrency` in the store's persistence/rehydration logic if
   `workspaceStore` persists to localStorage (check whether it uses `zustand/middleware`
   `persist`). If it does persist, add `entityCurrency` to the persisted keys.

4. In `switchOrg`, reset `entityCurrency` to `null` (org switch clears entity context).

---

## Section 3 — Update `useFormattedAmount` hook

**File:** `frontend/hooks/useFormattedAmount.ts`

1. Import `useWorkspaceStore` from `@/lib/store/workspace`.
2. Read `entityId` and `entityCurrency` from `workspaceStore`.
3. Derive the effective currency:
   ```typescript
   const { scale, currency: displayCurrency } = useDisplayScale()
   const { entityId, entityCurrency } = useWorkspaceStore(
     (s) => ({ entityId: s.entityId, entityCurrency: s.entityCurrency })
   )
   const effectiveCurrency = entityId && entityCurrency ? entityCurrency : displayCurrency
   ```
4. Replace `currency` with `effectiveCurrency` in the `formatAmount(...)` calls inside
   the hook.

**Verify no callers break:** The hook's public API (`fmt`, `fmtCompact`, etc.) is unchanged.
Callers do not pass currency — it is resolved internally. Run typecheck after this section.

---

## Section 4 — Spot-check call sites (no changes required)

After Sections 1–3, run this verification:

```bash
# Confirm formatAmount direct call sites are not affected
rg "formatAmount\(" frontend/ -n | grep -v "hooks/useFormattedAmount\|lib/utils\|lib/api/reconciliation" | head -10
```

For each remaining call site (if any), confirm it either:
- Uses `fmt()` from the hook (indirectly correct — no change needed)
- Is a standalone `formatAmount(amount, scale, currency)` call with an explicit currency
  arg (already correct — caller supplies currency)
- Is in `lib/api/reconciliation.ts` calling without currency (uses default `₹`) — this is
  an intentional default for a specific display context; leave it

If any call site is using `useFormattedAmount`'s `fmt()` and should now pick up entity
currency automatically, verify it will do so after this change (it will, because the hook
now uses `effectiveCurrency` internally).

**STOP checkpoint:** If more than 10 call sites require manual review, report before
proceeding.

---

## Verification

```bash
cd frontend

npm run build 2>&1 | tail -20
npx tsc --noEmit 2>&1 | tail -30
npm run lint 2>&1 | tail -20

# Confirm entityCurrency is in workspaceStore
rg "entityCurrency" frontend/lib/store/workspace.ts -n

# Confirm useFormattedAmount now reads from workspaceStore
rg "workspaceStore\|entityCurrency\|effectiveCurrency" frontend/hooks/useFormattedAmount.ts -n

# Confirm useOrgEntities now carries functional_currency
rg "functional_currency" frontend/hooks/useOrgEntities.ts -n
```

---

## Commit

```bash
git add frontend/hooks/useOrgEntities.ts \
        frontend/lib/store/workspace.ts \
        frontend/hooks/useFormattedAmount.ts

git status   # confirm only those 3 files staged

git commit -m "$(cat <<'EOF'
feat(phase2/sp-2d): currency from entity functional_currency

- useOrgEntities: extend toSwitcherItem to carry functional_currency + country_code
- workspaceStore: add entityCurrency field; reset on switchOrg; set on switchEntity
- useFormattedAmount: use entityCurrency when entityId != null, fall back to displayScale
- No call-site changes needed; hook internal resolution is transparent to callers (OQ-5)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
git log --oneline -1
git status
```

**Do NOT push. Do NOT merge.**

---

## Report back

Report to the human:

1. Commit hash and branch name
2. Which `switchEntity` option was chosen (A or B) and why
3. Whether `workspaceStore` persists to localStorage and how `entityCurrency` was handled
4. Count of `formatAmount` direct call sites reviewed in Section 4, and whether any
   required manual attention
5. Files changed with line counts
6. Any deviations from section specs and why
