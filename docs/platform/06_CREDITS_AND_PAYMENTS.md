# FinanceOps Platform — Credits & Payments Master
> Version 1.0 | Status: Locked
> Single source of truth for all monetisation, credits, and payment architecture

---

## 1. Philosophy

### Why Credits (Not Pure Subscription)

Pure subscription gives users unlimited access — you absorb all AI and compute costs
regardless of usage. Heavy users destroy your margins. Light users subsidise them.

Credits solve this:
- Every task has a defined cost → you always know your margin per task
- Heavy users buy more credits → revenue scales with usage
- Light users pay only for what they use → better retention
- Platform errors = zero charge → builds trust
- Subscription gives base credits → predictable base revenue
- Top-ups give variable revenue → scales with platform value delivered

### The 70% Margin Commitment

Every pricing decision must be tested against this formula:

```
Task Revenue (credits × $0.10) − Task Cost (AI + compute + storage) ≥ 70% margin

Example: GL/TB Reconciliation
Revenue:  5 credits × $0.10 = $0.50
Cost:     AI ($0.00 — local model) + compute ($0.04) + storage ($0.01) = $0.05
Margin:   ($0.50 − $0.05) / $0.50 = 90% ✅

Example: FDD Basic Report
Revenue:  1,000 credits × $0.10 = $100
Cost:     AI ($8) + compute ($3) + storage ($1) = $12
Margin:   ($100 − $12) / $100 = 88% ✅

Example: AI Complex Analysis
Revenue:  8 credits × $0.10 = $0.80
Cost:     Claude API ($0.10) + compute ($0.04) = $0.14
Margin:   ($0.80 − $0.14) / $0.80 = 82.5% ✅
```

---

## 2. Credit System Architecture

### Credit Value
```
1 credit = $0.10 USD (base rate)
```

### Credit Lifecycle
```
CREDIT STATES:
├── ALLOCATED    — credited to tenant (from subscription or top-up)
├── AVAILABLE    — allocated, not reserved, not expired
├── RESERVED     — task started, credits held (not yet deducted)
├── DEDUCTED     — task completed, credits consumed
├── RELEASED     — task cancelled/failed, reservation returned to available
├── EXPIRED      — 3 months passed, credits zeroed out (cannot be used)
└── REFUNDED     — admin manual credit back (rare, for disputes)

TRANSITIONS:
Subscription payment → ALLOCATED (expires in 3 months)
Top-up payment → ALLOCATED (expires in 3 months)
Task starts → RESERVATION created (reduces available, not balance)
Task completes → RESERVATION → DEDUCTION (permanent)
Task cancelled → RESERVATION → RELEASED (returns to available)
Platform error → RESERVATION → RELEASED (zero charge, auto-retry)
3 months pass → Celery Beat job → ALLOCATED → EXPIRED
```

### Credit Database Schema (Append-Only)
```sql
CREATE TABLE credit_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    org_id UUID REFERENCES organisations(id),
    user_id UUID REFERENCES users(id),
    
    transaction_type VARCHAR NOT NULL,
    -- SUBSCRIPTION_ALLOCATION | TOPUP | RESERVATION |
    -- DEDUCTION | RELEASE | EXPIRY | REFUND | ADJUSTMENT
    
    credits DECIMAL(12,2) NOT NULL,
    -- positive = credit, negative = debit
    
    task_id UUID REFERENCES tasks(id),
    -- linked for RESERVATION/DEDUCTION/RELEASE
    
    payment_id UUID REFERENCES payments(id),
    -- linked for SUBSCRIPTION_ALLOCATION/TOPUP
    
    package_id VARCHAR,
    -- subscription tier or top-up package identifier
    
    expires_at TIMESTAMPTZ,
    -- NULL for deductions/releases, set for allocations
    
    notes TEXT,
    -- human-readable reason (required for ADJUSTMENT/REFUND)
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID NOT NULL REFERENCES users(id),
    
    -- Immutability
    version INTEGER NOT NULL DEFAULT 1,
    prev_hash VARCHAR(64),
    hash VARCHAR(64) NOT NULL
    
    -- NO UPDATE, NO DELETE — enforced at DB level
);

-- Available balance view
CREATE VIEW tenant_credit_balance AS
SELECT
    tenant_id,
    SUM(CASE
        WHEN transaction_type IN ('SUBSCRIPTION_ALLOCATION','TOPUP','REFUND','ADJUSTMENT')
             AND (expires_at IS NULL OR expires_at > NOW())
        THEN credits
        WHEN transaction_type IN ('DEDUCTION','EXPIRY')
        THEN credits  -- negative
        ELSE 0
    END) AS available_credits,
    SUM(CASE WHEN transaction_type = 'RESERVATION' THEN ABS(credits) ELSE 0 END) AS reserved_credits,
    SUM(CASE WHEN transaction_type = 'DEDUCTION' THEN ABS(credits) ELSE 0 END) AS total_used_credits,
    SUM(CASE WHEN transaction_type = 'EXPIRY' THEN ABS(credits) ELSE 0 END) AS expired_credits
FROM credit_transactions
GROUP BY tenant_id;
```

