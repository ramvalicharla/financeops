# FU-002 — Unify tenant-coa-accounts query keys

**Opened:** 2026-04-25
**Related to:** Phase 0 Sub-prompt 0.2 (`feat/phase0-query-keys`)
**Status:** Open
**Priority:** Low — no functional impact, cache isolation may be intentional
**Estimated effort:** Half a day, one Claude Code session.

## Context

Four separate query keys all resolve the same `/api/v1/coa/accounts` resource:

| Key | Caller |
|-----|--------|
| `["tenant-coa-accounts"]` | `settings/chart-of-accounts`, `journals/new` |
| `["tenant-coa-accounts-for-erp-mapping"]` | `erp/mappings` |
| `["tenant-coa-accounts-for-mapping"]` | `settings/erp-mapping` |
| `["org-setup-tenant-coa-accounts"]` | org-setup `Step6ErpMapping` |

These four keys are factored separately in `frontend/lib/query/keys/coa.ts` and `frontend/lib/query/keys/orgSetup.ts`:

- `queryKeys.coa.tenantAccounts()`
- `queryKeys.coa.tenantAccountsForErpMapping()`
- `queryKeys.coa.tenantAccountsForMapping()`
- `queryKeys.orgSetup.tenantCoaAccounts()`

## Why this was deferred

Phase 0 sub-prompt 0.2 had a hard exact-preservation constraint: refactored call sites must produce identical query-key arrays to what they produced before. Unifying these four keys is a *semantic* change (affects cache invalidation behaviour), not a mechanical refactor. Doing it in the same PR as the factory migration would have mixed mechanical preservation with behavioural change.

## What to investigate when picked up

1. Do all four callers share the same `staleTime` and `enabled` conditions?
2. When one screen saves/updates a COA account, should the others see the change immediately, or is per-screen caching intentional?
3. Are there any race conditions or stale-data bugs in production that would be resolved by unification?

## Two possible outcomes

### Outcome A — Unify into a single key

If the investigation finds that all four callers want the same caching semantics, collapse all four methods into a single `queryKeys.coa.tenantAccounts()`. Update all call sites. Run smoke tests on each affected screen.

### Outcome B — Keep separate, document why

If the investigation finds intentional isolation (e.g., ERP mapping screens want stale data preserved during a long mapping session), add a JSDoc comment block above each method explaining the intent. Close this follow-up as "won't fix — intentional."

## Acceptance criteria

- Either a single `queryKeys.coa.tenantAccounts()` exists with all four call sites consolidated, OR
- Each of the four methods has a clear JSDoc explaining why it is distinct
- `tsc --noEmit`, `npm run lint`, `npm run build` all pass
- Manual smoke test on each of the four affected screens confirms no regression

## Files to touch (starting points)

- `frontend/lib/query/keys/coa.ts`
- `frontend/lib/query/keys/orgSetup.ts`
- Callers (identify via grep):
  - `frontend/app/**/settings/chart-of-accounts/**`
  - `frontend/app/**/journals/new/**`
  - `frontend/app/**/erp/mappings/**`
  - `frontend/app/**/settings/erp-mapping/**`
  - `frontend/app/**/org-setup/Step6ErpMapping**`
