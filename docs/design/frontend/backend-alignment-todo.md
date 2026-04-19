# Backend Alignment Protocol (For Upcoming Tasks)

This document tracks backend modifications that will be required to fully enable the `v3.0` Frontend UI structure. Since the current active sprint places the backend in a freeze for API contracts, the frontend is currently employing workarounds (e.g., Client-side routing overrides, Zustand injections). 

Later, the backend team should clear this checklist to ensure true 1-to-1 parity.

## 1. True Module Extensibility via Auth
* **Current Fallback:** The frontend is statically mapping URL features via `lib/ui-access.ts` (`ROUTE_FEATURES` array) because the `MePayload` from the NextAuth backend JWT does not contain explicit "Enabled Modules" for the specific tenant.
* **Backend Fix Required:** Update `GET /api/v1/auth/me`. Embed an array `tenant.enabled_modules: string[]` inside the payload. This allows dynamic resolution without the frontend hardcoding what routes exist.

## 2. API Prefix Context
* **Current Fallback:** The frontend injects `X-Tenant-ID` and `X-Entity-ID` directly into HTTP Headers via `api/client.ts` Axios interceptors pulling from `useTenantStore`.
* **Backend Fix Required:** The backend Python FastAPI schema requires migrating entirely to respect path-based multi-tenancy. Endpoints should formally evolve from `GET /api/v1/accounting/journals` to `GET /api/v1/tenant/{tenant_id}/entity/{entity_id}/accounting/journals` for maximum RESTful clarity and security, matching the new Frontend Next.js routing architecture exactly.

## 3. Omnisearch Enrichment (DONE ✅)
* **Status:** The frontend and backend have now established the UnifiedSearchResponse DTO. Global search spans across Journals, Expenses, Users, Reports, and Entities, seamlessly rendering results natively into the Command Palette and `/search` standalone page.

## 4. Drawers & Aggressive Pagination (DONE ✅)
* **Status:** Frontend Tanstack Data Grid implementations and the global PaginationBar components are now fully wired to proactively pass `offset`, `limit`, and server-side arguments to backend data fetches.
