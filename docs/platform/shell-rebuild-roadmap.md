# Shell Rebuild — Roadmap

> **Last updated:** 2026-04-26, after Phase 1 exit gate (all sub-prompts 1.1–1.4 merged).
> **Authoritative source:** This file is the single source of truth for shell rebuild planning. Sub-prompt resolution log lives in `docs/audits/finqor-shell-audit-2026-04-24.md`.

---

## Executive summary

The pre-Phase-0 gap resolution surfaced one significant finding that reshapes the roadmap: **Phase 2 (Org + Entity Switching) is not a frontend-only phase.** It requires a backend schema migration (`user_org_memberships` table) that must ship before Phase 2 frontend work can begin.

**Phase 1 is now complete.** All 5 sub-prompts (1.1, 1.1.5, 1.2, 1.3, 1.4) have been merged. The shell skeleton — sidebar groups, TopBar 48px, module tabs 40px with icons, and route metadata — is in. Phase 2 is next; it is blocked by backend BE-001.

---

## Current state

| Item | Status |
|---|---|
| `main` HEAD (latest merged) | `19f37b3` (Phase 1.4 metadata sweep merge) |
| Tag | `v4.3.0-phase1-complete` |
| Shell quick wins (QW-0 through QW-10) | ✅ Merged |
| Tier 1 a11y fixes | ✅ Merged |
| Audit register sync + coverage matrix + audit prompt | ✅ Committed and merged |
| Gap 1 (portal subdomain decision) | **Open** — product decision pending |
| Gap 2 (OrgSwitcher trace + schema check) | ✅ **Resolved** — see `docs/audits/gap2-orgswitcher-trace-2026-04-25.md` |
| Phase 0 sub-prompt 0.1 (workspaceStore, redo as v2) | ✅ Merged at `aa50a99` |
| Phase 0 sub-prompt 0.2 (query key factory) | ✅ Merged at `44a4678` |
| Phase 0 sub-prompt 0.3 (EntitySwitcher live) | ✅ Merged at `8b2e44b` |
| Phase 0 sub-prompt 0.4 (cleanup + phase exit gate) | ✅ Closed implicitly — see note below |
| Phase 1 sub-prompt 1.1 (sidebar structural rebuild) | ✅ Merged at `6afac67` |
| Phase 1 sub-prompt 1.1.5 (hotfix: client entity-id read) | ✅ Merged at `73b725d` |
| Phase 1 sub-prompt 1.2 (TopBar verify + landmark sweep) | ✅ Merged at `4778e84` |
| Phase 1 sub-prompt 1.3 (ModuleTabs + icon registry) | ✅ Merged at `f3baabf` |
| Phase 1 sub-prompt 1.4 (route metadata sweep) | ✅ Merged at `19f37b3` |
| Backend prerequisite ticket (BE-001) | Captured in `docs/tickets/backend-user-org-memberships.md` |

> **Phase 0.4 note:** 0.4 cleanup tasks were absorbed into the Phase 1 tech-debt audit (2026-04-25) and exit-gate documentation. Phase 0 was tagged at `v4.2.0-phase0-complete` on the strength of 0.1–0.3 delivery; 0.4 as a discrete sub-prompt was never executed.

---

## Key findings from pre-Phase-0 work

### Gap 2 — OrgSwitcher is an admin impersonation tool, not a user switcher

The current `OrgSwitcher.tsx` only renders for `platform_owner` / `super_admin` and uses it to impersonate into any tenant in the system. It reaches `/api/v1/platform/admin/tenants/…` which is hard-guarded by admin-only middleware.

Phase 2's plan of "remove the role gate and expose to all users" was based on a misread — removing the gate would just produce immediate 403s on the backend. Phase 2 needs a different endpoint (`GET /api/v1/users/me/orgs`) that lists the logged-in user's memberships.

**Reusable plumbing from today's flow:** the Zustand `is_switched` flag and the Axios interceptor that swaps the Bearer token on switch are reusable as-is for the user-facing switcher. Only the data source and the endpoint change.

### Gap 2 (continued) — IamUser is single-org at the schema level

Four independent signals confirm that a user can belong to exactly one tenant today:

- Model docstring: "Belongs to exactly one tenant."
- Schema: single `tenant_id` FK, `nullable=False`
- JWT: always carries singular `tenant_id`
- Frontend types: `tenant_id: string` (not array)

