# FinanceOps Corrected Backend Stabilization And Scale Plan

## Objective
Bring the backend to a state that is secure, concurrency-safe, operationally reliable, and ready for high-scale growth without introducing contract-breaking changes unless explicitly intended.

## Ground Rules
- Fix correctness and security issues before feature additions.
- Preserve existing API response contracts unless product explicitly approves changes.
- Prefer database-enforced correctness over in-memory or middleware-only protection.
- Add tests for each critical fix before calling the work complete.
- Separate true code gaps from infra/ops hardening and from optional product enhancements.

---

## Execution Status

### Completed

- `GAP-01` implemented with insert-first webhook claiming in `webhook_service.py`
- `GAP-02` validated on the generic SaaS webhook path with explicit-id, derived-id, and cross-tenant tests
- `GAP-04` implemented with cleanup for immortal idempotency keys only
- `GAP-05` implemented with configurable retention, scheduled cleanup, and retention coverage
- `GAP-07` implemented with environment-aware DB TLS enforcement and focused tests
- `GAP-08` implemented with stronger RLS coverage and a real session-role reapply fix
- `GAP-09` implemented as expanded webhook idempotency coverage across Stripe, Razorpay, and generic SaaS paths
- `GAP-11` implemented as tighter AI provider startup validation
- `GAP-12` implemented with Redis-backed `slowapi` storage plus in-memory fallback
- `GAP-13` implemented with explicit read-replica plumbing and search routed to the read session
- `GAP-14` implemented as Redis topology-aware broker/cache/result configuration hardening
- `GAP-15` implemented as payment/webhook dead-letter visibility hardening
- `GAP-16` implemented with Grafana dashboard updates and repo-tracked latency alert rules
- `GAP-17` completed in revised form as webhook-retention hot-path hardening instead of physical table partitioning

### Deferred / Not Executed In This Pass

- `GAP-03` intentionally left deferred after `GAP-01/02`, as planned
- `GAP-06` remains a deferred product enhancement
- `GAP-10` remains not required now

### Important GAP-17 Deviation

- Physical partitioning of `webhook_events` was intentionally not implemented.
- Reason: the current global idempotency guarantee depends on the unique key `(tenant_id, provider, provider_event_id)`, and partitioning `webhook_events` by `created_at` would conflict with that guarantee in PostgreSQL.
- Safe replacement delivered:
  - keep `webhook_events` unpartitioned
  - preserve the global dedupe key
  - improve retention observability with cleanup timing and row-count reporting

### Verification Status

- Focused regression verification for the completed gap work passed (`49 passed` in the targeted regression set).
- A subsequent full backend suite pass is **not green yet**.
- The strongest blocker in that full run is a Redis test-environment mismatch on `localhost:6380`, plus a wider set of unrelated auth/platform/board-pack regressions outside the specific stabilization gap set.
- This means the gap plan itself is largely executed, but the overall backend is not yet at a clean full-suite release gate.

---

## Phase 0: Critical Correctness

### GAP-01: Webhook Idempotency Race In Payment Webhook Service
**Status:** Real issue. Current plan's proposed fix is not sufficient.

**Current code**
- Duplicate check is a read-before-write pattern in [webhook_service.py](backend/financeops/modules/payment/application/webhook_service.py).
- Uniqueness is enforced by the DB in [payment.py](backend/financeops/db/models/payment.py).

**Why the previous plan is wrong**
- `SELECT ... FOR UPDATE` does not protect the missing-row case.
- Two concurrent requests can both see "no row exists yet" and then both attempt side effects.
- The unique constraint must be the source of truth.

**Correct implementation**
- Create the `WebhookEvent` row first.
- Use one of these patterns:
  1. `INSERT ... ON CONFLICT DO NOTHING RETURNING id`
  2. ORM insert + `flush()` + catch `IntegrityError`
