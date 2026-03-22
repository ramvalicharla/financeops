# FinanceOps — Phase 4C: ERP Sync Kernel
## Claude Code Implementation Prompt — v1 (Final)

> Prerequisite: Phase 4B complete, zero test failures.
> Paste this entire prompt into Claude Code. Do not modify it.
> This is the permanent architectural core of the entire ERP integration layer.
> Everything built here is frozen after this phase. Connectors added later never touch it.

---

## WHO YOU ARE AND WHERE YOU ARE

You are Claude Code working inside the FinanceOps repository at `D:\finos\`.

**What Phase 4C delivers:**
- The complete `erp_sync` module structure
- All 46 canonical dataset schemas (Pydantic only — permanent contract)
- All enum declarations: 23 `ConnectorType` values, 46 `DatasetType` values
- The `AbstractConnector` framework with all extract methods
- The connector registry with all 23 connectors registered
- Two fully implemented live connectors: `GENERIC_FILE` and `ZOHO`
- All 21 remaining connectors as clean stubs (raise `ConnectorCapabilityNotSupported`)
- Full sync engine: extract → freeze → hash → validate → drift → health → period lock → publish
- Migration numbered correctly from live `alembic heads` output

**What Phase 4C deliberately does NOT deliver:**
- Implementations for connectors 3–23 (Phase 4D, 4E, 4F)
- GSTR-9, GSTR-9C, FORM_26AS, AIS_REGISTER canonical schemas (Phase 4F)
  — their `DatasetType` enum values ARE declared here as stubs so no future migration needed

**The proving path inside this phase:**
Build and test in this exact order before expanding:
1. Canonical schemas + enums (all declared)
2. AbstractConnector + registry + all 21 stubs
3. Models + migration
4. `GENERIC_FILE` connector — fully live
5. Core sync pipeline using Generic File: COA → Trial Balance → General Ledger
6. Drift engine, period lock, health engine, publish governance
7. `ZOHO` connector — fully live for 15 dataset types
8. Full test suite

Do not proceed to step N+1 until step N has zero test failures.

---

## STEP 0 — READ EVERYTHING BEFORE WRITING ANYTHING

**Specification documents:**
```
D:\finos\docs\platform\01_MASTER_BLUEPRINT.md
D:\finos\docs\platform\02_IMPLEMENTATION_PLAN.md
D:\finos\docs\platform\03_FRONTEND_BACKEND_INTEGRATION.md
D:\finos\docs\platform\04_ERROR_LEDGER.md
D:\finos\docs\platform\05_USER_MANUAL.md
D:\finos\docs\platform\06_CREDITS_AND_PAYMENTS.md
D:\finos\docs\platform\07_BUSINESS_MODEL_AND_PRICING.md
D:\finos\docs\platform\08_TELEMETRY_SCALABILITY_METRICS.md
D:\finos\docs\platform\09_HR_SALES_ENTERPRISE_OS.md
```

**Existing codebase:**
```
D:\finos\backend\
D:\finos\financeops\
D:\finos\financeops\modules\
D:\finos\financeops\platform\
D:\finos\financeops\shared_kernel\
D:\finos\alembic\versions\
D:\finos\tests\
D:\finos\pyproject.toml
D:\finos\KNOWN_ISSUES.md
```

**Run before writing anything:**
```bash
alembic heads
```

State the current head filename. Your migration file must use the next sequential
number. Do NOT hardcode `0026` — use the actual live number.

**Confirm all 16 patterns before writing code:**
1. DDD module structure (api / application / domain / infrastructure / policies)
2. Append-only enforcement (`db/append_only.py`)
3. RLS + FORCE RLS on every financial table
4. Supersession pattern
5. Deterministic run token pattern
6. Chain hash integrity (`chain_hash` + `previous_hash`)
7. Control plane module registration (`CpModuleRegistry`, `CpTenantModuleEnablement`)
8. Control plane authorizer chain
9. MIS upload / airlock / storage pattern
10. `CpOrganisation` / `CpEntity` / `CpTenant` hierarchy
11. Currency and reporting period modeling
12. Six-dimensional test pattern (`_api_`, `_append_only_`, `_determinism_`, `_isolation_`, `_rls_`, `_supersession_`)
13. `.env` / AES-256-GCM secret pattern
14. `CpWorkflowApproval` pattern
15. `ApiResponse[T]` envelope from Phase 4B — wrap ALL endpoint responses
16. Idempotency key middleware from Phase 4B — apply to required POST endpoints

Stop and report `PATTERN NOT FOUND: [name]` if any cannot be located.

---

## STEP 1 — MODULE STRUCTURE

`D:\finos\financeops\modules\erp_sync\`

```
financeops/modules/erp_sync/
│
├── api/
│   ├── connections.py
│   ├── sync_definitions.py
│   ├── sync_runs.py
│   ├── mappings.py
│   ├── publish.py
│   ├── datasets.py
│   ├── health.py
│   ├── drift.py
│   └── router.py
│
├── application/
│   ├── connection_service.py
│   ├── connector_version_service.py
│   ├── sync_service.py               # checkpoint + resume
│   ├── dataset_service.py
│   ├── normalization_service.py
│   ├── mapping_service.py
│   ├── validation_service.py         # 20 categories, fail-closed
│   ├── period_service.py
│   ├── publish_service.py
│   ├── drift_service.py
│   ├── period_lock_service.py
│   ├── health_service.py
│   └── consent_service.py
│
├── domain/
│   ├── models.py
│   ├── enums.py
│   ├── schemas.py
│   └── canonical/
│       ├── __init__.py
│       ├── trial_balance.py
│       ├── general_ledger.py
│       ├── accounts_receivable.py
│       ├── accounts_payable.py
│       ├── ageing.py
│       ├── fixed_assets.py
│       ├── prepaid.py
│       ├── profit_and_loss.py
│       ├── balance_sheet.py
│       ├── cash_flow.py
│       ├── invoice_register.py
│       ├── purchase_register.py
│       ├── sales_orders.py
│       ├── purchase_orders.py
│       ├── bank_transactions.py      # multi-currency
│       ├── inventory.py
│       ├── payroll_summary.py
│       ├── expense_claims.py
│       ├── tax_ledger.py
│       ├── tds_register.py
│       ├── gst_returns.py            # GSTR-1/2A/2B/3B live; GSTR-9/9C stub classes
│       ├── einvoice.py
│       ├── advances.py
│       ├── intercompany.py
│       ├── budget.py
│       ├── project_ledger.py
│       ├── contracts.py
│       ├── opening_balances.py
│       ├── sync_reconciliation.py
│       └── master_data.py
│
├── infrastructure/
│   ├── connectors/
│   │   ├── base.py                   # AbstractConnector — permanent contract
│   │   ├── capability.py             # ConnectorCapabilityMatrix
│   │   ├── registry.py               # all 23 registered
│   │   ├── generic_file.py           # LIVE
│   │   ├── zoho.py                   # LIVE
│   │   ├── tally.py                  # STUB
│   │   ├── busy.py                   # STUB
│   │   ├── marg.py                   # STUB
│   │   ├── munim.py                  # STUB
│   │   ├── quickbooks.py             # STUB
│   │   ├── xero.py                   # STUB
│   │   ├── freshbooks.py             # STUB
│   │   ├── wave.py                   # STUB
│   │   ├── netsuite.py               # STUB
│   │   ├── dynamics365.py            # STUB
│   │   ├── sage.py                   # STUB
│   │   ├── odoo.py                   # STUB
│   │   ├── sap.py                    # STUB
│   │   ├── oracle.py                 # STUB
│   │   ├── razorpay.py               # STUB
│   │   ├── stripe.py                 # STUB
│   │   ├── aa_framework.py           # STUB
│   │   ├── plaid.py                  # STUB
│   │   ├── keka.py                   # STUB
│   │   ├── darwinbox.py              # STUB
│   │   └── razorpay_payroll.py       # STUB
│   ├── secret_store.py
│   ├── snapshot_store.py
│   └── pii_masker.py
│
└── policies/
    ├── rls_policies.sql
    └── permissions.py
