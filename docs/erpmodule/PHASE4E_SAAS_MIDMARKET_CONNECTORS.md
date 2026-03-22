# FinanceOps — Phase 4E: SaaS Cloud + Mid-Market + Payments + Payroll Connectors
## Claude Code Implementation Prompt — v1 (Final)

> Prerequisite: Phase 4D complete, zero test failures.
> Paste this entire prompt into Claude Code. Do not modify it.
> This phase is purely additive. Canonical kernel is frozen. Do not touch it.

---

## WHO YOU ARE AND WHERE YOU ARE

You are Claude Code working inside the FinanceOps repository at `D:\finos\`.

**What Phase 4E delivers:**
Implementation of 15 stub connectors across four categories:

SaaS Cloud ERPs (4):
- QuickBooks Online
- Xero
- FreshBooks
- Wave

Mid-Market ERPs (4):
- NetSuite
- Odoo
- Sage (multi-variant)
- Microsoft Dynamics 365

Payments / Banking (4):
- Razorpay
- Stripe
- RBI Account Aggregator Framework
- Plaid

Payroll / HR (3):
- Keka
- Darwinbox
- Razorpay Payroll

**Permitted file changes:**
- Each connector's own file
- `infrastructure/connectors/registry.py` — capability status only
- `tests/` — new test files only
- `docs/` — documentation

**Not permitted to change:**
- Any canonical schema
- Any application service
- Any model or migration
- Any enum
- Any frozen engine (phases 0–3)

---

## STEP 0 — CONFIRM PHASE 4D IS COMPLETE

```bash
pytest tests/ -x -q
# Must show zero failures
```

Read before writing:
```
D:\finos\financeops\modules\erp_sync\infrastructure\connectors\base.py
D:\finos\financeops\modules\erp_sync\domain\canonical\
```

---

## IMPLEMENTATION ORDER

Build and pass tests one connector at a time in this order.

---

## CONNECTOR 1 — QUICKBOOKS ONLINE

File: `infrastructure/connectors/quickbooks.py`

Protocol: Intuit QuickBooks Online API v3 (REST/JSON)
Auth: OAuth2 — `client_id`, `client_secret`, `refresh_token`, `realm_id`

Supported datasets:
```
CHART_OF_ACCOUNTS, TRIAL_BALANCE, GENERAL_LEDGER, PROFIT_AND_LOSS, BALANCE_SHEET,
ACCOUNTS_RECEIVABLE, ACCOUNTS_PAYABLE, AR_AGEING, AP_AGEING,
INVOICE_REGISTER, PURCHASE_REGISTER, CREDIT_NOTE_REGISTER,
BANK_STATEMENT, VENDOR_MASTER, CUSTOMER_MASTER, CURRENCY_MASTER
```

Implementation:
- Token refresh via `https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer`
- Report-based endpoints for TB, P&L, BS (Intuit has dedicated report endpoints)
- Query-based endpoints using Intuit Query Language (IQL) for transactional data
- Pagination: `startPosition` + `maxResults` (max 1000 per request)
- `supports_resumable_extraction: True` — checkpoint `{"startPosition": N}`
- Rate limiting: 500 requests/minute per company — exponential backoff on 429
- `erp_control_totals`: from Intuit's report summary rows for TB and BS
- Sandbox support: `use_sandbox: bool` credential field for testing

---

## CONNECTOR 2 — XERO

File: `infrastructure/connectors/xero.py`

Protocol: Xero API v2 (REST/JSON)
Auth: OAuth2 — `client_id`, `client_secret`, `refresh_token`, `tenant_id`

Supported datasets:
```
CHART_OF_ACCOUNTS, TRIAL_BALANCE, GENERAL_LEDGER, PROFIT_AND_LOSS, BALANCE_SHEET,
ACCOUNTS_RECEIVABLE, ACCOUNTS_PAYABLE,
INVOICE_REGISTER, PURCHASE_REGISTER, CREDIT_NOTE_REGISTER, DEBIT_NOTE_REGISTER,
BANK_STATEMENT, VENDOR_MASTER, CUSTOMER_MASTER, CURRENCY_MASTER
```

Implementation:
- `Xero-Tenant-Id` header required on every request
- Rate limiting: 60 calls/minute — exponential backoff on 429
- Xero uses `page` parameter — max 100 records per page
- `supports_resumable_extraction: True` — checkpoint `{"page": N}`
- Xero returns report data in a nested structure — flatten to raw_data dict
- `erp_control_totals`: Xero's TrialBalance report has summary rows

---

## CONNECTOR 3 — FRESHBOOKS

File: `infrastructure/connectors/freshbooks.py`

Protocol: FreshBooks API v3 (REST/JSON)
Auth: OAuth2 — `client_id`, `client_secret`, `refresh_token`, `account_id`

Supported datasets:
```
CHART_OF_ACCOUNTS, ACCOUNTS_RECEIVABLE, INVOICE_REGISTER,
EXPENSE_CLAIMS, CUSTOMER_MASTER
```

Implementation:
- FreshBooks has a limited API — only the above dataset types are extractable
- `supports_resumable_extraction: True` — FreshBooks uses `page` parameter
- Checkpoint: `{"page": N}`
- Rate limiting: respect `X-RateLimit-Limit` / `X-RateLimit-Reset` response headers

---

## CONNECTOR 4 — WAVE ACCOUNTING

File: `infrastructure/connectors/wave.py`

Protocol: Wave GraphQL API
Auth: OAuth2 — `client_id`, `client_secret`, `access_token`

Supported datasets:
```
CHART_OF_ACCOUNTS, TRIAL_BALANCE, PROFIT_AND_LOSS, BALANCE_SHEET,
ACCOUNTS_RECEIVABLE, INVOICE_REGISTER, CUSTOMER_MASTER
```

Implementation:
- All requests via GraphQL POST to `https://gql.waveapps.com/graphql/public`
- Build GraphQL query per dataset type
- `supports_resumable_extraction: True` — Wave uses cursor-based pagination
- Checkpoint: `{"after_cursor": "..."}`
- Wave's free tier has API rate limits — implement backoff on 429

