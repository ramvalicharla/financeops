# Phase 4 Pre-flight Planning Document

**Date:** 2026-04-27
**Branch:** `chore/phase4-preflight` (off `main` at `8f9473c`)
**Investigator:** Claude Sonnet 4.6 (read-only Sections 0–5, doc-write Section 6)
**Phase:** Phase 4 — Collapsed Rail polish
**Status:** Pre-flight complete — persistence decision (OQ-1) PENDING user input before SP-4A can be scoped

---

## 1. Working Tree State at Pre-flight Start

| Check | Value | Status |
|---|---|---|
| Branch | `chore/phase4-preflight` (off `main`) | ✓ |
| HEAD | `8f9473cb22cb9d70a3566f0dcb90ff7a0e764932` | ✓ |
| main HEAD | `8f9473c` — Merge chore/phase3-close-handoff | ✓ |
| Working tree | Clean (doc-only branch) | ✓ |
| Tag at Phase 3 close | `v4.6.0-phase3-complete` at `8f9473c` | (context) |
| Build baseline | `next build` ✓ (129 routes) | ✓ |
| Lint baseline | `next lint` ✓ (0 warnings) | ✓ |
| Vitest baseline | 212/214 — FU-007 unchanged | ✓ |

**Phase history at pre-flight:** Pre-Phase-0 → Phase 0 → Phase 1 → Pre-Phase-2 → Phase 2 → Pre-Phase-3 → Phase 3 all complete. Phase 4 is next. The most recent substantive work was Phase 3's verification cleanup (keyboard reorder spec, removal of substitute test, `README.md` update). `main` is clean and in sync with origin.

### Section 1.4 — Locked design scope for Phase 4

The locked design (`docs/audits/finqor-shell-audit-2026-04-24-v2.md` §3.3 "Phase 4 — Collapsed rail") specifies:

- **Findings to fix:** #13, #15, #20, #21, #22, #23
- **Total estimate:** 4 days
- **Dependencies:** Phase 1, Phase 2
- **Verification checklist (verbatim from audit):**
  1. Collapsed rail width is exactly 52px.
  2. Entity indicator reflects aggregate vs single entity.
  3. Workspace, Org, and Governance icon stacks are separated by dividers.
  4. Every icon has a tooltip that works for hover and keyboard focus.
  5. Collapse preference persists in localStorage and server-side user preferences.

Status of each finding at pre-flight start — see Section 2 (Decision Log).

---

## 2. Decision Log

Factual resolutions from reading the codebase. These are not user decisions — they are evidence-based findings.