```

---

## STEP 2 — ENUMS

`domain/enums.py`

### ConnectorType (23 values)

```python
class ConnectorType(str, Enum):
    # Indian SMB / Desktop
    TALLY               = "tally"
    BUSY                = "busy"
    MARG                = "marg"
    MUNIM               = "munim"
    # SaaS Cloud
    ZOHO                = "zoho"            # LIVE Phase 4C
    QUICKBOOKS          = "quickbooks"
    XERO                = "xero"
    FRESHBOOKS          = "freshbooks"
    WAVE                = "wave"
    # Mid-Market
    NETSUITE            = "netsuite"
    DYNAMICS_365        = "dynamics_365"
    SAGE                = "sage"
    ODOO                = "odoo"
    # Enterprise
    SAP                 = "sap"
    ORACLE              = "oracle"
    # Banking / Payments
    RAZORPAY            = "razorpay"
    STRIPE              = "stripe"
    AA_FRAMEWORK        = "aa_framework"
    PLAID               = "plaid"
    # Payroll / HR
    KEKA                = "keka"
    DARWINBOX           = "darwinbox"
    RAZORPAY_PAYROLL    = "razorpay_payroll"
    # Generic
    GENERIC_FILE        = "generic_file"    # LIVE Phase 4C
```

### DatasetType (46 values — all declared, 4 marked as Phase 4F stubs)

```python
class DatasetType(str, Enum):
    # GL & TB
    TRIAL_BALANCE                   = "trial_balance"
    GENERAL_LEDGER                  = "general_ledger"
    # Financial Statements
    PROFIT_AND_LOSS                 = "profit_and_loss"
    BALANCE_SHEET                   = "balance_sheet"
    CASH_FLOW_STATEMENT             = "cash_flow_statement"
    # AR & AP
    ACCOUNTS_RECEIVABLE             = "accounts_receivable"
    ACCOUNTS_PAYABLE                = "accounts_payable"
    AR_AGEING                       = "ar_ageing"
    AP_AGEING                       = "ap_ageing"
    # Assets
    FIXED_ASSET_REGISTER            = "fixed_asset_register"
    PREPAID_REGISTER                = "prepaid_register"
    # Transaction Registers
    INVOICE_REGISTER                = "invoice_register"
    PURCHASE_REGISTER               = "purchase_register"
    CREDIT_NOTE_REGISTER            = "credit_note_register"
    DEBIT_NOTE_REGISTER             = "debit_note_register"
    # Order Registers
    SALES_ORDER_REGISTER            = "sales_order_register"
    PURCHASE_ORDER_REGISTER         = "purchase_order_register"
    # Banking
    BANK_STATEMENT                  = "bank_statement"
    BANK_TRANSACTION_REGISTER       = "bank_transaction_register"
    # Inventory
    INVENTORY_REGISTER              = "inventory_register"
    INVENTORY_MOVEMENT              = "inventory_movement"
    # Payroll
    PAYROLL_SUMMARY                 = "payroll_summary"
    EXPENSE_CLAIMS                  = "expense_claims"
    # Tax & Compliance
    TAX_LEDGER                      = "tax_ledger"
    TDS_REGISTER                    = "tds_register"
    GST_RETURN_GSTR1                = "gst_return_gstr1"
    GST_RETURN_GSTR2A               = "gst_return_gstr2a"
    GST_RETURN_GSTR2B               = "gst_return_gstr2b"
    GST_RETURN_GSTR3B               = "gst_return_gstr3b"
    EINVOICE_REGISTER               = "einvoice_register"
    # Deferred to Phase 4F — declared now so no future migration needed
    GST_RETURN_GSTR9                = "gst_return_gstr9"        # Phase 4F
    GST_RETURN_GSTR9C               = "gst_return_gstr9c"       # Phase 4F
    FORM_26AS                       = "form_26as"               # Phase 4F
    AIS_REGISTER                    = "ais_register"            # Phase 4F
    # Advances
    STAFF_ADVANCES                  = "staff_advances"
    VENDOR_ADVANCES                 = "vendor_advances"
    CUSTOMER_ADVANCES               = "customer_advances"
    # Intercompany
    INTERCOMPANY_TRANSACTIONS       = "intercompany_transactions"
    # Budgets / Projects / Contracts
    BUDGET_DATA                     = "budget_data"
    PROJECT_LEDGER                  = "project_ledger"
    CONTRACT_REGISTER               = "contract_register"
    # Opening Balances
    OPENING_BALANCES                = "opening_balances"
    # Drift
    SYNC_RECONCILIATION_SUMMARY     = "sync_reconciliation_summary"
    # Master Data
    CHART_OF_ACCOUNTS               = "chart_of_accounts"
    VENDOR_MASTER                   = "vendor_master"
    CUSTOMER_MASTER                 = "customer_master"
    DIMENSION_MASTER                = "dimension_master"
    CURRENCY_MASTER                 = "currency_master"


class PeriodGranularity(str, Enum):
    MONTHLY     = "monthly"
    QUARTERLY   = "quarterly"
    YEARLY      = "yearly"
    CUSTOM      = "custom"
    AS_AT       = "as_at"
    NO_PERIOD   = "no_period"
