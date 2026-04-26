# Claude Code Prompt — Phase 2 Step 3: Draft Sub-Prompts SP-2A through SP-2F

> **Purpose:** Produce 5 executable sub-prompt files (SP-2A, SP-2B, SP-2C, SP-2D, SP-2F) plus a placeholder for SP-2E (deferred via TD-016). Each sub-prompt is a complete Claude Code prompt that another session will execute later.
>
> **Mode:** Doc-only. The only writes are 6 markdown files under `docs/prompts/phase2/`. No source code changes.
>
> **Branch:** `docs/phase2-sub-prompts` from `main` at `c3ee9a3`.
>
> **Expected runtime:** 1.5–2.5 hours of agent work. Most of that is reading the pre-flight doc thoroughly and re-verifying file-touch lists.
>
> **Push:** NO. Local commit only. The merge prompt is a separate downstream step.

---

## Background context

Phase 2 pre-flight is complete. Main is at `c3ee9a3`. The pre-flight document at `docs/platform/phase2-preflight-2026-04-26.md` contains:

- 6 of 8 decisions resolved (D2.6 and D2.7 deferred to TD-016)
- 4 defaults adopted on open questions (OQ-1, OQ-3, OQ-4, OQ-5)
- Surprises S-001 and S-003 with fix locations
- A sub-prompt dependency map in Section 4

This drafting prompt produces the 5 executable sub-prompts based on that pre-flight content.

**Sub-prompt mapping to Phase 2 deliverables:**

| Sub-prompt | Covers | Deferred? |
|---|---|---|
| SP-2A | OrgSwitcher repurpose + S-001 fix + S-003 `switch_mode` discriminator + post-switch flow | No |
| SP-2B | Sidebar entity card + tree + collapsed-rail entity chip | No (but waits for SP-2A merge) |
| SP-2C | EntityScopeBar (replaces ContextBar). First-pass fields per OQ-3 default. | No |
| SP-2D | Currency from entity functional currency | No |
| SP-2E | Consolidation tab disable + Tax/GST jurisdictional relabel | YES — deferred to TD-016 |
| SP-2F | FU-018 invite modal entity-fetch warning (30 min standalone) | No |

---

## Hard rules

1. **READ-ONLY on source code.** No edits to `.ts`, `.tsx`, `.py`, etc. The only writes are 6 markdown files under `docs/prompts/phase2/`.
2. **STOP and report at >10% scope deviation** from this prompt.
3. **No push, no merge.** Commit to `docs/phase2-sub-prompts` locally.
4. **Verbatim outputs for every claim.** Each sub-prompt's "Touched files" list must be backed by `rg`/`grep` outputs gathered during this drafting session. No speculative file lists.
5. **Trust-but-verify the pre-flight's Section 4.** If Section 4 of the pre-flight specifies file-touch lists, **re-verify them with grep before transcribing into each sub-prompt.** If Section 4 does not specify file-touch lists, **identify them as part of drafting each sub-prompt.** Either way, the file-touch list in each sub-prompt must come from a verified `rg`/`grep` output, not from memory or inference.
6. **No drafting of SP-2E logic.** SP-2E is a placeholder file documenting the deferral and pointing at TD-016. Do not include implementation steps for it.

---

## Pre-flight (do this first, report before proceeding)

```bash
git status                                              # expect clean
git fetch
git log --oneline main -1                               # expect c3ee9a3 (or newer doc-only)
git log --oneline origin/main -1                        # confirm origin/main vs main
git checkout -b docs/phase2-sub-prompts
git branch --show-current                               # confirm

# Confirm the pre-flight doc and TD-016 are on main
ls docs/platform/phase2-preflight-2026-04-26.md
ls docs/tech-debt/TD-016-phase2-consolidation-tax-tabs.md
ls docs/platform/TODO.md

# Confirm or create the prompts directory
ls docs/prompts/phase2/ 2>/dev/null || echo "directory does not exist yet — will create"
```

If any pre-flight check fails, STOP and report. Do not proceed.

---

## Section 1 — Read the pre-flight document end to end

Read `docs/platform/phase2-preflight-2026-04-26.md` in full. Extract these specific items into a working notes file at `/tmp/phase2-drafting-notes.md` (this file is for your own use during drafting; it does not get committed):