---

## CONNECTOR 5 — ORACLE NETSUITE

File: `infrastructure/connectors/netsuite.py`

Protocol: NetSuite REST API + SuiteQL
Auth: Token-Based Authentication (TBA) — `account_id`, `consumer_key`, `consumer_secret`, `token_id`, `token_secret`

Supported datasets: All 42 active dataset types

Implementation:
- SuiteQL for transactional data: `POST /services/rest/query/v1/suiteql`
- REST API for record-based data (vendors, customers, COA)
- OAuth1 signing required on every request
- SuiteQL supports OFFSET/LIMIT — `supports_resumable_extraction: True`
- Checkpoint: `{"offset": N, "page_size": 1000}`
- NetSuite has per-account API limits — log limit usage from response headers
- For large datasets (GL, invoices): use date-range sub-queries to manage response size
- `erp_control_totals`: NetSuite's TrialBalanceSummary saved search

---

## CONNECTOR 6 — ODOO

File: `infrastructure/connectors/odoo.py`

Protocol: Odoo JSON-RPC API
Auth: `url`, `database`, `username`, `api_key` (or password for older versions)

Supported datasets:
```
CHART_OF_ACCOUNTS, TRIAL_BALANCE, GENERAL_LEDGER, PROFIT_AND_LOSS, BALANCE_SHEET,
ACCOUNTS_RECEIVABLE, ACCOUNTS_PAYABLE,
INVOICE_REGISTER, PURCHASE_REGISTER, CREDIT_NOTE_REGISTER, DEBIT_NOTE_REGISTER,
INVENTORY_REGISTER, VENDOR_MASTER, CUSTOMER_MASTER, CURRENCY_MASTER
```

Implementation:
- JSON-RPC calls to `/web/dataset/call_kw`
- Auth via `/web/session/authenticate` — session token stored in extraction scope
- Odoo uses `domain` filters + `fields` + `limit`/`offset` for pagination
- `supports_resumable_extraction: True` — checkpoint `{"offset": N}`
- Support Odoo versions 14, 15, 16, 17 — note version in `connector_version` field
- `erp_control_totals`: call `account.move.line` aggregation for TB totals

---

## CONNECTOR 7 — SAGE (MULTI-VARIANT)