```

**Period semantics:**

| Period type | Dataset types |
|---|---|
| `AS_AT` | TRIAL_BALANCE, BALANCE_SHEET, FIXED_ASSET_REGISTER, PREPAID_REGISTER, AR_AGEING, AP_AGEING, INVENTORY_REGISTER, STAFF_ADVANCES, VENDOR_ADVANCES, CUSTOMER_ADVANCES, OPENING_BALANCES |
| Date range | All others except master data |
| `NO_PERIOD` | CHART_OF_ACCOUNTS, VENDOR_MASTER, CUSTOMER_MASTER, DIMENSION_MASTER, CURRENCY_MASTER |

---

## STEP 3 — CANONICAL SCHEMAS (ALL 42 ACTIVE — PERMANENT CONTRACT)

All in `domain/canonical/`. Pydantic only. Stored in R2.

**Global rules — apply to every schema without exception:**
- All monetary: `Decimal` never `float`
- All dates: `date` never `str`
- All currency codes: ISO 4217 three-letter string
- All entity refs: `entity_id: str` → `CpEntity`
- All dimension refs: `dimension_refs: dict[str, str]`
- Every root schema: `dataset_token: str` (SHA256 of full serialized content)
- All schemas with party names / GSTINs / PANs: `pii_masked: bool`
- All transaction schemas: `attachment_references: list[str]`
- Schemas that carry ERP-side totals: `erp_reported_*` fields for drift detection

### `trial_balance.py`
```python
class CanonicalTBLine(BaseModel):
    account_code: str
    account_name: str
    account_type: str               # ASSET/LIABILITY/EQUITY/INCOME/EXPENSE
    account_group: str
    opening_debit: Decimal
    opening_credit: Decimal
    period_debit: Decimal
    period_credit: Decimal
    closing_debit: Decimal
    closing_credit: Decimal
    currency: str
    entity_id: str
    dimension_refs: dict[str, str]

class CanonicalTrialBalance(BaseModel):
    as_at_date: date
    entity_id: str
    currency: str
    lines: list[CanonicalTBLine]
    total_closing_debit: Decimal
    total_closing_credit: Decimal
    balanced: bool
    erp_reported_total_debit: Decimal | None
    erp_reported_total_credit: Decimal | None
    dataset_token: str
```

### `general_ledger.py`
```python
class CanonicalGLLine(BaseModel):
    entry_date: date
    voucher_number: str
    voucher_type: str               # JOURNAL/PAYMENT/RECEIPT/CONTRA/SALES/PURCHASE/DEBIT_NOTE/CREDIT_NOTE
    account_code: str
    account_name: str
    debit: Decimal
    credit: Decimal
    narration: str
    reference: str
    party_code: str | None
    party_name: str | None
    party_type: str | None          # VENDOR/CUSTOMER/BANK/EMPLOYEE/INTERNAL
    currency: str
    base_currency_debit: Decimal
    base_currency_credit: Decimal
    exchange_rate: Decimal
    entity_id: str
    dimension_refs: dict[str, str]
    source_entry_id: str
    is_opening_entry: bool
    is_closing_entry: bool
    attachment_references: list[str]

class CanonicalGeneralLedger(BaseModel):
    from_date: date
    to_date: date
    entity_id: str
    currency: str
    lines: list[CanonicalGLLine]
    line_count: int
    total_debits: Decimal
    total_credits: Decimal
    balanced: bool
    erp_reported_line_count: int | None
    erp_reported_total_debits: Decimal | None
    erp_reported_total_credits: Decimal | None
    dataset_token: str
```

### `accounts_receivable.py`
```python
class CanonicalAREntry(BaseModel):
    invoice_date: date
    due_date: date | None
    invoice_number: str
    customer_code: str
    customer_name: str
    gstin: str | None
    invoice_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    amount_received: Decimal
    tds_deducted: Decimal
    balance_due: Decimal
    currency: str
    base_currency_balance: Decimal
    exchange_rate: Decimal
    payment_terms: str | None
    status: str                     # OPEN/PARTIAL/CLOSED/OVERDUE/DISPUTED
    dispute_reason: str | None
    entity_id: str
    dimension_refs: dict[str, str]
    source_entry_id: str
    attachment_references: list[str]
    pii_masked: bool

class CanonicalAccountsReceivable(BaseModel):
    from_date: date
    to_date: date
    entity_id: str
    entries: list[CanonicalAREntry]
    total_invoiced: Decimal
    total_received: Decimal
    total_tds: Decimal
    total_outstanding: Decimal
    erp_reported_outstanding: Decimal | None
    dataset_token: str
```

### `accounts_payable.py`
```python
class CanonicalAPEntry(BaseModel):
    bill_date: date
    due_date: date | None
    bill_number: str
    vendor_code: str
    vendor_name: str
    gstin: str | None
    bill_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    tds_deducted: Decimal
    balance_due: Decimal
    currency: str
    base_currency_balance: Decimal
    exchange_rate: Decimal
    payment_terms: str | None
    status: str                     # OPEN/PARTIAL/CLOSED/OVERDUE
    entity_id: str
    dimension_refs: dict[str, str]
    source_entry_id: str
    attachment_references: list[str]
    pii_masked: bool

class CanonicalAccountsPayable(BaseModel):
    from_date: date
    to_date: date
    entity_id: str
    entries: list[CanonicalAPEntry]
    total_billed: Decimal
    total_paid: Decimal
    total_tds: Decimal
    total_outstanding: Decimal
    erp_reported_outstanding: Decimal | None
    dataset_token: str
```

### `ageing.py`
```python
class CanonicalAgeingBucket(BaseModel):
    label: str          # "Current"/"1-30"/"31-60"/"61-90"/"91-120"/"121-180"/"180+"
    days_from: int
    days_to: int | None
    amount: Decimal
    count: int

class CanonicalAgeingEntry(BaseModel):
    party_code: str
    party_name: str
    party_type: str     # CUSTOMER/VENDOR
    total_outstanding: Decimal
    currency: str
    base_currency_outstanding: Decimal
    buckets: list[CanonicalAgeingBucket]
    oldest_due_date: date | None
    entity_id: str
    pii_masked: bool

class CanonicalAgeing(BaseModel):
    as_at_date: date
    ageing_type: str    # AR/AP
    entity_id: str
    entries: list[CanonicalAgeingEntry]
    total_outstanding: Decimal
    bucket_summary: list[CanonicalAgeingBucket]
    dataset_token: str
```

### `fixed_assets.py`
```python
class CanonicalFAREntry(BaseModel):
    asset_code: str
    asset_name: str
    asset_category: str
    asset_class: str                # TANGIBLE/INTANGIBLE/CWIP/ROU_ASSET
    purchase_date: date
    capitalisation_date: date | None
    purchase_cost: Decimal
    additions_ytd: Decimal
    disposals_ytd: Decimal
    gross_block: Decimal
    accumulated_depreciation: Decimal
    depreciation_ytd: Decimal
    impairment_ytd: Decimal
    net_book_value: Decimal
    depreciation_method: str        # SLM/WDV/UNITS_OF_PRODUCTION/NONE
    useful_life_months: int
    remaining_life_months: int
    salvage_value: Decimal
    currency: str
    location: str | None
    department: str | None
    custodian: str | None
    status: str                     # ACTIVE/DISPOSED/FULLY_DEPRECIATED/IMPAIRED/CWIP
    disposal_date: date | None
    disposal_proceeds: Decimal | None
    entity_id: str
    source_entry_id: str
    attachment_references: list[str]

class CanonicalFixedAssetRegister(BaseModel):
    as_at_date: date
    entity_id: str
    assets: list[CanonicalFAREntry]
    total_gross_block: Decimal
    total_accumulated_depreciation: Decimal
    total_net_book_value: Decimal
    dataset_token: str
