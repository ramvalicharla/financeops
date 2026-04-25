---
id: FU-009
title: Install WebKit Playwright browser binary for Mobile Safari E2E
opened: 2026-04-25
related_to: Phase 0 test gate (pre-existing)
status: open
---

# FU-009 — Install WebKit Playwright browser binary for Mobile Safari E2E

## Problem

`playwright.config.ts` declares three projects: `chromium`, `Mobile Chrome`, and `Mobile Safari` (WebKit). The WebKit binary is not installed in this environment, so any E2E run targeting `Mobile Safari` fails immediately with:

```
Error: browserType.launch: Executable doesn't exist at /path/to/webkit
Hint: run `npx playwright install webkit`
```

Chromium and Mobile Chrome run fine; only WebKit is missing.

## Attribution

Pre-existing. WebKit was listed in the Playwright config before `v4.1.0`. No Phase 0 sub-prompt changed `playwright.config.ts`.

## Fix

### Local developer machines
```bash
npx playwright install webkit
```

### CI (GitHub Actions / Docker)
Add to the CI workflow before the E2E step:
```yaml
- run: npx playwright install webkit --with-deps
```

Or, if all browsers should be installed in one step:
```yaml
- run: npx playwright install --with-deps
```

## Scope

- CI workflow file (`.github/workflows/` or equivalent) — add install step
- Developer onboarding docs — note `npx playwright install webkit` as a one-time setup step
- Do NOT remove WebKit from `playwright.config.ts`

## Notes

If CI minutes are a concern, Mobile Safari coverage can be limited to a subset of critical-path specs by adding `grep` / `grepInvert` to the WebKit project config in `playwright.config.ts`.
