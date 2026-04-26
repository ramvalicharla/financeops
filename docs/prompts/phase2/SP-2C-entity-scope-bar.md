# Claude Code Prompt — SP-2C: EntityScopeBar (Replaces ContextBar)

> **Purpose:** Create the new `EntityScopeBar` component (first-pass fields per OQ-3
> default: entity name, country, functional currency + "Clear scope ✕" action), mount it
> at `app/(dashboard)/layout.tsx:85` replacing `<ContextBar>`, and remove `ContextBar` if
> it has no unique logic worth preserving.
>
> **Mode:** Code. Frontend-only.
>
> **Branch:** `feat/sp-2c-entity-scope-bar` from `main`
>
> **Estimated runtime:** ~1 dev-day
>
> **Push:** NO. Local commit only.
>
> **Can run in parallel with:** SP-2A, SP-2D (disjoint file sets).

---

## Background context

The Phase 2 pre-flight (`docs/platform/phase2-preflight-2026-04-26.md`) covers this
sub-prompt through Decision 2.4, Surprise S-006, and OQ-3 + OQ-5 defaults.

### Decision 2.4 — Mount point and visibility

- **Mount point:** Replace `<ContextBar>` at `app/(dashboard)/layout.tsx:85`. The
  `ContextBar` already occupies this exact slot between `<ModuleTabs />` and `<main>`.
- **Visibility:** Visible when `workspaceStore.entityId !== null`. Hidden (renders nothing)
  when `entityId === null` (all-entities / consolidated view).
- **Recommendation:** Full replacement — `ContextBar` serves a different design pattern
  (always-on strip) while `EntityScopeBar` is conditional. Do not keep both.

### Surprise S-006 — ContextBar already at layout slot

`frontend/components/layout/ContextBar.tsx` exists and is mounted at `layout.tsx:85`.
SP-2C must **read `ContextBar.tsx` in full** (Section 0 gate) before deciding whether to
delete it or migrate any logic. If `ContextBar` has no unique logic beyond what
`EntityScopeBar` covers, delete it cleanly.

### OQ-3 default — First-pass fields only