| # | Decision | Evidence | Impact |
|---|---|---|---|
| D-01 | Finding #15 (collapsed rail width) is already fixed. Sidebar uses inline `style={{ width: sidebarCollapsed ? "52px" : "220px" }}` | `components/layout/Sidebar.tsx:154` | Verification checklist item 1 is already met — no work needed |
| D-02 | Finding #20 (tooltip component on collapsed nav icons) is already fixed. `SidebarNavItem.tsx` imports and uses `<Tooltip>`, `<TooltipContent>`, `<TooltipTrigger>` | `components/layout/_components/SidebarNavItem.tsx:9,43–62` | Verification checklist item 4 is already met — no work needed |
| D-03 | Finding #23 (Workspace/Org/Governance group separation in collapsed rail) is already fixed. Phase 3 SP-3C restructured `nav-config.ts` into three groups; collapsed mode renders `<hr>` dividers between groups | `components/layout/Sidebar.tsx:251–263`, `components/layout/sidebar/nav-config.ts` | Verification checklist item 3 is already met — no work needed |
| D-04 | Finding #21 (entity-state chip) is half-fixed. The aggregate/single-entity logic is correct — single entity shows entity initial; aggregate shows org initial + count. But the toggle chip still uses `title=` attribute, not `<Tooltip>` component — keyboard focus does not show the entity/aggregate label | `components/layout/Sidebar.tsx:157–178` (uses `title=` on line 164 and `title=` on line 174) | Checklist item 2 is functionally met; keyboard tooltip is not — partial gap remains (see Gap-A) |
| D-05 | Finding #13 (DashboardShell offsets) is NOT fixed. Sidebar width IS 52px/220px (D-01), but `DashboardShell.tsx` still uses `md:pl-14` (56px) / `md:pl-60` (240px). Results in a 4px over-padding on collapsed and 20px over-padding on expanded | `components/layout/DashboardShell.tsx:25` | Content area shifts more than sidebar width — layout precision gap |
| D-06 | Finding #22 (server-side sidebar preference) is NOT fixed. A `display-preferences` endpoint exists (`GET/PATCH /api/v1/tenants/display-preferences`) and covers `display_scale`. It does NOT include `sidebar_collapsed`. No `IamUser` column for sidebar state. | `backend/financeops/api/v1/tenants.py:333–376`, `frontend/lib/api/sprint11.ts:126–141` | Checklist item 5 is half-met (localStorage ✅, server-side ❌). Backend schema + migration + frontend wiring needed if in scope |
| D-07 | Gap-A (auditor role in collapsed mode) belongs on the **user-footer avatar**, not the entity chip. The entity chip's job is entity context. Per locked design §1.3, role information lives in the user footer. The collapsed footer avatar button (lines 304–312) already carries the role string via `title=` (`"${userName} · ${userRole}\n${userEmail}\nClick to sign out"`), but uses `title=` not `<Tooltip>` (keyboard gap) and `aria-label="Sign out"` strips identity context for screen readers. For an auditor the role renders as "tenant viewer" — inconsistent with the expanded footer's "Read-only access" badge. | `components/layout/Sidebar.tsx:304–312` | Fix in SP-4A Section 2: wrap collapsed avatar button in `<Tooltip>` with content `{userName} · {isTenantViewer(userRole) ? "Read-only access" : role} — Click to sign out`; update `aria-label` to `"Sign out ${userName}"` |
| D-08 | Group divider `<hr>` separators in collapsed mode carry no accessible group name. Screen readers cannot announce which group boundary is being crossed | `components/layout/Sidebar.tsx:254` — `<hr className="my-1 border-border" />` with no `aria-label` | Minor a11y gap; `aria-orientation="horizontal"` + `aria-label` would fix |
| D-11 | **User-footer audit (collapsed mode):** Footer renders ✅. Avatar button shows initials ✅. Role string is present in `title=` attribute (includes `userRole` and `userEmail`) ✅. Toggle action on click (sign-out) ✅. Settings cog `<Link>` below avatar ✅. **Gaps:** (1) `title=` not `<Tooltip>` — keyboard focus shows no tooltip, (2) `aria-label="Sign out"` loses user identity for screen readers, (3) auditor role reads "tenant viewer" (raw enum) vs "Read-only access" (badge label in expanded footer) — terminology inconsistency, (4) collapse toggle button at the very bottom is a separate element with correct `aria-label` ("Expand/Collapse sidebar") | `components/layout/Sidebar.tsx:300–376` | All four gaps fixed in SP-4A Section 2 as corrected below |
| D-09 | Module Manager `+` button lives in the Topbar (ModuleTabs), NOT the sidebar. In collapsed mode the topbar is fully visible — no collision risk with the 52px rail | `components/layout/ModuleTabs.tsx` — Phase 3 SP-3A confirmed | Phase 4 handoff concern confirmed resolved |
| D-10 | Three existing Sidebar unit tests cover group rendering and item counts. No tests for collapse/expand toggle, localStorage persistence, or the collapsed chip tooltip | `components/layout/__tests__/Sidebar.test.tsx` — 3 describe blocks, 5 tests | Phase 4 sub-prompts should add collapse toggle + chip tooltip tests |

---

## 3. Surprises Register

| ID | Severity | Summary | Affected Sub-prompts | Recommended Resolution |
|---|---|---|---|---|
| S-001 | HIGH (SCOPE REDUCTION) | Findings #15, #20, and #23 are already fixed in main — 3 of the 5 Phase 4 locked findings require no work. Phase 4 is substantially smaller than the 4-day locked estimate. | All | Downsize sub-prompt plan accordingly; re-estimate to ~1–3 days depending on OQ-1 |
| S-002 | LOW | Finding #21 entity-state chip is 90% done — entity/aggregate logic correct, but the toggle chip header still uses `title=` not `<Tooltip>`. Keyboard focus does not expose the entity name in collapsed mode. | SP-4A | Fix is one-line: replace `title={...}` with `<Tooltip>` wrapper on the collapsed header chip (2 buttons) |
| S-003 | LOW | `display-preferences` backend endpoint scaffolding is already in place (GET/PATCH at `/api/v1/tenants/display-preferences`). Adding `sidebar_collapsed` is an additive field to an existing endpoint + 1 new `IamUser` column. No new endpoint design needed. | SP-4B (if in scope) | Backend effort for Finding #22 is smaller than the M-estimate suggested. Migration + field + wire = ~1 day backend, ~0.5 day frontend |
| S-004 | LOW | Collapsed `<hr>` dividers between nav groups are visually correct but have no `aria-label` — screen readers cannot announce the group boundary name. This is a minor a11y regression introduced in Phase 3 SP-3C. | SP-4A | Add `aria-label="End of Workspace group"` (or similar) to each divider `<hr>` — trivial fix, pair with SP-4A |

