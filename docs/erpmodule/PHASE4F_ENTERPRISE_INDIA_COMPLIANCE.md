# FinanceOps — Phase 4F: Enterprise Connectors + India Compliance Stack
## Claude Code Implementation Prompt — v1 (Final)

> Prerequisite: Phase 4E complete, zero test failures.
> Paste this entire prompt into Claude Code. Do not modify it.
> This phase completes the connector set and activates the deferred India compliance datasets.

---

## WHO YOU ARE AND WHERE YOU ARE

You are Claude Code working inside the FinanceOps repository at `D:\finos\`.

**What Phase 4F delivers:**

Part A — Enterprise ERP Connectors (2):
- SAP (S/4HANA Cloud + ECC on-premise — profile-based)
- Oracle (Fusion Cloud + EBS on-premise — profile-based)

Part B — India Compliance Stack (4 deferred dataset types):
- GSTR-9 (annual return) — canonical schema + normalizer + validator
- GSTR-9C (reconciliation statement) — canonical schema + normalizer + validator
- FORM_26AS (TDS credit from Income Tax portal) — canonical schema + normalizer + validator
- AIS_REGISTER (Annual Information Statement) — canonical schema + normalizer + validator

After Phase 4F, all 23 connectors are live and all 46 dataset types are active.
The `erp_sync` module is complete.

**Permitted file changes:**
- `infrastructure/connectors/sap.py` — full implementation
- `infrastructure/connectors/oracle.py` — full implementation
- `domain/canonical/gst_returns.py` — activate GSTR-9, GSTR-9C stub classes
- `domain/canonical/form_26as_ais.py` — new file
- `application/normalization_service.py` — add handlers for 4 new dataset types
- `application/validation_service.py` — add validators for 4 new dataset types
- `application/dataset_service.py` — mark 4 dataset types as active
- `application/publish_service.py` — update TDS Reconciliation consumption entry
- `infrastructure/connectors/registry.py` — capability status only
- `tests/` — new test files only
- `docs/` — documentation

**Not permitted to change:**
- Any other canonical schema
- Any model or migration (no new tables needed — `DatasetType` is VARCHAR)
- Any enum (all 46 values were declared in Phase 4C)
- Any frozen engine (phases 0–3)

---

## STEP 0 — CONFIRM PHASE 4E IS COMPLETE

```bash
pytest tests/ -x -q
# Must show zero failures

# Verify SAP and Oracle are still stubs
python -c "
from financeops.modules.erp_sync.infrastructure.connectors.sap import SAPConnector
from financeops.modules.erp_sync.infrastructure.connectors.oracle import OracleConnector
import asyncio
s = SAPConnector()
cap = asyncio.run(s.declare_capabilities())
print('SAP status:', cap.implementation_status)  # Must print: stub
"

# Verify the 4 deferred dataset types are declared but have no active normalizer
python -c "
from financeops.modules.erp_sync.domain.enums import DatasetType
print(DatasetType.GST_RETURN_GSTR9)         # must exist
print(DatasetType.GST_RETURN_GSTR9C)        # must exist
print(DatasetType.FORM_26AS)                # must exist
print(DatasetType.AIS_REGISTER)             # must exist
"
```

State before proceeding:
```
PHASE 4E TEST STATUS    : [zero failures confirmed]
SAP CURRENT STATUS      : [stub confirmed]
ORACLE CURRENT STATUS   : [stub confirmed]
GSTR-9 ENUM EXISTS      : [confirmed]
FORM_26AS ENUM EXISTS   : [confirmed]
```

---

## PART A — SAP CONNECTOR

File: `infrastructure/connectors/sap.py`

SAP is not a single connector — it is two different integration patterns behind one
connector type. Route based on `sap_profile` credential field.

### Credentials schema

```
sap_profile             str     "S4HANA_CLOUD" or "ECC_ONPREMISE"

# S/4HANA Cloud:
client_id               str     SAP BTP OAuth2 client ID
client_secret           str
token_url               str     e.g. "https://[subdomain].authentication.eu10.hana.ondemand.com/oauth/token"
api_base_url            str     e.g. "https://[tenant].s4hana.ondemand.com"
company_code            str