```

### `prepaid.py`
```python
class CanonicalPrepaidEntry(BaseModel):
    prepaid_code: str
    description: str
    vendor_code: str | None
    vendor_name: str | None
    start_date: date
    end_date: date
    total_amount: Decimal
    amortized_to_date: Decimal
    balance_remaining: Decimal
    monthly_amortization: Decimal
    currency: str
    account_code: str
    category: str | None            # INSURANCE/RENT/SUBSCRIPTION/LICENSE/OTHER
    entity_id: str
    source_entry_id: str
    attachment_references: list[str]

class CanonicalPrepaidRegister(BaseModel):
    as_at_date: date
    entity_id: str
    entries: list[CanonicalPrepaidEntry]
    total_prepaid_balance: Decimal
    dataset_token: str
```

### `profit_and_loss.py`
```python
class CanonicalPLLine(BaseModel):
    account_code: str
    account_name: str
    account_group: str              # REVENUE/COGS/GROSS_PROFIT/OPEX/EBITDA/DEPRECIATION/EBIT/INTEREST/PBT/TAX/PAT/OCI
    sequence: int
    current_period: Decimal
    prior_period: Decimal | None
    ytd_current: Decimal
    ytd_prior: Decimal | None
    budget_current: Decimal | None
    budget_variance: Decimal | None
    currency: str
    entity_id: str
    dimension_refs: dict[str, str]

class CanonicalProfitAndLoss(BaseModel):
    from_date: date
    to_date: date
    entity_id: str
    currency: str
    lines: list[CanonicalPLLine]
    total_revenue: Decimal
    total_cogs: Decimal
    gross_profit: Decimal
    gross_margin_pct: Decimal
    total_opex: Decimal
    ebitda: Decimal
    ebitda_margin_pct: Decimal
    depreciation_amortization: Decimal
    ebit: Decimal
    interest_expense: Decimal
    pbt: Decimal
    tax_expense: Decimal
    pat: Decimal
    pat_margin_pct: Decimal
    erp_reported_pat: Decimal | None
    dataset_token: str
```

### `balance_sheet.py`
```python
class CanonicalBSLine(BaseModel):
    account_code: str
    account_name: str
    account_group: str              # CURRENT_ASSETS/FIXED_ASSETS/OTHER_ASSETS/CURRENT_LIABILITIES/LT_LIABILITIES/EQUITY/MINORITY_INTEREST
    sequence: int
    balance: Decimal
    prior_period_balance: Decimal | None
    currency: str
    entity_id: str

class CanonicalBalanceSheet(BaseModel):
    as_at_date: date
    entity_id: str
    currency: str
    lines: list[CanonicalBSLine]
    total_current_assets: Decimal
    total_fixed_assets: Decimal
    total_assets: Decimal
    total_current_liabilities: Decimal
    total_lt_liabilities: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    total_minority_interest: Decimal
    balance_check_passed: bool
    erp_reported_total_assets: Decimal | None
    dataset_token: str
```

### `cash_flow.py`
```python
class CanonicalCFLine(BaseModel):
    activity_type: str              # OPERATING/INVESTING/FINANCING
    line_code: str
    line_description: str
    amount: Decimal
    prior_period: Decimal | None
    currency: str
    entity_id: str

class CanonicalCashFlowStatement(BaseModel):
    from_date: date
    to_date: date
    entity_id: str
    currency: str
    method: str                     # DIRECT/INDIRECT
    lines: list[CanonicalCFLine]
    net_operating: Decimal
    net_investing: Decimal
    net_financing: Decimal
    net_change_in_cash: Decimal
    opening_cash: Decimal
    closing_cash: Decimal
    fx_effect_on_cash: Decimal
    dataset_token: str
```

### `bank_transactions.py` — multi-currency
```python
class CanonicalBankTransaction(BaseModel):
    transaction_date: date
    value_date: date | None
    transaction_id: str
    description: str
    transaction_currency: str           # currency the txn was made in
    transaction_debit: Decimal
    transaction_credit: Decimal
    account_currency: str               # bank account base currency
    account_debit: Decimal              # in account_currency
    account_credit: Decimal             # in account_currency
    exchange_rate_applied: Decimal      # transaction_currency → account_currency
    balance_in_account_currency: Decimal
    transaction_type: str
    cheque_number: str | None
    reference: str | None
    party_name: str | None
    bank_account_code: str
    entity_id: str
    source_entry_id: str
    attachment_references: list[str]

class CanonicalBankStatement(BaseModel):
    from_date: date
    to_date: date
    bank_account_code: str
    bank_name: str
    account_number_masked: str          # last 4 digits only — hard rule
    account_currency: str
    opening_balance: Decimal
    closing_balance: Decimal
    total_debits_in_account_currency: Decimal
    total_credits_in_account_currency: Decimal
    fx_transactions_present: bool
    entity_id: str
    transactions: list[CanonicalBankTransaction]
    transaction_count: int
    erp_reported_closing_balance: Decimal | None
    dataset_token: str
```

### `invoice_register.py`
```python
class CanonicalInvoiceLine(BaseModel):
    line_number: int
    item_code: str | None
    item_description: str
    hsn_sac_code: str | None
    quantity: Decimal
    unit: str | None
    unit_price: Decimal
    discount_pct: Decimal
    discount_amount: Decimal
    taxable_amount: Decimal
    cgst_rate: Decimal
    cgst_amount: Decimal
    sgst_rate: Decimal
    sgst_amount: Decimal
    igst_rate: Decimal
    igst_amount: Decimal
    cess_amount: Decimal
    total_tax: Decimal
    line_total: Decimal
    account_code: str
    dimension_refs: dict[str, str]

class CanonicalInvoice(BaseModel):
    invoice_date: date
    invoice_number: str
    invoice_type: str               # TAX_INVOICE/EXPORT_WITH_TAX/EXPORT_WITHOUT_TAX/B2C_LARGE/B2C_SMALL/SEZ/DEEMED_EXPORT/CREDIT_NOTE/PROFORMA
    customer_code: str
    customer_name: str
    customer_gstin: str | None
    billing_state: str | None
    place_of_supply: str | None
    is_interstate: bool
    reverse_charge: bool
    subtotal: Decimal
    total_discount: Decimal
    total_taxable: Decimal
    total_cgst: Decimal
    total_sgst: Decimal
    total_igst: Decimal
    total_cess: Decimal
    total_tax: Decimal
    total_amount: Decimal
    tds_deducted: Decimal
    currency: str
    base_currency_total: Decimal
    exchange_rate: Decimal
    payment_terms: str | None
    due_date: date | None
    status: str
    irn_number: str | None
    irn_date: date | None
    qr_code_present: bool
    eway_bill_number: str | None
    eway_bill_date: date | None
    eway_bill_valid_until: date | None
    lines: list[CanonicalInvoiceLine]
    entity_id: str
    source_entry_id: str
    attachment_references: list[str]
    pii_masked: bool

class CanonicalInvoiceRegister(BaseModel):
    from_date: date
    to_date: date
    entity_id: str
    invoices: list[CanonicalInvoice]
    total_invoiced: Decimal
    total_tax: Decimal
    total_tds: Decimal
    invoice_count: int
    dataset_token: str
