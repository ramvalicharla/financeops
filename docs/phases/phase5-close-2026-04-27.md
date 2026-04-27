# Phase 5 Close Document

**Phase:** 5 — Global UX Polish
**Status:** Closed
**Tag:** `v4.10.0-phase5-complete`
**Closed:** 2026-04-27
**Pre-flight commit:** `436a15e` (`docs/phases/phase5-preflight-2026-04-27.md`)
**Close commit:** `f37e31d`
**Total commits in phase:** 18 work commits + 1 close-doc commit = **19 total**

---

## 1. Phase Summary

Phase 5 was a frontend-only polish pass: zero backend commits, zero schema changes, zero migration bumps. Five sub-prompts shipped in chronological order (SP-5E → SP-5A → SP-5B → SP-5D → SP-5C), each targeting a distinct concern surfaced during the Phase 5 pre-flight audit.

Pre-flight commit: `436a15e` (merged `chore/phase5-preflight`).
Phase 5 HEAD at close: `fb9554c` (merged `chore/sp-5c-a11y-polish-pass`).

---

## 2. Sub-Prompts Shipped

| SP | Branch | Merge | Scope | Outcome | FUs |
|---|---|---|---|---|---|
| SP-5E | `chore/sp-5e-fu-cleanup` | `f8814d1` | FU paperwork close + onboarding wizard test fix | FU-007 assertions realigned to current copy; FU-019 and FU-004 closed via paperwork (both silently resolved in prior phases) | FU-007 closed; FU-019 closed; FU-004 closed |
| SP-5A | `chore/sp-5a-commandpalette-dedup` | `2e900fc` | Duplicate CommandPalette component + dual ⌘K handler removal (🔴 blocker) | Removed hardcoded duplicate palette; single `CommandPalettePortal` with unified ⌘K listener | — |
| SP-5B | `chore/sp-5b-formatamount-currency-sweep` | `d9152d5` | Replace raw currency `.toFixed(2)` with `formatAmount` / `useFormattedAmount` | 5 call-sites updated across financial display components | — |
| SP-5D | `chore/sp-5d-topbar-brand-mark` | `623af8e` | TopBar Finqor brand mark (FU-011 paperwork) | FU-011 confirmed resolved in commit `d28c5ba` (prior to Phase 5); paperwork closed | FU-011 closed |
| SP-5C | `chore/sp-5c-a11y-polish-pass` | `fb9554c` | `prefers-reduced-motion` guard + `loading.tsx` coverage (15 routes) + `RouteAnnouncer` + EmptyState audit | Motion prefs guarded; 15 route-level skeletons added; `RouteAnnouncer` component wired; EmptyState sweep confirmed 1 adoption (bespoke border-dashed pattern valid on remainder) | FU-020 filed |

---

## 3. FU Register Changes

| FU | Action | Reason |
|---|---|---|
| FU-007 | **Closed** | Onboarding wizard text-match assertions realigned to current copy in SP-5E (`538f751`). Vitest count restored: 222/224 → 224/224. |
| FU-019 | **Closed** | Silently resolved between Phase 2 close and Phase 5 entry (control_plane test failures no longer reproducible). Paperwork closed in SP-5E. |
| FU-004 | **Closed** | Lint already at 0 errors / 0 warnings on Phase 5 entry. Silently resolved in a prior phase. Paperwork closed in SP-5E. |
| FU-011 | **Closed** | TopBar Finqor brand mark silently resolved in commit `d28c5ba` before Phase 5. Paperwork closed in SP-5D. |
| FU-020 | **Filed** | Deferred skeleton coverage (86 routes without `loading.tsx`) + EmptyState pattern unification (two valid coexisting patterns, no documented preference). Scoped for a future polish window. |

---

## 4. Lessons Learned

### (a) Silent FU resolutions are a process gap

Three FUs (FU-019, FU-011, FU-004) were silently resolved in prior phases without paperwork updates. Phase 5's audit-driven pre-flight surfaced all three. **Recommendation for Phase 6+:** when closing a piece of work that incidentally resolves an open FU, update `docs/follow-ups/INDEX.md` in the same commit. The cost is one line; the benefit is that the FU register stays a source of truth rather than a stale ledger.

### (b) Pre-flight gap counts are estimates, not censuses

Pre-flight estimated ~28 routes needing `loading.tsx` (actual: 101 — 3.6× off), ~38 routes needing `EmptyState` (actual: 1 in scope; the remainder used a valid bespoke pattern), and ~12 currency `.toFixed()` instances (actual: 5). **Recommendation:** sub-prompt audit checkpoints remain the source of truth. Pre-flight numbers are useful for sub-prompt scoping (cap setting, parallelization decisions) but should be communicated as order-of-magnitude estimates, not definitive scope figures. Framing matters: "roughly 30" vs "28" signals very different confidence levels to the reader.

### (c) Bespoke patterns can be valid — audit before sweeping