# ECC On-Premise:
sap_host                str
sap_port                int     default 8000
sap_client              str     e.g. "100"
sap_username            str
sap_password            str
sap_system_id           str
```

### S/4HANA Cloud — supported datasets and API mapping

```
CHART_OF_ACCOUNTS       → /API_GLACCOUNT_0001/A_GLAccount
TRIAL_BALANCE           → /API_GLACCOUNTBALANCE_0001/A_GLAccountBalance (aggregated)
GENERAL_LEDGER          → /API_JOURNALENTRYITEMBASIC_0001/A_JournalEntryItem
PROFIT_AND_LOSS         → /API_FINANCIALPLANNINGDATA_0001 or custom CDS view
BALANCE_SHEET           → same as above
ACCOUNTS_RECEIVABLE     → /API_CUSTOMER_0001/A_CustomerCompany + payment data
ACCOUNTS_PAYABLE        → /API_SUPPLIER_0001/A_SupplierCompany + payment data
AR_AGEING               → custom report via /sap/opu/odata/sap/
AP_AGEING               → custom report
INVOICE_REGISTER        → /API_BILLING_DOCUMENT_SRV/A_BillingDocument
PURCHASE_REGISTER       → /API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrder
BANK_STATEMENT          → /API_BANKACCOUNTSTATEMENT_0001/A_BankStatementItem
FIXED_ASSET_REGISTER    → /API_FIXEDASSET_0001/A_FixedAsset
PAYROLL_SUMMARY         → /API_PAYROLLRESULT_SRV (if payroll module active)
VENDOR_MASTER           → /API_BUSINESS_PARTNER/A_BusinessPartner
CUSTOMER_MASTER         → /API_BUSINESS_PARTNER/A_BusinessPartner
CURRENCY_MASTER         → /API_EXCHANGERATE_0001/A_ExchangeRate
```

### ECC On-Premise — supported datasets and integration pattern

For ECC, use SAP's RFC/BAPI interface via the SAP Connector for Python (`pyrfc`).
Note: `pyrfc` requires SAP NW RFC SDK libraries — document installation separately.

```
CHART_OF_ACCOUNTS   → BAPI_GL_GETGLACCOUNTS
TRIAL_BALANCE       → BAPI_GL_GETBALANCE
GENERAL_LEDGER      → BAPI_GL_GETITEMS
ACCOUNTS_RECEIVABLE → BAPI_AR_ACC_GETKEYFIGURES
ACCOUNTS_PAYABLE    → BAPI_AP_ACC_GETKEYFIGURES
INVOICE_REGISTER    → BAPI_BILLINGDOC_GETLIST
PURCHASE_REGISTER   → BAPI_PO_GETLIST
VENDOR_MASTER       → BAPI_VENDOR_GETLIST
CUSTOMER_MASTER     → BAPI_CUSTOMER_GETLIST
```

### Implementation requirements

- S/4HANA Cloud: all calls via `async httpx` with OAuth2 bearer token
- ECC On-Premise: `pyrfc` calls wrapped in `asyncio.run_in_executor` to avoid blocking
- `pyrfc` is an optional dependency — if not installed, ECC profile raises
  `ConnectorDependencyMissing("pyrfc not installed. Install SAP NW RFC SDK and pyrfc to use ECC.")` 
- `supports_resumable_extraction: True` for S/4HANA Cloud (OData `$skip`/`$top`)
- `supports_resumable_extraction: False` for ECC (BAPI returns full dataset)
- Checkpoint (S/4HANA): `{"skip": N, "page_size": 500}`
- Large GL extractions: log warning if estimated records > 100,000, recommend date-range split
- `erp_control_totals`: available from S/4HANA balance summary endpoints and ECC BAPI totals

---

## PART B — ORACLE CONNECTOR

File: `infrastructure/connectors/oracle.py`

Oracle also has two integration profiles. Route based on `oracle_profile` credential field.

### Credentials schema

```
oracle_profile          str     "FUSION_CLOUD" or "EBS_ONPREMISE"

# Oracle Fusion Cloud:
client_id               str     Oracle IDCS OAuth2 client ID
client_secret           str
token_url               str     e.g. "https://[tenant].login.us2.oraclecloud.com/oauth2/v1/token"
api_base_url            str     e.g. "https://[tenant].fa.us2.oraclecloud.com"
business_unit_name      str