```

### Remaining schemas

Implement all remaining canonical schemas following the exact same global rules.
Full field specifications for these are identical to those in v5 of the prompt:

- `purchase_register.py` — `CanonicalPurchaseLine`, `CanonicalPurchase`, `CanonicalPurchaseRegister`
- `sales_orders.py` — `CanonicalSOLine`, `CanonicalSalesOrder`, `CanonicalSalesOrderRegister`
- `purchase_orders.py` — `CanonicalPOLine`, `CanonicalPurchaseOrder`, `CanonicalPurchaseOrderRegister`
- `inventory.py` — `CanonicalInventoryItem`, `CanonicalInventoryRegister`, `CanonicalInventoryMovement`
- `payroll_summary.py` — `CanonicalPayrollHeadLine`, `CanonicalPayrollSummary` (includes `pii_masked`)
- `expense_claims.py` — `CanonicalExpenseClaim`, `CanonicalExpenseClaimsRegister`
- `tax_ledger.py` — `CanonicalTaxLedgerEntry`, `CanonicalTaxLedger`
- `tds_register.py` — `CanonicalTDSEntry` (PAN masked), `CanonicalTDSRegister`
- `gst_returns.py` — `CanonicalGSTR1`, `CanonicalGSTR2B`, `CanonicalGSTR3BSummary` (live); `CanonicalGSTR9Summary`, `CanonicalGSTR9C` (stub empty classes only — Phase 4F)
- `einvoice.py` — `CanonicalEInvoiceRecord`, `CanonicalEInvoiceRegister`
- `advances.py` — `CanonicalAdvanceEntry`, `CanonicalAdvanceRegister`
- `intercompany.py` — `CanonicalIntercompanyTransaction`, `CanonicalIntercompanyRegister`
- `budget.py` — `CanonicalBudgetLine`, `CanonicalBudget`
- `project_ledger.py` — `CanonicalProjectLedgerLine`, `CanonicalProjectLedger`
- `contracts.py` — `CanonicalContract`, `CanonicalContractRegister`
- `opening_balances.py` — `CanonicalOpeningBalanceLine`, `CanonicalOpeningBalances`
- `sync_reconciliation.py` — `CanonicalSyncReconciliationLine`, `CanonicalSyncReconciliationSummary`
- `master_data.py` — `CanonicalAccount`, `CanonicalChartOfAccounts`, `CanonicalVendor`, `CanonicalCustomer`, `CanonicalDimension`, `CanonicalCurrencyRate`, `CanonicalMasterData`

---

## STEP 4 — ABSTRACT CONNECTOR

`infrastructure/connectors/base.py`

```python
class ConnectorCapabilityNotSupported(Exception):
    pass

class ConnectorImplementationStatus(str, Enum):
    LIVE    = "live"
    STUB    = "stub"

class ExtractionScope(BaseModel):
    entity_id: str
    dataset_type: DatasetType
    period_resolution: PeriodResolution
    connector_credentials: dict         # decrypted at call — never stored
    extraction_options: dict
    checkpoint: dict | None = None      # resume token

class RawPayload(BaseModel):
    connector_type: ConnectorType
    dataset_type: DatasetType
    raw_data: dict
    extraction_timestamp: datetime
    connector_version: str
    erp_control_totals: dict | None
    extraction_checkpoint: dict | None  # next resume token if chunked
    is_complete: bool                   # False if more pages remain

class ConnectorCapabilityMatrix(BaseModel):
    connector_type: ConnectorType
    supported_datasets: list[DatasetType]
    supports_resumable_extraction: bool
    implementation_status: ConnectorImplementationStatus
    available_in_phase: str             # e.g. "4C", "4D", "4E", "4F"
```

`AbstractConnector` declares all methods for every `DatasetType` as `@abstractmethod`.
Total: 48 methods (46 dataset extract methods + `test_connection` + `declare_capabilities` +
`extract_erp_control_totals`).

**Stub connector pattern — all 21 non-live connectors must follow this exactly:**

```python
class TallyConnector(AbstractConnector):
    connector_type = ConnectorType.TALLY

    async def declare_capabilities(self) -> ConnectorCapabilityMatrix:
        return ConnectorCapabilityMatrix(
            connector_type=ConnectorType.TALLY,
            supported_datasets=[],
            supports_resumable_extraction=False,
            implementation_status=ConnectorImplementationStatus.STUB,
            available_in_phase="4D",
        )

    async def test_connection(self, credentials: dict) -> ConnectionTestResult:
        raise ConnectorCapabilityNotSupported(
            "Tally connector is not yet implemented. Available in Phase 4D."
        )

    # Every extract method:
    async def extract_trial_balance(self, scope: ExtractionScope) -> RawPayload:
        raise ConnectorCapabilityNotSupported(
            f"Tally connector not implemented. Phase 4D."
        )
    # ... all other extract methods raise same exception
