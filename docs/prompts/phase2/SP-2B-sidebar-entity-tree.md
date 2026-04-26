# Claude Code Prompt — SP-2B: Sidebar Entity Card as Picker + Entity Tree + Collapsed Rail Chip

> **Purpose:** Make the sidebar entity card interactive (clickable picker), add a compact
> entity tree below it, wire the collapsed-rail entity chip, and implement the OQ-1 default
> (Org → Entity only, no module level in the tree). Also applies OQ-5: "All entities"
> pseudo-node highlighting when `entityId === null`.
>
> **Mode:** Code. Frontend-only.
>
> **Branch:** `feat/sp-2b-sidebar-entity-tree` from `main` **after SP-2A merges**
>
> **Estimated runtime:** ~2 dev-days
>
> **Push:** NO. Local commit only.
>
> **Prerequisite:** SP-2A must be merged to main before branching. The tenant store's
> `switch_mode` field (added in SP-2A) is a compile-time dependency.

---

## Background context

The Phase 2 pre-flight (`docs/platform/phase2-preflight-2026-04-26.md`) covers this
sub-prompt primarily through Decision 2.3, Decision 2.5, and OQ-1 + OQ-5 defaults.

### Decision 2.3 — Entity card shape

The sidebar entity card (`Sidebar.tsx:139–166`) is currently a **static div** — no click
handler, no dropdown. Phase 2 makes it the primary interactive entity picker:

- Add `cursor-pointer` and an `onClick` handler
- Opens a `Popover` (or `Sheet` on mobile) containing: entity search input + entity list
- Inside the picker: Org → Entity tree (OQ-1 default: no module level)
- Click on an entity row calls `workspaceStore.switchEntity(entity.entity_id)`
- TopBar `EntitySwitcher` is **untouched** — it remains the secondary flat-list picker (S-005)

### Decision 2.5 — Sidebar entity tree behavior

- Compact list/tree rendered below the entity card (not replacing it)
- Uses `GET /api/v1/org-setup/entities` (existing `listOrgEntities()` via `useOrgEntities`)
- Click on an entity row: `workspaceStore.switchEntity(entityId)`
- "← All entities" link at bottom: `workspaceStore.switchEntity(null)`
- Active entity highlighted (`bg-accent` / `text-primary`)

### OQ-1 default — Org + Entity only

Show Org → Entity tree only. No module level. The tab bar already provides module
navigation; duplicating modules in the tree adds complexity without user benefit. If a
later sub-prompt needs to add module depth, it is additive work.

### OQ-5 default — "All entities" pseudo-node

