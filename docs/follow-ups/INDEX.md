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
| FU-004 | [Address pre-existing lint warnings](./FU-004-pre-existing-lint-warnings.md) | 2026-04-25 | Phase 0 |
| FU-005 | [Remove deprecated fields from legacy Zustand stores](./FU-005-legacy-store-cleanup.md) | 2026-04-25 | Phase 0 sub-prompt 0.1 redo |
| FU-006 | [Add useSession mock to OrgSwitcher unit tests (partially resolved 2026-04-25)](./FU-006-useSession-mock-incompleteness.md) | 2026-04-25 | Phase 0 test gate (pre-existing) |
| FU-007 | [Fix onboarding wizard test text mismatches](./FU-007-onboarding-wizard-text-mismatches.md) | 2026-04-25 | Phase 0 test gate (pre-existing) |
| FU-008 | [Resolve E2E test data dependencies (seed or stub)](./FU-008-e2e-data-dependencies.md) | 2026-04-25 | Phase 0 test gate (pre-existing) |
| FU-009 | [Install WebKit Playwright browser binary for Mobile Safari E2E](./FU-009-webkit-binary-missing.md) | 2026-04-25 | Phase 0 test gate (pre-existing) |
| FU-010 | [Control-plane test render harness incomplete](./FU-010-control-plane-test-render-harness.md) | 2026-04-25 | Pre-existing — unmasked by FU-006 |
| FU-011 | [TopBar Finqor brand mark + wordmark](./FU-011-topbar-brand-mark.md) | 2026-04-25 | Phase 1 sub-prompt 1.2 |
| FU-012 | [Sidebar behavioral wiring (badges, RBAC, real routes)](./FU-012-sidebar-behavioral-wiring.md) | 2026-04-25 | Phase 1 sub-prompt 1.1 |
| FU-013 | [Sidebar pinning decision](./FU-013-sidebar-pinning-decision.md) | 2026-04-25 | Phase 1 sub-prompt 1.1 |
| FU-014 | [Vitest coverage thresholds with measured baseline](./FU-014-vitest-coverage-thresholds.md) | 2026-04-25 | Tech-debt audit F1 |
| FU-015 | [Remaining writers of deprecated active_entity_id](./FU-015-remaining-active-entity-id-writers.md) | 2026-04-25 | Hotfix 1.1.5; extends FU-005 |
