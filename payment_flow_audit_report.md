# PAYMENT/BILLING FLOW AUDIT REPORT
## FinanceOps Platform - Payment Webhook Security Audit
**Date:** April 18, 2026  
**Audit Scope:** Payment webhook endpoints, idempotency handling, race conditions

---

## EXECUTIVE SUMMARY

The payment/billing flow implements robust idempotency controls but has several critical gaps that could lead to double-charging, race conditions, and data inconsistency. The system uses a dual-layer idempotency approach (Redis + Database) but lacks proper cleanup mechanisms and has webhook-specific vulnerabilities.

## WEBHOOK ENDPOINTS FOUND

### Payment Webhooks
1. **`/webhooks/stripe`** - `backend/financeops/modules/payment/api/webhooks.py:37-70`
2. **`/webhooks/razorpay`** - `backend/financeops/modules/payment/api/webhooks.py:73-106`
3. **Generic SaaS webhook** - `backend/financeops/modules/payment/api/saas.py` (line not specified)

### ERP Webhooks
1. **`/webhooks/zoho`** - `backend/financeops/modules/erp_push/api/webhook_routes.py`
2. **`/webhooks/qbo`** - `backend/financeops/modules/erp_push/api/webhook_routes.py`
3. **`/webhooks/tally`** - `backend/financeops/modules/erp_push/api/webhook_routes.py`

## FLOW ANALYSIS

### Payment Webhook Processing Chain
1. **Webhook Receive** (`webhooks.py:37-106`)
   - Extract tenant ID from payload metadata
   - Validate webhook signature with provider
   - Return early if tenant cannot be resolved

2. **Idempotency Check** (`webhook_service.py:51-62`)
   - Check `WebhookEvent` table for existing `provider_event_id`
   - Uses database-level unique constraint: `uq_webhook_events_provider_event`
   - Fallback: Generate deterministic hash from payload if no provider event ID

3. **Database Update** (`webhook_service.py:274-398`)
   - Update invoice status (paid/uncollectible)
   - Create payment record with provider reference
   - Update subscription status

4. **Receipt Generation** - NOT FOUND IN CODE
   - No evidence of automated receipt/confirmation generation
   - Payment records created but no email/SMS notifications traced

## CRITICAL FINDINGS

### 🔴 HIGH RISK: Race Condition in Webhook Processing
**File:** `backend/financeops/modules/payment/application/webhook_service.py:51-62`

```python
existing = (
    await self._session.execute(
        select(WebhookEvent).where(
            WebhookEvent.tenant_id == tenant_id,
            WebhookEvent.provider == provider.value,
            WebhookEvent.provider_event_id == provider_event_id,
        )
    )
).scalar_one_or_none()
if existing is not None:
    return
```

**Issue:** Concurrent webhook deliveries can bypass idempotency check due to:
1. No database transaction isolation around the check
2. Check happens before transaction begins
3. Multiple processes can pass check simultaneously

**Impact:** Double payment processing, duplicate payment records

### 🔴 HIGH RISK: Missing Idempotency Keys for Generic Webhooks
**File:** `backend/financeops/modules/payment/api/saas.py`

**Issue:** Generic SaaS webhook endpoint (`/webhook`) appears to lack:
1. Provider event ID extraction
2. WebhookEvent table deduplication
3. Signature verification (not visible in search)

**Impact:** Unprotected endpoint vulnerable to replay attacks

### 🟡 MEDIUM RISK: Idempotency Middleware Bypass
**File:** `backend/financeops/shared_kernel/idempotency.py:145-146`

```python
if "/webhooks/" in path:
    return await call_next(request)
```

**Issue:** Payment webhooks explicitly excluded from global idempotency middleware
**Rationale:** Webhooks have their own idempotency mechanism (database-level)
**Risk:** If database mechanism fails, no fallback protection

### 🟡 MEDIUM RISK: Redis TTL Without Cleanup Job
**File:** `backend/financeops/shared_kernel/idempotency.py:16, 201`

```python
IDEMPOTENCY_TTL_SECONDS = 86_400  # 24 hours
await api_deps._redis_pool.setex(redis_key, IDEMPOTENCY_TTL_SECONDS, body.decode("utf-8"))
```

**Issue:** 
1. 24-hour TTL for idempotency keys in Redis
2. No scheduled cleanup job for expired keys
3. Redis memory bloat over time
4. No monitoring of Redis key growth

### 🟡 MEDIUM RISK: Database Idempotency Table Growth
**File:** `backend/financeops/db/models/payment.py:205-219`

**Issue:** `WebhookEvent` table has:
1. No automatic cleanup/archiving
2. No TTL/expiration policy
3. Unlimited growth potential
4. No partitioning by date

### 🟢 LOW RISK: Deterministic Fallback Hash
**File:** `backend/financeops/modules/payment/application/webhook_service.py:42-49`

```python
payload_hash = hashlib.sha256(payload or b"").hexdigest()
provider_event_id = f"derived:{provider.value}:{canonical_event_type}:{payload_hash}"
```