1. **Decision 2.1** — exact recommendation on OrgSwitcher repurpose vs fork. The chosen option determines SP-2A's primary action.
2. **Decision 2.2** — the numbered post-switch flow sequence. This becomes SP-2A's onSelect handler spec.
3. **Decision 2.3** — entity card/tree picker shape. This becomes SP-2B's component-shape spec.
4. **Decision 2.4** — EntityScopeBar mount point and visibility rules. This becomes SP-2C's scope.
5. **Decision 2.5** — sidebar entity tree behavior. This is part of SP-2B's scope.
6. **Decision 2.8** — currency-from-entity strategy. This becomes SP-2D's spec.
7. **Surprise S-001** — switch endpoint response shape divergence. The exact fix lives in SP-2A; the response shape adapter is the 15-minute fix.
8. **Surprise S-003** — `switch_mode` discriminator + ViewingAsBanner gate. Lives in SP-2A.
9. **Section 4** — sub-prompt dependency map. Note whether it includes file-touch lists.
10. **Update section** — defaults adopted on OQ-1, OQ-3, OQ-4, OQ-5. These are the operational defaults the sub-prompts implement.
11. **TD-016 reference** — for the SP-2E placeholder.

Also read:
- `docs/follow-ups/FU-018-*.md` (invite modal warning) — full content for SP-2F
- `docs/tech-debt/TD-016-phase2-consolidation-tax-tabs.md` — for SP-2E placeholder cross-references

If the pre-flight doc's Section 4 does NOT include file-touch lists, note that explicitly and proceed to Section 2 with the understanding that Section 2 will identify them.

---

## Section 2 — Verify file-touch lists for each sub-prompt

For each sub-prompt (SP-2A, SP-2B, SP-2C, SP-2D, SP-2F), produce a file-touch list backed by grep/rg outputs. Either re-verify what's in Section 4 of the pre-flight or identify from scratch.

Save the verification outputs to `/tmp/phase2-file-touch-verification.md` for use during drafting.

### SP-2A — OrgSwitcher repurpose + switch infrastructure

Run these greps and capture verbatim output:

```bash
# OrgSwitcher and call sites
rg -l "OrgSwitcher" frontend/

# is_switched flag — every read and write
rg "is_switched" frontend/ -n

# Switch token rotation in Axios interceptor
rg "switch.*token|rotateToken|interceptors" frontend/lib/api/ -n

# ViewingAsBanner component (S-003)
rg -l "ViewingAsBanner|Read-only.*15" frontend/

# tenant store — for switch_mode addition
rg -l "tenantStore|useTenantStore" frontend/

# The actual switch endpoint call site
rg "users/me/orgs.*switch|/switch" frontend/ -n

# workspaceStore reads — relevant for post-switch invalidation
rg "workspaceStore" frontend/lib/store/ -n
```

