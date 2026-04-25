---
id: FU-008
title: Resolve E2E test data dependencies (seed or stub)
opened: 2026-04-25
related_to: Phase 0 test gate (pre-existing)
status: open
---

# FU-008 — Resolve E2E test data dependencies (seed or stub)

## Problem

The Playwright E2E suite (`frontend/tests/e2e/`) requires a running dev server at `localhost:3010` and a seeded database with specific tenants, entities, and users. When run against a fresh environment (no server, no seed data), every test fails with either a network error or a redirect to the login/setup page.

This makes E2E tests non-deterministic in CI unless the environment is explicitly prepared. The current `package.json` `test:e2e` script does not start the dev server or run any seed step before Playwright.

## Attribution

Pre-existing. The E2E tests existed before `v4.1.0` and have never been wired into a self-contained CI pipeline.

## Fix

Choose one approach:

### Option A — API mocking via Playwright route interception (preferred)
- Add a `tests/e2e/fixtures/` directory with MSW or Playwright `route()` stubs for the backend API calls the E2E specs rely on.
- Eliminates the need for a real backend/seed entirely.

### Option B — Seed script + `webServer` config
- Add `webServer` to `playwright.config.ts` so Playwright starts and stops the dev server automatically.
- Add a `scripts/seed-e2e.ts` (or equivalent) that creates the required tenant/entity/user records before the suite runs.
- Run the seed script as a `globalSetup` in `playwright.config.ts`.

## Scope

- `frontend/playwright.config.ts` — add `webServer` or `globalSetup`
- `frontend/tests/e2e/fixtures/` — new directory for stubs/seed helpers
- Do NOT change any E2E spec files as part of this plumbing work

## Notes

Until this is resolved, E2E tests should be excluded from the standard `npm test` / `vitest` run (they already are, via vitest config). They should only be run explicitly with `npm run test:e2e` in a prepared environment.