File: `infrastructure/connectors/sage.py`

Sage has multiple products. Support via `sage_product` credential field:
- `SAGE_BUSINESS_CLOUD` — Sage Business Cloud Accounting API
- `SAGE_INTACCT` — Sage Intacct Web Services API

### Sage Business Cloud
Protocol: REST/JSON — `https://api.accounting.sage.com/v3.1`
Auth: OAuth2

Supported datasets:
```
CHART_OF_ACCOUNTS, TRIAL_BALANCE, PROFIT_AND_LOSS, BALANCE_SHEET,
ACCOUNTS_RECEIVABLE, ACCOUNTS_PAYABLE,
INVOICE_REGISTER, PURCHASE_REGISTER, BANK_STATEMENT,
VENDOR_MASTER, CUSTOMER_MASTER
```

### Sage Intacct
Protocol: XML Web Services — `https://api.intacct.com/ia/xml/xmlgw.phtml`
Auth: `company_id`, `user_id`, `user_password`, `sender_id`, `sender_password`

Supported datasets:
```
CHART_OF_ACCOUNTS, TRIAL_BALANCE, GENERAL_LEDGER, PROFIT_AND_LOSS, BALANCE_SHEET,
ACCOUNTS_RECEIVABLE, ACCOUNTS_PAYABLE, AR_AGEING, AP_AGEING,
INVOICE_REGISTER, PURCHASE_REGISTER, VENDOR_MASTER, CUSTOMER_MASTER
```

Implementation:
- Route all calls based on `sage_product` credential field
- Sage Business Cloud: `supports_resumable_extraction: True` — `$next` cursor pagination
- Sage Intacct: XML-based pagination using `pagesize` + `offset`
- `erp_control_totals`: available from both variants

---

## CONNECTOR 8 — MICROSOFT DYNAMICS 365

File: `infrastructure/connectors/dynamics365.py`

Protocol: OData REST API
Auth: Azure AD OAuth2 — `tenant_id` (Azure), `client_id`, `client_secret`, `environment_url`

Support via `dynamics_product` credential field:
- `BUSINESS_CENTRAL` — Dynamics 365 Business Central
- `FINANCE_OPERATIONS` — Dynamics 365 Finance & Operations

Supported datasets:
```
CHART_OF_ACCOUNTS, TRIAL_BALANCE, GENERAL_LEDGER, PROFIT_AND_LOSS, BALANCE_SHEET,
ACCOUNTS_RECEIVABLE, ACCOUNTS_PAYABLE, AR_AGEING, AP_AGEING,
INVOICE_REGISTER, PURCHASE_REGISTER,
BANK_STATEMENT, FIXED_ASSET_REGISTER,
VENDOR_MASTER, CUSTOMER_MASTER, CURRENCY_MASTER
```

Implementation:
- OData `$top`/`$skip` pagination — max 1000 per request
- `supports_resumable_extraction: True` — checkpoint `{"skip": N}`
- Token refresh against Azure AD token endpoint
- Business Central API version: v2.0 (stable)
- Finance & Operations: use Data Management Framework entities
- `erp_control_totals`: available from BC's TrialBalance API entity

---

## CONNECTOR 9 — RAZORPAY

File: `infrastructure/connectors/razorpay.py`

Protocol: Razorpay REST API v1
Auth: `key_id`, `key_secret` (Basic auth)

Supported datasets:
```
BANK_STATEMENT, BANK_TRANSACTION_REGISTER,
INVOICE_REGISTER, ACCOUNTS_RECEIVABLE
```

Notes:
- BANK_STATEMENT: map from Razorpay settlements data
- BANK_TRANSACTION_REGISTER: map from payments, refunds, transfers
- INVOICE_REGISTER: map from Razorpay payment links / invoices
- `supports_resumable_extraction: True` — cursor pagination via `from`/`to` timestamps
- Checkpoint: `{"from_timestamp": N, "last_id": "..."}`
- `erp_control_totals`: total settled amount for period
- Rate limiting: 500 requests/minute — respect `X-RateLimit-*` headers
- Amounts in Razorpay are in paise (1/100 INR) — convert to INR `Decimal` in raw_data

---

## CONNECTOR 10 — STRIPE

