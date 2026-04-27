---
id: FU-007
title: Fix onboarding wizard test text mismatches
opened: 2026-04-25
related_to: Phase 0 test gate (pre-existing)
status: open
---

# FU-007 — Fix onboarding wizard test text mismatches

## Problem

`frontend/tests/unit/onboarding_wizard.test.tsx` fails with text-match errors. The test expects literal strings (e.g. step headings, button labels, progress indicators) that no longer match the rendered output of the current `OnboardingWizard` component.

This is a copy-drift failure: the component copy was updated after the test was written, and the two were never re-synced.

## Attribution

Pre-existing. Confirmed by `git log v4.1.0..HEAD -- frontend/tests/unit/onboarding_wizard.test.tsx`: the test file has not been touched by any Phase 0 sub-prompt.

## Fix

1. Run the test in isolation to get the current rendered output:
   ```
   npx vitest run tests/unit/onboarding_wizard.test.tsx
   ```
2. For each failing `getByText` / `findByText` assertion, update the expected string to match the current component copy.
3. Do not alter component behaviour — only update string literals in the test file.

## Scope

- `frontend/tests/unit/onboarding_wizard.test.tsx` — update string literals only
- Do NOT change any component under `frontend/components/onboarding/`

## Notes

If more than five strings have drifted, consider switching to a `data-testid` approach for step markers so future copy changes do not require test updates.

---

## Resolution

**Closed:** SP-5E (Phase 5), 2026-04-27
**Branch:** `chore/sp-5e-fu-cleanup`

Three assertions updated in `tests/unit/onboarding_wizard.test.tsx` (test-only changes, no component changes):

| Location | Old string | New string | Source |
|---|---|---|---|
| Line 321 | `/…module state\. module enablement remains unavailable in the setup intent contract/i` | `/review generated from backend-confirmed module state\./i` | `OnboardingWizard.tsx:211` — trailing clause removed from `moduleReviewMutation.onSuccess` text |
| Lines 334 + 409 | `/submitted to backend - pending backend confirmation/i` | `/submitted – pending backend confirmation/i` | `OnboardingWizard.tsx:247` — `uploadConfirmationLabel` ternary changed hyphen to U+2013 en dash and dropped "to backend" |

Vitest: 222/224 → 224/224. Verified twice with no flakiness.