# Oracle EBS On-Premise:
ebs_host                str
ebs_port                int     default 8000
ebs_username            str
ebs_password            str
ebs_responsibility_key  str
```

### Oracle Fusion Cloud — supported datasets and API mapping

```
CHART_OF_ACCOUNTS       → /fscmRestApi/resources/v11.13.18.05/chart-of-accounts
TRIAL_BALANCE           → /fscmRestApi/resources/v11.13.18.05/ledgerBalances
GENERAL_LEDGER          → /fscmRestApi/resources/v11.13.18.05/journalEntries
PROFIT_AND_LOSS         → /analytics (Oracle BI Publisher reports endpoint)
BALANCE_SHEET           → /analytics
ACCOUNTS_RECEIVABLE     → /fscmRestApi/resources/v11.13.18.05/receivables
ACCOUNTS_PAYABLE        → /fscmRestApi/resources/v11.13.18.05/payables
INVOICE_REGISTER        → /fscmRestApi/resources/v11.13.18.05/receivablesInvoices
PURCHASE_REGISTER       → /procurementRestApi/resources/v11.13.18.05/purchaseOrders
BANK_STATEMENT          → /fscmRestApi/resources/v11.13.18.05/cashManagementTransactions
FIXED_ASSET_REGISTER    → /fscmRestApi/resources/v11.13.18.05/fixedAssets
VENDOR_MASTER           → /fscmRestApi/resources/v11.13.18.05/suppliers
CUSTOMER_MASTER         → /fscmRestApi/resources/v11.13.18.05/customers
CURRENCY_MASTER         → /fscmRestApi/resources/v11.13.18.05/currencies
```

### Oracle EBS On-Premise

Use Oracle's XML Gateway / REST services available in EBS 12.2+.
Alternatively, direct DB read via Oracle JDBC if REST not available — wrap in executor.

For EBS, support same dataset types as Fusion where REST is available.
Document per-dataset the EBS API or table source in connector comments.

### Implementation requirements

- Fusion Cloud: all calls via `async httpx` with OAuth2 bearer token
- EBS On-Premise: `cx_Oracle` or `oracledb` (Oracle Python driver) via executor
- `cx_Oracle`/`oracledb` is optional — if not installed, EBS raises `ConnectorDependencyMissing`
- `supports_resumable_extraction: True` for Fusion (REST pagination)
- Checkpoint: `{"offset": N, "limit": 500}`
- Oracle BI Publisher reports require special handling — document in connector
- `erp_control_totals`: ledger balance summary from Oracle REST

---

## PART C — INDIA COMPLIANCE STACK

### C1 — Activate GSTR-9 and GSTR-9C schemas

In `domain/canonical/gst_returns.py`, replace the stub classes with full implementations:

```python
class CanonicalGSTR9Summary(BaseModel):
    financial_year: str             # "2024-25"
    entity_id: str
    gstin: str
    total_outward_supplies: Decimal
    total_outward_taxable: Decimal
    total_outward_exempted: Decimal
    total_outward_nil_rated: Decimal
    total_outward_non_gst: Decimal
    total_inward_supplies: Decimal
    total_itc_availed: Decimal
    total_itc_cgst: Decimal
    total_itc_sgst: Decimal
    total_itc_igst: Decimal
    total_itc_cess: Decimal
    total_tax_payable: Decimal
    total_tax_paid: Decimal
    total_interest_paid: Decimal
    total_late_fee_paid: Decimal
    filing_status: str              # FILED / PENDING / NIL
    filing_date: date | None
    pii_masked: bool
    dataset_token: str

class CanonicalGSTR9C(BaseModel):
    financial_year: str
    entity_id: str
    gstin: str
    turnover_as_per_books: Decimal
    turnover_as_per_gst: Decimal
    variance: Decimal
    reason_for_variance: str | None
    itc_as_per_books: Decimal
    itc_as_per_gstr3b: Decimal
    itc_variance: Decimal
    net_tax_payable_as_per_books: Decimal
    net_tax_paid_as_per_gst: Decimal
    tax_variance: Decimal
    auditor_name: str | None
    auditor_firm: str | None
    auditor_certified: bool
    filing_status: str
    filing_date: date | None
    pii_masked: bool
    dataset_token: str
```

### C2 — Create `domain/canonical/form_26as_ais.py`

```python
from decimal import Decimal
from datetime import date
from pydantic import BaseModel


class Canonical26ASEntry(BaseModel):
    deductor_tan: str
    deductor_name: str
    tds_section: str
    payment_nature: str
    payment_date: date
    amount_paid: Decimal
    tds_deducted: Decimal
    tds_deposited: Decimal
    certificate_number: str | None
    remarks: str | None
    pii_masked: bool

class CanonicalForm26AS(BaseModel):
    financial_year: str             # "2024-25"
    assessment_year: str            # "2025-26"
    entity_id: str
    pan_number: str | None          # last 4 chars only — hard rule
    entries: list[Canonical26ASEntry]
    total_tds_as_per_26as: Decimal
    total_tds_deposited: Decimal
    pii_masked: bool
    dataset_token: str