### S-001 full text

Three of the five locked Phase 4 findings are already fixed in main at pre-flight start:

- **#15 (52px width)** — fixed via inline style `width: sidebarCollapsed ? "52px" : "220px"` in a prior sprint (between Phase 2 close and Phase 3 start, based on git blame)
- **#20 (Tooltip component)** — fixed in `SidebarNavItem.tsx`: full `<Tooltip>/<TooltipContent>/<TooltipTrigger>` import and usage for all collapsed nav icons
- **#23 (W/O/G group structure)** — fixed as part of Phase 3 SP-3C, which restructured `nav-config.ts` into three proper groups and renders `<hr>` dividers in collapsed mode

Remaining locked-design work for Phase 4:
- **#13** (DashboardShell offset precision) — open
- **#21 partial** (chip tooltip — keyboard gap) — open
- **#22** (server-side sidebar preference) — open; needs OQ-1 decision

Additional items surfaced by investigation:
- **Gap-A** (auditor collapsed tooltip) — open; Phase 4 handoff explicitly calls this out
- **Gap-B** (divider `<hr>` ARIA labels) — open; minor a11y

---

## 4. Sub-prompt Dependency Map

### Proposed sub-prompt list

| ID | Scope | Files touched | Dependencies | Backend tickets | Est. size | Parallel? |
|---|---|---|---|---|---|---|
| **SP-4A** | DashboardShell offset fix (#13) + collapsed chip tooltip upgrade (#21 gap) + auditor role in chip tooltip (Gap-A) + divider aria-labels (Gap-B) + unit tests for collapse toggle and chip | `components/layout/DashboardShell.tsx`, `components/layout/Sidebar.tsx` (lines 157–178, 251–263), `components/layout/__tests__/Sidebar.test.tsx` | Phase 3 complete (done) | None | S (0.5–1 day) | Standalone, no blockers |
| **SP-4B** | Server-side sidebar preference (#22) — add `sidebar_collapsed` to `display-preferences` endpoint + `IamUser` migration + frontend wiring | `backend/financeops/api/v1/tenants.py`, new migration file, `frontend/lib/store/workspace.ts`, `frontend/lib/api/sprint11.ts` (seed from API on load) | SP-4A merged (clean baseline) | None (extends existing endpoint) | M (1.5–2 days) | After SP-4A merges |

### Recommended execution order

```
SP-4A — unblocked, ~1 day
  ↓ (sequential, SP-4A must be merged first)
SP-4B — if OQ-1 resolves to "implement"  (1.5–2 days)
     OR deferred to Phase 5/6 if OQ-1 resolves to "defer"
```

SP-4A is fully unblocked and small — fix the four remaining gaps, add tests, merge. SP-4B depends on OQ-1 user decision.

**If OQ-1 = defer:** Phase 4 is SP-4A only (~1 day). Post-Phase-4 checklist item 5 ("server-side persistence") remains open; mark as FU-XXX in the close handoff.

**If OQ-1 = implement:** Phase 4 is SP-4A + SP-4B (~2.5–3 days total). All 5 verification checklist items met at close.

### Phase 4 verification checklist status after SP-4A only

| Checklist item | Post-SP-4A |
|---|---|
| 1. Collapsed rail width is exactly 52px | ✅ Already met (D-01) |
| 2. Entity indicator reflects aggregate vs single entity | ✅ Fixed in SP-4A (chip tooltip upgrade) |
| 3. Workspace, Org, and Governance icon stacks separated by dividers | ✅ Already met (D-03) |
| 4. Every icon has a tooltip for hover and keyboard focus | ✅ Fixed in SP-4A (chip tooltip; nav items already met by D-02) |
| 5. Collapse preference persists in localStorage and server-side | ⚠️ localStorage ✅, server-side ❌ → fixed in SP-4B (OQ-1 resolved: in scope) |

---

## 5. Persistence Decision — RESOLVED

**OQ-1 resolved 2026-04-27: Option A — implement SP-4B.** Server-side `sidebar_collapsed` preference will be wired in Phase 4. Phase 4 is SP-4A + SP-4B, ~2.5–3 days total. Original framing preserved below for reference.

### Finding #22 — Server-side sidebar preference

**What the locked design requires:**
> "Collapse preference persists in localStorage and server-side user preferences."

**Current state:**
- localStorage persistence: ✅ fully working (Zustand `persist()` middleware, key `finqor-workspace`)
- Server-side persistence: ❌ not implemented. The existing `PATCH /api/v1/tenants/display-preferences` endpoint handles `display_scale` only.

**What implementation would cost (S-003 confirms this is smaller than the M-estimate):**

Backend (≈0.5 day):
- Add `sidebar_collapsed: bool | None = None` to `UpdateDisplayPreferencesRequest` schema in `tenants.py`
- Add `IamUser.sidebar_collapsed` column (boolean, nullable, default NULL) — new Alembic migration
- Wire: if body contains `sidebar_collapsed`, update `current_user.sidebar_collapsed`
- Add to `GET /api/v1/tenants/display-preferences` response: `"sidebar_collapsed": current_user.sidebar_collapsed`

Frontend (≈0.5 day):
- On sidebar mount: call `getDisplayPreferences()` and seed `sidebarCollapsed` from `response.sidebar_collapsed` if not null (server preference wins over localStorage on first load)
- On toggle: fire `updateDisplayPreferences({ sidebar_collapsed: !sidebarCollapsed })` debounced (250ms)
- No new query keys needed — `display-preferences` already fetched by `useDisplayPreferences()` hook in `sprint11.ts`

**Two options:**

**Option A — Implement in SP-4B (~1.5 days)**
- Phase 4 closes with all 5 verification items met
- Adds ~1.5 days to Phase 4 estimate
- Useful if sidebar preference should survive across devices / browser clears

**Option B — Defer to Phase 5/6 (~0 days)**
- Phase 4 closes with 4 of 5 checklist items met; item 5 noted as `⚠️ localStorage only`
- SP-4B filed as FU-XXX deferred item in the close handoff
- Phase 4 becomes SP-4A only (~1 day)
- Appropriate if localStorage persistence is sufficient for the current product stage

**Agent recommendation was Option B (defer).** User resolved to **Option A (implement SP-4B now)** on 2026-04-27. SP-4A + SP-4B are both in Phase 4 scope. All 5 verification checklist items will be met at Phase 4 close.

---

## 6. Gap Status Table

| ID | Finding/Gap | Status | Notes |
|---|---|---|---|
| #13 | DashboardShell offsets 52px/220px | ❌ Open | `pl-14`/`pl-60` = 56px/240px vs sidebar 52px/220px — fix in SP-4A |
| #15 | Collapsed rail width 52px | ✅ Fixed | Inline style already correct (D-01) |
| #20 | Tooltip component on collapsed nav icons | ✅ Fixed | Full `<Tooltip>` usage in SidebarNavItem (D-02) |
| #21 | Entity-state chip (aggregate vs single) | ⚠️ Partial | Logic correct; chip uses `title=` not `<Tooltip>` — keyboard gap; fix in SP-4A |
| #22 | Server-side sidebar preference | ❌ Open | Requires OQ-1 decision; localStorage works |
| #23 | W/O/G group structure + dividers | ✅ Fixed | Phase 3 SP-3C delivered (D-03) |
| Gap-A | Auditor role indicator in collapsed mode | ❌ Open | User-footer avatar uses `title=` not `<Tooltip>`; `aria-label="Sign out"` strips identity; role reads "tenant viewer" not "Read-only access" — fix in SP-4A Section 2 |
| Gap-B | Collapsed group divider ARIA labels | ⚠️ Open | `<hr>` has no `aria-label` for screen readers — fix in SP-4A |

**Summary: 3 ✅ (already fixed) / 2 ⚠️ (partial/cosmetic) / 3 ❌ (open)**
- Open gaps in SP-4A scope: #13, #21 partial, Gap-A (user-footer avatar), Gap-B
- Open gap in SP-4B scope (OQ-1 resolved → implement): #22

---

## 7. Surprises Summary

| ID | Severity | One-line summary |
|---|---|---|
| S-001 | HIGH | #15 + #20 + #23 already fixed — Phase 4 is ~1–3 days not 4 |
| S-002 | LOW | #21 chip uses `title=` not `<Tooltip>` — trivial keyboard gap remaining |
| S-003 | LOW | `display-preferences` endpoint already exists; SP-4B backend cost is small |
| S-004 | LOW | Collapsed `<hr>` dividers have no ARIA labels — minor a11y regression from Phase 3 |

---

## 8. Open Questions

| ID | Question | Blocks | Recommendation |
|---|---|---|---|
| ~~OQ-1~~ | ~~Persistence decision~~ | ~~SP-4B scoping~~ | **RESOLVED 2026-04-27 — Option A (implement SP-4B).** Phase 4 includes both SP-4A and SP-4B. |

No open questions remain. SP-4A can be drafted immediately.

---

## 9. Deferred Items Carried Forward

| Item | Status | Phase 4 relevance | When/where |
|---|---|---|---|
| BE-002 — Consolidation + tax workspace tab promotion | ⏸ Filed, not executed | None | When backend lands, triggers SP-2E |
| `module.manage` backend ticket | ⏸ Not drafted | None | Draft before next sub-prompt depending on Module Manager save path |
| `GET /api/v1/billing/module-pricing` | ⏸ Not drafted | None | Premium tab zero-state until it lands |
| FU-005 (deprecated Zustand fields) | ⏸ Pair with any store-touching sub-prompt | None in Phase 4 (SP-4A doesn't touch stores) | SP-4B touches `workspace.ts` — good pairing point |
| FU-007 (Onboarding wizard test mismatches) | ⏸ Polish window | None | Standalone polish |
| FU-008 (E2E mockSession sweep) | ⏸ Polish window | None | Standalone polish |
| FU-009 (WebKit Playwright binary) | ⏸ Policy decision | None | Not a Claude task |
| TD-017 (`orgs.ts` endpoint duplication) | ⏸ Pair with Phase 4+ orgs work | None in Phase 4 | Low priority |
| Auditor in-page write-button disabling (URL-bypass gap) | ⏸ Phase 6 | None | Phase 6 RBAC scope |
| GitHub PAT in plaintext `.git/config` | ⏸ Local hygiene | None | Replace with credential helper at convenience |

---

## 10. Sub-prompt Structure Recommendation

### Recommended sequence (OQ-1 resolved — Option A)

```
SP-4A  (0.5–1 day)
  ↓ merge ↓
SP-4B  (1.5–2 days — backend + frontend preference wiring)
  ↓ merge ↓
Phase 4 close handoff + tag v4.7.0-phase4-complete
```
Total: ~2.5–3 days. 4–5 sub-prompt commits, 2 merges, 1 handoff doc. All 5 verification checklist items met at close.

### SP-4A brief (frontend-only, S effort)

**Sections:**
1. Section 0 — Verification gate (read current state, confirm baseline, STOP before any edits)
2. Section 1 — DashboardShell offset precision (#13): `md:pl-14` → `md:pl-[52px]`; `md:pl-60` → `md:pl-[220px]` in `DashboardShell.tsx`
3. Section 2 — Collapsed tooltips (#21 gap + Gap-A, corrected surfaces): (a) Entity chip (#21 gap) — wrap the two collapsed header chip buttons in `<Tooltip>` showing entity name only (entity context, not role) in `Sidebar.tsx:157–178`; (b) User-footer avatar (Gap-A — correct surface per locked design §1.3) — wrap collapsed avatar button in `<Tooltip>` with `{userName} · {isTenantViewer(userRole) ? "Read-only access" : role.replace(/_/g, " ")} — Click to sign out`; update `aria-label` to `"Sign out ${userName}"` in `Sidebar.tsx:304–312`. Role information belongs on the user footer, not the entity chip.
4. Section 3 — Divider ARIA labels (Gap-B): add `role="separator"` + `aria-label="End of {group.label} group"` to each `<hr>` in the collapsed nav loop in `Sidebar.tsx`
5. Section 4 — Unit tests: add collapse toggle test + chip tooltip content test to `Sidebar.test.tsx`
6. Section 5 — Build + lint + vitest gate; STOP for merge approval

### SP-4B brief (full-stack, M effort — OQ-1 resolved: in Phase 4 scope)

**Sections:**
1. Section 0 — Verification gate + backend schema review
2. Section 1 — Backend: add `sidebar_collapsed: bool | None` to `UpdateDisplayPreferencesRequest` + `IamUser` column + migration + GET response field
3. Section 2 — Frontend: seed `sidebarCollapsed` from `getDisplayPreferences()` on Sidebar mount; wire debounced `updateDisplayPreferences` on toggle; pair FU-005 field removal
4. Section 3 — Tests: unit test for seeding behavior (null server pref → localStorage wins; non-null → server wins)
5. Section 4 — Build + lint + vitest gate; STOP for merge approval