**Strength:** Provides idempotency even when providers omit event IDs
**Weakness:** SHA-256 of entire payload - computationally expensive for large payloads

## IDEMPOTENCY KEY STORAGE ANALYSIS

### Redis Storage (Global Middleware)
- **Key Format:** `idempotency:{tenant_id}:{idempotency_key}`
- **TTL:** 24 hours (86,400 seconds)
- **Scope:** All POST endpoints except `/webhooks/`
- **Cleanup:** Automatic Redis expiry, no manual cleanup

### Database Storage (Webhook-specific)
- **Table:** `webhook_events`
- **Unique Constraint:** `(tenant_id, provider, provider_event_id)`
- **TTL:** None (permanent storage)
- **Cleanup:** No automated cleanup found

### Missing: Hybrid Storage Coordination
No synchronization between Redis and database idempotency mechanisms. Webhook processed successfully could still trigger Redis idempotency replay for related API calls.

## RACE CONDITION ANALYSIS

### Scenario: Concurrent Webhook Delivery
1. Two identical webhook requests arrive simultaneously
2. Both pass `WebhookEvent` check (no existing record yet)
3. Both begin processing
4. Database unique constraint prevents duplicate insert
5. **BUT:** Second request gets `IntegrityError` after performing business logic

**Actual Code Flow:**
```python
# Check happens first
existing = await self._session.execute(select(...))

# Business logic executes
await self._route_event(...)

# WebhookEvent insert happens later via AuditWriter
await AuditWriter.insert_financial_record(...)
```

**Result:** Business logic executes twice, only second fails on insert.

## RECOMMENDATIONS

### Immediate Fixes (High Priority)

1. **Add Database Transaction Isolation**
   ```python
   async with self._session.begin_nested():  # or proper transaction
       existing = await self._session.execute(select(...))
       if existing: return
       # Process webhook
   ```

2. **Implement Webhook Processing Lock**
   ```python
   lock_key = f"webhook_lock:{tenant_id}:{provider_event_id}"
   async with redis_lock(lock_key, timeout=30):
       # Process webhook
   ```

3. **Add Generic Webhook Idempotency**
   - Apply same `WebhookEvent` pattern to generic SaaS webhook
   - Add provider_event_id extraction for all webhook types

### Short-term Improvements (Medium Priority)

1. **Add Cleanup Jobs**
   ```python
   # Daily job to delete Redis keys older than 24h
   # Monthly job to archive old WebhookEvent records
   ```

2. **Add Monitoring**
   - Alert on WebhookEvent table growth rate
   - Monitor Redis memory usage for idempotency keys
   - Track webhook processing failures due to duplicate detection

3. **Implement Receipt Generation**
   - Add email/SMS notification on successful payment
   - Generate PDF receipts for paid invoices

### Long-term Enhancements (Low Priority)

1. **Database Partitioning**
   - Partition `WebhookEvent` table by `created_at` monthly
   - Implement retention policy (e.g., 90 days for raw payloads)

2. **Idempotency Service**
   - Centralize idempotency logic for all endpoints
   - Support multiple storage backends (Redis, DB, in-memory)
   - Add metrics and analytics

3. **Webhook Signature Verification**
   - Ensure all webhook endpoints validate signatures
   - Add provider-specific verification logic registry

## CONCLUSION

The payment/billing flow has strong foundational idempotency controls but contains critical race condition vulnerabilities that could lead to financial impact. The most urgent issue is the lack of transaction isolation around the idempotency check, which could result in double payment processing.

**Overall Risk Rating: HIGH** due to potential for duplicate financial transactions.

**Priority Actions:**
1. Fix race condition in `webhook_service.py`
2. Add idempotency to generic SaaS webhook
3. Implement webhook processing locks
4. Add cleanup and monitoring for idempotency storage

---

## APPENDIX: FILE PATHS AND LINE NUMBERS

### Critical Issues
1. **Race Condition:** `backend/financeops/modules/payment/application/webhook_service.py:51-62`
2. **Missing Webhook Idempotency:** `backend/financeops/modules/payment/api/saas.py` (generic webhook)
3. **Middleware Bypass:** `backend/financeops/shared_kernel/idempotency.py:145-146`
4. **No Cleanup Job:** `backend/financeops/shared_kernel/idempotency.py:16, 201` (TTL but no cleanup)

### Webhook Endpoints
1. **Stripe:** `backend/financeops/modules/payment/api/webhooks.py:37-70`
2. **Razorpay:** `backend/financeops/modules/payment/api/webhooks.py:73-106`
3. **ERP Webhooks:** `backend/financeops/modules/erp_push/api/webhook_routes.py`

### Database Models
1. **WebhookEvent:** `backend/financeops/db/models/payment.py:205-219`
2. **Unique Constraint:** Line 209: `UniqueConstraint("tenant_id", "provider", "provider_event_id", name="uq_webhook_events_provider_event")`

### Idempotency Configuration
1. **Redis TTL:** `backend/financeops/shared_kernel/idempotency.py:16`
2. **Key Storage:** `backend/financeops/shared_kernel/idempotency.py:201`