# Finqor Frontend — Phase 3 Close Handoff

**Date:** 2026-04-26 (Phase 3 close)
**Stack:** Next.js 14, TypeScript, Tailwind, shadcn/ui, TanStack Query, Zustand, dark mode only
**Working style:** Solo engineer, Claude Code agents, branch-per-task, `--no-ff` merges, per-section commits for risky work, `git worktree` for parallel sessions (not used in Phase 3 — sequential)
**main on origin:** `ed7eb29` + 2 close-handoff commits (this doc's branch + merge), tagged `v4.6.0-phase3-complete`
**Prior tag:** `v4.5.0-phase2-complete` at `20985cf` — unchanged

---

## Phase status overview

| Phase | Status | Tag | What it delivered |
|---|---|---|---|
| Pre-Phase-0 through Phase 2 | ✅ Complete | up to `v4.5.0-phase2-complete` | See Phase 2 close handoff for full history |
| Pre-Phase-3 cleanup | ✅ Complete | (no tag) | Sprint 2 FU triage; TD-016 Option A; BE-002 + TD-018 filed |
| **Phase 3 — Module System** | **✅ Complete** | **`v4.6.0-phase3-complete`** | **Module Manager modal (4 tabs), drag-reorder with a11y, auditor sidebar filtering + read-only badge, /settings/modules redirect, FU-019 closed** |
| Phase 4 | ⏸ Queued | — | Collapsed Rail polish |
| Phase 5 | ⏸ Queued | — | Global UX Polish (CommandPalette live search) |
| Phase 6 | ⏸ Queued | — | RBAC + Portal Alignment (includes auditor in-page write-button disabling — see Known scope gap below) |

---

## What Phase 3 delivered

### Pre-Phase-3 work (already merged before Phase 3 sub-prompts started)

- Pre-flight pass at `24658a7`, merged at `63b7145` — produced planning doc at `docs/phases/phase3-preflight-2026-04-26.md`
- OQ triage at `38b50cc`, merged at `272e9bc` — resolved 6 open questions (OQ-1 through OQ-6); reclassified S-001 to HIGH and resolved alongside S-003 and S-004; corrected the `"overview"` → `"dashboard"` documentation error in the locked design

### Phase 3 sub-prompts

**SP-3A — Module Manager modal + RBAC + redirect + FU-019** — merged at `29514a8`
- Module Manager modal at `frontend/components/modules/ModuleManager.tsx` with 4 tabs (Active, Available, Premium, Custom) — Dialog gets a 640px width override
- Active tab with `frontend/lib/store/moduleOrder.ts` Zustand store and localStorage persistence (key: `finqor:module-order:v1`)
- Available tab with toggle UI; write path stubbed pending backend (toast: "Module enable/disable will activate when backend support lands")
- Premium tab zero-state pending billing endpoint
- Custom tab stub: "Custom modules coming soon — contact your admin to request a custom module"
- `+` button with `module.manage` RBAC gate using `canPerformAction("module.manage", ...)` — speculative-with-TODO; currently returns false for all users until backend ticket lands
- `/settings/modules` redirect to `/dashboard?modal=module-manager` with URL param cleanup
- FU-019 closed: TooltipProvider wrapping in 2 control_plane tests + assertion drift fix

**SP-3B — dnd-kit drag-to-reorder Active tab** — merged at `daca21a`
- Packages: `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities` (no modifiers)
- Mouse drag wired via `DndContext` + `SortableContext` + `useSortable`
- Persists reorder via `moduleOrder.reorder()`; localStorage round-trips correctly
- DragOverlay with `shadow-lg`, `ring-1 ring-border/50`, `scale-[1.02]`, `bg-card`
- Drop indicator: `border-t-2 border-[#185FA5]` thin blue line at insertion point
- Keyboard a11y: `KeyboardSensor` + `sortableKeyboardCoordinates`, focusable drag handle, custom screen-reader announcements naming the module

**SP-3C — Auditor sidebar filtering + read-only badge** — merged at `6b0f7eb`
- `writesRequired?: boolean` annotation on `NavItem` interface; 7 items annotated (period-close, approvals, org-settings, connectors, modules, billing, team-rbac)
- `isTenantViewer(role)` helper exported from `frontend/lib/ui-access.ts`
- Sidebar post-filter step in `frontend/components/layout/Sidebar.tsx`
- Auditor visible items: Overview, Today's focus, Entities, Audit trail, Compliance
- "Read-only access" badge in expanded sidebar footer, neutral muted color (`bg-muted text-muted-foreground ring-border`); omitted in collapsed sidebar

### Phase 3 verification work

- Verification suite merged at `6eedd11` — 4 specs, 23 tests passing on chromium + Mobile Chrome, with helpers for mocking auditor session and module.manage permission
- Keyboard reorder verification merged at `0d37756` — closes the gap left by the original suite's substituted attribute-presence test (root cause was using `element.press()` instead of `element.focus() + page.keyboard.press()`, not a `@dnd-kit` KeyboardSensor incompatibility)
- Cleanup chore merged at `ed7eb29` — removed the now-redundant attribute-presence substitute test, updated `frontend/tests/e2e/phase3/README.md` to reflect actual coverage

---

## Repository state at handoff

### Origin
- `main` at the post-handoff merge HEAD (this doc's commit + merge)
- Tag `v4.6.0-phase3-complete` at the same commit
- Tag `v4.5.0-phase2-complete` still at `20985cf`

### Local
- `main` in sync with origin
- Working tree clean
- All chore and feat branches preserved per convention; only `main` is on origin

### Phase 3 branches preserved (local only)
- `chore/phase3-preflight` at `24658a7`
- `chore/phase3-oq-triage` at `38b50cc`
- `chore/sp-3a-module-manager` at `939afc2`
- `chore/sp-3b-dnd-kit` at `bc42fe9`
- `chore/sp-3c-auditor-sidebar` at `874924c`
- `chore/phase3-verification` at `6f24e69`
- `chore/phase3-keyboard-verification` at `7916af1`
- `chore/phase3-cleanup-substituted-test` at `265a0c5`
- `chore/phase3-close-handoff` at this doc's commit

Plus all branches preserved from prior phases.

### Build/lint/test state
- `next build` ✓ at every gate
- `next lint` ✓ at every gate
- `vitest run` 212/214 — 2 pre-existing FU-007 failures unchanged baseline
- E2E (Phase 3) — 23/23 passing on chromium + Mobile Chrome; webkit binary not installed locally (works in CI with `npx playwright install`)

---

## Known deferred items (folded into Phase 4+ windows)

| Item | Status | When/where |
|---|---|---|
| BE-002 — Promote consolidation + tax to top-level workspace tabs | ⏸ Filed pre-Phase-3, NOT yet executed | When ready, triggers SP-2E (frontend) and `MODULE_ICON_MAP` extension for consolidation/tax keys |
| `module.manage` backend ticket | ⏸ Still not drafted — pre-flight Section 5 sharpened the "frontend expects this shape" portion (see planning doc); ticket file at `docs/tickets/module-manage-permission.md` to be filed | Draft just-in-time before next sub-prompt that depends on it; until then, `+` button shows locked state for all users |
| `GET /api/v1/billing/module-pricing` backend ticket | ⏸ Not drafted; Premium tab renders zero-state until it lands | Draft alongside `module.manage` ticket, or whenever Premium tab moves from zero-state to functional |
| FU-005 (deprecated Zustand field removal) | ⏸ Pair with any Phase 4+ sub-prompt touching the same stores | ~30 min |
| FU-007 (Onboarding wizard test text mismatches) | ⏸ Polish window | Real ongoing follow-up |
| FU-008 (E2E spec mockSession sweep) | ⏸ Polish window — partially advanced by Phase 3's verification suite which uses the helper pattern | ~1-2h remaining |
| FU-009 (WebKit Playwright binary) | ⏸ Policy decision pending | "Do we test WebKit at all?" — not a Claude task |
| FU-014 (Vitest coverage thresholds) | ⏸ Post-launch / polish window | Low priority |
| TD-017 (`orgs.ts` endpoint duplication) | ⏸ Pair with any Phase 4+ work touching `lib/api/orgs.ts` or the orgs `PageClient.tsx` | Otherwise leave deferred |
| GitHub PAT in plaintext `.git/config` | ⏸ Local credential hygiene — not pushed, but stored in plaintext locally | Replace with credential helper or SSH remote at convenience |

---

## Known scope gap — auditor in-page write-button disabling

The locked design at `docs/audits/finqor-shell-audit-2026-04-24.md` (v2 line 160) implies "read-only audit portal behavior" beyond sidebar filtering — auditors should also see disabled action buttons on pages they can reach by direct URL. Phase 3 SP-3C explicitly scoped to sidebar filtering only per the Phase 3 task wording. **An auditor who navigates directly to e.g. `/settings/team` reaches the page** with full write-action UI — they cannot navigate there from the sidebar (filtered out), but URL-bar typing or bookmarks bypass the filter.

This is a Phase 6 scope item (RBAC + Portal Alignment). Recorded in SP-3C's Section 0 risk register and surfaced in this handoff so the next chat doesn't re-litigate.

---

## Working-style notes from Phase 3

These patterns earned their keep across SP-3A, SP-3B, and SP-3C. Carry forward.

1. **Pre-flight pass before any execution.** Phase 3 pre-flight surfaced 4 surprises (S-001, S-002, S-003, S-004) and produced 6 open questions that, once resolved, made SP-3A drafting straightforward. The OQ triage step between pre-flight and SP-3A was new this phase and worked well — separating "investigation" from "decisions" prevented decisions from being made by the agent under time pressure.

2. **Section 0 verification gate as the first commit on each implementation branch.** Continued from Phase 2. SP-3A's Section 0 absorbed FU-019; SP-3B's Section 0 confirmed the existing `moduleOrder` store API surface; SP-3C's Section 0 read the locked design auditor specification before any code was written. Section 0 STOPs caught at least one architectural call (SP-3C's "filter by id, not href" mitigation) that would have been hard to unwind later.

3. **Per-section commits on every multi-section sub-prompt.** No accumulated uncommitted work. SP-3A's 8 commits across 8 sections (plus FU-019 as Section 0) merged cleanly with no collisions.

4. **Sequential SP-3A → SP-3B → SP-3C — no `git worktree`.** This phase chose sequential execution over parallel. Worked fine; topology stayed clean. Worktree remains the right tool for genuinely parallel work; not every phase needs it.

5. **STOP-and-report on surprises.** SP-3B's Section 1 surfaced a Next.js incremental cache casing conflict on `Dialog.tsx` (resolved with `rm -rf .next`); SP-3C's Section 0 surfaced the placeholder href collision (mitigated with id-based annotation); SP-3A's Section 1 surfaced the bilateral `_WORKSPACE_DEFINITIONS` agreement that informed OQ-2's resolution. The STOP cadence let these surface before they became merge-time problems.

6. **Section commit messages must enumerate every file touched.** Calibrated mid-phase after SP-3A Section 7 silently absorbed two unanticipated test file modifications (legitimate, but undocumented in the section spec). All subsequent sections enumerated explicitly. **Carry this forward as the standard going into Phase 4.**

7. **Pre-push verification sweep at phase boundaries.** 8 checks (build, topology, secrets, untracked, tests, branches, tags, remote). Cost: ~5 min. Caught a worth-noting (not blocking) finding: GitHub PAT stored in plaintext `.git/config`. The sweep is the right gate before push.

8. **Working-style breach worth logging.** Phase 3's verification suite was merged to main without explicit "merge approved" — Section 2's STOP language was ambiguous enough that the agent acted on what it interpreted as a clear path. Functional outcome was fine, but the discipline matters. **Carry forward: every section that ends in a merge must explicitly STOP and wait for the user's "merge approved" message — no implicit "if all green, proceed" interpretation.** Future sub-prompts should make this gate language sharper.

9. **Drag-and-drop verification needs Playwright + screenshots, not unit tests.** SP-3B's verification couldn't be done with vitest alone — visual interactions need Playwright with screenshot capture. The original substitute test pattern (attribute-presence as a stand-in for live interaction) was suboptimal; the real fix was using the right Playwright API (`element.focus()` + `page.keyboard.press()` rather than `element.press()`). Captured in the cleanup commit; carry forward as a lesson for any future interaction-heavy sub-prompts.

10. **Calibrate prompt weight to risk weight.** Holds across Phase 3:
    - SP-3A (high-touch architectural): 9 sections, 3 STOPs
    - SP-3B (focused integration): 6 sections, 2 STOPs
    - SP-3C (small additive): 3 sections, 1 STOP
    - Pre-flight (read-only investigation): 8 sections, 3 STOPs
    - OQ triage (single decision-recording pass): 1 chore commit, 1 merge gate
    - Verification suite: 3 sections, 1 STOP

11. **TypeScript compilation is implicit in `next build` for this project.** No standalone `npm run typecheck` script exists. Continue using `next build && next lint` (typecheck implicit in build) at every gate. Carry-forward note from prior handoffs.

---

## What Phase 4 is

Phase 4 is **"Collapsed Rail polish"** per the locked roadmap. The collapsed sidebar (52px rail with avatar tooltip showing role) needs polish work — exact scope is in the locked design at `docs/audits/finqor-shell-audit-2026-04-24.md`. Phase 4 pre-flight should investigate:
- Current Collapsed Rail rendering quality vs locked design
- Tooltip behavior on the avatar and any other rail icons
- Any auditor-specific rail considerations (the SP-3C badge is omitted in collapsed mode; verify the tooltip carries the role information adequately)
- Module Manager + Module Tabs interaction with the collapsed rail (SP-3A's `+` button was added to ModuleTabs which is part of the topbar, not the rail — verify consistency)

**Phase 4 estimate per locked roadmap:** smaller than Phase 3, no backend dependencies, frontend-only.

---

## How to resume in the next chat

Paste this entire document at the top of the new chat with a one-line context request:

> "Resuming Finqor frontend at Phase 4 kickoff. Phase 3 close handoff above. main is at HEAD on origin/main, tagged v4.6.0-phase3-complete. Ready to start the Phase 4 pre-flight."

Recommended sequence:
1. New chat, paste handoff
2. Pre-flight pass for Phase 4 (read-only, ~2-3 hours estimated — Phase 4 is smaller than Phase 3)
3. Defer-or-fix decisions on any surprises
4. OQ triage if pre-flight surfaces decisions to make
5. Sub-prompts execute sequentially (or with worktree if parallelism is genuinely valuable for Phase 4 — likely not given the smaller scope)
6. Per-section commits, STOPs at architectural sections, defensive verification on every merge
7. Pre-push verification sweep at Phase 4 close
8. Push, tag `v4.7.0-phase4-complete`, file Phase 4 close handoff

The pattern from Phase 3 carries forward unchanged. The two adjustments worth baking in from Phase 3's lessons:
- **Section commit messages enumerate every file touched.** Always.
- **Merge gates are explicit. No interpretive "if green, proceed" by the agent.** Every merge waits for "merge approved."

Phase 3 closed cleanly. See you in Phase 4.