When `entityId === null` (all-entities / consolidated view), the sidebar tree highlights an
"All entities" pseudo-node at the top of the list. No EntityScopeBar is shown (that is
SP-2C's conditional). The collapsed-rail chip shows org initial + entity count when
`entityId === null`.

### Collapsed-rail chip

The current collapsed-rail chip at `Sidebar.tsx:130–133` is a static 32px "F" brand chip
(`bg-primary`, `text-primary-foreground`). Phase 2 replaces it with an entity context chip:
- When `entityId !== null`: first letter of entity name on `bg-accent`
- When `entityId === null`: org initial + entity count (e.g., "A7")
- Chip click in collapsed state: toggles sidebar open (existing collapse behavior) or opens
  a mini entity picker flyout — choose whichever is simpler given the existing toggle.

---

## Hard rules

1. **Do not touch** `frontend/components/layout/Topbar.tsx` or
   `frontend/components/layout/EntitySwitcher.tsx`. TopBar EntitySwitcher is untouched.
2. **Do not touch** SP-2A files: `OrgSwitcher.tsx`, `lib/api/orgs.ts`, `lib/store/tenant.ts`,
   `ViewingAsBanner.tsx`.
3. **OQ-1 default enforced:** no module level in the entity tree or picker.
4. Keyboard navigation on the tree (arrow keys, Enter to select) is required.
5. Build, typecheck, and lint must pass clean before committing.

---

## Pre-flight (run before writing any code)

```bash
git status        # must be clean
git log --oneline main -1  # confirm SP-2A is present in main

git checkout -b feat/sp-2b-sidebar-entity-tree
git branch --show-current

# Confirm Sidebar.tsx exists and find the static entity card location
rg "ACTIVE ENTITY|entity_name|cursor-pointer" frontend/components/layout/Sidebar.tsx -n
# Expected: static div with "ACTIVE ENTITY" label, no onClick

# Confirm collapsed-rail brand chip
rg "bg-primary.*text-primary|F.*chip|collapsed.*32px" frontend/components/layout/Sidebar.tsx -n | head -10
# Expected: static "F" or brand-initial chip around line 130-133

# Confirm useOrgEntities hook location and shape
rg "useOrgEntities\|toSwitcherItem" frontend/hooks/useOrgEntities.ts -n
# Expected: returns { entity_id, entity_name, role }
# Note: SP-2D will add functional_currency to this hook later; SP-2B does not depend on it

# Confirm workspaceStore.switchEntity signature
rg "switchEntity" frontend/lib/store/workspace.ts -n
# Expected: switchEntity: (entityId: string | null) => void

# Confirm that SP-2A's switch_mode field is present in tenant store
rg "switch_mode" frontend/lib/store/tenant.ts -n
# Expected: present (added by SP-2A). STOP if absent — SP-2A has not merged yet.

# Confirm EntityCardPicker does NOT already exist
ls frontend/components/layout/EntityCardPicker.tsx 2>/dev/null && echo "EXISTS — investigate" || echo "not found — will create"
```

**STOP and report if:**
- `switch_mode` is absent from `lib/store/tenant.ts` (SP-2A has not merged — do not proceed)
- The static entity card in `Sidebar.tsx` has already been made interactive in a prior commit

---

## Section 1 — Entity card as picker

**File:** `frontend/components/layout/Sidebar.tsx` (the static entity card block)
**New file:** `frontend/components/layout/EntityCardPicker.tsx` (or inline — see below)

**Choice:** If the picker popover logic is under ~80 lines, implement it inline in
`Sidebar.tsx`. If it is larger, create a separate `EntityCardPicker.tsx` and import it.
Document which choice was made in the commit message.

**Picker requirements:**
1. Entity card div gets `cursor-pointer` and an `onClick` that toggles a `Popover` (use
   existing `@/components/ui/Popover` or equivalent already in the codebase).
2. Inside the popover:
   - A `<input type="search">` or `Command` input for filtering
   - Entity list rendered from `useOrgEntities()` (existing hook)
   - "All entities" pseudo-item at top of list (always visible)
   - Each entity row: entity name + optional role badge
   - Click → `workspaceStore.switchEntity(entity.entity_id)` + close popover
   - "All entities" click → `workspaceStore.switchEntity(null)` + close popover
3. Active entity (matching `workspaceStore.entityId`) gets `bg-accent` highlight.
4. "All entities" pseudo-item gets `bg-accent` when `entityId === null`.
5. Keyboard: arrow-up/down navigate list, Enter confirms, Escape closes.

---

## Section 2 — Sidebar entity tree

**File:** `frontend/components/layout/Sidebar.tsx` (the nav section below the entity card)

Add a compact entity list/tree section below the entity card in the expanded sidebar state.
This is distinct from the picker popover — it is always visible in expanded mode.

Requirements:
1. Render entities from `useOrgEntities()` as a compact list (tree if ownership data available,
   flat list with indentation otherwise).
2. "← All entities" link at the top: `workspaceStore.switchEntity(null)`.
3. Active entity highlighted with `bg-accent` or `text-primary font-medium`.
4. "All entities" pseudo-node highlighted when `entityId === null`.
5. Max height with vertical scroll if entity list > 8 items (prevent sidebar overflow).
6. Each entity click: `workspaceStore.switchEntity(entity.entity_id)`.
7. Section is only rendered in expanded sidebar state (`!sidebarCollapsed`).

**STOP checkpoint:** After this section, build and typecheck before proceeding. Confirm the
sidebar renders correctly in both collapsed and expanded states.

---

## Section 3 — Collapsed-rail entity chip

**File:** `frontend/components/layout/Sidebar.tsx` (lines ~130–133, the brand chip)

Replace the static "F" brand chip with a context-aware entity chip:

```tsx
// When entityId !== null (entity scoped)
<div className="h-8 w-8 rounded-md bg-accent flex items-center justify-center text-xs font-semibold text-accent-foreground cursor-pointer"
     onClick={handleToggleCollapse}  // existing collapse toggle or mini picker flyout
     title={activeEntityName}>
  {activeEntityName?.[0]?.toUpperCase() ?? "?"}
</div>

// When entityId === null (all entities)
<div className="h-8 w-8 rounded-md bg-primary flex items-center justify-center text-xs font-semibold text-primary-foreground cursor-pointer"
     onClick={handleToggleCollapse}
     title="All entities">
  {orgInitial}{entityCount}
</div>
```

Where:
- `orgInitial` = first letter of org name from `useTenantStore` (or workspaceStore)
- `entityCount` = `entities.length` from `useOrgEntities()`
- `activeEntityName` = name of entity matching `workspaceStore.entityId`

Chip click behavior: toggle sidebar open (simplest correct implementation). Do not introduce
a mini flyout unless the existing collapse toggle is inappropriate here.

---

## Section 4 — "All entities" visual treatment (OQ-5)

Verify the following are consistent across all three surfaces added in SP-2B:
- [ ] Entity picker popover: "All entities" pseudo-item highlighted when `entityId === null`
- [ ] Sidebar entity tree: "All entities" pseudo-node highlighted when `entityId === null`
- [ ] Collapsed-rail chip: org initial + entity count shown when `entityId === null`
- [ ] All three call `workspaceStore.switchEntity(null)` for the "clear scope" action

---

## Verification

```bash
cd frontend

# Build
npm run build 2>&1 | tail -20

# Typecheck
npx tsc --noEmit 2>&1 | tail -30

# Lint
npm run lint 2>&1 | tail -20

# Run Sidebar-specific tests if they exist
npx vitest run components/layout/__tests__/Sidebar 2>/dev/null || echo "no test file or no vitest"
```

Manual smoke-check:
- Expanded sidebar: entity card is clickable, picker opens, entity selection updates `workspaceStore.entityId`
- Expanded sidebar: entity tree visible, entity selection and "← All entities" both work
- Collapsed sidebar: chip shows entity initial (or org+count), chip click toggles sidebar
- "All entities" pseudo-node highlighted when no entity is selected

---

## Commit

```bash
git add frontend/components/layout/Sidebar.tsx \
        frontend/components/layout/EntityCardPicker.tsx  # only if created as separate file

git status   # confirm only Sidebar-related files staged

git commit -m "$(cat <<'EOF'
feat(phase2/sp-2b): sidebar entity card picker + entity tree + collapsed chip

- Entity card (Sidebar.tsx ~139-166) becomes clickable; opens entity picker popover
- Picker: search input + entity list + "All entities" pseudo-node (OQ-1: no module level)
- Compact entity tree below card in expanded mode; "← All entities" link
- Collapsed-rail chip: entity initial when scoped, org-initial+count when all-entities (OQ-5)
- Active entity highlighted bg-accent throughout; keyboard nav on picker list

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
2. Whether `EntityCardPicker.tsx` was created as a separate file or implemented inline
3. Whether the ownership-tree API (`GET /api/v1/org-setup/ownership-tree`) was used for
   tree depth, or whether a flat indented list was used instead — and why
4. Files changed with line counts
5. Any deviations from section specs and why
6. Whether any existing Sidebar tests broke and how they were resolved