---

## 3. Credit Cost Table (Complete)

### Standard Tasks
| Task | Credits | USD | Margin Target |
|---|---|---|---|
| GL/TB Reconciliation (per entity) | 5 | $0.50 | 90% |
| Consolidation (1 entity) | 3 | $0.30 | 88% |
| Consolidation (5+ entities) | 10 | $1.00 | 85% |
| AI Query (simple — local model) | 2 | $0.20 | 95% |
| AI Query (complex — cloud model) | 8 | $0.80 | 82% |
| Upload + Process Paysheet | 5 | $0.50 | 90% |
| ERP Sync (on-demand) | 10 | $1.00 | 85% |
| Upload + Parse Contract (AI) | 8 | $0.80 | 82% |
| Covenant Compliance Computation | 5 | $0.50 | 90% |
| Forecast (3 scenarios) | 15 | $1.50 | 83% |
| Variance Analysis (AI commentary) | 12 | $1.20 | 83% |
| Revenue Recognition Run | 8 | $0.80 | 85% |
| Month-End PDF Pack | 25 | $2.50 | 82% |
| Board Pack Generation | 30 | $3.00 | 82% |
| Standards Query (cross-LLM) | 15 | $1.50 | 80% |
| MIS Backward Propagation | 20 | $2.00 | 84% |
| Run PPA Computation | 1,500 | $150.00 | 92% |
| FDD Report (basic) | 1,000 | $100.00 | 88% |
| FDD Report (comprehensive) | 2,500 | $250.00 | 90% |
| M&A Workspace Setup | 500 | $50.00 | 88% |
| Valuation Engine (full DCF + comps) | 500 | $50.00 | 87% |
| DD Tracker Setup | 200 | $20.00 | 85% |

### Zero-Credit Tasks (Always Free)
```
Reading/viewing any existing data
Downloading previously generated reports
Viewing dashboard and charts
Searching (global search)
Viewing audit trail
Managing users and settings
Viewing reconciliation breaks (already identified)
Reading news and events tab
Viewing compliance calendar
```

---

## 4. Subscription Tiers

### Tier Definitions
| Tier | Monthly Credits | Monthly Price | Annual Price | Per Credit |
|---|---|---|---|---|
| Starter | 500 | $49 | $490 (save $98) | $0.098 |
| Professional | 2,000 | $149 | $1,490 (save $298) | $0.075 |
| Business | 8,000 | $449 | $4,490 (save $898) | $0.056 |
| Enterprise | Custom | Negotiated | Negotiated | ≤$0.050 |

