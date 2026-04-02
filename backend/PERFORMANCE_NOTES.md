# Phase 11C Performance & Scaling Notes

## What was optimized

### 1) Query efficiency
- Replaced `len(result.scalars().all())` in JV numbering with `COUNT(*)` aggregate.
- Replaced count-via-subquery patterns in ERP sync list endpoints with direct `COUNT(table.id)`.
- Reduced list query payload in ERP sync endpoints by selecting only required columns instead of full ORM rows.

### 2) Pagination and dataset limiting
- Enforced bounded pagination for analytics alert listing (`limit`/`offset`, capped).
- Enforced bounded pagination for CoA ERP mapping lists (`limit`/`offset`, capped).
- Tightened FX list endpoint limits using explicit FastAPI `Query` constraints.

### 3) Caching (Redis, TTL-based, safe fallback)
- Added read caching for:
  - Analytics KPI/variance/trend/ratio/budget-variance/alert reads.
  - CoA templates and ERP mapping list reads.
  - FX latest rate lookup.
- Cache failures are fail-open: request still succeeds against DB when Redis is unavailable.
- Added analytics tenant-scoped cache versioning to invalidate cached reads after alert writes.

### 4) Async offload for long-running AI workloads
- Added async narrative generation queue path:
  - `POST /api/v1/ai/narrative/async` (enqueue, returns `task_id`)
  - `GET /api/v1/ai/narrative/tasks/{task_id}` (poll status/result)
- Narrative generation now supports non-blocking execution through Celery workers.

### 5) Response optimization
- Enabled GZip middleware globally (`minimum_size=1024`) for large API responses.

## Operational guidance
- Keep Redis available for best read latency; platform remains functionally correct without it.
- Monitor:
  - `financeops_api_request_latency_ms`
  - `financeops_erp_sync_duration_ms`
  - `financeops_ai_narrative_duration_ms`
  - worker queue depth metrics.

## Remaining risks / follow-ups
- Some legacy list endpoints outside the core Phase 11C target set still use count-subquery patterns and can be migrated incrementally.
- CoA cache invalidation is TTL-based for mapping reads; if stricter freshness is needed, add explicit mapping cache-version bump on mapping mutations.
- For very large analytics drilldowns, cursor pagination can be introduced as a follow-up (current hard limits already cap GL and journal expansions).