- Only continue to `_route_event(...)` if the insert succeeds.
- Persist enough metadata up front so the inserted row is the durable claim that this event is being processed.
- Keep current success-style response semantics unless product wants to change them.

**Files involved**
- `backend/financeops/modules/payment/application/webhook_service.py`
- `backend/financeops/db/models/payment.py`
- `backend/financeops/services/audit_writer.py`

**Test plan**
- Add concurrent duplicate webhook tests with 5-10 simultaneous identical requests.
- Assert exactly one durable processing outcome:
  - one `WebhookEvent`
  - one downstream invoice/payment/subscription state change
- Do not hardcode `409` unless contract is intentionally changed.

**Acceptance**
- No duplicate side effects under concurrent duplicate delivery.
- Replayed webhook after first commit does not create a second financial effect.

### GAP-02: Generic SaaS Webhook Idempotency
**Status:** Real issue path exists, but previous fix design is also wrong.

**Current code**
- Generic webhook exists in `backend/financeops/modules/payment/api/saas.py`.
- Tenant context is already set and cleared there.

**Correct implementation**
- Reuse the same insert-first DB idempotency approach from `GAP-01`.
- Derive a deterministic event ID when provider payload lacks one.
- Keep tenant-context logic intact.
- Preserve current response contract unless explicitly changed.

**Files involved**
- `backend/financeops/modules/payment/api/saas.py`
- `backend/financeops/modules/payment/application/saas_billing_service.py`
- `backend/financeops/modules/payment/application/webhook_service.py`

**Test plan**
- Duplicate identical payload with explicit event ID.
- Duplicate identical payload without event ID, relying on derived hash.
- Concurrent delivery test.
- Cross-tenant duplicate payload should not collide incorrectly.

**Acceptance**
- Generic webhook is idempotent for both explicit and derived event IDs.
- No cross-tenant bleed.

### GAP-03: Redis Idempotency Middleware Webhook Bypass
**Status:** Partly valid, but not the primary fix.

**Current code**
- Webhooks are bypassed in `backend/financeops/shared_kernel/idempotency.py`.

**Correct implementation**
- Do not remove this bypass first.
- First make DB webhook idempotency correct in `GAP-01/02`.
- Then decide whether webhook routes should also support middleware-level replay prevention.
- Only enable middleware for webhooks if:
  - providers or callers actually send usable idempotency keys
  - replay behavior is well-defined
  - cached-response semantics will not hide needed processing states

**Acceptance**
- DB layer remains primary correctness boundary.
- Middleware, if added, is only defense in depth.

---

## Phase 1: Security And Reliability

### GAP-07: SSL Verification Disabled
**Status:** Real security issue.

**Current code**
- TLS context disables hostname verification and certificate validation in `backend/financeops/db/session.py`.

**Correct implementation**
- Use current environment source of truth, `APP_ENV`, not a new env var.
- In production:
  - `check_hostname = True`
  - `verify_mode = ssl.CERT_REQUIRED`
- In non-production, relaxed mode may remain only when explicitly needed.
- Fail fast at startup if production config would run with insecure TLS.

**Files involved**
- `backend/financeops/db/session.py`
- `backend/financeops/config.py`

**Test plan**
- Unit test for SSL context behavior by environment.
- Startup validation test for production misconfiguration.

**Acceptance**
- Production cannot boot with insecure DB TLS settings.

### GAP-08: Comprehensive RLS Bypass Coverage
**Status:** Valid and important.

**Current state**
- RLS exists, but comprehensive bypass coverage is not broad enough.

**Correct implementation**
Add tests for:
- cross-tenant reads
- tenant-context leakage between sessions
- tenant-context leakage across transaction boundaries
- privileged-role bypass behavior
- raw SQL access under RLS
- multi-session visibility with committed data

**Related files**
- `backend/financeops/db/session.py`
- `backend/tests/conftest.py` if committed-session fixtures are involved
- existing RLS-related tests under `tests/integration`

