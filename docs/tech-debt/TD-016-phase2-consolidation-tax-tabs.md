# TD-016 — Phase 2 Consolidation + Tax Tab Architecture

**Status:** Open
**Filed:** 2026-04-26
**Source:** Phase 2 pre-flight surprise S-002 + open question OQ-2
**Pre-flight doc:** `docs/platform/phase2-preflight-2026-04-26.md` (commit 0880440)
**Severity:** Pre-launch decision required (not blocking Phase 2 close, but blocking final product surface)

## Summary

Phase 2 of the shell rebuild specified two deliverables that target a UI surface
that does not exist in the current backend workspace architecture:

- Deliverable 5 — Consolidation-aware tab disable (modules like Consolidation
  disable when not in "all entities" view; tooltip explains)
- Deliverable 6 — Tax/GST jurisdictional relabeling (entity country drives
  module label: GST vs VAT vs Sales Tax)

Both deliverables assumed standalone `consolidation` and `tax` workspace tabs.
The backend `_WORKSPACE_DEFINITIONS` has 7 tabs:

```
dashboard, erp, accounting, reconciliation, close, reports, settings
```

Consolidation lives as a `module_code` inside the `close` tab.
GST lives as a `module_code` inside the `accounting` tab.

## Why this is open

The locked design at `docs/audits/finqor-shell-audit-2026-04-24.md` was written
before the Phase 1 shell finalized its workspace tab structure. The deliverables
require a product/architecture decision before any implementation:

| Option | What it means | Cost | Trade-off |
|---|---|---|---|
| A — Promote tabs | Add `consolidation` and `tax` as top-level workspace tabs in `_WORKSPACE_DEFINITIONS`. Backend change + frontend. | Higher (backend ticket BE-002 + frontend SP-2E) | Cleanest user mental model; matches the locked design intent. |
| B — Keep nested, gate at module level | Apply consolidation-aware disable and tax relabeling at the `module_code` level inside `close` and `accounting`. | Lower (frontend only, smaller SP-2E scope) | Less prominent UX, but matches current backend topology. |
| C — Defer indefinitely | Ship Phase 2 without these deliverables. Revisit in Phase 3 or post-launch. | Zero now | Two locked-design deliverables remain unmet at Phase 2 close. |

## Pre-flight evidence

From `docs/platform/phase2-preflight-2026-04-26.md`:

**S-002 (verbatim from surprises register):**
> No standalone `consolidation` or `tax` workspace tab exists in `_WORKSPACE_DEFINITIONS`.
> Both deliverables 5 and 6 target tabs that don't exist. Requires either (a) new backend
> workspace entries or (b) redesign of what "disable consolidation" and "relabel tax" mean
> given the current 7-tab structure.

**OQ-2 (verbatim from open questions):**
> Given that there is no standalone `consolidation` or `tax/gst` workspace tab (they are
> sub-modules of `close` and `accounting` respectively), what is the intended behavior?
> Default assumption to unblock SP-2E partially: Option C (route-level in-page warning when
> navigating to consolidation with entity selected). Tab bar unchanged.

D2.6 and D2.7 in the decision log are both marked OPEN with this as root cause.

## What needs to happen to close TD-016

1. Product/architecture decision between options A, B, C
2. If A: file BE-002 backend ticket; draft SP-2E frontend prompt; estimate +2–3 dev-days
3. If B: draft SP-2E frontend prompt against the nested approach; estimate ~1 dev-day
4. If C: update the locked design doc to remove Deliverables 5 and 6, or reschedule them
   to a named later phase

## Owner

Pre-launch product/architecture review.

## Related

- Phase 2 pre-flight doc: `docs/platform/phase2-preflight-2026-04-26.md`
- Locked Phase 2 design: `docs/audits/finqor-shell-audit-2026-04-24.md` (Deliverables 5 and 6)
- Backend workspace definitions: `backend/financeops/platform/api/v1/control_plane.py:44–99`