Therefore a schema migration is prerequisite to any multi-org frontend work. See `docs/tickets/backend-user-org-memberships.md` (BE-001).

### Gap 1 — Portal subdomain decision still open

Whether to separate `app.finqor.ai`, `platform.finqor.ai`, and `partners.finqor.ai` is a product decision that affects Phase 1 sidebar design and Phase 6 portal separation. Not blocking Phase 0 or the immediate next sprint, but should be resolved before Phase 1 design review.

Working assumption (to unblock Phase 1 if no decision lands): **Option B** (single subdomain, role-based shell). This is the fastest path; easier to migrate from B→A later than the opposite direction.

---

## Phase plan

### Pre-Phase-0 — done

- Quick wins merged ✅
- Tier 1 a11y merged ✅
- Audit register sync + docs merged ✅
- Gap 2 resolved ✅
- `v4.1.0` tagged ✅

### Phase 0 — Foundation — COMPLETE ✅

- **0.1** — Unified `workspaceStore` ✅ Merged at `aa50a99` (executed as v2 redo; original branch was authored locally but never merged; v2 closed completeness gaps including 18 component reads and 2 split-brain bugs)
- **0.2** — Query key convention via factory (23 domains, 194 call sites) ✅ Merged at `44a4678`
- **0.3** — EntitySwitcher wired to live `/api/v1/org-setup/entities` ✅ Merged at `8b2e44b`
- **0.4** — ✅ Closed implicitly. Cleanup tasks absorbed into Phase 1 audit + exit-gate documentation. See note under "Current state."

**Tag:** `v4.2.0-phase0-complete`

**Design choice locked in 0.1:** `workspaceStore.orgId` is modeled as a workspace setting, not an identity fact. This makes Phase 2's multi-org switching a data-source change rather than a structural refactor.

### Phase 1 — Shell Skeleton — COMPLETE ✅

Sidebar rebuild (220px, ACTIVE ENTITY label, groups), TopBar (48px, FY chip), module tab bar (40px, 2px blue underline, icon+label), metadata sweep.

- **1.1** — Sidebar structural rebuild (220px, three nav groups, nav-config) ✅ Merged at `6afac67`
- **1.1.5** — Hotfix: API client reads entityId from workspaceStore instead of deprecated `tenantStore.active_entity_id` ✅ Merged at `73b725d` (pre-onboarding fix from tech-debt audit F5)
- **1.2** — TopBar verification + landmark sweep + FU-011/FU-012/FU-013 filed ✅ Merged at `4778e84`
- **1.3** — ModuleTabs 40px container + module icon registry (7 backend workspace_keys) ✅ Merged at `f3baabf`
- **1.4** — Route metadata sweep — 4 pages updated, 2 parallel-route intercepts documented ✅ Merged at `19f37b3`

**Tag:** `v4.3.0-phase1-complete`

**Phase 1 totals:** 15 commits, 43 files changed, 4 102 insertions, 310 deletions vs Phase 0 tag.

### Phase 2 — Org + Entity Switching (next — blocked by BE-001)

**Phase 1 is complete. Phase 2 is next. Backend BE-001 (user_org_memberships table) blocks Phase 2 frontend work.**

**Backend prerequisite (parallel to Phases 0–1, now overdue):**
- Ticket: BE-001 — `feat(schema): add user_org_memberships table + backfill`
- Estimate: 6–10 dev-days
- Must ship before Phase 2 frontend begins

**Phase 2 frontend (once backend prereq ships):**
- OrgSwitcher for all users (data source: new `/api/v1/users/me/orgs` endpoint)
- Entity card as picker with tree view
- EntityScopeBar conditional component
- Entity tree in sidebar
- Consolidation tab disable logic on single-entity scope
- Tax/GST jurisdictional relabeling
- Entity indicator chip on collapsed rail
- Currency from entity functional currency

**FU-003 dependency:** entity endpoint org-scoping. Current endpoint is JWT-scoped; multi-org switching needs either an `orgId` path parameter on the endpoint or JWT rotation on switch.

### Phases 3–6 — unchanged from original plan

- Phase 3 — Module System (~10 days, parallelizable)
- Phase 4 — Collapsed Rail (~3 days, parallelizable after Phase 1)
- Phase 5 — Global UX Polish (~4 days, parallelizable)
- Phase 6 — RBAC + Portal Alignment (~3 days, parallelizable after Phases 2 + 3)

