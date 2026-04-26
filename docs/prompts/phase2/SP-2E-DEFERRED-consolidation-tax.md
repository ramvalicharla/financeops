# SP-2E — DEFERRED

**Status:** Not authorized. Deferred via TD-016.

**Originally covered:** Phase 2 deliverables 5 (consolidation-aware tab disable)
and 6 (Tax/GST jurisdictional relabel).

**Why deferred:** Pre-flight surprise S-002 surfaced that the backend has no
standalone `consolidation` or `tax` workspace tabs — both live as `module_code`
values inside `close` and `accounting` respectively. Implementing tab-level
behavior against a UI surface that doesn't exist would require either a backend
ticket (BE-002) to promote them to top-level tabs, or a redesign to gate at the
module-code level.

**Resolution path:** TD-016 documents the three options (promote tabs / keep
nested / defer indefinitely). Resolution is a product/architecture decision,
not engineering.

**Cross-references:**
- TD-016: docs/tech-debt/TD-016-phase2-consolidation-tax-tabs.md
- Pre-flight: docs/platform/phase2-preflight-2026-04-26.md (S-002, OQ-2, D2.6, D2.7)
- Locked design: docs/audits/finqor-shell-audit-2026-04-24.md (Deliverables 5 and 6)

**Do not draft an executable prompt for SP-2E** until TD-016 is resolved with a
chosen direction.