### What Each Tier Enables (Features)
```
STARTER ($49/month)
├── 1 organisation
├── 5 users
├── Core modules only (MIS, TB, Reconciliation, Consolidation, Reporting)
├── 2 ERP connectors
├── 1 cloud storage connection
└── Email support

PROFESSIONAL ($149/month)
├── Up to 10 organisations (or CA Firm: up to 10 clients)
├── 25 users
├── All core modules + FAR, Leases, RevRec, Paysheets, Contracts
├── All 7 ERP connectors
├── All cloud storage connections
├── FDD and PPA modules (credit-based)
├── Compliance calendar
└── Priority support

BUSINESS ($449/month)
├── Up to 50 organisations
├── Unlimited users
├── All modules including M&A Workspace
├── Advanced analytics and custom reports
├── White label option
├── API access (developer webhooks)
├── Dedicated account manager
└── SLA: 99.9% uptime

ENTERPRISE (Custom)
├── Unlimited organisations
├── Unlimited users
├── All modules
├── Dedicated infrastructure option
├── Custom integrations
├── SOC2 evidence package on request
├── SLA: 99.95% uptime
├── 24/7 support
└── Custom credit rollover policy
```

### Credit Rollover Policy
```
Standard (Starter, Professional, Business):
- Unused credits roll over for 3 calendar months
- Example: January allocation expires at end of April
- Celery Beat runs on 1st of every month → expires credits >3 months old
- Expired credits shown in dashboard (greyed out, for transparency)

Enterprise:
- Custom rollover period (typically 6-12 months)
- Negotiated in contract
```

---

## 5. Top-Up Packages

| Package | Credits | Price | Per Credit | Discount vs Starter |
|---|---|---|---|---|
| Small | 500 | $45 | $0.090 | 8% cheaper than Starter per-credit |
| Medium | 2,000 | $160 | $0.080 | 18% cheaper |
| Large | 5,000 | $350 | $0.070 | 29% cheaper |
| Bulk | 20,000 | $1,200 | $0.060 | 39% cheaper |

**Pricing note:** Top-up per-credit rates are always slightly worse than subscription.
This incentivises subscription (predictable revenue) while allowing à la carte use.

---

## 6. Payment Gateway Integration

### Gateway Routing Logic
```python
GATEWAY_ROUTING = {
    "IN": "razorpay",           # India
    "AE": "telr",               # UAE
    "SA": "telr",               # Saudi Arabia
    "BH": "telr",               # Bahrain
    "KW": "telr",               # Kuwait
    "OM": "telr",               # Oman
    "QA": "telr",               # Qatar
    # All other countries → Stripe
}

def get_gateway(tenant_country_code: str) -> str:
    return GATEWAY_ROUTING.get(tenant_country_code, "stripe")
```

### Stripe Integration
```
Supported: USA, UK, Australia, Singapore, UAE, and 135+ countries
Products used:
  - Stripe Billing (subscriptions)
  - Stripe Checkout (one-time top-ups)
  - Stripe Connect (marketplace payouts to contributors)
  - Stripe Webhooks (payment confirmation)

Key webhooks to handle:
  invoice.payment_succeeded  → allocate subscription credits
  invoice.payment_failed     → send payment failure email, grace period
  checkout.session.completed → allocate top-up credits
  customer.subscription.deleted → downgrade tenant, stop allocations
```

### Razorpay Integration
```
Supported: India
Payment methods: UPI, Netbanking, Cards (Visa/MC/Rupay), Wallets, EMI, NEFT/RTGS
Products used:
  - Razorpay Subscriptions (recurring billing)
  - Razorpay Orders (one-time top-ups)
  - Razorpay Webhooks

Key webhooks:
  subscription.charged       → allocate subscription credits
  payment.captured           → allocate top-up credits (after order verify)
  subscription.cancelled     → downgrade tenant

Important: Razorpay requires payment signature verification
  verify_signature(razorpay_payment_id, razorpay_order_id, razorpay_signature)
```

### Telr Integration
```
Supported: UAE, Saudi Arabia, Bahrain, Kuwait, Oman, Qatar
Products used:
  - Telr Hosted Payment Page
  - Telr IPN (Instant Payment Notification — their webhook equivalent)

Key IPN events:
  auth   → payment authorised (not yet captured)
  sale   → payment captured → allocate credits
  void   → payment cancelled
  refund → credits to be refunded
```

