---
# FU-014 — Vitest coverage thresholds with measured baseline

**Opened:** 2026-04-25
**Related to:** Frontend tech-debt audit 2026-04-25 finding F1
**Severity at audit:** Major

## Background

Tech-debt audit 2026-04-25 finding F1 identified that `vitest.config.ts` has a
`test:coverage` script but no `coverage` block, no thresholds, and no provider
configured. Coverage runs produce per-file line counts but enforce nothing.

The audit recommended setting thresholds (suggested: statements 40%, branches
35%, lines 40%) as a hotfix. We deferred this to a follow-up because:

1. Setting thresholds without measuring current coverage is theatre. With
   component test colocation at 4% (F2), naive 40% thresholds would fail CI
   immediately.

2. Setting thresholds low enough to pass today (likely 5–10%) encodes
   current weakness as the floor and provides no regression protection.

3. The right path is: measure, decide thresholds slightly below current
   measured baseline, then ratchet upward as more tests land.

## Scope

1. Run `npm run test:coverage` once on main and capture the baseline:
   - statements %
   - branches %
   - functions %
   - lines %
   - per-package breakdown if useful

2. Choose thresholds 2–5 percentage points below current. The intent is "do
   not regress," not "raise the bar by fiat."

3. Add to `vitest.config.ts`:
   ```ts
   test: {
     coverage: {
       provider: 'v8',  // or 'istanbul' — check what's installed
       reporter: ['text', 'html', 'lcov'],
       thresholds: {
         statements: <baseline - 3>,
         branches: <baseline - 3>,
         functions: <baseline - 3>,
         lines: <baseline - 3>,
       },
       exclude: [
         'node_modules/',
         '.next/',
         '**/*.config.*',
         '**/*.d.ts',
         'tests/e2e/**',
       ],
     },
   }
   ```

4. Verify CI runs the coverage step (or add it to CI if missing).

5. Document the ratchet plan: after each phase exit, raise thresholds by
   ~5 percentage points if current coverage exceeds the floor by that much.

## Acceptance criteria

- [ ] Coverage baseline measured and recorded in commit body
- [ ] Thresholds set 2–5 points below baseline
- [ ] `npm run test:coverage` passes
- [ ] CI fails on a manufactured regression test
- [ ] Ratchet plan documented in repo README or here

## Out of scope

- Increasing coverage itself. F2 (4% component colocation) is a separate,
  larger problem. This FU is purely about preventing silent regression.

## Estimate

2–3 hours. Mostly the measurement + decision; the config change is small.