class CanonicalAISEntry(BaseModel):
    transaction_type: str           # SALARY/DIVIDEND/INTEREST/PURCHASE/SALE/RENT/OTHER
    source: str                     # payer/deductor name
    source_pan: str | None          # masked
    amount: Decimal
    tds_tcs: Decimal
    financial_year: str
    reported_by: str                # entity reporting to IT dept
    pii_masked: bool

class CanonicalAISRegister(BaseModel):
    financial_year: str
    assessment_year: str
    entity_id: str
    pan_number: str | None          # last 4 chars only — hard rule
    entries: list[CanonicalAISEntry]
    total_income_reported: Decimal
    total_tds_tcs: Decimal
    pii_masked: bool
    dataset_token: str
```

### C3 — Add normalizers

In `application/normalization_service.py`, add normalization handlers for:
- `DatasetType.GST_RETURN_GSTR9` → `CanonicalGSTR9Summary`
- `DatasetType.GST_RETURN_GSTR9C` → `CanonicalGSTR9C`
- `DatasetType.FORM_26AS` → `CanonicalForm26AS`
- `DatasetType.AIS_REGISTER` → `CanonicalAISRegister`

### C4 — Add validators

In `application/validation_service.py`, add validation coverage for all 4 new types.

Key validation rules:
- `GSTR9_PERIOD_CONSISTENCY`: financial_year format must be "YYYY-YY" (e.g. "2024-25")
- `GSTR9C_VARIANCE_COMPLETENESS`: if `variance != 0` then `reason_for_variance` must be populated
- `FORM_26AS_PAN_MASKING`: `pan_number` must never contain more than 4 unmasked chars
- `AIS_PAN_MASKING`: same rule

### C5 — Update dataset_service.py

Mark all 4 dataset types as active (remove any "Phase 4F" status flags if present).

### C6 — Update publish_service.py (one line only)

Update TDS Reconciliation engine entry:

```python
# Replace:
# TDS Reconciliation: TDS_REGISTER (+ FORM_26AS, AIS_REGISTER when Phase 4F lands)

# With:
# TDS Reconciliation: TDS_REGISTER, FORM_26AS, AIS_REGISTER
```

---

## STEP 1 — DEPENDENCIES

Add to `pyproject.toml`:
```toml
# SAP ECC (optional — only needed for ECC on-premise profile)
# pyrfc is not on PyPI — document manual installation via SAP NW RFC SDK
# Do NOT add pyrfc to pyproject.toml — it cannot be pip-installed without SAP SDK
# Handle via ConnectorDependencyMissing exception

# Oracle EBS (optional — only needed for EBS on-premise profile)
oracledb = ">=2.0,<3.0"    # modern Oracle Python driver (replaces cx_Oracle)
```

Note: `oracledb` can be installed without Oracle client libraries for thin mode.
Thin mode supports most Oracle Cloud/EBS REST endpoints.
Document thin vs thick mode in `oracle.py` connector comments.

---

## STEP 2 — IMPLEMENTATION ORDER

1. India compliance schemas (C1–C5) → tests pass
2. publish_service.py TDS update (C6) → tests pass
3. SAP S/4HANA Cloud profile → tests pass
4. SAP ECC profile (with ConnectorDependencyMissing fallback) → tests pass
5. Oracle Fusion Cloud profile → tests pass
6. Oracle EBS profile (with ConnectorDependencyMissing fallback) → tests pass
7. Full suite → zero failures

---

## STEP 3 — TESTS

```
tests/unit/erp_sync/connectors/
  test_sap_connector.py
    # - S4HANA_CLOUD: mock OAuth2 + OData responses per dataset type
    # - ECC_ONPREMISE: mock pyrfc BAPI responses
    # - ECC with pyrfc not installed → ConnectorDependencyMissing raised cleanly
    # - profile routing (S4HANA vs ECC)
    # - large extraction warning (> 100k records)
    # - erp_control_totals extraction

  test_oracle_connector.py
    # - FUSION_CLOUD: mock OAuth2 + REST responses per dataset type
    # - EBS_ONPREMISE: mock oracledb responses
    # - EBS with oracledb thin mode
    # - profile routing
    # - BI Publisher report endpoint handling

tests/unit/erp_sync/
  test_gstr9_schemas.py
    # - CanonicalGSTR9Summary field validation
    # - CanonicalGSTR9C — variance with reason vs without
    # - GSTR9_PERIOD_CONSISTENCY validation rule
    # - GSTR9C_VARIANCE_COMPLETENESS validation rule

  test_form_26as_ais_schemas.py
    # - CanonicalForm26AS PAN masking rule enforced
    # - CanonicalAISRegister PAN masking rule enforced
    # - FORM_26AS_PAN_MASKING validation rule
    # - AIS_PAN_MASKING validation rule