```

---

## STEP 5 — GENERIC FILE CONNECTOR (LIVE)

`infrastructure/connectors/generic_file.py`

Supports CSV, Excel (.xlsx), JSON upload for any of the 42 active dataset types.

- File type auto-detected from extension or content sniffing
- Parse CSV/Excel with `pandas`, JSON with `json`
- Column headers mapped to canonical fields using active `MappingDefinition` for the connection
- Raw data returned in `RawPayload.raw_data` — no computation
- File encoding: UTF-8 required, reject with clear error if not
- Max file size: 100 MB — reject with `ExtractionError` if exceeded
- Chunked extraction: `extraction_chunk_size` rows per chunk (default 500)
- `supports_resumable_extraction: True`
- `erp_control_totals`: if file contains a summary/totals row (detected heuristically or via config), extract it into `erp_control_totals`
- Capability: all 42 active `DatasetType` values

---

## STEP 6 — ZOHO BOOKS CONNECTOR (LIVE)

`infrastructure/connectors/zoho.py`

Protocol: Zoho Books API v3. Auth: OAuth2.

Supported dataset types in Phase 4C:
```
TRIAL_BALANCE, GENERAL_LEDGER, PROFIT_AND_LOSS, BALANCE_SHEET,
ACCOUNTS_RECEIVABLE, ACCOUNTS_PAYABLE, AR_AGEING, AP_AGEING,
INVOICE_REGISTER, PURCHASE_REGISTER, BANK_STATEMENT,
CHART_OF_ACCOUNTS, VENDOR_MASTER, CUSTOMER_MASTER, CURRENCY_MASTER
```

Implementation requirements:
- Token refresh handled automatically — never store access token in DB
- All API calls via `async httpx`
- Rate limiting: 100 req/min — exponential backoff on 429
- Pagination: `page` param + `has_more_page` response field
- `supports_resumable_extraction: True` — checkpoint = `{"page": N}`
- On 429 or 503: backoff and retry up to 3 times, then fail with `ExtractionError`
- `erp_control_totals`: for TRIAL_BALANCE and BALANCE_SHEET, call Zoho balance summary endpoint
- `test_connection`: attempt token refresh + one lightweight API call

---

## STEP 7 — DETERMINISTIC SYNC TOKEN

SHA256 of canonical JSON string of these exact fields in this exact order:

```
tenant_id
organisation_id
entity_id
dataset_type
connector_type
connector_version
source_system_instance_id
sync_definition_id
sync_definition_version
period_resolution_hash          SHA256 of JSON-serialized PeriodResolution
extraction_scope_hash           SHA256 of JSON-serialized extraction scope
raw_snapshot_payload_hash
mapping_version_token
normalization_version
pii_masking_enabled
data_residency_region
```

Same inputs → same token. Always.
Duplicate token → `DUPLICATE_SYNC` validation failure → run rejected.

**Idempotency key (separate from sync token):**
- Client-supplied via `Idempotency-Key` header (required on sync run creation)
- Stored on `ExternalSyncRun.idempotency_key`
- Checked in Redis before creating run — if found, return cached `ApiResponse`
- TTL: 24 hours
- Sync token = content deduplication; idempotency key = request deduplication

**Publish idempotency:**
- `POST /erp-sync/publish-events/{id}/approve` is fully idempotent
- Second call returns existing `ExternalSyncPublishEvent` — no duplicate created

---

## STEP 8 — VALIDATION ENGINE (20 CATEGORIES — FAIL-CLOSED)

```
REQUIRED_FIELD_PRESENCE             required canonical fields populated
DUPLICATE_SYNC_DETECTION            sync_token already exists → halt
CURRENCY_CONSISTENCY                all monetary values have valid ISO 4217 code
ENTITY_SCOPE_CONSISTENCY            all entity_ids map to known CpEntity records
PERIOD_CONSISTENCY                  all dates within declared period_resolution window
BALANCE_CHECK                       TB balanced | BS balanced | P&L PAT reconciles
SNAPSHOT_INTEGRITY                  canonical_payload_hash matches recomputed hash
DELTA_BOUNDARY                      incremental does not overlap prior sync period
CAPABILITY_MISMATCH                 dataset_type supported by connector capability matrix
MAPPING_COMPLETENESS                every source account code has active mapping version
AGEING_BUCKET_INTEGRITY             ageing buckets sum to total_outstanding
REGISTER_LINE_INTEGRITY             register line totals reconcile to header totals
BANK_BALANCE_INTEGRITY              opening + net movements = closing (account_currency)
BANK_MULTICURRENCY_INTEGRITY        all fx transactions have exchange_rate_applied > 0
INVENTORY_VALUE_INTEGRITY           closing = opening + receipts - issues
MASTER_DATA_REFERENTIAL             all codes exist in master data snapshot
PII_CONSENT_CHECK                   if pii_masking_enabled, all PII fields masked before freeze
IRN_FORMAT_VALIDITY                 if irn_number present, must be 64-char hex string
GSTR_PERIOD_CONSISTENCY             GST return period string matches sync definition period
BACKDATED_MODIFICATION_CHECK        if period locked, flag value changes as modification alert
```

All 20 must pass. Any failure → `HALTED`. No partial publishes. Ever.

---

## STEP 9 — DRIFT DETECTION ENGINE

`application/drift_service.py`

Runs automatically after every sync run. Not optional. Not configurable off.

```python
class DriftSeverity(str, Enum):
    NONE        = "none"
    MINOR       = "minor"           # variance < 1%
    SIGNIFICANT = "significant"     # 1–5%
    CRITICAL    = "critical"        # > 5% or structural mismatch

class DriftMetric(BaseModel):
    metric_name: str
    erp_value: Decimal | int | None
    financeops_value: Decimal | int | None
    variance: Decimal | None
    variance_pct: Decimal | None
    status: str                     # MATCHED/VARIANCE/ERP_MISSING/FO_MISSING
    threshold_breached: bool

class DriftReport(BaseModel):
    sync_run_id: str
    dataset_type: DatasetType
    period_label: str
    entity_id: str
    connector_type: ConnectorType
    metrics_checked: list[DriftMetric]
    total_variances: int
    drift_detected: bool
    drift_severity: DriftSeverity
    generated_at: datetime
```

`CRITICAL` drift → sync run status = `DRIFT_ALERT` → publish blocked until acknowledged.

---

## STEP 10 — SYNC HEALTH SLA ENGINE

`application/health_service.py`

Default SLA hours (configurable per tenant per dataset via `ExternalSyncSLAConfig`):

```python
DEFAULT_SLA_HOURS = {
    DatasetType.BANK_STATEMENT:             4,
    DatasetType.BANK_TRANSACTION_REGISTER:  4,
    DatasetType.AR_AGEING:                  12,
    DatasetType.AP_AGEING:                  12,
    DatasetType.INVOICE_REGISTER:           12,
    DatasetType.PURCHASE_REGISTER:          12,
    DatasetType.TRIAL_BALANCE:              24,
    DatasetType.GENERAL_LEDGER:             24,
    DatasetType.PROFIT_AND_LOSS:            24,
    DatasetType.BALANCE_SHEET:              24,
    DatasetType.GST_RETURN_GSTR1:           72,
    DatasetType.GST_RETURN_GSTR2B:          72,
    DatasetType.GST_RETURN_GSTR3B:          72,
    DatasetType.CHART_OF_ACCOUNTS:          168,
    DatasetType.VENDOR_MASTER:              168,
    DatasetType.CUSTOMER_MASTER:            168,
}
```

Alert types: `SCHEDULED_SYNC_MISSED`, `CONSECUTIVE_FAILURE_THRESHOLD` (default 3),
`DATA_STALENESS`, `CONNECTION_DEAD` (consecutive failures ≥ threshold AND last success > 7 days).

---

## STEP 11 — PERIOD LOCK AND BACKDATED MODIFICATION

`application/period_lock_service.py`

- Auto-lock: period P locked when a sync run for period P is successfully published
- `check_backdated_modifications(sync_run_id)` runs after every sync
- `ExternalBackdatedModificationAlert` created when ERP values differ from locked snapshot
- `CRITICAL` backdated modifications block publish until acknowledged by authorized user
- Locks are permanent — superseded only, never deleted

---

## STEP 12 — PII MASKING AND CONSENT

`infrastructure/pii_masker.py` + `application/consent_service.py`

Hard rules — no exceptions, no configuration overrides:
- PAN numbers: show only last 4 characters
- Bank account numbers: store last 4 digits only, never full number

When `pii_masking_enabled = True` on connection:
- Mask all PII fields before writing canonical snapshot to R2
- Masking method: deterministic SHA256 truncated to 8 chars (preserves cross-dataset matching)
- `ExternalDataConsentLog` created for every sync run (append-only)

---

## STEP 13 — CHUNKED EXTRACTION AND RESUME

Add to `ExternalSyncRun`:
```
extraction_total_records    int | None
extraction_fetched_records  int default 0
extraction_checkpoint       JSONB | None
extraction_chunk_size       int default 500
is_resumable                bool default False
resumed_from_run_id         UUID | None → ExternalSyncRun
```

Paused run status: `PAUSED` (not `FAILED`).
Resume via: `POST /erp-sync/sync-runs/{id}/resume`.
Raw snapshot not frozen until `is_complete = True`.

---

## STEP 14 — ALL MODELS (20 TABLES)

All inherit `FinancialBase`. All in `db/append_only.py`. All RLS + FORCE RLS.

```
ExternalConnection              (data_residency_region, pii_masking_enabled,
                                 consent_reference, pinned_connector_version)