### Payment Abstraction Layer
```python
# backend/payments/gateway.py

class PaymentGateway(ABC):
    @abstractmethod
    async def create_subscription(
        self, tenant_id: str, tier: str, annual: bool
    ) -> SubscriptionResult:
        pass

    @abstractmethod
    async def create_topup_order(
        self, tenant_id: str, package: str, amount: float, currency: str
    ) -> OrderResult:
        pass

    @abstractmethod
    async def verify_payment(
        self, payment_data: dict
    ) -> PaymentVerificationResult:
        pass

    @abstractmethod
    async def handle_webhook(
        self, payload: bytes, headers: dict
    ) -> WebhookEvent:
        pass

    @abstractmethod
    async def cancel_subscription(
        self, subscription_id: str
    ) -> bool:
        pass


class PaymentService:
    def __init__(self):
        self.gateways = {
            "stripe": StripeGateway(),
            "razorpay": RazorpayGateway(),
            "telr": TelrGateway(),
        }

    def get_gateway(self, tenant_country: str) -> PaymentGateway:
        gateway_name = GATEWAY_ROUTING.get(tenant_country, "stripe")
        return self.gateways[gateway_name]
```

---

## 7. Webhook Security

### All Webhooks Must Be Verified
```python
# Stripe webhook verification
stripe.WebhookSignature.verify_header(
    payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
)

# Razorpay signature verification
razorpay_client.utility.verify_webhook_signature(
    payload, signature, settings.RAZORPAY_WEBHOOK_SECRET
)

# Telr: verify using shared secret in IPN payload
# Check IP whitelist (Telr IPN IPs)

# All webhooks:
# - Verify before processing
# - Idempotency: check if webhook already processed (store event_id)
# - Respond 200 immediately, process async via Celery
# - Failed processing: DLQ, retry, alert platform team
```

---

## 8. Margin Monitoring

### Per-Tenant Cost Attribution
```
Every month, for each tenant, compute:
├── Subscription revenue + top-up revenue = Total Revenue
├── AI cost: sum of AI Gateway cost logs per tenant
├── Compute cost: estimate from Railway metrics per tenant
│   (allocated by request count / compute time)
├── Storage cost: Cloudflare R2 storage + egress per tenant
└── Payment gateway fees: 2.9% + $0.30 per Stripe transaction
                          2% Razorpay, 2.5% Telr

Gross Margin = (Revenue - Direct Costs) / Revenue

Alert: if any tenant margin < 65% → investigate and adjust
```

### Platform-Level Margin Dashboard
```
PLATFORM ECONOMICS (Founder Dashboard)

This Month:
  Total Revenue:           $24,890
  AI Costs:                $2,340   (9.4%)
  Compute Costs:           $1,890   (7.6%)
  Storage Costs:             $340   (1.4%)
  Payment Fees:              $720   (2.9%)
  ──────────────────────────────────
  Total COGS:              $5,290   (21.2%)
  Gross Profit:           $19,600   (78.8%) ✅

Top Cost Tenants:
  Tenant A (heavy FDD usage):  $890 cost, $4,200 revenue, 78.8% margin ✅
  Tenant B (many AI queries):  $340 cost, $1,490 revenue, 77.2% margin ✅

⚠️ Margin Alert: None this month
```

---

## 9. Billing & Invoicing

### Invoice Generation
```
Monthly invoices auto-generated:
├── Subscription charge (fixed)
├── Top-up charges (variable, per transaction)
├── Credits consumed (informational)
├── Credit balance (closing)
└── PDF invoice (WeasyPrint, professional format)

Invoice delivery:
├── Email to billing contact on payment
├── Available in-app under Billing → Invoices
└── Downloadable PDF

GST/VAT handling:
├── India tenants: GST invoice (18% GST, tenant's GSTIN captured)
├── UAE tenants: VAT invoice (5% VAT)
├── Other countries: depends on local rules
└── Tax calculation via TaxJar API (or manual rate table)
```

