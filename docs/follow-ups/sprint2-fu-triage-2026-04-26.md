# Sprint 2 FU Triage — 2026-04-26

**Analyst:** Claude Code (claude-sonnet-4-6)  
**Branch at time of investigation:** `main` @ `198768a`  
**Working tree:** clean

---

## Summary

| FU | Title | Verdict |
|---|---|---|
| FU-006 | useSession mock in OrgSwitcher unit tests | **Resolved by SP-2A** |
| FU-008 | E2E test data dependencies | **Small mechanical fix remaining** |
| FU-013 | Sidebar pinning decision | **Wontfix (Option 3)** |

---

## FU-006 — useSession mock in OrgSwitcher unit tests

### Evidence

**FU as filed (2026-04-25):**
The original `OrgSwitcher.tsx` called `useSession()` from `next-auth/react` to gate rendering behind a role check (`platform_owner` / `super_admin`). The test file `frontend/tests/unit/org_switcher.test.tsx` failed because it rendered `OrgSwitcher` without mocking `useSession`, causing the component to return `null` in an indeterminate state and assertions to miss.

The `gap2-orgswitcher-trace-2026-04-25.md` audit confirms the old wiring:
> `useSession() reads session.user.role via next-auth (line 24)` → `if role NOT in ['platform_owner', 'super_admin']: return null`

**Current state (main @ 198768a):**
- `frontend/components/layout/OrgSwitcher.tsx` — **zero imports from `next-auth/react`**. The component was completely rewritten by SP-2A. Imports are: `useTenantStore`, `useWorkspaceStore`, `listUserSwitchableOrgs`, `useQueryClient`, React hooks, and UI primitives.
- `frontend/tests/unit/org_switcher.test.tsx` — **does not exist**. No test file in `frontend/tests/` references `OrgSwitcher` (grep: no matches).
- The INDEX already annotated this as "(partially resolved 2026-04-25)".

**Caveat:** The rewritten OrgSwitcher has no unit tests at all. The original FU was about a broken mock in an existing test; the SP-2A rewrite deleted that test (or it was never written for the new component). Adding unit tests for the new OrgSwitcher is a separate concern — not what FU-006 tracks.

### Verdict

**Resolved by SP-2A.** The `useSession` import is gone from `OrgSwitcher.tsx`. The mock incompleteness issue is moot. The failing test file no longer exists.

Close FU-006. If unit tests for the new OrgSwitcher are wanted, open a new FU scoped to "Add unit tests for rewritten OrgSwitcher (useTenantStore / listUserSwitchableOrgs mocking)".

---

## FU-008 — E2E test data dependencies

### Evidence

**FU as filed (2026-04-25):**
Two infrastructure gaps identified:
1. No `webServer` in `playwright.config.ts` → Playwright didn't start the dev server before tests.
2. No seed data or API mocking → specs depended on a live backend with specific tenants/entities seeded.

**Current state (main @ 198768a):**

**Gap 1 — webServer:** `frontend/playwright.config.ts` now has `webServer` configured:
```ts
webServer: {
  command: "npm run dev -- --port 3010",
  url: "http://localhost:3010",
  reuseExistingServer: !process.env.CI,
  timeout: 120000,
}
```
The `webServer` gap is closed.

**Gap 2 — API mocking:** `frontend/tests/e2e/helpers/mocks.ts` exists (375 lines) and implements comprehensive Playwright `route()` stubs via Option A (route interception). Routes covered include:
- `/api/auth/session`, `/api/auth/providers`, `/api/auth/csrf`, `/api/auth/signout`
- `/api/v1/platform/entities`, `/api/v1/platform/control-plane/context`
- `/api/v1/tenants/display-preferences`, `/api/v1/tenants/me`
- `/api/v1/notifications/unread-count`
- `/api/v1/billing/entitlements/current`
- `/api/v1/auth/login`, `/api/v1/auth/me`, `/api/v1/auth/refresh`

The `reconciliation.spec.ts` (representative mid-complexity spec) imports and uses `mockSession`, `mockCSRF`, `enableAuthBypassHeader`, `fulfillJson` from `helpers/mocks`. The `auth.spec.ts` tests public pages that require no mocking.

**Remaining gap:** The helpers infrastructure is in place, but a full audit of all 14 E2E specs is needed to confirm every authenticated spec calls `mockSession()` / `authenticate()` before navigating to gated routes. Some specs (especially older ones like `reconciliation.spec.ts`, `consolidation.spec.ts`, `mis.spec.ts`) may have been written expecting a running backend and only partially converted to use mocks.

