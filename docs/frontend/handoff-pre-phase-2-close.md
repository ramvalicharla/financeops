# Finqor Frontend — Handoff Summary (Pre-Phase-2 Close)

**Date:** 2026-04-26 (Pre-Phase-2 close)
**Stack:** Next.js 14, TypeScript, Tailwind, shadcn/ui, TanStack Query, Zustand, dark mode only
**Working style:** Solo engineer, Claude Code agents (parallel where files disjoint), branch-per-task, `--no-ff` merges
**Latest push:** main at `14cb364` on origin, 22 commits pushed in synchronized batch
**Recommended tag:** `v4.4.0-pre-phase2-complete` on `14cb364` (tag prompt drafted, may already be applied by the time you read this)

---

## Phase status overview

| Phase | Status | Tag | What it delivered |
|---|---|---|---|
| Pre-Phase-0 | ✅ Complete | `v4.1.0` | Quick wins (QW-0 through QW-10), Tier 1 a11y, audit register sync |
| Phase 0 | ✅ Complete | `v4.2.0-phase0-complete` | Foundation: workspaceStore, query key factory, EntitySwitcher live |
| Phase 1 | ✅ Complete | `v4.3.0-phase1-complete` + `v4.3.1` | Shell skeleton + IA-correct routes |
| **Pre-Phase-2** | **✅ Complete** | **`v4.4.0-pre-phase2-complete`** (proposed) | **Sprint 1 (5 frontend FUs) + BE-001 (3 backend checkpoints)** |
| Phase 2 | ⏸ Ready to start | — | Org + Entity Switching (frontend) |
| Phase 3 | ⏸ Queued | — | Module System (with Module Manager) |
| Phase 4 | ⏸ Queued | — | Collapsed Rail polish |
| Phase 5 | ⏸ Queued | — | Global UX Polish (CommandPalette live search) |
| Phase 6 | ⏸ Queued | — | RBAC + Portal Alignment |

---

## Pre-Phase-2 — what was delivered

### Lane A — Planning (3 commits, all on `8fa957b` and `3170898`)

| Item | Status | Output |
|---|---|---|
| Lane A.1 — BE-001 pre-flight | ✅ Complete | FU-003 decided (Option B — JWT rotation), BE-001 ticket schema bug fixed (`org_id/orgs` → `tenant_id/iam_tenants`), test plan + rollout plan added |
| Lane A.2 — FU-016 backend dependency | ✅ Complete | Scenario X confirmed — 6 user-management endpoints fully exist; FU-016 is frontend-only |
| Section 0 gate addition | ✅ Complete | Pre-implementation investigation gate added to BE-001 ticket |

### Sprint 1 — Frontend FUs (5 of 5 merged)

| ID | Item | Branch tip | Merged via |
|---|---|---|---|
| FU-011 | TopBar Finqor brand mark + wordmark | `d28c5ba` | `d5e778d` |
| FU-015 | Remove deprecated `active_entity_id` writers | `d87724e` | `d99391a` |
| FU-001 | Sync cache-busting sentinel removed | `8748056` | `8935fe2` |
| FU-002 | Tenant-coa-accounts keys (Outcome B — documented isolation) | `3773a27` | `8935fe2` |
| FU-004 | Pre-existing lint warnings (11 resolved, 0 remaining) | `8a8eb1e` | `3fe129d` |
| FU-016 | Real user management on `/settings/team` Users tab | `b368ac2` | `c1024e4` |

### Sprint 3 — BE-001 (complete, 3 checkpoints + amendment + gate report)

| Stage | Branch tip | Merged via |
|---|---|---|
| Section 0 investigation gate report | `10630df` | `e801baa` (with CP1) |
| Checkpoint 1 — `UserOrgMembership` model + alembic 0145 + 6 unit tests | `030cf83` | `e801baa` |
| Ticket amendment §4.3 (auth path for switch tokens) | `c763526` (cherry-picked from orphan after between-session reset) | direct on main |
| Checkpoint 2 — `GET /api/v1/users/me/orgs` + 4 integration tests | `62fc8a7` | `f3843f1` |
| Checkpoint 3 — `POST /switch` endpoint + `deps.py:281` amendment + 7 integration tests + 3 unit tests | `7f24cdd` | `833e675` |

