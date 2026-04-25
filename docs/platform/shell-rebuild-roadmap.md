# Shell Rebuild — Roadmap

> **Last updated:** 2026-04-25, after Phase 0 sub-prompts 0.1 (redo as v2), 0.2, 0.3 merged.
> **Authoritative source:** This file is the single source of truth for shell rebuild planning. Sub-prompt resolution log lives in `docs/audits/finqor-shell-audit-2026-04-24.md`.

---

## Executive summary

The pre-Phase-0 gap resolution surfaced one significant finding that reshapes the roadmap: **Phase 2 (Org + Entity Switching) is not a frontend-only phase.** It requires a backend schema migration (`user_org_memberships` table) that must ship before Phase 2 frontend work can begin.

Phase 0, Phase 1, and the rest of the phase structure are unchanged from the original plan. The schema migration runs in parallel with Phases 0 and 1.

---

## Current state

| Item | Status |
|---|---|
| `main` HEAD (latest merged) | `aa50a99` (sub-prompt 0.1 redo merge) |
| Tag | `v4.1.0` (pre-Phase-0 baseline) |
| Shell quick wins (QW-0 through QW-10) | ✅ Merged |
| Tier 1 a11y fixes | ✅ Merged |
| Audit register sync + coverage matrix + audit prompt | ✅ Committed and merged |
| Gap 1 (portal subdomain decision) | **Open** — product decision pending |
| Gap 2 (OrgSwitcher trace + schema check) | ✅ **Resolved** — see `docs/audits/gap2-orgswitcher-trace-2026-04-25.md` |
| Phase 0 sub-prompt 0.1 (workspaceStore, redo as v2) | ✅ Merged at `aa50a99` |
| Phase 0 sub-prompt 0.2 (query key factory) | ✅ Merged at `44a4678` |
| Phase 0 sub-prompt 0.3 (EntitySwitcher live) | ✅ Merged at `8b2e44b` |
| Phase 0 sub-prompt 0.4 (cleanup + phase exit gate) | 🔄 In progress |
| Backend prerequisite ticket (BE-001) | Captured in `docs/tickets/backend-user-org-memberships.md` |

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

### Phase 0 — Foundation

- **0.1** — Unified `workspaceStore` ✅ Merged at `aa50a99` (executed as v2 redo; original branch was authored locally but never merged; v2 closed completeness gaps including 18 component reads and 2 split-brain bugs)
- **0.2** — Query key convention via factory (23 domains, 194 call sites) ✅ Merged at `44a4678`
- **0.3** — EntitySwitcher wired to live `/api/v1/org-setup/entities` ✅ Merged at `8b2e44b`
- **0.4** — Cleanup, dark-mode verify, docs update, phase exit gate (test infra audit + full test run) 🔄 In progress

**Design choice locked in 0.1:** `workspaceStore.orgId` is modeled as a workspace setting, not an identity fact. This makes Phase 2's multi-org switching a data-source change rather than a structural refactor.

After Phase 0 completes → tag `v4.2.0-phase0-complete`, decide on push, continue.

### Phase 1 — Shell Skeleton (~5 dev-days, parallelizable)

Sidebar rebuild (220px, ACTIVE ENTITY label, groups), TopBar (48px, brand mark, FY chip), module tab bar (40px, 2px blue underline, icon+label), metadata sweep, landmark cleanup.

First user-visible phase. Runs after Phase 0 finishes. Gap 1 should be resolved before Phase 1 design review.

### Phase 2 — Org + Entity Switching (revised: ~7 frontend days + backend prerequisite)

**Backend prerequisite (parallel to Phases 0–1):**
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
1. Frontend: Phase 0 → Phase 1 (blocker-free, ~8 calendar days)
2. Backend: BE-001 migration (blocker-free, 6–10 dev-days)
3. Product: Gap 1 portal subdomain decision (blocker-free, should land before Phase 1 review)

If backend ships on the 6-day end of its estimate, it arrives at roughly the same time Phase 1 finishes — no Phase 2 idle time.

If backend ships on the 10-day end, Phase 2 starts ~2 days after Phase 1 finishes — minor idle time.

---

## Backend tickets queue

### Immediate (file today)

1. **BE-001 — `feat(schema): add user_org_memberships table + backfill`** — see `docs/tickets/backend-user-org-memberships.md`

### Phase 3 blocker (file now, needed in ~2 weeks)

2. **`feat(rbac): add module.manage permission`** — Phase 3 Module Manager cannot gate the `+` button without this

### Phase 5 blocker (file now, needed in ~3 weeks)

3. **`feat(api): GET /api/v1/search`** — Phase 5 command palette live search depends on this. Verify first whether the endpoint already exists in a different form.

---

## What to watch

- **Backend schema ticket slippage.** If BE-001 goes beyond 10 days, Phase 2 starts slipping. Weekly check-in with backend during Phases 0 and 1 is worth the overhead.
- **Gap 1 resolution.** If the portal subdomain decision takes more than 2 weeks, escalate. Phase 1 sidebar design can proceed on the Option B working assumption, but Phase 6 scope changes meaningfully if Option A or C is chosen.
- **Approach A vs Approach B for the identity migration.** The recommendation is Approach A now, Approach B as a follow-up. If backend pushes for Approach B upfront, that's an ~+4 day slip on the prereq — evaluate whether that's worth it versus shipping and iterating.

---

## Git artifacts

- Tag `v4.1.0` — pre-Phase-0 baseline
- Tag `v4.2.0-phase0-complete` — planned, after Phase 0 finishes
- Tag `v4.3.0-phase1-complete` — planned, after Phase 1 finishes
- Subsequent tags per phase

**Branch discipline:** sub-prompts produce short-lived feature branches that merge into `main` via `--no-ff` to preserve topology. Push cadence is at the user's discretion — current session has held all merges local since `v4.1.0`.

---

## Follow-ups in flight

| ID | Title | Related to |
|---|---|---|
| FU-001 | Refactor sync cache-busting sentinel | Sub-prompt 0.2 |
| FU-002 | Unify tenant-coa-accounts query keys | Sub-prompt 0.2 |
| FU-003 | Entity endpoint org-scoping for Phase 2 | Sub-prompt 0.3, Phase 2 |
| FU-004 | Address pre-existing lint warnings | Phase 0 |
| FU-005 | Remove deprecated fields from legacy stores | Sub-prompt 0.1 redo |

See `docs/follow-ups/INDEX.md` for current status.