### Classification

**Small mechanical fix remaining.** The architectural gap described in FU-008 (no webServer, no mocking infrastructure) is resolved. What remains is a verification sweep + targeted fixes in any spec that still reaches out to a live backend. This is a slot-into-Phase-3-polish-window task, not an architectural rebuild.

### Verdict

**Keep open, small mechanical fix.** Revise scope to: audit all 14 E2E specs in `frontend/tests/e2e/`, confirm each authenticated spec calls `authenticate()` or `mockSession()`, patch any that don't. Estimated effort: 1–2 hours.

---

## FU-013 — Sidebar pinning decision

### Evidence

**FU as filed (2026-04-25):**
Phase 1 sub-prompt 1.1 removed the "Pinned" section from the sidebar (it depended on the old flat `NAV_GROUP_DEFINITIONS` structure). FU-013 deferred the decision: bring pinning back (Option 1), move it to the modules tab bar (Option 2), or drop it entirely (Option 3). The FU's own acceptance criteria included: "nav-config.ts FU-013 reference removed."

**Locked design check — `finqor-shell-audit-2026-04-24.md`:**
Pinning is not named as a requirement. Finding #22 mentions tab order not being user-persistable, but that is module-tab reordering (Phase 3 Module Manager scope), not sidebar pinning. Finding #10 mentions `pinnedModules` in `useUIStore` as a legacy state-fragmentation issue (not a spec requirement for pinning). The audit's deferred work section records only: "FU-013 (sidebar pinning decision)" — i.e., it filed the question, it did not mandate pinning.

**Current sidebar surface:**
- `frontend/components/layout/Sidebar.tsx` — three nav groups (workspace / org / governance), entity tree (added SP-2B), collapsed-rail chip. No pinning section, no `pinnedModules` read.
- `frontend/components/layout/sidebar/nav-config.ts` — grep for `FU-013`, `pin`, `pinned`, `Pinned` returns **no matches**. The dangling FU-013 comment reference in nav-config.ts (an acceptance criterion in the FU) is already gone.

**v2 audit finding #2:** `useUIStore` contains `pinnedModules` as legacy mixed state — flagged for cleanup, not as a feature to preserve. This aligns with FU-005 (legacy store cleanup) scope.

**SP-2B context:** The sidebar surface has grown richer since FU-013 was filed — entity tree, org-context chip, collapsed rail. The "14+ items flat" scenario that made pinning useful no longer exists; the three-group structure with 3–5 items per group renders pinning unnecessary by the FU's own analysis.

### Verdict

**Wontfix — Option 3 (no pinning).** Rationale:
1. The locked design does not require sidebar pinning.
2. The nav-config.ts FU-013 reference is already gone (one acceptance criterion already met).
3. The three-group structure makes pinning unnecessary (FU-013's own Option 3 analysis).
4. `pinnedModules` in `useUIStore` is a legacy artifact tracked under FU-005; its removal does not constitute a pinning feature.
5. SP-2B's entity tree and collapsed rail have made the sidebar surface richer in the directions the spec actually requires.

The decision to record in the FU file: **Option 3 selected.** Implementation effort: 0 hours (nav-config.ts comment already removed). Close after recording the decision.

---

## Recommended INDEX.md updates

These are proposals only. Do NOT apply until reviewed.

### FU-006

Change the open-table row from:
```
| FU-006 | [Add useSession mock to OrgSwitcher unit tests (partially resolved 2026-04-25)](./FU-006-useSession-mock-incompleteness.md) | 2026-04-25 | Phase 0 test gate (pre-existing) |
```
Move to merged/closed section:
```
| FU-006 | Add useSession mock to OrgSwitcher unit tests | 2026-04-25 | Closed 2026-04-26 — resolved by SP-2A (OrgSwitcher rewritten, useSession removed) |
```

### FU-008

Update the open-table title to reflect narrowed scope:
```
| FU-008 | [Audit and fix remaining E2E specs for mockSession coverage](./FU-008-e2e-data-dependencies.md) | 2026-04-25 | Phase 0 test gate (pre-existing) |
```
(webServer and mocks.ts infrastructure is done; remaining work is the sweep)

### FU-013

Move to closed/wontfix section:
```
| FU-013 | Sidebar pinning decision | 2026-04-25 | Closed 2026-04-26 — Option 3 (no pinning). Three-group structure sufficient; not in locked design; nav-config.ts comment already removed. |
```