SP-5C Section 4 audit revealed the codebase has a deliberate `border-dashed + bg-muted/20` empty-state convention used consistently across ~12 list pages. The pre-flight framed this as "EmptyState used in only 2 of ~40 routes, implying widespread inconsistency," but the audit showed two valid coexisting patterns with no documented preference for either. **Recommendation:** when pre-flight surfaces "component X used in N of M sites," verify the M-N sites are actually broken before scoping a sweep. A consistent bespoke pattern is not a bug.

**Process note:** Direct-to-main hotfix `5d3ad77` (`fix(sp-5b): add fmt to useMemo dep array in budget edit page`) landed outside the sub-prompt branch structure — a small lint/correctness fix that did not warrant a branch. Legitimate. Documented here for future topology readers so the commit does not appear anomalous in the Phase 5 commit graph.

---

## 5. Test Baselines (Closing State)

| Check | Result |
|---|---|
| `npm run build` | ✓ 0 errors |
| `npm run lint` | ✓ 0 warnings, 0 errors |
| Vitest | **224/224** (verified 2× in pre-push) |
| Backend pytest | not in scope (Phase 5 frontend-only) |
| Alembic head | unchanged from Phase 4 (`0146_sidebar_collapsed`) |

**Vitest delta across Phase 5:**

| Sub-prompt | Δ tests | What they cover |
|---|---|---|
| SP-5E | +2 | Onboarding wizard copy-drift assertions restored (FU-007) |
| SP-5A | 0 | Refactor only — existing palette tests cover the unified path |
| SP-5B | 0 | Display-layer change; no new unit tests required |
| SP-5D | 0 | Paperwork only |
| SP-5C | 0 | New components (RouteAnnouncer, loading.tsx stubs); future test coverage in FU-020 |
| **Total** | **+2** | 222 → 224 green |

---

## 6. Commits in This Phase

`git log 436a15e..fb9554c --oneline` (18 work commits; close-doc commit adds 1):

```
fb9554c Merge SP-5C: motion + loading + RouteAnnouncer + EmptyState polish
1ec0f27 docs(fu): file FU-020 — deferred skeleton + EmptyState coverage
6193862 feat(empty-state): adopt EmptyState on 1 route (sweep audit complete)
3ef47fd feat(a11y): RouteAnnouncer for route-change announcements
91688f6 feat(loading): add route-level loading.tsx skeletons to 15 routes
8b7ef91 fix(motion): guard animations with prefers-reduced-motion
623af8e Merge SP-5D: TopBar Finqor brand mark (FU-011)
29538fe docs(fu): close FU-011 (TopBar brand mark)
5d3ad77 fix(sp-5b): add fmt to useMemo dep array in budget edit page   ← direct-to-main hotfix
d9152d5 Merge branch 'chore/sp-5b-formatamount-currency-sweep' into main
73c5e97 feat(sp-5b): replace currency .toFixed(2) with formatAmount / useFormattedAmount
2e900fc Merge SP-5A: remove duplicate CommandPalette, reconcile ⌘K handler
f6c2af9 refactor(commandpalette): remove duplicate hardcoded palette
f8814d1 Merge SP-5E: FU-007 fix + FU-019/FU-004 paperwork close
444b768 docs(fu): close FU-007, FU-019, FU-004 (SP-5E)
538f751 test(onboarding-wizard): fix copy-drift assertions (FU-007)
436a15e Merge branch 'chore/phase5-preflight' into main   ← pre-flight (not counted in 18)
```

---

## 7. Branch Retention

Per the project pattern (50+ historical branches retained from Phases 0–4): **all Phase 5 branches retained, none deleted.**

| Branch | Status |
|---|---|
| `chore/phase5-preflight` | retained |
| `chore/sp-5e-fu-cleanup` | retained |
| `chore/sp-5a-commandpalette-dedup` | retained |
| `chore/sp-5b-formatamount-currency-sweep` | retained |
| `chore/sp-5d-topbar-brand-mark` | retained |
| `chore/sp-5c-a11y-polish-pass` | retained |

Total branches (local) at Phase 5 close: **54** (including all Phase 5 branches).

---

## 8. Carry-Overs into Phase 6

| Item | Origin | Notes |
|---|---|---|
| **FU-020** — deferred skeleton coverage + EmptyState pattern unification | Phase 5 | 86 routes without `loading.tsx`; bespoke vs `EmptyState` preference undocumented. Scoped for a future polish window. |
| **FU-XXX** — RBAC alias audit (`isTenantViewer("tenant_viewer")` returns false) | Phase 4 / SP-4A | `"auditor"` is the runtime alias; `"tenant_viewer"` is the permission string. Low priority; pair with next RBAC-touching sub-prompt. |
| **Aggregate chip format** | Phase 3 | "All entities" vs "OrgName — N entities" — low priority; blocked on `organizationLabel` test reliability. |
| **Gap 1** — portal subdomain decision | Phase 5 pre-flight | Single `app.finqor.ai` vs split `app.` / `platform.` / `partners.`. Must resolve before Phase 6 design review. |

---

## 9. Phase 6 Entry Conditions

- `main` at `f37e31d` (post-amend)
- Tag `v4.10.0-phase5-complete` pushed to `origin`
- All Phase 5 sub-prompt branches retained per project pattern
- `origin/main` and `main` aligned post-push
- No open blockers from Phase 5