**BE-001 final state:** 20 new tests (model unit, deps unit, list integration, switch integration), all passing. 1 pre-existing failure (`test_list_user_tenants_returns_only_accessible_tenants`) confirmed unrelated and unchanged.

### Doc-only commits

| Commit | Content |
|---|---|
| `8fa957b` | Lane A pre-flight complete (FU-003 decision, FU-016 clarification, BE-001 ticket lock) |
| `3170898` | Section 0 gate addition to BE-001 ticket |
| `c763526` | BE-001 ticket amendment §4.3 (auth path for switch tokens) |
| `14cb364` | FU-018 record filed (invite modal entity-fetch warning) |

---

## Sprint 2 — explicitly deferred

Sprint 2 was the conditional sprint per the original plan ("runs in parallel with BE-001 if frontend agent capacity allows"). Capacity went into Sprint 1 (which absorbed FU-016) and Sprint 3 verification. Sprint 2 deferred wholesale, intentionally.

| FU | Title | Why deferred |
|---|---|---|
| FU-006 | useSession mock in OrgSwitcher unit tests | Test infra; not user-visible |
| FU-007 | Onboarding wizard test text mismatches | Pre-existing baseline failure; not regression |
| FU-008 | E2E test data dependencies (seed/stub) | Test infra; needs scoping pass |
| FU-009 | WebKit Playwright browser binary | Test infra; cross-browser coverage |
| FU-010 | Control-plane test render harness | Pre-existing baseline failure; not regression |
| FU-013 | Sidebar pinning decision + impl | Decision needed; can land late |
| FU-014 | Vitest coverage thresholds with measured baseline | Quality gate; not pre-onboarding-visible |

These are genuinely good follow-ups but none block Phase 2.

---

## FU register — full state

| FU | Title | Status |
|---|---|---|
| FU-001 | Sync cache-busting sentinel refactor | ✅ Merged |
| FU-002 | Tenant-coa-accounts query keys | ✅ Closed Outcome B (documented isolation) |
| FU-003 | Entity endpoint org-scoping | ✅ Decided (Option B) |
| FU-004 | Pre-existing lint warnings | ✅ Merged |
| FU-005 | Remove deprecated fields from legacy Zustand stores | ⏸ Open (writers cleared by FU-015; field removal pending) |
| FU-006 | useSession mock in OrgSwitcher unit tests | ⏸ Sprint 2 deferred |
| FU-007 | Onboarding wizard test text mismatches | ⏸ Sprint 2 deferred |
| FU-008 | E2E test data dependencies | ⏸ Sprint 2 deferred |
| FU-009 | Install WebKit Playwright browser binary | ⏸ Sprint 2 deferred |
| FU-010 | Control-plane test render harness | ⏸ Sprint 2 deferred |
| FU-011 | TopBar Finqor brand mark + wordmark | ✅ Merged |
| FU-012 | Sidebar behavioral wiring (Approvals badge, RBAC, real routes) | ⏸ Open (Phase 2 backend dependent) |
| FU-013 | Sidebar pinning decision | ⏸ Sprint 2 deferred |
| FU-014 | Vitest coverage thresholds | ⏸ Sprint 2 deferred |
| FU-015 | Remaining writers of deprecated `active_entity_id` | ✅ Merged (writers cleared; field itself pending FU-005) |
| FU-016 | Real user management on `/settings/team` | ✅ Merged |
| FU-017 | (number gap by design — `org_admin` type drift folded into FU-016) | N/A |
| FU-018 | Invite modal entity-fetch warning | ✅ Filed; implementation queued |

---

## Repository state at handoff

### Origin
- `origin/main` at `14cb364`
- 22 commits pushed in this synchronized batch (the first push since `9ee4ff9`)

