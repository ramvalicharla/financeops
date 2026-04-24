# FU-001 — Refactor sync cache-busting sentinel

**Opened:** 2026-04-25
**Related to:** Phase 0 Sub-prompt 0.2 (`feat/phase0-query-keys`)
**Status:** Open
**Estimated effort:** Half a day, one Claude Code session.

## Context

The sync query keys (`["sync-connections", version]`, `["sync-runs", connectionId, version]`, `["sync-run", id, version]`, `["sync-drift", runId, version]`) use a `version` parameter as a cache-busting sentinel. This is a hack — proper TanStack Query semantics should replace it (either direct `refetch()` calls, `staleTime: 0`, or explicit `invalidateQueries` calls).

## Why this was deferred

Phase 0 sub-prompt 0.2 had a hard constraint: every refactored call site must produce an identical query key array to what it produced before. The sync keys technically comply (they continue to include `version`), but the right fix is to remove `version` from the key shape entirely, which is a behavioral change, not a mechanical refactor.

Mixing that behavioral change into the mechanical refactor PR would have violated the one-PR-one-concern discipline.

## Scope when picked up

1. Identify every hook and component that passes `version` into a sync query key.
2. For each call site, decide the correct replacement:
   - Manual `refetch()` when the user explicitly triggers a re-sync.
   - `staleTime: 0` when data is always considered stale.
   - Explicit `queryClient.invalidateQueries({ queryKey: queryKeys.sync.connections() })` when specific events should invalidate.
3. Remove `version` parameter from all methods in `frontend/lib/query/keys/sync.ts`.
4. Update every call site to drop `version`.
5. Verify no regression in the sync UX (connections list refreshes on trigger, run status updates, drift detection still works).

## Acceptance criteria

- `queryKeys.sync.*` methods have no `version` parameter.
- No call site in `frontend/` passes `version` into a sync query key.
- Manual testing confirms sync UX behaviour unchanged.
- `tsc --noEmit`, `npm run lint`, `npm run build` all pass.

## Files to touch (starting points)

- `frontend/lib/query/keys/sync.ts`
- `frontend/hooks/useSync.ts`
- Any component/page importing from `useSync`
