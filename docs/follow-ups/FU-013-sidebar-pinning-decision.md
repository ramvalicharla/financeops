# FU-013 — Sidebar pinning decision

**Opened:** 2026-04-25
**Related to:** Phase 1 sub-prompt 1.1 (Pinned section removed)
**Spec ref:** Phase 1 sidebar rebuild discussion; nav-config.ts header

## Background

Phase 1 sub-prompt 1.1 rebuilt the sidebar with three groups (Workspace /
Org / Governance) per spec §1.3. The previous sidebar had a "Pinned"
section above the groups that allowed users to pin frequently-used
modules to the top. That section was removed in 1.1 because:

1. It depended on the old flat NAV_GROUP_DEFINITIONS structure, which 1.1
   replaced wholesale.
2. "Pinned modules" semantically belongs to the modules tab bar (Phase 3
   Module Manager), not the sidebar nav.
3. Re-implementing pinning in 1.1 risked scope creep on a structural-only
   sub-prompt.

The decision to bring pinning back, where it lives, and what gets pinned
is deferred — but the dangling reference in nav-config.ts comments needs
a tracking ID to point at.

## Scope (decision required, then implementation)

### Decision phase

Choose one of:

- **Option 1: Sidebar pinning returns** — re-implement Pinned section above
  the three nav groups in the sidebar. Reads pinned items from
  workspaceStore (not the deprecated UI store).

- **Option 2: Modules tab pinning** — pinning becomes a modules-tab feature.
  The Phase 3 Module Manager allows starring modules; starred modules
  appear earlier in the tab bar. No sidebar pinning at all.

- **Option 3: No pinning** — the three nav groups are the canonical
  organization. Pinning was useful when the nav was 14+ items flat; with
  3 groups of 3-5 items each, pinning is unnecessary.

### Implementation phase (only after decision)

Depends on the option chosen. Estimated effort:
- Option 1: ~4 hours (UI + state + persistence)
- Option 2: ~2 hours (extends Phase 3 Module Manager scope)
- Option 3: 0 hours (just delete the nav-config.ts FU-013 comment reference)

## Acceptance criteria

- [ ] Decision recorded in this FU file (which option was chosen and why)
- [ ] Implementation matches chosen option
- [ ] nav-config.ts FU-013 reference removed (or replaced with the
      implementation reference)

## Out of scope

- Module Register changes (Phase 3 territory regardless)
- Sidebar group collapse persistence (separate concern, will be folded
  into Phase 4 collapsed-rail server preferences)

## Recommendation (not binding)

Option 2 — modules-tab pinning. Reasons:
- Aligns with the spec's clean separation: sidebar = structural nav,
  tab bar = workspace context
- Avoids re-introducing per-user state into the sidebar
- Solves the "I use Banking 90% of the time" use case at the right layer
  (the tab bar is where users actually live during work)

But this is a UX decision, not a code decision. Decide with whoever owns
product/design.

## Estimate

Decision phase: 30 minutes (read this, pick an option, document it).
Implementation phase: 0–4 hours depending on option.