### Local-only branches (preserved for reference, not on origin)
- `feat/be001-user-org-memberships` at `7f24cdd`
- `feat/fu001-fu002-query-key-cleanup` at `3773a27`
- `feat/fu004-lint-warnings` at `8a8eb1e`
- `feat/fu011-brand-mark` at `d28c5ba`
- `feat/fu015-deprecated-field-cleanup` at `d87724e`
- `feat/fu016-user-management` at `b368ac2`

### Working tree
- Clean

---

## Backend tickets queued

| Ticket | Blocks | Estimate | Status |
|---|---|---|---|
| ~~BE-001~~ | ~~Phase 2~~ | ~~6–10 dev-days~~ | ✅ **Complete** — schema, two endpoints, deps.py amendment all on main |
| `feat(rbac): add module.manage permission` | Phase 3 | 1–2 dev-days | Not drafted yet (just-in-time) |
| `feat(api): GET /api/v1/search` (verify if exists) | Phase 5 | 1–5 dev-days | Not drafted yet (just-in-time) |

---

## What Phase 2 is

Phase 2 is **"Org + Entity Switching"** — the first phase where the shell becomes truly multi-tenant from the user's perspective. Now unblocked because BE-001 shipped.

Concrete deliverables (per the locked design at `docs/audits/finqor-shell-audit-2026-04-24.md`):

1. **OrgSwitcher repurposing.** Today's `OrgSwitcher.tsx` is a platform admin impersonation tool. Phase 2 either replaces or forks it into a user-facing switcher that lists the current user's actual org memberships via `GET /api/v1/users/me/orgs` (now live). The Zustand `is_switched` flag and Axios token-rotation interceptor are reusable.
2. **Entity card as picker with tree view** — Org → Entity → Module hierarchy made visual.
3. **EntityScopeBar** — conditional component below the module tab bar showing active entity scope; hidden in consolidated views.
4. **Entity tree in sidebar** — Workspace nav group's entity placeholders go live.
5. **Consolidation-aware tab disable** — modules like Consolidation disable when not in "all entities" view; tooltip explains.
6. **Tax/GST jurisdictional relabeling** — entity country drives tax-module label (GST vs VAT vs Sales Tax).
7. **Entity indicator chip on collapsed rail** — 52px collapsed sidebar shows active-entity chip since labels are hidden.
8. **Currency from entity functional currency** — numbers render in the active entity's functional currency.

**Phase 2 frontend estimate:** ~7 dev-days once planning is done.

---

## What's open / decisions deferred

**For Phase 2 itself:**
- Whether Phase 2 sub-prompts should be drafted in a Lane-A-shaped pre-flight pass first, or directly. (Recommended: pre-flight first, same shape as Lane A. The locked design + the now-merged BE-001 reality together produce a concrete planning input.)

**For after Phase 2 or independent:**
- **GitHub PAT rotation** — token in plaintext in `.git/config`, advisory from pre-push verification. Not blocking, but rotate within days. Switch remote to SSH or `gh auth login`.
- **Portal subdomain decision** (Gap 1 from past chat `99ba28dc`) — `app.finqor.ai` vs `platform.finqor.ai` vs `partners.finqor.ai`. Phase 0 unblocked itself with Option B (single subdomain, role-based). Not blocking Phase 2; expands Phase 6 if it lands on Option A or C.
- **Sprint 2 FUs** — 7 deferred items. Pickup window is between Phase 2 sub-prompts or as a polish sprint after Phase 2 lands.
- **FU-005 field removal** — full closure of audit finding F5. Small, can pair with any nearby store cleanup.
- **FU-018 implementation** — ~30 minutes, can land alongside any Phase 2 modal work.

---

## Working style notes that paid off (carry into Phase 2)

These are the patterns that produced clean, mergeable work across this session. Worth keeping deliberate in Phase 2:

1. **Lane-A-shaped planning pass before any execution.** Pre-flight reads, identifies surprises, locks the spec. Cost: a few hours. Benefit: caught the BE-001 ticket schema bug (`org_id/orgs` → `tenant_id/iam_tenants`) before 6-10 dev-days of execution against a stale spec.