### Failed Payment Handling (Dunning)
```
Day 0:   Payment fails → email to billing contact
Day 3:   Retry payment → if fails, second email with update link
Day 7:   Retry payment → if fails, credit allocation paused
         (existing credits still usable, no new allocation)
Day 14:  Final retry → if fails, account suspended (read-only)
Day 30:  Data retention period → Finance Leader notified
Day 60:  Account scheduled for deletion (with 30-day warning)

Grace period credits:
  During dunning period (Day 0-14): tenant keeps existing credits
  After Day 14: no new task runs, read-only access only
```

---

## 10. Marketplace Revenue Share (Payments)

### Contributor Payouts via Stripe Connect
```
Marketplace sale occurs:
  Buyer purchases template for $29
  Platform takes 30% = $8.70
  Contributor receives 70% = $20.30

Payout schedule:
  Monthly payouts (1st of each month)
  Minimum payout threshold: $50 (below threshold: carries over)
  Payment method: Stripe Connect → contributor's bank account
  International: Stripe Connect supports 40+ countries

For India contributors:
  Razorpay Route (payouts API) for INR payouts
  Or contributor connects Stripe account (if available)
```

---

## 11. Credits Dashboard — Frontend Specification

### Component: CreditWidget (top navigation bar, compact)
```tsx
// Always visible, real-time, WebSocket updated
<CreditWidget>
  [Credits icon] 1,847 credits  [↑ Buy]
</CreditWidget>

// Click expands to:
Available:    1,847
Reserved:        45 (3 tasks running)
Expires soon:   200 (28 days)
[View Details] [Buy Credits]
```

### Page: /billing/credits (full credits dashboard)
```
SECTIONS:
1. Credit Balance Card (large, prominent)
   - Available, Reserved, Used This Month, Expiring Soon
   - Visual bar showing % of monthly allocation used

2. Usage Breakdown Table
   - Columns: Task, Date, Credits Used, Status, Org
   - Filterable by: date range, module, org, task type
   - Exportable to Excel

3. Credit History Chart
   - 6-month bar chart: allocated vs used vs expired per month
   - Recharts bar chart, clean design

4. Alerts Section
   - Current alert threshold setting
   - Edit threshold
   - Test alert button

5. Quick Top-Up Panel
   - 4 package cards
   - Current balance context ("500 credits = ~20 more reconciliations")
   - [Buy Now] → payment flow
```

### Task Run Button States
```tsx
// When credits available
<Button onClick={runTask}>
  Run Consolidation  [5 credits]
</Button>

// When credits insufficient
<Tooltip content="Insufficient credits — you need 5 credits but have 2. Top up to continue.">
  <Button disabled>
    Run Consolidation  [5 credits]
  </Button>
</Tooltip>

// When task is running (credits reserved)
<Button loading>
  Running... [5 credits reserved]
  [Cancel — release credits]
</Button>

// When task complete
<Button variant="success">
  ✓ Complete  [5 credits used]
</Button>
```

---

## 12. User Value Proposition Summary

### What Users Get for Their Money

| User Type | Monthly Spend | Hours Saved | Labour Value Replaced | ROI |
|---|---|---|---|---|
| Solo CA / Small firm (3 clients) | $49 (Starter) | 50 hrs/month | $2,500 | 51x |
| CA Firm (10 clients) | $149 (Professional) | 200 hrs/month | $10,000 | 67x |
| Corporate CFO (5 entities) | $149 (Professional) | 80 hrs/month | $4,000 | 27x |
| Large Group CFO (20 entities) | $449 (Business) | 300 hrs/month | $15,000 | 33x |
| M&A / FDD (one deal) | $400 top-up | 300 hrs | $150,000+ | 375x |

### Positioning Statement
```
"Enterprise-grade financial operations at 1/50th the cost of alternatives.
 Every task AI-validated. Every number traceable. Every output auditable.
 Built by a finance professional, for finance professionals."
```

---

*End of Credits & Payments Master v1.0*