File: `infrastructure/connectors/stripe.py`

Protocol: Stripe API v1 (REST)
Auth: `secret_key`

Supported datasets:
```
BANK_STATEMENT, BANK_TRANSACTION_REGISTER,
INVOICE_REGISTER, ACCOUNTS_RECEIVABLE
```

Notes:
- BANK_STATEMENT: map from Stripe payouts
- BANK_TRANSACTION_REGISTER: map from charges, refunds, disputes
- `supports_resumable_extraction: True` — cursor pagination via `starting_after`
- Checkpoint: `{"starting_after": "ch_xxxxx"}`
- Amounts in Stripe are in smallest currency unit — convert correctly per currency
- `erp_control_totals`: total payout amount for period

---

## CONNECTOR 11 — RBI ACCOUNT AGGREGATOR FRAMEWORK

File: `infrastructure/connectors/aa_framework.py`

Protocol: Account Aggregator (AA) ecosystem API (RBI-regulated, India)
This is the most compliance-heavy connector in Phase 4E.

Auth:
```
aa_handle           str     Account Aggregator handle (e.g. "finvu", "onemoney")
client_id           str     FIU client ID registered with AA ecosystem
client_secret       str
fip_id              str     Financial Information Provider ID
consent_artefact    str     AA consent artefact (obtained via customer consent flow)
```

Supported datasets:
```
BANK_STATEMENT, BANK_TRANSACTION_REGISTER
```

Implementation:
- Consent artefact must be stored in `ExternalConnection.external_metadata` JSONB
  (not in credentials — it is not a secret, it is a compliance artefact)
- Flow: use consent artefact → call FIP data endpoint → receive encrypted FI data
- Decrypt FI data using AA ecosystem keys (documented in AA API spec)
- `supports_resumable_extraction: False` — AA returns data in one response per consent
- Artefact expiry: check consent artefact expiry before extraction — if expired, fail with
  `ConsentExpiredError` and require customer to re-consent

Special requirement: log consent artefact ID in `ExternalDataConsentLog` for every extraction.

---

## CONNECTOR 12 — PLAID

File: `infrastructure/connectors/plaid.py`

Protocol: Plaid API v2
Auth: `access_token` per institution link, `client_id`, `secret`, `environment` (sandbox/development/production)

Supported datasets:
```
BANK_STATEMENT, BANK_TRANSACTION_REGISTER
```