2. **Investigation gate as the first commit on the implementation branch.** Section 0 gate caught the scope claim handling and `create_access_token` signature questions cleanly. It did NOT catch the `tenant_id` consistency check — that surfaced during Checkpoint 2 integration. The gate isn't omniscient, but it's cheap insurance against the predictable category of misses.

3. **Checkpoint discipline.** BE-001 was structured as 3 checkpoints, each independently mergeable. This matters because:
   - Each piece got reviewed against main rather than accumulating risk
   - The Checkpoint 2 finding (`tenant_id` consistency) was caught and handled in a ticket amendment before Checkpoint 3 began
   - Long-pole work didn't sit unmerged for the full duration

4. **One agent task = one branch = one merge gate, with `--no-ff` merges.** Topology stayed readable in `git log --graph` across all 11 lanes (Lane A, FU-011, FU-015, FU-001+FU-002, FU-004, FU-016, BE-001 CP1/CP2/CP3, amendment, FU-018).

5. **Parallel agents only on file-disjoint work.** Frontend FUs ran alongside BE-001 backend with zero conflict. Two frontend FUs touching overlapping files were serialized.

6. **Hard rules in every prompt:** STOP-and-report at >10% scope deviation, branch verification at pre-flight, NO PUSH everywhere except the deliberate close gate. These caught the between-session reset on the BE-001 amendment commit and the FU-016 stash conflict cleanly.

7. **Pre-push verification as a read-only sweep.** Cost: 5-10 minutes. Benefit: definitive PROCEED verdict before pushing 22 commits. Found one advisory (PAT exposure) but cleared all 8 substantive checks.

---

## Surprises and how they were handled

Worth carrying into the new chat as institutional memory:

1. **The amendment commit got orphaned by a between-session `git reset`.** Recovered cleanly via `git cherry-pick` of the orphan onto main. New hash `c763526`. Lesson: pre-flight `git status` + `git log -1` checks are not optional. Keep them in every prompt.

2. **FU-004 stash conflict with FU-016 in-flight.** Multiple parallel Claude Code sessions sharing one filesystem can collide on uncommitted working-tree changes. The agents handled this correctly (stash, merge, restore) but the report wording about "backend changes already in flight" was initially misleading and required a verification prompt to confirm the FU-016 commit was actually clean. Lesson: parallel sessions are productive but need the `git status` checks at pre-flight to be honest about what's in the working tree.

3. **Checkpoint 2 surfaced a real architectural question** that the Section 0 gate didn't anticipate (`tenant_id` consistency check). This was a fair miss at the planning stage — the gate was scoped to scope-claim handling and `create_access_token` signature. The amendment process worked: Checkpoint 2 stopped, ticket amended, Checkpoint 3 implemented against the amended spec. Lesson: gates catch what they're scoped to catch. Plan to amend in flight rather than try to predict every axis upfront.

4. **FU-002 turned out to be Outcome B (documented isolation)** rather than the expected Outcome A (key unification). The 4 distinct key prefixes were intentionally different by cache lifecycle. Lesson: trust the agent's evidence-gathering — sometimes the FU record's expected outcome is wrong, and the right move is documentation rather than refactor.

5. **The PAT in `.git/config`** showed up in pre-push verification output. Not exposed externally but treated as advisory. Lesson: pre-push verification with a heuristic secret scan is worth the 5-10 minutes.

---

## How to resume in the new chat

Paste this entire document at the top of the new chat with a one-line context request like:

> "Resuming Finqor frontend work at pre-Phase-2 close. Handoff doc above. Where do you think we should start for Phase 2?"

That's enough to re-establish context. The Phase 2 work begins with a Lane-A-shaped planning pass before any sub-prompts get drafted.

The pattern that worked across Phase 0, Phase 1, and pre-Phase-2:

1. New chat, paste handoff
2. Ask for recommendation up front (don't ask Claude to do too much in turn 1)
3. Pre-flight before execution
4. Sub-prompts that produce one branch + one merge gate each
5. Internal STOP-and-report on surprises
6. `--no-ff` merges, push only at phase boundaries

Phase 2 should follow the same shape.
