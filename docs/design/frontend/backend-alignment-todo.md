# Backend Alignment Protocol (For Upcoming Tasks)

This document tracks backend modifications that will be required to fully enable the `v3.0` Frontend UI structure. Since the current active sprint places the backend in a freeze for API contracts, the frontend is currently employing workarounds (e.g., Client-side routing overrides, Zustand injections). 

Later, the backend team should clear this checklist to ensure true 1-to-1 parity.

## 1. True Module Extensibility via Auth
* **Current Fallback:** The frontend is statically mapping URL features via `lib/ui-access.ts` (`ROUTE_FEATURES` array) because the `MePayload` from the NextAuth backend JWT does not contain explicit "Enabled Modules" for the specific tenant.
* **Backend Fix Required:** Update `GET /api/v1/auth/me`. Embed an array `tenant.enabled_modules: string[]` inside the payload. This allows dynamic resolution without the frontend hardcoding what routes exist.

## 2. API Prefix Context
* **Current Fallback:** The frontend injects `X-Tenant-ID` and `X-Entity-ID` directly into HTTP Headers via `api/client.ts` Axios interceptors pulling from `useTenantStore`.
* **Backend Fix Required:** The backend Python FastAPI schema requires migrating entirely to respect path-based multi-tenancy. Endpoints should formally evolve from `GET /api/v1/accounting/journals` to `GET /api/v1/tenant/{tenant_id}/entity/{entity_id}/accounting/journals` for maximum RESTful clarity and security, matching the new Frontend Next.js routing architecture exactly.

## 3. Omnisearch Enrichment 
* **Current Frontend Need:** The Global Command Palette (`Cmd+K`) provides instant navigation, but needs a global search text aggregator to be "World-Class".
* **Backend Fix Required:** Ensure `GET /api/v1/search?q={query}` scans across Journals, Users, Invoices, Workflows, and Intent pipelines globally, returning categorized hits (e.g., `type: 'journal', id: '123'`) so the frontend can render rich dropdown states natively.

## 4. Drawers & Aggressive Pagination
* **Current Frontend Need:** The frontend is utilizing Slide-over "Sheet" drawers for editing data, meaning it will pull data more aggressively. 
* **Backend Fix Required:** Ensure all list endpoints correctly support standardized `offset`, `limit`, and multi-array `sort` parameters (e.g., `?sort=-created_at,amount_asc`) so the Tanstack Data Grid implementations can fetch sub-pages without forcing heavy localized data processing on the client machine.
