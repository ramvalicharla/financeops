# TD-018 — Pre-Launch Workspace Tab Architecture Review

**Status:** Open — pre-launch decision required
**Filed:** 2026-04-26
**Source:** Phase 2 close → TD-016 resolution conversation (2026-04-26)
**Severity:** Pre-launch architectural decision (not blocking Phase 3, but blocking final product surface)
**Pairs with:** BE-002 (consolidation + tax tab promotion)

## Summary

The current backend `_WORKSPACE_DEFINITIONS` has 7 top-level workspace tabs:

```
dashboard, erp, accounting, reconciliation, close, reports, settings
```

TD-016 resolution promotes consolidation and tax to top-level tabs
(Option A), bringing the total to 9. During the TD-016 conversation,
several other capabilities were raised as candidates for top-level tab
promotion. This TD captures the broader question for pre-launch resolution.

## Candidate capabilities for top-level tab promotion

The following are currently modules within other tabs (or not yet implemented).
The pre-launch review should decide which, if any, deserve top-level tab status:

| Capability | Currently lives in | Candidate for top-level? |
|---|---|---|
| Prepaid | accounting | Open question |
| Fixed Assets | accounting | Open question |
| GL Reconciliation | reconciliation | Open question |
| Bank Reconciliation | reconciliation | Open question |
| Payroll | varies — module under accounting in some configurations | Open question |
| AP (Accounts Payable) | accounting | Open question |
| AR (Accounts Receivable) | accounting | Open question |
| MIS | reports or close (jurisdiction-dependent) | Open question |
| Consolidation | TD-016 → being promoted via BE-002 | Decided: Yes (Option A) |
| Tax / GST / VAT | TD-016 → being promoted via BE-002 | Decided: Yes (Option A) |

## Why this is open

**Tab count vs UX.** Horizontal tab navigation patterns degrade past
roughly 7–8 items. Promoting all candidates above would push the tab
count to 16+. That likely requires either a navigation redesign
(sidebar-grouped, left-rail-of-modules pattern) or selective promotion.

**User mental model.** Each capability promotion is a product judgment
about "is this a first-class capability or a sub-mode of an existing one?"

**Backend migration cost.** Each batch of `_WORKSPACE_DEFINITIONS`
changes is a backend ticket + migration. Bundling the decisions into
one combined ticket is significantly cheaper than serial decisions.

## Resolution path

The pre-launch review should produce:

1. A final list of capabilities that become top-level workspace tabs
2. A combined backend ticket (or expansion of BE-002) that updates
   `_WORKSPACE_DEFINITIONS` with the chosen final tab set
3. UX confirmation that the resulting tab count is renderable in the
   current navigation pattern (or a navigation redesign decision)

If the review decides additional promotions, BE-002's scope can expand
to include them rather than filing separate tickets — provided the review
lands before BE-002 is executed.

## Cross-references

- TD-016 (consolidation + tax — Option A resolved): `docs/tech-debt/TD-016-phase2-consolidation-tax-tabs.md`
- BE-002 (immediate backend execution): `docs/tickets/backend-promote-consolidation-tax-tabs.md`
- Locked design: `docs/audits/finqor-shell-audit-2026-04-24.md`
- Phase 2 pre-flight (where the workspace tab structure was first verified):
  `docs/platform/phase2-preflight-2026-04-26.md`