Ship `EntityScopeBar` with these fields only:
- Entity name
- Country (from entity's `country_code`)
- Functional currency (from entity's `functional_currency`)
- "Clear scope ✕" action → `workspaceStore.switchEntity(null)` + `queryClient.invalidateQueries(['workspace'])`

Fields mentioned in the locked design (GAAP, consolidation-eliminated status) are
**second-pass** — data sources unconfirmed. Do not block on them; they are additive.

### OQ-5 default — Hidden in all-entities view

When `entityId === null`, `EntityScopeBar` renders nothing (`return null`). There is no
placeholder or "all entities" strip at this slot — the slot is empty.

### Design spec (locked design §3.3, Deliverable 4)

- Full-width strip with `bg-[#E6F1FB]` background
- Shows: entity name, currency, "Clear scope ✕" button
- "Clear scope ✕" is the interactive element

---

## Hard rules

1. Do not touch `ModuleTabs.tsx`, `Topbar.tsx`, `OrgSwitcher.tsx`, `Sidebar.tsx`, or any
   SP-2A / SP-2D files.
2. `EntityScopeBar` must be a new component, not an inline fragment in `layout.tsx`.
3. The "Clear scope ✕" must call `workspaceStore.switchEntity(null)` (not a navigation).
4. First-pass only: entity name, country, functional currency. No GAAP field.
5. Build, typecheck, and lint must pass clean before committing.

---

## Pre-flight (run before writing any code)

```bash
git status         # must be clean
git log --oneline main -1

git checkout -b feat/sp-2c-entity-scope-bar
git branch --show-current

# Confirm ContextBar exists and read mount location
rg "ContextBar" frontend/app/\(dashboard\)/layout.tsx -n
# Expected: <ContextBar tenantSlug={tenantSlug} /> around line 85

# Confirm EntityScopeBar does NOT yet exist
ls frontend/components/layout/EntityScopeBar.tsx 2>/dev/null && echo "EXISTS — investigate" || echo "not found — will create"

# Confirm workspaceStore.switchEntity signature
rg "switchEntity" frontend/lib/store/workspace.ts -n

# Confirm entity type has country_code and functional_currency
rg "country_code\|functional_currency" frontend/lib/api/orgSetup.ts -n | head -8
```

**STOP if** `EntityScopeBar.tsx` already exists or if `ContextBar` is not at `layout.tsx:85`.

---

## Section 0 — Investigation gate: read ContextBar.tsx

**Required before any changes.**

```bash
cat frontend/components/layout/ContextBar.tsx
```

Assess:
1. Does `ContextBar` display any data that `EntityScopeBar` will NOT display (first-pass)?
2. Are there any consumers of `ContextBar` other than `layout.tsx`?
   ```bash
   rg -l "ContextBar" frontend/ | grep -v layout.tsx | grep -v __tests__
   ```
3. Does `ContextBar` have unique business logic (not just read from `workspaceStore`/context)?

**If `ContextBar` has unique logic:** Migrate it into `EntityScopeBar` or a separate hook.
**If `ContextBar` is a thin wrapper:** Delete it entirely in Section 3.

**STOP checkpoint:** Report your assessment of ContextBar before proceeding to Section 1.

---

## Section 1 — Component scaffold

**File to create:** `frontend/components/layout/EntityScopeBar.tsx`

Requirements:
1. Reads `entityId` from `workspaceStore`. Returns `null` if `entityId === null` (OQ-5).
2. Fetches entity data to resolve name, country, functional currency. Two options:
   - **Option A (preferred):** Read from `useOrgEntities()` hook — find the entity in the
     list by `entity_id`. No new API call. Note that SP-2D will later extend `useOrgEntities`
     to carry `functional_currency`; for now, verify whether it already carries it. If not,
     call `listOrgEntities()` directly via a separate `useQuery` in this component.
   - **Option B (fallback):** Call `GET /api/v1/org-setup/entities/{entityId}` if a
     single-entity endpoint exists. Check first: `rg "entities/{id}" frontend/lib/api/orgSetup.ts`
3. Renders:
   ```tsx
   <div className="w-full bg-[#E6F1FB] px-4 py-2 flex items-center gap-3 text-sm">
     <span className="font-medium">{entityName}</span>
     <span className="text-muted-foreground">{countryCode}</span>
     <span className="text-muted-foreground">{functionalCurrency}</span>
     <button
       onClick={handleClearScope}
       className="ml-auto text-xs text-muted-foreground hover:text-foreground"
     >
       Clear scope ✕
     </button>
   </div>
   ```
4. `handleClearScope` calls `workspaceStore.switchEntity(null)` then
   `queryClient.invalidateQueries({ queryKey: ['workspace'] })`.
5. Loading state: show a skeleton or nothing (not an error spinner) while entity data loads.

---

## Section 2 — Mount point

**File:** `frontend/app/(dashboard)/layout.tsx`

1. Import `EntityScopeBar` from `@/components/layout/EntityScopeBar`
2. Replace `<ContextBar tenantSlug={tenantSlug} />` with `<EntityScopeBar />`
3. Remove the `ContextBar` import

Verify the layout renders correctly:
```
<ModuleTabs />
<EntityScopeBar />          ← new (renders nothing when entityId === null)
<main>
  <DataActivationReminder />
  <Breadcrumb />
  {children}
</main>
```

**STOP checkpoint:** Build and typecheck after this section. Confirm `EntityScopeBar`
renders the strip when `entityId` is set and renders nothing when it is null.

---

## Section 3 — Remove ContextBar

**Based on Section 0 findings:**

If `ContextBar` has no unique logic beyond what `EntityScopeBar` covers:
```bash
# Remove ContextBar component file
rm frontend/components/layout/ContextBar.tsx

# Verify no remaining imports
rg "ContextBar" frontend/ -n
# Expected: zero results
```

If `ContextBar` has logic worth preserving, migrate it first, then remove. Document what
was migrated in the commit message.

Verify:
```bash
rg "ContextBarBase" frontend/components/shell/primitives/ -n
# If ContextBarBase exists and ContextBar imports it, check if ContextBarBase is used elsewhere
rg -l "ContextBarBase" frontend/ | grep -v ContextBar
# If ContextBarBase is only used by ContextBar (now deleted), remove it too
```

---

## Verification

```bash
cd frontend

npm run build 2>&1 | tail -20
npx tsc --noEmit 2>&1 | tail -30
npm run lint 2>&1 | tail -20

# Confirm no orphaned ContextBar imports
rg "ContextBar" frontend/ -n 2>/dev/null | grep -v "EntityScopeBar"
# Expected: zero results
```

---

## Commit

```bash
git add frontend/components/layout/EntityScopeBar.tsx \
        frontend/app/\(dashboard\)/layout.tsx \
        frontend/components/layout/ContextBar.tsx  # deletion

# If ContextBarBase was also removed:
# git add frontend/components/shell/primitives/ContextBarBase.tsx

git status   # confirm only EntityScopeBar-related files staged

git commit -m "$(cat <<'EOF'
feat(phase2/sp-2c): EntityScopeBar replaces ContextBar

- New EntityScopeBar: full-width bg-[#E6F1FB] strip below ModuleTabs
- Visible when entityId != null, hidden (null) when entityId === null (OQ-5)
- First-pass fields: entity name, country_code, functional_currency (OQ-3 default)
- "Clear scope ✕" → workspaceStore.switchEntity(null) + queryClient.invalidateQueries
- Remove ContextBar (replaced entirely; no unique logic migrated / <logic description>)
- Mount: layout.tsx:85

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
2. `ContextBar` disposition: deleted cleanly OR logic migrated (describe what)
3. Whether `ContextBarBase` (`components/shell/primitives/ContextBarBase.tsx`) was also
   removed, and why
4. Entity data source used (Option A via `useOrgEntities`, Option B via single-entity
   endpoint, or other)
5. Files changed with line counts
6. Any deviations from section specs and why