ExternalConnectionVersion
ExternalSyncDefinition
ExternalSyncDefinitionVersion
ExternalSyncRun                 (idempotency_key, checkpoint + resume fields)
ExternalRawSnapshot
ExternalNormalizedSnapshot
ExternalMappingDefinition
ExternalMappingVersion
ExternalSyncEvidenceLink
ExternalSyncError
ExternalSyncPublishEvent
ExternalConnectorCapabilityRegistry
ExternalConnectorVersionRegistry
ExternalPeriodLock
ExternalBackdatedModificationAlert
ExternalSyncDriftReport
ExternalSyncHealthAlert
ExternalDataConsentLog
ExternalSyncSLAConfig
```

---

## STEP 15 — FROZEN ENGINE CONSUMPTION TABLE

`application/publish_service.py`

```
GL / TB Reconciliation          TRIAL_BALANCE, GENERAL_LEDGER
Bank Reconciliation             BANK_STATEMENT, BANK_TRANSACTION_REGISTER, GENERAL_LEDGER
GST Reconciliation              INVOICE_REGISTER, PURCHASE_REGISTER, TAX_LEDGER,
                                TDS_REGISTER, GST_RETURN_GSTR1, GST_RETURN_GSTR2B,
                                GST_RETURN_GSTR3B, EINVOICE_REGISTER
Working Capital                 BALANCE_SHEET, AR_AGEING, AP_AGEING, INVENTORY_REGISTER
IAS 16 Fixed Assets             FIXED_ASSET_REGISTER
Prepaid                         PREPAID_REGISTER
IFRS 15 Revenue Recognition     INVOICE_REGISTER, SALES_ORDER_REGISTER, CONTRACT_REGISTER
Ratio / Variance                PROFIT_AND_LOSS, BALANCE_SHEET, TRIAL_BALANCE, BUDGET_DATA
Financial Risk                  BALANCE_SHEET, AR_AGEING, AP_AGEING, CASH_FLOW_STATEMENT, BANK_STATEMENT
Anomaly Pattern                 GENERAL_LEDGER, INVOICE_REGISTER, PURCHASE_REGISTER, BANK_TRANSACTION_REGISTER
Multi-Entity Consolidation      TRIAL_BALANCE, PROFIT_AND_LOSS, BALANCE_SHEET, INTERCOMPANY_TRANSACTIONS
FX Translation                  TRIAL_BALANCE, GENERAL_LEDGER, CURRENCY_MASTER
Ownership Consolidation         BALANCE_SHEET, PROFIT_AND_LOSS
Cash Flow Engine                CASH_FLOW_STATEMENT, GENERAL_LEDGER, BANK_STATEMENT
Board Pack                      PROFIT_AND_LOSS, BALANCE_SHEET, CASH_FLOW_STATEMENT, AR_AGEING, AP_AGEING, INVENTORY_REGISTER
Payroll GL                      PAYROLL_SUMMARY, GENERAL_LEDGER
MIS Manager                     All dataset types
Budget vs Actual                PROFIT_AND_LOSS, BALANCE_SHEET, BUDGET_DATA
TDS Reconciliation              TDS_REGISTER  (+ FORM_26AS, AIS_REGISTER when Phase 4F lands)
```

---

## STEP 16 — API ENDPOINTS

All async. All JWT + control plane token. All `ApiResponse[T]` envelope.

```
# Connections
POST   /erp-sync/connections                        Idempotency-Key required
GET    /erp-sync/connections
GET    /erp-sync/connections/{id}
POST   /erp-sync/connections/{id}/test
POST   /erp-sync/connections/{id}/activate
POST   /erp-sync/connections/{id}/suspend
POST   /erp-sync/connections/{id}/revoke
POST   /erp-sync/connections/{id}/rotate-credentials
POST   /erp-sync/connections/{id}/upgrade-connector-version
GET    /erp-sync/connections/{id}/versions
GET    /erp-sync/connections/{id}/capabilities

# Sync Definitions
POST   /erp-sync/sync-definitions
GET    /erp-sync/sync-definitions
GET    /erp-sync/sync-definitions/{id}
POST   /erp-sync/sync-definitions/{id}/supersede
POST   /erp-sync/sync-definitions/{id}/retire

# Sync Runs
POST   /erp-sync/sync-runs                          Idempotency-Key required
GET    /erp-sync/sync-runs
GET    /erp-sync/sync-runs/{id}
GET    /erp-sync/sync-runs/{id}/evidence
GET    /erp-sync/sync-runs/{id}/errors
GET    /erp-sync/sync-runs/{id}/drift-report
POST   /erp-sync/sync-runs/{id}/replay
POST   /erp-sync/sync-runs/{id}/resume
POST   /erp-sync/sync-runs/{id}/publish              Idempotency-Key required

# Datasets
GET    /erp-sync/datasets
GET    /erp-sync/datasets/{dataset_type}
GET    /erp-sync/datasets/{dataset_type}/periods
GET    /erp-sync/datasets/{dataset_type}/template
POST   /erp-sync/datasets/{dataset_type}/preview

# Mappings
POST   /erp-sync/mappings
GET    /erp-sync/mappings
GET    /erp-sync/mappings/{id}
POST   /erp-sync/mappings/{id}/versions
GET    /erp-sync/mappings/{id}/versions
POST   /erp-sync/mappings/{id}/versions/{vid}/activate

# Publish
GET    /erp-sync/publish-events
GET    /erp-sync/publish-events/{id}
POST   /erp-sync/publish-events/{id}/approve         Idempotency-Key required (idempotent)
POST   /erp-sync/publish-events/{id}/reject

# Health
GET    /erp-sync/health
GET    /erp-sync/health/{connection_id}
GET    /erp-sync/health/alerts

# Drift + Period Locks
GET    /erp-sync/drift-reports
GET    /erp-sync/drift-reports/{id}
GET    /erp-sync/period-locks
POST   /erp-sync/period-locks
POST   /erp-sync/backdated-alerts/{id}/acknowledge