**Acceptance**
- RLS behavior is explicitly covered for normal, privileged, and transaction-boundary scenarios.

### GAP-09: Payment Webhook Idempotency Tests
**Status:** Valid and currently under-covered.

**Current tests**
- Unit coverage is basic in `backend/tests/unit/payment/test_payment_webhook_service.py`.
- Integration happy-path coverage exists in:
  - `backend/tests/integration/payment/test_payment_webhook_stripe.py`
  - `backend/tests/integration/payment/test_payment_webhook_razorpay.py`

**Correct implementation**
Add tests for:
- concurrent identical webhook requests
- delayed duplicate delivery
- duplicate delivery across worker/session boundaries
- duplicate delivery after partial downstream failure
- duplicate delivery with same provider event ID but different payload body
- generic SaaS webhook path

**Acceptance**
- The suite proves one logical outcome per provider event per tenant.

### GAP-04: Redis Idempotency Key Hygiene
**Status:** Valid but not critical.

**Current code**
- Normal storage path uses `setex` in `backend/financeops/shared_kernel/idempotency.py`.
- TTL constant exists there as well.

**Correct implementation**
- Add cleanup only for keys with `ttl == -1`.
- Treat this as hygiene for malformed/manual keys, not as a critical memory leak in the normal path.
- Schedule cleanup through the existing Celery beat system if implemented.

**Acceptance**
- No immortal idempotency keys remain after cleanup runs.

### GAP-05: Webhook Event Retention / Archival
**Status:** Valid.

**Current code**
- `webhook_events` table exists in `backend/financeops/db/models/payment.py`.

**Correct implementation**
- Define retention policy with product/compliance first.
- Add a scheduled cleanup/archive task.
- Add supporting index only if data volume and query plans justify it.
- Prefer configurable retention over hardcoded "3 months".

**Files involved**
- `backend/financeops/db/models/payment.py`
- `backend/financeops/tasks/celery_app.py`

**Acceptance**
- Old webhook rows are managed on schedule.
- Cleanup does not block hot paths.

### GAP-12: Distributed Rate Limiting
**Status:** Real scale gap.

**Current code**
- App uses `slowapi` limiter in `backend/financeops/config.py`.
- Rate-limited routes already exist in auth and other modules.

**Correct implementation**
- Move limiter storage to a Redis-backed configuration compatible with the existing `slowapi` usage.
- Avoid replacing the whole system unless current library cannot support the required backend.
- Validate behavior under multiple app instances.

**Files involved**
- `backend/financeops/config.py`
- `backend/financeops/main.py` if limiter wiring is updated

**Test plan**
- Multi-instance simulation or integration test against shared Redis.
- Confirm limits are enforced consistently across instances.

**Acceptance**
- Rate limits are shared across all backend instances.

---

## Phase 2: Already Partly Addressed, Needs Hardening

### GAP-11: AI Provider Configuration Validation
**Status:** Partly addressed already.

**Current code**
- Startup checks already exist in `backend/financeops/main.py`.

**Correct implementation**
- Keep existing startup validation.
- Extend to validate:
  - provider-specific required fields
  - endpoint shape where applicable
  - model presence and supported fallback configuration
- Do not rebuild this from scratch.

**Acceptance**
- Invalid AI provider configs fail early with actionable error messages.

### GAP-15: Dead Letter Queues
**Status:** Already partly addressed.

**Current code**
- Dead-letter queue configuration and monitoring already exist in `backend/financeops/tasks/celery_app.py`.

**Correct implementation**
- Re-scope this work to payment/webhook-specific dead-letter handling and alerting.
- Confirm failed payment/webhook jobs are routed and visible operationally.
- Add missing task-level alerting/runbooks if needed.

**Acceptance**
- Failed payment/webhook async work is not silently lost.

### GAP-16: P99 Latency Dashboards
**Status:** Already partly addressed.

