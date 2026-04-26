# Claude Code Prompt — SP-2F: FU-018 Invite Modal Entity-Fetch Warning

> **Purpose:** Add a visible in-modal warning + retry button when the entity fetch fails
> inside the invite modal in `UsersPanel.tsx`. Upgrades the silent `.catch(() => [])` to a
> user-visible soft warning without changing the happy path or the submit fallback.
>
> **Mode:** Code. Frontend-only, single file.
>
> **Branch:** `feat/sp-2f-fu018-invite-modal` from `main`
>
> **Estimated runtime:** ~30 minutes
>
> **Push:** NO. Local commit only.
>
> **Can run in parallel with:** Any SP (fully disjoint file set).
>
> **Source:** FU-018 — `docs/follow-ups/FU-018-invite-modal-entity-fetch-warning.md`

---

## Background context

During FU-016 implementation of the Users tab on `/settings/team`, the invite modal
includes an optional entity assignment field. Entities are fetched via `listOrgEntities()`
in a `useEffect` at `UsersPanel.tsx:118`:

```typescript
listOrgEntities()
  .then(setEntities)
  .catch(() => setEntities([]))   // ← silent failure
```

If the fetch fails, `setEntities([])` silently hides the entity selector section. The user
can still submit the invite; the backend defaults `entity_ids` to `[]`. Functionally safe,
but the inviter doesn't know entity assignment was unavailable.

FU-018 upgrades this to a **visible warning** without changing functional behavior.

---

## Hard rules

1. Single file change: `frontend/app/(dashboard)/settings/team/_components/UsersPanel.tsx`.
2. Happy path (fetch succeeds) must be completely unchanged.
3. Submit button stays enabled even when entity fetch has failed.
4. The existing fallback (`entity_ids: []` on submit) is preserved.
5. Use a persistent in-modal indicator — not a Sonner toast (too transient).
6. Build, typecheck, and lint must pass clean.

---

## Pre-flight (run before writing any code)

```bash
git status
git log --oneline main -1

git checkout -b feat/sp-2f-fu018-invite-modal
git branch --show-current

# Confirm the target file and the silent-catch line
rg "listOrgEntities\|setEntities\|catch" frontend/app/\(dashboard\)/settings/team/_components/UsersPanel.tsx -n
# Expected: listOrgEntities().then(setEntities).catch(() => setEntities([])) around line 118

# Find the entity selector section in the modal JSX to understand what to replace
rg "entity\|entities\|entityIds\|EntitySelector" frontend/app/\(dashboard\)/settings/team/_components/UsersPanel.tsx -n | head -20

# Check for an existing inline-warning or alert pattern in the file or nearby components
rg "Alert\|alert\|warning\|inline.*error" frontend/app/\(dashboard\)/settings/team/ -n | head -10
# Note what pattern is already in use to match it
```

---

## Section 1 — Add entity fetch error state and retry

**File:** `frontend/app/(dashboard)/settings/team/_components/UsersPanel.tsx`

### 1a — Add state

Add an `entityFetchError` boolean state near the existing `entities` state:

```typescript
const [entityFetchError, setEntityFetchError] = useState(false)
```

### 1b — Update the fetch effect

Replace the silent-catch with error-tracking:

```typescript
listOrgEntities()
  .then((data) => {
    setEntities(data)
    setEntityFetchError(false)
  })
  .catch(() => {
    setEntities([])
    setEntityFetchError(true)
  })
```

Add a `fetchEntities` callback (or inline retry function) so the retry button can call it:

```typescript
const fetchEntities = useCallback(() => {
  setEntityFetchError(false)
  listOrgEntities()
    .then((data) => {
      setEntities(data)
      setEntityFetchError(false)
    })
    .catch(() => {
      setEntities([])
      setEntityFetchError(true)
    })
}, [])
```

Call `fetchEntities()` in the `useEffect` that was previously calling `listOrgEntities()`
directly.

### 1c — Update the invite modal JSX

In the invite modal's entity selector section, render the warning when `entityFetchError` is
true, instead of (or instead of silently hiding) the entity selector:

```tsx
{entityFetchError ? (
  <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
    <p>Couldn&apos;t load entities. The user will be created without entity scope. You can
    assign entities later.</p>
    <button
      type="button"
      onClick={fetchEntities}
      className="mt-1 text-xs underline hover:no-underline"
    >
      Retry
    </button>
  </div>
) : (
  /* existing entity selector JSX — unchanged */
)}
```

Match the color/border pattern to whatever inline warning pattern already exists in
`UsersPanel.tsx` or its sibling components (check in pre-flight). If the codebase has a
shared `<InlineAlert>` or `<Alert>` component, use that instead of raw divs.

### 1d — Verify happy path is unchanged

Confirm:
- When `entityFetchError === false` (fetch succeeded or not yet attempted), the entity
  selector renders exactly as before
- The submit handler still sends `entity_ids: inviteForm.entity_ids` (the empty array when
  no entity is selected is still the correct fallback)
- The `inviteOpen` dialog can still be submitted even when the warning is shown

---

## Verification

```bash
cd frontend

npm run build 2>&1 | tail -20
npx tsc --noEmit 2>&1 | tail -30
npm run lint 2>&1 | tail -20

# Confirm the silent catch is gone
rg "catch.*setEntities\(\[\]\)" frontend/app/\(dashboard\)/settings/team/_components/UsersPanel.tsx -n
# Expected: zero results (replaced by error-tracking catch)

# Confirm entityFetchError state is present
rg "entityFetchError" frontend/app/\(dashboard\)/settings/team/_components/UsersPanel.tsx -n
# Expected: state declaration + catch setter + JSX conditional
```

---

## Commit

```bash
git add frontend/app/\(dashboard\)/settings/team/_components/UsersPanel.tsx

git status   # confirm only UsersPanel.tsx staged

git commit -m "$(cat <<'EOF'
fix(fu-018): show visible warning + retry when entity fetch fails in invite modal

When listOrgEntities() fails in UsersPanel's invite modal, previously the entity
selector was silently hidden. Now shows an amber in-modal warning with retry button.
Happy path and submit fallback (entity_ids: []) unchanged.

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
2. Whether a shared `Alert`/`InlineAlert` component was used or raw divs
3. File changed: `UsersPanel.tsx` — lines added/removed
4. Confirmation that `rg "catch.*setEntities\(\[\]\)"` returns zero results after the change
5. Any deviations from the spec and why