# Connector catalog
GET    /erp-sync/connectors
GET    /erp-sync/connectors/{connector_type}/capabilities
GET    /erp-sync/connectors/{connector_type}/versions
```

---

## STEP 17 — MIGRATION

File: `alembic/versions/[ACTUAL_NEXT_NUMBER]_phase4c_erp_sync.py`

Determine the number by running `alembic heads` at the start of this phase.
Use head + 1. Do NOT hardcode.

- Create all 20 tables
- RLS + FORCE RLS on every table
- RLS policy: `tenant_id = current_setting('app.tenant_id')::uuid`
- Register all 20 tables in `db/append_only.py`
- Register `erp_sync` in `CpModuleRegistry`
- `alembic upgrade head` must complete in under 30 seconds on empty DB
- `alembic downgrade -1` must cleanly reverse

---

## STEP 18 — CONTROL PLANE PERMISSIONS

```
erp_sync:connection:manage
erp_sync:connection:view
erp_sync:sync_definition:manage
erp_sync:sync_run:trigger
erp_sync:sync_run:view
erp_sync:sync_run:resume
erp_sync:mapping:manage
erp_sync:mapping:view
erp_sync:publish:approve
erp_sync:publish:view
erp_sync:health:view
erp_sync:drift:view
erp_sync:drift:acknowledge
erp_sync:period_lock:manage
erp_sync:consent:view
erp_sync:connector_version:manage
```

---

## STEP 19 — TESTS

Build and pass in proving order. Do not write all tests up front and try to pass them all at once.

**Proving order:**
1. Canonical schema tests → all pass
2. Stub connector tests (all 21 raise `ConnectorCapabilityNotSupported`) → all pass
3. Generic File connector unit tests → all pass
4. Migration applies + append-only + RLS → all pass
5. Core sync pipeline: Generic File → COA → Trial Balance → GL → all pass
6. Drift engine tests → all pass
7. Health + period lock tests → all pass
8. Publish governance tests → all pass
9. Zoho connector tests (mocked httpx) → all pass
10. Full suite → zero failures

```
tests/unit/erp_sync/
  test_erp_sync_canonical_schemas.py
  test_erp_sync_token_determinism.py
  test_erp_sync_normalization.py
  test_erp_sync_mapping.py
  test_erp_sync_validation.py             # all 20 categories
  test_erp_sync_capability_matrix.py
  test_erp_sync_period_service.py
  test_erp_sync_drift_service.py
  test_erp_sync_health_service.py
  test_erp_sync_period_lock_service.py
  test_erp_sync_pii_masker.py
  test_erp_sync_connector_version_service.py
  test_erp_sync_idempotency.py

tests/integration/erp_sync/
  test_erp_sync_api.py
  test_erp_sync_append_only.py
  test_erp_sync_rls.py
  test_erp_sync_isolation.py
  test_erp_sync_supersession.py
  test_erp_sync_publish_governance.py
  test_erp_sync_replay_safety.py
  test_erp_sync_no_upstream_mutation.py
  test_erp_sync_secret_isolation.py
  test_erp_sync_dataset_coverage.py
  test_erp_sync_frozen_engine_handoff.py
  test_erp_sync_generic_file_connector.py
  test_erp_sync_zoho_connector.py
  test_erp_sync_connector_registry.py
  test_erp_sync_chunked_extraction.py
  test_erp_sync_drift_integration.py
  test_erp_sync_backdated_modification.py
  test_erp_sync_health_integration.py
  test_erp_sync_multicurrency_bank.py
  test_erp_sync_pii_consent_integration.py
  test_erp_sync_response_envelope.py
  test_erp_sync_idempotency_integration.py
```

All prior phase tests must continue to pass. Zero failures.

---

## STEP 20 — SEMANTIC BOUNDARIES (PERMANENT)

1. No source system name in any frozen engine file — grep check required
2. No frozen engine consumes raw payload — canonical via `publish_event_id` only
3. No connector computes or transforms — extract raw only
4. No webhook payload used as accounting truth
5. No raw credential in any log, error, JSONB, or audit trail
6. All 20 validation categories must pass before publish — no exceptions
7. No snapshot mutated after `frozen = True`
8. RLS enforced at DB level on all tables
9. No bidirectional sync in Phase 4 — read-only to all sources
10. `erp_sync` additive only — zero changes to phases 0–3
11. Adding a new connector = one new file + one registry line + tests/docs. Nothing else.
12. PAN numbers always masked beyond last 4 chars — no exceptions, no config override
13. Bank account numbers always stored as last 4 digits only — no exceptions
14. Drift check always runs after every sync — cannot be disabled
15. Period locks are permanent — superseded only, never deleted
16. All API responses use `ApiResponse[T]` envelope — no raw returns anywhere

---

## DEFINITION OF DONE

- [ ] 46 DatasetType enum values (42 active + 4 Phase 4F stubs)
- [ ] 23 ConnectorType enum values
- [ ] All 42 active canonical schemas complete with correct fields
- [ ] GSTR-9, GSTR-9C declared as stub classes only (no normalizer/validator yet)
- [ ] `pii_masked` and `attachment_references` on all transaction schemas
- [ ] `erp_reported_*` fields on TB, GL, AR, AP, BS, P&L, Inventory, Bank
- [ ] AbstractConnector with all 48 methods
- [ ] All 23 connectors in registry — 2 live, 21 clean stubs
- [ ] Generic File connector tested end-to-end (CSV + Excel + JSON)
- [ ] Zoho connector tested end-to-end with mocked httpx
- [ ] Core proving path tested: Generic File → COA → TB → GL → drift → publish
- [ ] PeriodService handles all granularity types + fiscal calendar
- [ ] DriftService with severity classification and CRITICAL-blocks-publish
- [ ] HealthService with SLA config and 4 alert types
- [ ] PeriodLockService with auto-lock and backdated modification detection
- [ ] ConsentService with PII masking and consent log per sync run
- [ ] ConnectorVersionService with pin/deprecate/upgrade
- [ ] PIIMasker with hard PAN and account number rules
- [ ] ChunkedExtraction with checkpoint/resume on ExternalSyncRun
- [ ] Idempotency key on sync run creation and publish approval
- [ ] All 20 models with FinancialBase, chain hash, RLS
- [ ] All 20 tables in `db/append_only.py`
- [ ] Migration applies clean with correct sequential number
- [ ] `alembic downgrade -1` reverses cleanly
- [ ] All 16 control plane permissions registered
- [ ] All API endpoints use `ApiResponse[T]`
- [ ] All 13 unit test files passing
- [ ] All 22 integration test files passing
- [ ] All prior phase tests passing
- [ ] `pytest` zero failures
- [ ] `docker-compose ps` all healthy
- [ ] Grep: no source system name in any frozen engine
- [ ] Grep: no raw credential in any log or JSONB
- [ ] Grep: no full PAN or full bank account number stored anywhere

---

## CRITICAL RULES

- Python 3.11 only
- `async def` everywhere
- `Decimal` not `float` for all monetary values
- No UPDATE / DELETE on any financial table
- All secrets from `.env` only
- RLS context on every request
- Every financial table: `id`, `tenant_id`, `chain_hash`, `previous_hash`, `created_at` TIMESTAMPTZ
- `WindowsSelectorEventLoopPolicy()` stays untouched
- `asyncio_default_test_loop_scope = "session"` stays untouched
- Run `pytest` after every step in the proving order — zero failures throughout

---

*42 active dataset types. 23 connectors (2 live). Permanent canonical contract.
Prove COA → TB → GL first. Then expand. Then open Phase 4D.*
