# Follow-ups Index

Deferred work captured during phased implementation. Each entry is a self-contained scope that was intentionally left out of the originating PR to preserve that PR's discipline (one concern per PR, exact preservation rules, etc.).

When picking up a follow-up:

1. Read the linked detail file.
2. Create a new branch from `main`.
3. Scope the work exactly as described.
4. Do not expand scope without updating this index first.

## Open follow-ups

| ID | Title | Opened | Related to |
|---|---|---|---|
| FU-001 | [Refactor sync cache-busting sentinel](./FU-001-refactor-sync-cache-busting.md) | 2026-04-25 | Phase 0 sub-prompt 0.2 |
| FU-002 | [Unify tenant-coa-accounts query keys](./FU-002-refactor-coa-tenant-accounts.md) | 2026-04-25 | Phase 0 sub-prompt 0.2 |
| FU-003 | [Add org-scoped entity endpoint for Phase 2](./FU-003-entity-endpoint-org-scoping.md) | 2026-04-25 | Phase 0 sub-prompt 0.3 |
| FU-005 | [Remove deprecated fields from legacy Zustand stores](./FU-005-legacy-store-cleanup.md) | 2026-04-25 | Phase 0 sub-prompt 0.1 redo |
| FU-008 | [Audit and fix remaining E2E specs for mockSession coverage](./FU-008-e2e-data-dependencies.md) | 2026-04-25 | Phase 0 test gate (pre-existing) — webServer + helpers/mocks.ts infrastructure shipped pre-Phase-2; remaining work is verification sweep across 14 specs, ~1–2 hours |
| FU-009 | [Install WebKit Playwright browser binary for Mobile Safari E2E](./FU-009-webkit-binary-missing.md) | 2026-04-25 | Phase 0 test gate (pre-existing) |
| FU-012 | [Sidebar behavioral wiring (badges, RBAC, real routes)](./FU-012-sidebar-behavioral-wiring.md) | 2026-04-25 | Phase 1 sub-prompt 1.1 |
| FU-014 | [Vitest coverage thresholds with measured baseline](./FU-014-vitest-coverage-thresholds.md) | 2026-04-25 | Tech-debt audit F1 |
| FU-015 | [Remaining writers of deprecated active_entity_id](./FU-015-remaining-active-entity-id-writers.md) | 2026-04-25 | Hotfix 1.1.5; extends FU-005 |
| FU-016 | [Real user management implementation](./FU-016-real-user-management-implementation.md) | 2026-04-26 | Phase 1 sub-prompt 1.6.3 |
| FU-020 | [Complete loading.tsx skeleton coverage + EmptyState unification](./FU-020-skeleton-and-emptystate-coverage-completion.md) | 2026-04-27 | SP-5C — 86 deferred loading routes + bespoke EmptyState pattern unification |

## Merged follow-ups

| ID | Title | Opened | Merged | Branch |
|---|---|---|---|---|
| FU-007 | [Fix onboarding wizard test text mismatches](./FU-007-onboarding-wizard-text-mismatches.md) | 2026-04-25 | 2026-04-27 | chore/sp-5e-fu-cleanup |
| FU-018 | [Invite modal: soft warning when entity fetch fails](./FU-018-invite-modal-entity-fetch-warning.md) | 2026-04-26 | b0161e5 (2026-04-26) | feat/sp-2f-fu018-invite-modal |

## Closed follow-ups

| ID | Title | Opened | Closed | Reason |
|---|---|---|---|---|
| FU-006 | [Add useSession mock to OrgSwitcher unit tests](./FU-006-useSession-mock-incompleteness.md) | 2026-04-25 | 2026-04-26 | Resolved by SP-2A — OrgSwitcher rewritten (fffc242), merged via 3a972f7; useSession import removed; failing test file no longer exists |
| FU-010 | [Control-plane test render harness incomplete](./FU-010-control-plane-test-render-harness.md) | 2026-04-25 | 2026-04-26 | Superseded by FU-019 — FU-019 documents the concrete control_plane test failures (TooltipProvider missing in panels and shell, stale assertion in state) |
| FU-004 | [Address pre-existing lint warnings](./FU-004-pre-existing-lint-warnings.md) | 2026-04-25 | 2026-04-27 | Silently resolved in or before Phase 0.4; `npm run lint` 0/0 on main; paperwork closed SP-5E |
| FU-013 | [Sidebar pinning decision](./FU-013-sidebar-pinning-decision.md) | 2026-04-25 | 2026-04-26 | Wontfix — Option 3 (no pinning) selected; three-group sidebar with entity tree (SP-2B) sufficient; not in locked design; nav-config.ts FU-013 comment already removed in Phase 1 |
| FU-019 | [control_plane_*.test.tsx pre-existing failures](./FU-019-control-plane-test-preexisting-failures.md) | 2026-04-26 | 2026-04-27 | Silently resolved between Phase 2 close and Phase 5 entry; all 7 tests passing; paperwork closed SP-5E |
| FU-011 | [TopBar Finqor brand mark + wordmark](./FU-011-topbar-brand-mark.md) | 2026-04-25 | 2026-04-27 | Silently implemented in d28c5ba before Phase 5; BrandMark component + Topbar mounts verified green; paperwork closed SP-5D |