tests/integration/erp_sync/
  test_sap_integration.py
    # - full flow: S4HANA Cloud → raw → canonical → validation
    # - test with COA, TB, GL

  test_oracle_integration.py
    # - full flow: Fusion Cloud → raw → canonical → validation

  test_india_compliance_stack.py
    # - GSTR-9 full flow: extraction → normalization → validation → publish
    # - GSTR-9C variance reconciliation flow
    # - Form 26AS TDS reconciliation flow
    # - AIS register flow
    # - TDS Reconciliation engine consumption: TDS_REGISTER + FORM_26AS + AIS together
```

---

## FINAL STATE VERIFICATION

After Phase 4F, run full verification:

```bash
# Full test suite — must be zero failures
pytest tests/ -x -q

# Verify all 23 connectors are LIVE
python -c "
from financeops.modules.erp_sync.infrastructure.connectors.registry import CONNECTOR_REGISTRY
from financeops.modules.erp_sync.domain.enums import ConnectorType
import asyncio

async def check():
    for ct, cls in CONNECTOR_REGISTRY.items():
        instance = cls()
        cap = await instance.declare_capabilities()
        status = cap.implementation_status
        print(f'{ct.value:30} {status}')

asyncio.run(check())
# Every connector must print: live
"

# Verify all 46 dataset types have active normalizer
python -c "
from financeops.modules.erp_sync.application.normalization_service import NormalizationService
from financeops.modules.erp_sync.domain.enums import DatasetType
svc = NormalizationService()
deferred = [DatasetType.GST_RETURN_GSTR9, DatasetType.GST_RETURN_GSTR9C,
            DatasetType.FORM_26AS, DatasetType.AIS_REGISTER]
for dt in DatasetType:
    has_normalizer = svc.has_normalizer(dt)
    print(f'{dt.value:45} {has_normalizer}')
# All must print True
"

# Security grep checks
grep -r "sap\|oracle\|tally\|zoho\|quickbooks" financeops/modules/*/application/ \
     financeops/modules/*/domain/ --include="*.py" | grep -v "erp_sync"
# Must return empty — no source system names in frozen engines

grep -rn "pan_number\s*=" financeops/modules/erp_sync/ --include="*.py" | \
     grep -v "masked\|mask\|last_4\|test\|canonical"
# Review any matches — no full PAN should be stored

# Final docker check
docker-compose up -d
docker-compose ps
# All services must show: Up (healthy)
```

---

## DEFINITION OF DONE

- [ ] SAP S/4HANA Cloud profile implemented for all supported dataset types
- [ ] SAP ECC on-premise profile implemented with `ConnectorDependencyMissing` fallback
- [ ] Oracle Fusion Cloud profile implemented for all supported dataset types
- [ ] Oracle EBS on-premise profile implemented with `ConnectorDependencyMissing` fallback
- [ ] SAP and Oracle `implementation_status = LIVE`
- [ ] `CanonicalGSTR9Summary` fully implemented (replacing stub)
- [ ] `CanonicalGSTR9C` fully implemented (replacing stub)
- [ ] `CanonicalForm26AS` and `CanonicalAISRegister` implemented in new file
- [ ] Normalizers for all 4 new dataset types implemented and tested
- [ ] Validators for all 4 new dataset types implemented and tested
- [ ] TDS Reconciliation consumption table updated in publish_service.py
- [ ] `oracledb` added to `pyproject.toml`
- [ ] All new test files passing
- [ ] All prior phase tests still passing
- [ ] `pytest` zero failures
- [ ] All 23 connectors report `implementation_status = LIVE`
- [ ] All 46 dataset types have active normalizer
- [ ] `docker-compose ps` all healthy
- [ ] Grep: no source system name in any frozen engine
- [ ] Grep: no raw credential in any log or JSONB
- [ ] Grep: no full PAN or full bank account number stored anywhere

---

## CRITICAL RULES

- Python 3.11 only
- `async def` everywhere — Oracle/SAP sync calls wrapped in `run_in_executor`
- `Decimal` not `float`
- No new migrations (all enum values were declared in Phase 4C — `DatasetType` is VARCHAR)
- No changes to any canonical schema other than the 4 explicitly listed
- No changes to any model
- No UPDATE / DELETE on financial tables
- All secrets from `.env`
- `WindowsSelectorEventLoopPolicy()` stays untouched
- `asyncio_default_test_loop_scope = "session"` stays untouched
- Run `pytest` after each part — zero failures throughout

---

*2 enterprise connectors. 4 India compliance datasets. 23 total connectors live.
46 dataset types active. erp_sync module complete.*
