# Phase 4 Close Document

**Phase:** 4 — Frontend Rail Polish + Server-side Sidebar Preference
**Closed:** 2026-04-27
**Pre-flight:** `9747964` (`docs/phases/phase4-preflight-2026-04-27.md`)
**SP-4A merge:** `b751b9b`
**SP-4B merge:** `044d194`
**Phase tag:** `frontend-phase-4`

---

## 1. Scope Delivered

All 5 locked Phase 4 findings shipped across 2 sub-prompts.

| Finding | Description | Closed by | Merge SHA |
|---|---|---|---|
| #13 | DashboardShell padding aligned to sidebar width (52px / 220px exact; was 56px / 240px) | SP-4A | `b751b9b` |
| #21 | Entity chip `<Tooltip>` replaces `title=` — keyboard a11y in collapsed rail | SP-4A | `b751b9b` |
| Gap-A | User-footer avatar: `<Tooltip>` with name + role + sign-out hint; `aria-label` carries identity; "Read-only access" matches SP-3C badge | SP-4A | `b751b9b` |
| Gap-B | Collapsed group divider `<hr>` elements carry `role="separator"` + `aria-label="End of {group} group"` | SP-4A | `b751b9b` |
| #22 | Server-side sidebar collapse preference: `sidebar_collapsed BOOLEAN NULL` on `iam_users`, `GET/PATCH /api/v1/users/me/preferences`, `SidebarCollapseBootstrap` component | SP-4B | `044d194` |

**Findings that were already closed at Phase 4 pre-flight start (no work needed):**

| Finding | Description | Status at pre-flight |
|---|---|---|
| #15 | Collapsed rail width = 52px | ✅ Already fixed (inline `style={{ width }}`) |
| #20 | Tooltip component on collapsed nav icons | ✅ Already fixed (`SidebarNavItem.tsx`) |
| #23 | Workspace / Org / Governance group structure + dividers | ✅ Fixed by Phase 3 SP-3C |

---

## 2. OQ Resolution Recap

**OQ-1 — Server-side sidebar preference (Finding #22):**
- Pre-flight offered two options: Option A (implement in Phase 4) or Option B (defer).
- Resolved 2026-04-27: **Option A — implement.** Phase 4 includes both SP-4A and SP-4B.
- Executed: backend migration + endpoint in SP-4B; frontend bootstrap component wired in SP-4B.

No other open questions were recorded for Phase 4.

---

## 3. Verification at Close

All checks run on `main` HEAD at close (`044d194` merged).

| Check | Result |
|---|---|
| Frontend `npm run build` | ✓ (130 routes, 0 errors) |
| Frontend `npm run lint` | ✓ (0 warnings, 0 errors) |
| Frontend Vitest | **222/224** — FU-007 baseline preserved; 2 known failures unchanged |
| Backend pytest (key suites) | ✓ — 34/34 across health, auth, tenant, preferences endpoints |
| Backend SP-4B new tests | ✓ — 6/6 (`test_user_preferences_endpoint.py`) |

**Vitest breakdown (Phase 4 additions):**

| Sub-prompt | New tests | What they cover |
|---|---|---|
| SP-4A | +5 | Collapse toggle width, entity chip tooltip (single + aggregate), avatar tooltip, avatar `aria-label` |
| SP-4B | +5 | Server null → localStorage fallback, server override, toggle PATCH fires, API failure handling |
| **Total new** | **+10** | Phase 4 test additions (212 → 222 green) |

**Manual cross-device test (SP-4B acceptance criteria):**
Deferred to staging smoke test. The `SidebarCollapseBootstrap` component is wired and the backend endpoint is verified by integration tests. Cross-device session test requires a deployed environment; marked for the next staging deploy.

---

## 4. Commits in This Phase

Output of `git log origin/main..main --oneline` at close (before push):

```
044d194 Merge branch 'feat/sp-4b-server-sidebar-pref' into main
e53a305 feat(sp-4b): SidebarCollapseBootstrap — localStorage-first, server-sync-second
7d78cf1 feat(sp-4b): add sidebar_collapsed column + GET/PATCH /users/me/preferences
b706354 chore(sp-4b): investigation — three facts established before code
b751b9b Merge branch 'feat/sp-4a-rail-polish' into main
dbb6975 test(sp-4a): collapse toggle + tooltip content + aria-label coverage
56ad19f fix(sp-4a): add ARIA labels to collapsed group dividers (Gap-B)
17709b6 fix(sp-4a): replace title= with Tooltip on collapsed chip + avatar (#21, Gap-A)
123f0a4 fix(sp-4a): align DashboardShell padding to sidebar width (#13)
064d5ad chore(sp-4a): section 0 verification gate
9747964 Merge branch 'chore/phase4-preflight' into main
0fbef11 chore(phase4): pre-flight planning doc
```

12 phase work commits + 1 close-doc commit = **13 total commits pushed** to origin/main.

---

## 5. Deferred / Out of Scope

### Pre-existing tracked items (unchanged by Phase 4)

| Item | Status | Notes |
|---|---|---|
| FU-007 (2 Vitest baseline failures — onboarding wizard) | ⏸ Pre-existing | Vitest count was 212/214 at Phase 4 start; 222/224 at close. The 2 failures are the same FU-007 tests. Not a Phase 4 regression. |
| FU-XXX (potential): `isTenantViewer()` alias audit | ⏸ New, low priority | Surfaced in SP-4A: literal `"tenant_viewer"` string is not in `ROLE_ALIASES` as a self-alias — `"auditor"` is the runtime alias that resolves to `tenant_viewer`. Worth a small audit pass during a Phase 6 RBAC-touching sub-prompt. Not blocking. |
| TD-017 (`lib/api/orgs.ts` endpoint duplication) | ⏸ Deferred | Not touched in Phase 4. Low priority. |
| FU-005 (deprecated Zustand fields in `workspace.ts`) | ⏸ Deferred | SP-4B touched `workspace.ts` indirectly (read-only) but FU-005 cleanup was intentionally deferred. Pair with next store-touching sub-prompt. |
| Manual cross-device sync test | ⏸ Staging | Logged above in Section 3. Requires deployed environment. |

### Items noted during close audit (no existing ticket)

None. The 12-commit diff contained only expected Phase 4 files. No surprises detected.

---

## 6. Phase 5 Entry Conditions

- `main` is clean, pushed to `origin/main`, tagged `frontend-phase-4`.
- Locked design Phase 4 items: **5/5 closed.**
- Phase 4 verification checklist:
  1. Collapsed rail width = 52px ✅
  2. Entity indicator reflects aggregate vs single entity ✅
  3. Workspace / Org / Governance groups separated by dividers ✅
  4. Every icon has a tooltip for hover and keyboard focus ✅
  5. Collapse preference persists in localStorage and server-side ✅
- Phase 5 opens fresh — no carry-over blockers from Phase 4.