**Current code**
- Histograms already exist in `backend/financeops/observability/business_metrics.py`.

**Correct implementation**
- Build Grafana dashboards and alerts from existing Prometheus metrics.
- Define SLOs for critical paths:
  - auth
  - billing webhooks
  - search
  - high-value finance workflows

**Acceptance**
- P50/P95/P99 are visible and alertable in production.

---

## Phase 3: Infra / Scale Architecture

### GAP-13: Database Read Replicas
**Status:** Valid future scale item.

**Implementation**
- Introduce read/write split only after measuring read pressure.
- Keep all financial write paths on primary.
- Be careful with read-after-write consistency for tenant-facing billing screens.

**Acceptance**
- Read replica usage is explicit and safe for stale-read scenarios.

### GAP-14: Redis HA / Cluster
**Status:** Valid resilience item.

**Implementation**
- Move from single-node Redis to HA/cluster architecture.
- Validate Celery broker semantics, limiter storage, and cache behavior against that topology.

**Acceptance**
- Redis failure does not become a full platform outage.

### GAP-17: Partitioning Strategy
**Status:** Valid, but should be data-driven.

**Implementation**
- Profile `webhook_events`, transactions, and other hot large tables first.
- Partition only when row counts and query plans justify it.
- Prefer operational evidence over speculative schema complexity.

**Acceptance**
- Partitioning is introduced where it measurably improves retention and query performance.

---

## Deferred / Optional

### GAP-06: Payment Receipt Generation
**Status:** Useful product enhancement, not a top stabilization blocker.

**Correct approach**
- If implemented, dispatch asynchronously after commit.
- Do not let email/notification failures affect payment durability.

**Priority**
- After correctness, security, and reliability work.

### GAP-10: Faker Runtime Locale Cleanup
**Status:** Not required now.

**Reason**
- I did not find active `Faker()` instantiations in the repo.
- Do this only if profiling shows a real dependency-memory issue tied to Faker.

---

## Recommended Execution Order

1. Fix webhook insert-first idempotency in `backend/financeops/modules/payment/application/webhook_service.py`.
2. Apply the same pattern to generic SaaS webhook handling in `backend/financeops/modules/payment/api/saas.py`.
3. Add concurrent webhook idempotency tests.
4. Expand RLS bypass and session-leakage tests.
5. Fix production TLS verification in `backend/financeops/db/session.py`.
6. Add webhook retention/archive lifecycle.
7. Move rate limiting to distributed/shared backing.
8. Tighten AI config validation.
9. Harden payment/webhook dead-letter handling and dashboards.
10. Plan replicas, Redis HA, and partitioning as infra projects.

---

## Definition Of Done

The plan is complete when all of the following are true:

- Duplicate webhook delivery does not create duplicate financial side effects.
- Generic SaaS webhook path is idempotent and tenant-safe.
- Payment webhook concurrency tests are green.
- RLS bypass coverage includes transaction/session-boundary cases.
- Production DB TLS cannot run with disabled verification.
- `webhook_events` retention is defined and automated.
- Rate limiting is shared across instances.
- AI provider misconfiguration fails early and clearly.
- Dead-lettered payment/webhook failures are observable.
- P99 dashboards and alerts exist for critical backend flows.

---

## Final Status Summary By Gap

- `GAP-01`: completed
- `GAP-02`: completed
- `GAP-03`: re-scope after `01/02`
- `GAP-04`: completed
- `GAP-05`: completed
- `GAP-06`: defer
- `GAP-07`: completed
- `GAP-08`: completed
- `GAP-09`: completed
- `GAP-10`: not required now
- `GAP-11`: completed
- `GAP-12`: completed
- `GAP-13`: completed
- `GAP-14`: completed
- `GAP-15`: completed
- `GAP-16`: completed
- `GAP-17`: completed as revised retention hot-path hardening; physical partitioning deferred
