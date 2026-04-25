# FU-005 — Remove deprecated fields from legacy Zustand stores

**Opened:** 2026-04-25
**Related to:** Phase 0 sub-prompt 0.1 redo (`feat/phase0-workspace-store-v2`), Phase 0 sub-prompt 0.4
**Status:** Open
**Priority:** Low — fields are commented as deprecated and don't actively harm the codebase
**Estimated effort:** Half a day, one Claude Code session.

## Context

Sub-prompt 0.1 (redo) introduced `useWorkspaceStore` and migrated all callers from the legacy stores (`useTenantStore`, `useUIStore`). The migration was caller-by-caller — fields on the legacy stores were marked @deprecated but not removed, because some callers still legitimately read them (e.g., `useOrgEntities` reads `useTenantStore.entity_roles` as a fallback when the live endpoint fails).

Sub-prompt 0.4 (cleanup) deliberately deferred this work to keep the phase exit PR docs-only and reviewable.

## What to do when picked up

1. For each deprecated field on legacy stores, run a grep for remaining readers:
   ```
   grep -rn "<field_name>" frontend/ --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v "<store_file>.ts"
   ```
2. For each field with ZERO remaining readers: remove it from the store, the TypeScript interface, and the `partialize` config.
3. For fields that still have readers (e.g., `entity_roles` for fallback): leave them with the existing deprecation comment. Document why each remaining field is still needed.
4. Update legacy stores' shapes to the minimum required for current use cases.

## What NOT to do

- Do not remove `useTenantStore` itself — even if its shape becomes minimal, removing the store is a larger refactor that affects auth bootstrap.
- Do not remove `entity_roles` while `useOrgEntities` fallback still references it. That removal is gated on a separate decision: do we still want session-data fallback, or do we trust the live endpoint enough to remove the safety net?

## Acceptance criteria

- Each remaining field on the legacy store has a clear reason to exist
- All TRULY unused deprecated fields are removed
- `tsc --noEmit`, `npm run lint`, `npm run build`, all tests pass
- No regression in entity switching, location switching, or other affected flows