Note: Phase 6 scope expands slightly if Gap 1 resolves to Option A or C (full portal separation).

---

## Critical path and parallelization

```
Now    Phase 0    Phase 1    Phase 2    Phase 3    Phase 4    Phase 5    Phase 6
 │       │          │          │          │          │          │          │
 └─┬─────┘          │          │          │          │          │          │
   └────────────────┘          │          │          │          │          │
   │                           │          │          │          │          │
   │ Backend BE-001 ────────────┘          │          │          │          │
   │ (user_org_memberships)                │          │          │          │
   │                                       │          │          │          │
                                           └──────────┘
                                                      └─── parallelize where possible ───
```

**Critical path:** backend BE-001 → Phase 2 → Phase 6

**Immediate parallel tracks:**
1. Frontend: Phase 2 (blocked by BE-001), Phase 3 can begin in parallel
2. Backend: BE-001 migration — status unknown; check with backend team
3. Product: Gap 1 portal subdomain decision — still open

---

## Backend tickets queue

### Immediate (now overdue — Phase 2 is blocked)

1. **BE-001 — `feat(schema): add user_org_memberships table + backfill`** — see `docs/tickets/backend-user-org-memberships.md`

### Phase 3 blocker (file now, needed in ~2 weeks)

2. **`feat(rbac): add module.manage permission`** — Phase 3 Module Manager cannot gate the `+` button without this

### Phase 5 blocker (file now, needed in ~3 weeks)

3. **`feat(api): GET /api/v1/search`** — Phase 5 command palette live search depends on this. Verify first whether the endpoint already exists in a different form.

---

## What to watch

- **Backend schema ticket slippage.** BE-001 is now the active critical-path blocker. Phase 2 cannot begin without it. Weekly check-in with backend is essential.
- **Gap 1 resolution.** If the portal subdomain decision takes more than 2 weeks, escalate. Phase 6 scope changes meaningfully if Option A or C is chosen.
- **FU-015 write-side cleanup.** 6 remaining writers of deprecated `tenantStore.active_entity_id` tracked in FU-015. The read-side (client.ts) was fixed in hotfix 1.1.5; the writes don't break behavior today but should be cleaned before Phase 2 multi-entity work begins.

---

## Git artifacts

- Tag `v4.1.0` — pre-Phase-0 baseline
- Tag `v4.2.0-phase0-complete` — Phase 0 complete
- Tag `v4.3.0-phase1-complete` — Phase 1 complete ✅
- Tag `v4.4.0-phase2-complete` — planned, after Phase 2 finishes
- Subsequent tags per phase

**Branch discipline:** sub-prompts produce short-lived feature branches that merge into `main` via `--no-ff` to preserve topology. Push cadence is at the user's discretion.

---

## Follow-ups in flight

| ID | Title | Related to |
|---|---|---|
| FU-001 | Refactor sync cache-busting sentinel | Sub-prompt 0.2 |
| FU-002 | Unify tenant-coa-accounts query keys | Sub-prompt 0.2 |
| FU-003 | Entity endpoint org-scoping for Phase 2 | Sub-prompt 0.3, Phase 2 |
| FU-004 | Address pre-existing lint warnings | Phase 0 |
| FU-005 | Remove deprecated fields from legacy stores | Sub-prompt 0.1 redo |
| FU-006 | Add useSession mock to OrgSwitcher unit tests | Phase 0 test gate (pre-existing) |
| FU-007 | Fix onboarding wizard test text mismatches | Phase 0 test gate (pre-existing) |
| FU-008 | Resolve E2E test data dependencies | Phase 0 test gate (pre-existing) |
| FU-009 | Install WebKit Playwright browser binary | Phase 0 test gate (pre-existing) |
| FU-010 | Control-plane test render harness incomplete | Pre-existing, unmasked by FU-006 |
| FU-011 | TopBar Finqor brand mark + wordmark | Phase 1 sub-prompt 1.2 |
| FU-012 | Sidebar behavioral wiring (badges, RBAC, real routes) | Phase 1 sub-prompt 1.1 |
| FU-013 | Sidebar pinning decision | Phase 1 sub-prompt 1.1 |
| FU-014 | Vitest coverage thresholds with measured baseline | Tech-debt audit F1 |
| FU-015 | Remaining writers of deprecated active_entity_id | Hotfix 1.1.5; extends FU-005 |

See `docs/follow-ups/INDEX.md` for full details.
