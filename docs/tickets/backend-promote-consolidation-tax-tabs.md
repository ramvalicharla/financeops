# BE-002 — Promote consolidation and tax to top-level workspace tabs

**Type:** Backend feature
**Priority:** High (blocks SP-2E)
**Estimate:** 1–2 dev-days (subject to entity-model verification finding)
**Filed:** 2026-04-26
**Source:** TD-016 resolution (Option A)
**Blocks:** SP-2E (frontend sub-prompt — drafted during Phase 3)

## Background

TD-016 resolved as Option A: promote `consolidation` and `tax` to top-level
workspace tabs in the backend `_WORKSPACE_DEFINITIONS`. This ticket implements
that promotion plus the entity-model attribute verification needed for the
sharpened consolidation gating rule.

See `docs/tech-debt/TD-016-phase2-consolidation-tax-tabs.md` for full context
and rationale.

## Acceptance criteria

### 1. Promote tabs in `_WORKSPACE_DEFINITIONS`

Add `consolidation` and `tax` as top-level tabs in the backend workspace
definitions. The current 7 tabs become 9:

```
dashboard, erp, accounting, reconciliation, close, consolidation, reports, tax, settings
```

(Final ordering subject to product/UX call. Listed here for completeness.)

### 2. Migrate existing module assignments

Any module currently registered under `close` with a consolidation-related
`module_code` should be re-registered under the new `consolidation` tab,
or surfaced under both during a transition window. Same for any module
registered under `accounting` with a tax/GST-related `module_code` — re-registered
under the new `tax` tab.

Tests: existing module-tab routing tests pass with the new structure.

### 3. Entity-model verification: parent / consolidation-eligible distinction

The frontend SP-2E gating rule (sharpened in TD-016 resolution) requires
the entity model to expose whether an entity is a parent / consolidation-
eligible entity. Specifically the frontend needs to determine, for each
entity, whether consolidation is applicable when that entity is the active
scope.

**Verify:** Does the entity model already expose this? Possible mechanisms:

- A boolean attribute (e.g., `is_consolidation_parent`)
- An inference from entity relationships (e.g., "has children" in
  `entity_hierarchy`)
- A calculated field on the entity GET response

**If yes:** Document where it lives, no schema change needed. Acceptance
criterion is met.

**If no:** Add the attribute (or expose the inference via API). The
recommended approach is a calculated boolean field on the entity GET
response (`is_consolidation_parent: bool`) that returns `true` if the entity
has any children in `entity_hierarchy`, else `false`. This avoids
schema-change cost on the entity table itself.

If this verification produces a "no" result, BE-002 scope expands to include
the API change. Update the estimate accordingly.

### 4. Entity-model verification: jurisdiction attribute

The frontend SP-2E tax relabeling rule requires the entity model to expose
the entity's jurisdiction (country code) so the frontend can choose between
"GST" / "VAT" / "Sales Tax" labels.

**Verify:** Does the entity model already expose `country_code` or
`jurisdiction` on the GET response?

**If yes:** Document, no change needed.

**If no:** Add the attribute. Most entity models expose country/jurisdiction
already; this is more sanity check than expected work.

### 5. Test coverage

- Unit test: `_WORKSPACE_DEFINITIONS` lists the new tabs
- Integration test: `GET /api/v1/workspaces/me` returns the 9-tab structure
- Integration test: an entity with children returns
  `is_consolidation_parent: true`; a leaf entity returns `false`
- Integration test: an Indian entity returns `country_code: "IN"`; verify
  for at least one non-IN jurisdiction
- No regressions in existing workspace tab routing tests

### 6. Documentation

Update API docs / OpenAPI spec to reflect the new tabs and any new entity
attributes. Frontend OpenAPI-generated types will pick up the changes
automatically when SP-2E executes.

## Out of scope

- Promoting other capabilities (Prepaid, Fixed Assets, Payroll, AP, AR,
  MIS, GL Reco, Bank Reco) to top-level tabs. That decision is captured
  in TD-018 and may expand BE-002 scope if the review lands before BE-002
  is executed.
- Frontend implementation of the gating + relabeling rules. That's SP-2E,
  drafted during Phase 3, executed after BE-002 lands.
- Any UX redesign of the tab navigation pattern (e.g., wrapping behavior
  at high tab counts). That's a separate UX decision tracked in TD-018.

## Cross-references

- TD-016 (resolution context): `docs/tech-debt/TD-016-phase2-consolidation-tax-tabs.md`
- TD-018 (broader pre-launch review that may expand this scope):
  `docs/tech-debt/TD-018-pre-launch-workspace-tab-review.md`
- SP-2E placeholder: `docs/prompts/phase2/SP-2E-DEFERRED-consolidation-tax.md`
- Locked design: `docs/audits/finqor-shell-audit-2026-04-24.md` (Deliverables 5 and 6)
- Phase 2 pre-flight (S-002 — original surface of the architectural mismatch):
  `docs/platform/phase2-preflight-2026-04-26.md`

## Definition of done

- All 6 acceptance criteria pass
- All tests green
- Existing workspace tab routing tests show no regressions
- TD-018 review (if landed by execution time) reviewed for expanded scope
- API docs updated
- Frontend can call `GET /api/v1/workspaces/me` and receive the 9-tab structure
- Frontend can call `GET /api/v1/entities/<id>` and receive
  `is_consolidation_parent` and `country_code`