Implementation:
- `supports_resumable_extraction: True` — Plaid cursor-based sync
- Checkpoint: `{"cursor": "..."}`
- Use `/transactions/sync` endpoint (Plaid's incremental sync)
- Map Plaid transaction categories to `transaction_type` field
- `erp_control_totals`: account balance from `/accounts/balance/get`

---

## CONNECTOR 13 — KEKA HR

File: `infrastructure/connectors/keka.py`

Protocol: Keka HR REST API
Auth: `client_id`, `client_secret`, `scope` (OAuth2 client credentials)

Supported datasets:
```
PAYROLL_SUMMARY, EXPENSE_CLAIMS, STAFF_ADVANCES
```

Implementation:
- OAuth2 client credentials flow — no user login required
- `supports_resumable_extraction: True` — `page`/`pageSize` pagination
- Payroll data: monthly payroll runs → map to `CanonicalPayrollSummary`
- Expense claims: approved claims → map to `CanonicalExpenseClaimsRegister`

---

## CONNECTOR 14 — DARWINBOX

File: `infrastructure/connectors/darwinbox.py`

Protocol: Darwinbox REST API
Auth: `api_key`, `base_url` (varies by customer deployment)

Supported datasets:
```
PAYROLL_SUMMARY, EXPENSE_CLAIMS, STAFF_ADVANCES
```

Implementation:
- API key passed as `x-api-key` header
- `supports_resumable_extraction: True`
- Same canonical mapping pattern as Keka

---

## CONNECTOR 15 — RAZORPAY PAYROLL

File: `infrastructure/connectors/razorpay_payroll.py`

Protocol: Razorpay Payroll API (separate from Razorpay Payments API)
Auth: `key_id`, `key_secret` (same credential type as Razorpay payments — but may be different keys)

Supported datasets:
```
PAYROLL_SUMMARY, STAFF_ADVANCES
```

Implementation:
- Same Basic auth pattern as Razorpay payments connector
- Payroll data: salary components → map to `CanonicalPayrollSummary`
- `supports_resumable_extraction: False` — payroll data returned per month

---

## STEP 1 — DEPENDENCIES

Add to `pyproject.toml` if not already present:
```toml
# No new major dependencies required for this phase
# All connectors use async httpx (already present) or lxml (added in 4D)
# Plaid: use httpx directly — do not use plaid-python SDK (adds too many deps)
# OAuth1 for NetSuite: use authlib
authlib = ">=1.3,<2.0"
```

---

## STEP 2 — TESTS

Build one test file per connector. All mock HTTP calls — no real API credentials.
Create fixture files in `tests/fixtures/connectors/[connector_name]/`.

```
tests/unit/erp_sync/connectors/
  test_quickbooks_connector.py
  test_xero_connector.py
  test_freshbooks_connector.py
  test_wave_connector.py
  test_netsuite_connector.py
  test_odoo_connector.py
  test_sage_connector.py          # both SAGE_BUSINESS_CLOUD and SAGE_INTACCT
  test_dynamics365_connector.py   # both BUSINESS_CENTRAL and FINANCE_OPERATIONS
  test_razorpay_connector.py
  test_stripe_connector.py
  test_aa_framework_connector.py
  test_plaid_connector.py
  test_keka_connector.py
  test_darwinbox_connector.py
  test_razorpay_payroll_connector.py

tests/integration/erp_sync/connectors/
  # One integration test per connector — full flow: scope → raw → canonical → validation
  test_quickbooks_integration.py
  test_xero_integration.py
  test_freshbooks_integration.py
  test_wave_integration.py
  test_netsuite_integration.py
  test_odoo_integration.py
  test_sage_integration.py
  test_dynamics365_integration.py
  test_razorpay_integration.py
  test_stripe_integration.py
  test_aa_framework_integration.py
  test_plaid_integration.py
  test_keka_integration.py
  test_darwinbox_integration.py
  test_razorpay_payroll_integration.py
```

Each unit test must cover:
- Correct dataset types supported (supported → returns `RawPayload`; unsupported → raises `ConnectorCapabilityNotSupported`)
- Pagination / checkpoint handling
- Token refresh / auth failure handling
- Amount conversion (paise → INR for Razorpay; smallest unit for Stripe; etc.)
- `erp_control_totals` extraction where supported
- Resumable extraction checkpoint round-trip

---

## DEFINITION OF DONE

- [ ] All 15 connectors implemented and `implementation_status = LIVE`
- [ ] All 15 connectors declare accurate `supported_datasets` and `supports_resumable_extraction`
- [ ] OAuth2 token refresh working in QuickBooks, Xero, FreshBooks, Wave, Sage BC, Dynamics
- [ ] OAuth1 (TBA) signing working in NetSuite
- [ ] Sage multi-variant routing (SAGE_BUSINESS_CLOUD / SAGE_INTACCT) working
- [ ] Dynamics 365 multi-variant routing (BUSINESS_CENTRAL / FINANCE_OPERATIONS) working
- [ ] AA Framework consent artefact logged in `ExternalDataConsentLog`
- [ ] Razorpay paise → INR conversion correct
- [ ] Stripe smallest-unit → currency conversion correct
- [ ] `authlib` added to `pyproject.toml`
- [ ] All 30 new test files passing (15 unit + 15 integration)
- [ ] All Phase 4D tests still passing
- [ ] All prior phase tests still passing
- [ ] `pytest` zero failures
- [ ] Grep: no source system name in any frozen engine
- [ ] Grep: no raw credential in any log or JSONB

---

## CRITICAL RULES

- Python 3.11 only
- `async def` everywhere
- `Decimal` not `float`
- No changes to canonical schemas, models, migrations, or frozen engines
- No UPDATE / DELETE on financial tables
- All secrets from `.env`
- `WindowsSelectorEventLoopPolicy()` stays untouched
- `asyncio_default_test_loop_scope = "session"` stays untouched
- Run `pytest` after each connector — zero failures throughout

---

*15 connectors. Zero kernel changes. Then open Phase 4F.*