Compile the SP-2A file-touch list from the union of files surfaced above. Mark each as **EDIT** (modify existing) or **NEW** (create) or **READ-ONLY** (the sub-prompt reads but doesn't change).

### SP-2B — Sidebar entity card + tree + collapsed-rail chip

```bash
# Sidebar component(s)
rg -l "Sidebar" frontend/components/

# Workspace nav group with entity placeholders
rg "ACTIVE ENTITY|entity.*placeholder|Workspace" frontend/components/ -n

# Collapsed rail (52px)
rg "52px|collapsed.*rail|sidebarCollapsed" frontend/ -n

# EntitySwitcher (Phase 0 wired) — to verify whether SP-2B reuses or replaces
rg -l "EntitySwitcher" frontend/

# TopBar entity card current location (relevant for the picker shape decision)
rg "TopBar|topbar" frontend/components/layout/ -l
```

Compile the SP-2B file-touch list. **Verify disjointness with SP-2A's list.** Any file that appears in both should be flagged as a serialization point (SP-2B must wait for SP-2A merge — already established in the dependency map, but file-level evidence confirms why).

### SP-2C — EntityScopeBar (replaces ContextBar)

```bash
# Existing ContextBar (if any)
rg -l "ContextBar" frontend/

# Module tab bar (where EntityScopeBar mounts below)
rg -l "ModuleTabBar|module.*tab.*bar|TabBar" frontend/components/

# Entity model fields for first-pass (per OQ-3 default: name, country, functional currency)
rg "functional_currency|country|entity_name" frontend/lib/types/ frontend/types/ -n

# Layout slot where EntityScopeBar would mount
rg -l "DashboardLayout|layout.tsx" frontend/app/
```

Compile the SP-2C file-touch list. **Verify disjointness with SP-2A and SP-2B.**

### SP-2D — Currency from entity functional currency

```bash
# formatAmount util
rg -l "formatAmount" frontend/lib/

# Sample call sites — limit to 10 representative ones
rg "formatAmount\(" frontend/ -n | head -20

# Entity functional currency wiring
rg "functional_currency" frontend/ -n

# workspaceStore.entityId reads (currency hook will use this)
rg "workspaceStore.*entityId|entityId.*workspaceStore" frontend/ -n
```

Compile the SP-2D file-touch list. **Verify disjointness with SP-2A, SP-2B, SP-2C.** Note: SP-2D may touch the same `formatAmount` util that some other components import; that's fine as long as SP-2D *modifies* the util and others only *read* from it. The disjointness rule is about *editing* the same file.

### SP-2F — FU-018 invite modal entity-fetch warning

```bash
# Invite modal component
rg -l "InviteModal|invite.*modal" frontend/

# Entity fetch on invite path
rg "entit.*fetch|useEntit" frontend/components/ -n | rg -i "invite"

# Any related warning/error display patterns already in use
rg "warning|console.warn" frontend/components/ -n | rg -i "invite"
```

Compile the SP-2F file-touch list. Should be the smallest set (1–3 files). **Verify disjointness with SP-2A, SP-2B, SP-2C, SP-2D.**

### Disjointness summary

After all 5 verifications, produce a matrix in `/tmp/phase2-file-touch-verification.md`:

| | SP-2A | SP-2B | SP-2C | SP-2D | SP-2F |
|---|---|---|---|---|---|
| SP-2A | — | overlap? | overlap? | overlap? | overlap? |
| SP-2B | | — | overlap? | overlap? | overlap? |
| ... | | | | | |

For each cell, mark "DISJOINT" or list the overlapping files. If any unexpected overlap is found, flag it explicitly so the parallel-launch plan can be adjusted.

**Expected from the pre-flight's dependency map:** SP-2A blocks SP-2B (overlap on workspaceStore, tenantStore, OrgSwitcher → EntitySwitcher integration). All others should be disjoint. If verification confirms this, the Day 1 plan stands. If it doesn't, STOP and report the unexpected overlap before drafting.

---

## Section 3 — Draft each sub-prompt

Each sub-prompt is its own complete Claude Code prompt. Use the same shape as previous sub-prompts in this project (BE-001 Checkpoint prompts, FU-016 prompt, etc.). The shape:

```
# Claude Code Prompt — <SP-ID>: <Title>

> Purpose, Mode, Branch, Runtime, Push policy

## Background context

## Hard rules

## Pre-flight (with grep/ls verifications)

## Section 0 — Investigation gate (if needed for this sub-prompt)

## Section 1...N — Implementation steps with internal STOP-and-report checkpoints

## Verification (build/lint/tests)

## Commit

## Report back
```

### Sub-prompt SP-2A — OrgSwitcher repurpose + switch infrastructure

**File:** `docs/prompts/phase2/SP-2A-orgswitcher-repurpose.md`

Required content:

- **Branch:** `feat/sp-2a-orgswitcher-repurpose` from main
- **Background:** D2.1 chosen direction (repurpose-in-place vs fork — transcribe whichever the pre-flight recommended), D2.2 post-switch flow sequence, S-001 endpoint shape divergence, S-003 switch_mode collision
- **Section 0 — Investigation gate (thin):** Verify the actual `POST /users/me/switch` response shape on main matches what S-001 documented. Verify ViewingAsBanner copy is exactly what S-003 quoted. STOP if either has changed.
- **Section 1 — `switch_mode` discriminator:** Add `switch_mode: "admin" | "user"` to the tenant store. Default to `"admin"` for the existing impersonation flow (preserves current behavior). Set to `"user"` only when the new user-org switch path runs.
- **Section 2 — S-001 response shape adapter:** Update OrgSwitcher's `handleSelect` to read `result.target_org.id` etc. from the actual nested response. The 15-minute fix.
- **Section 3 — Repurpose OrgSwitcher (per D2.1):** Implement whichever direction the pre-flight chose. If repurpose-in-place: switch the data source from platform admin endpoint to `GET /users/me/orgs`, gate the role guard appropriately. If fork: create a new component for user-mode and keep `OrgSwitcher` as platform-admin-only.
- **Section 4 — Post-switch flow (per D2.2):** Implement the numbered sequence from D2.2. Specifically: POST /switch → receive new token → rotate via interceptor → invalidate the cache keys D2.2 specified → update `workspaceStore`.
- **Section 5 — ViewingAsBanner gate (S-003 fix):** Update the banner's render condition to only show "Read-only · 15 min token" when `switch_mode === "admin"`. Per OQ-4 default, no banner is shown for `switch_mode === "user"`.
- **Verification:** Build clean, typecheck clean, lint clean. The unit tests for OrgSwitcher (whatever exists today) should still pass; new tests for the user-mode path are not in scope for SP-2A — they go into a separate testing follow-up.
- **Internal STOP checkpoints:** After Section 0 (gate), after Section 1 (switch_mode landed), after Section 4 (post-switch flow). Report and pause for human confirmation between each major section.
- **Estimate:** ~2 dev-days

### Sub-prompt SP-2B — Sidebar entity card + tree + collapsed-rail chip

**File:** `docs/prompts/phase2/SP-2B-sidebar-entity-tree.md`

Required content:

- **Branch:** `feat/sp-2b-sidebar-entity-tree` from main **after SP-2A merges**
- **Background:** D2.3 entity card/tree picker shape, D2.5 sidebar entity tree behavior, OQ-1 default (Org + Entity, no modules)
- **Pre-flight requires:** SP-2A merge present on main. Verify before starting.
- **Section 1 — Entity card as picker:** Implement the picker shape per D2.3. Per OQ-1 default, the tree is Org → Entity only (no module level).
- **Section 2 — Sidebar entity tree wiring:** Replace the Workspace nav group's entity placeholders with the live entity tree per D2.5. Click sets `entityId` in workspaceStore.
- **Section 3 — Collapsed-rail entity chip:** 52px rail shows active-entity chip when sidebar is collapsed. Click behavior per D2.5.
- **Section 4 — All-entities visual treatment (OQ-5 default):** Tree highlights "All entities" pseudo-node when `entityId === null`.
- **Verification:** Build, typecheck, lint, accessibility (keyboard nav on tree).
- **Internal STOP checkpoints:** After Section 1 (picker), after Section 2 (sidebar tree). Report and pause between.
- **Estimate:** ~2 dev-days

### Sub-prompt SP-2C — EntityScopeBar (replaces ContextBar)

**File:** `docs/prompts/phase2/SP-2C-entity-scope-bar.md`

Required content:

- **Branch:** `feat/sp-2c-entity-scope-bar` from main
- **Background:** D2.4 mount point and visibility rules, OQ-3 default (first-pass fields: name, country, functional currency), OQ-5 default (hidden in all-entities view)
- **Section 1 — Component scaffold:** New `EntityScopeBar` component. First-pass fields only per OQ-3.
- **Section 2 — Mount point per D2.4:** Mount below module tab bar at the location D2.4 specifies.
- **Section 3 — Visibility rules:** Visible when `entityId !== null`. Hidden when `entityId === null` (all-entities view, per OQ-5).
- **Section 4 — Replace ContextBar (if present):** If a `ContextBar` exists, EntityScopeBar replaces it. Verify call sites and update.
- **Verification:** Build, typecheck, lint, visible behavior on multi-entity test data.
- **Internal STOP checkpoints:** After Section 2 (mount point landed). Report and pause.
- **Estimate:** ~1 dev-day

### Sub-prompt SP-2D — Currency from entity functional currency

**File:** `docs/prompts/phase2/SP-2D-currency-from-entity.md`

Required content:

- **Branch:** `feat/sp-2d-currency-from-entity` from main
- **Background:** D2.8 strategy (transcribe what the pre-flight recommended — util-resolves vs call-site-passes), OQ-5 default (all-entities → org default currency)
- **Section 1 — Update `formatAmount` per D2.8:** Implement the chosen strategy.
- **Section 2 — Update or audit call sites:** If D2.8 chose util-resolves, no call-site changes required. If D2.8 chose call-site-passes-currency-via-hook, update representative call sites and document the new pattern.
- **Section 3 — All-entities fallback (OQ-5):** When `entityId === null`, fall back to org default currency.
- **Verification:** Build, typecheck, lint. Spot-check 5 representative call sites render correct currency for an entity with a non-default functional currency.
- **Internal STOP checkpoints:** After Section 1. Report and pause if call-site changes are larger than expected (>10 sites).
- **Estimate:** ~1 dev-day

### Sub-prompt SP-2E — DEFERRED placeholder

**File:** `docs/prompts/phase2/SP-2E-DEFERRED-consolidation-tax.md`

This file is a placeholder, not an executable prompt. Content:

```markdown
# SP-2E — DEFERRED

**Status:** Not authorized. Deferred via TD-016.

**Originally covered:** Phase 2 deliverables 5 (consolidation-aware tab disable)
and 6 (Tax/GST jurisdictional relabel).

**Why deferred:** Pre-flight surprise S-002 surfaced that the backend has no
standalone `consolidation` or `tax` workspace tabs — both live as `module_code`
values inside `close` and `accounting` respectively. Implementing tab-level
behavior against a UI surface that doesn't exist would require either a backend
ticket (BE-002) to promote them to top-level tabs, or a redesign to gate at the
module-code level.

**Resolution path:** TD-016 documents the three options (promote tabs / keep
nested / defer indefinitely). Resolution is a product/architecture decision,
not engineering.

**Cross-references:**
- TD-016: docs/tech-debt/TD-016-phase2-consolidation-tax-tabs.md
- Pre-flight: docs/platform/phase2-preflight-2026-04-26.md (S-002, OQ-2, D2.6, D2.7)
- Locked design: docs/audits/finqor-shell-audit-2026-04-24.md (Deliverables 5 and 6)

**Do not draft an executable prompt for SP-2E** until TD-016 is resolved with a
chosen direction.
```

### Sub-prompt SP-2F — FU-018 invite modal entity-fetch warning

**File:** `docs/prompts/phase2/SP-2F-fu018-invite-modal-warning.md`

Required content:

- **Branch:** `feat/sp-2f-fu018-invite-modal` from main
- **Background:** FU-018 entry from `docs/follow-ups/INDEX.md` and the individual FU file. Standalone, ~30 min.
- **Section 1 — Fix the warning:** Whatever FU-018 specifies. Likely a guard around the entity-fetch call when the modal opens without an entity context.
- **Verification:** Build, typecheck, lint. Modal opens cleanly without the warning.
- **Internal STOP checkpoints:** None — it's small enough to run end-to-end.
- **Estimate:** ~30 minutes

---

## Section 4 — Verification before commit

```bash
ls docs/prompts/phase2/
# Expected: 6 files
#   SP-2A-orgswitcher-repurpose.md
#   SP-2B-sidebar-entity-tree.md
#   SP-2C-entity-scope-bar.md
#   SP-2D-currency-from-entity.md
#   SP-2E-DEFERRED-consolidation-tax.md
#   SP-2F-fu018-invite-modal-warning.md

# Spot-check each file has the required structure
for f in docs/prompts/phase2/SP-2*.md; do
  echo "=== $f ==="
  rg "^## " "$f" | head -10
  echo
done

# SP-2E should be the placeholder shape
rg "DEFERRED" docs/prompts/phase2/SP-2E*.md

# Each non-deferred prompt should have a Pre-flight section, Hard rules, and Report back
for f in docs/prompts/phase2/SP-2{A,B,C,D,F}-*.md; do
  echo "=== $f ==="
  rg "^## (Hard rules|Pre-flight|Report back)" "$f" | sort -u
done
```

If any file is missing or any non-deferred prompt is missing the required section structure, fix and re-verify.

---

## Section 5 — Commit

```bash
git add docs/prompts/phase2/
git status                                              # confirm only the 6 prompt files staged
git diff --cached --stat                                # quick visual check

git commit -m "docs(phase2): draft sub-prompts SP-2A through SP-2F

5 executable sub-prompts + 1 deferred placeholder (SP-2E):
- SP-2A: OrgSwitcher repurpose + S-001/S-003 fixes + post-switch flow
- SP-2B: Sidebar entity card + tree + collapsed-rail chip (waits for SP-2A merge)
- SP-2C: EntityScopeBar (replaces ContextBar)
- SP-2D: Currency from entity functional currency
- SP-2E: DEFERRED via TD-016 — not authorized
- SP-2F: FU-018 invite modal entity-fetch warning

Each sub-prompt encodes the relevant pre-flight decision (D2.x), default
(OQ-x), and surprise (S-x) it implements, with file-touch lists verified by
grep at draft time.

Doc-only. No code changes."

git log --oneline -1                                    # confirm hash
git status                                              # expect clean
```

**Do NOT push. Do NOT merge.** The merge prompt is a separate downstream step.

---

## Report back

Report to the human:

1. The new commit hash
2. The 6 file paths created
3. File-disjointness matrix from Section 2 — confirmed disjoint or any unexpected overlaps
4. Whether the pre-flight's Section 4 had file-touch lists already (yes/no), and whether the verification matched it (if yes)
5. Total lines added across the 6 files
6. Any surprises or scope deviations encountered during drafting
7. Branch state: still on `docs/phase2-sub-prompts`, commits ahead of main: 1

If anything blocked or required scope expansion beyond the prompt's instructions, STOP and report rather than working around it.
