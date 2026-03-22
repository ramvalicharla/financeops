# FinanceOps — Phase 4D: Indian SMB Connectors
## Claude Code Implementation Prompt — v1 (Final)

> Prerequisite: Phase 4C complete, zero test failures, all 21 stubs in registry.
> Paste this entire prompt into Claude Code. Do not modify it.
> This phase is purely additive. The canonical kernel is frozen. Do not touch it.

---

## WHO YOU ARE AND WHERE YOU ARE

You are Claude Code working inside the FinanceOps repository at `D:\finos\`.

**What Phase 4D delivers:**
Implementation of 4 Indian SMB / desktop ERP connectors that were stubs in Phase 4C:
- `Tally` (Tally Prime / Tally ERP 9)
- `Busy` (Busy Accounting Software)
- `Marg` (Marg ERP — pharma/FMCG India)
- `Munim` / Vyapar (micro-SMB India)

**The only files permitted to change outside connector files:**
- `infrastructure/connectors/registry.py` — capability status update only (implementation_status STUB → LIVE)
- `tests/` — new test files only, no edits to existing passing tests
- `docs/` — connector documentation

**No changes permitted to:**
- Any canonical schema in `domain/canonical/`
- Any service in `application/`
- Any model in `domain/models.py`
- Any enum in `domain/enums.py`
- Any migration
- Any frozen engine (phases 0–3)

---

## STEP 0 — CONFIRM PHASE 4C IS COMPLETE

```bash
# Must show zero failures before writing a single line
pytest tests/ -x -q

# Confirm all 4 connectors are currently stubs
python -c "
from financeops.modules.erp_sync.infrastructure.connectors.tally import TallyConnector
from financeops.modules.erp_sync.infrastructure.connectors.busy import BusyConnector
from financeops.modules.erp_sync.infrastructure.connectors.marg import MargConnector
from financeops.modules.erp_sync.infrastructure.connectors.munim import MunimConnector
import asyncio
t = TallyConnector()
cap = asyncio.run(t.declare_capabilities())
print('Tally status:', cap.implementation_status)  # Must print: stub
"

# Read the abstract connector contract before touching any connector file
D:\finos\financeops\modules\erp_sync\infrastructure\connectors\base.py
D:\finos\financeops\modules\erp_sync\infrastructure\connectors\capability.py
D:\finos\financeops\modules\erp_sync\domain\canonical\   ← read but do not modify
```

State the following before writing code:
```
PHASE 4C TEST STATUS    : [zero failures confirmed]
TALLY CURRENT STATUS    : [stub confirmed]
BUSY CURRENT STATUS     : [stub confirmed]
MARG CURRENT STATUS     : [stub confirmed]
MUNIM CURRENT STATUS    : [stub confirmed]
```

---

## CONNECTOR 1 — TALLY PRIME / TALLY ERP 9

File: `infrastructure/connectors/tally.py`

### Protocol

Tally exposes an HTTP XML Gateway on the local machine (default port 9000).
FinanceOps sends HTTP POST requests with a TDL (Tally Definition Language) XML request
body and receives an XML response.

For cloud-hosted Tally (Tally on AWS/Azure/VPS):
- Same protocol, different host
- Support both `localhost` and remote host via `tally_host` credential field

### Credentials schema

```
tally_host          str     default "localhost"
tally_port          int     default 9000
tally_company_name  str     required — must match exact company name in Tally
username            str     optional (Tally security if enabled)
password            str     optional
```

### Authentication / connection test

1. Send minimal XML request to get Tally version
2. Verify company name matches `tally_company_name`
3. Return `ConnectionTestResult` with Tally version string

### Supported dataset types

```
CHART_OF_ACCOUNTS, TRIAL_BALANCE, GENERAL_LEDGER,
PROFIT_AND_LOSS, BALANCE_SHEET,
ACCOUNTS_RECEIVABLE, ACCOUNTS_PAYABLE,
INVOICE_REGISTER, PURCHASE_REGISTER, CREDIT_NOTE_REGISTER, DEBIT_NOTE_REGISTER,
BANK_STATEMENT, TDS_REGISTER,
GST_RETURN_GSTR1, EINVOICE_REGISTER,
VENDOR_MASTER, CUSTOMER_MASTER
```

### Implementation requirements

- All XML parsing via `lxml` (add to `pyproject.toml` if not present)
- Build TDL XML request per dataset type — each type has its own TDL query structure
- Parse XML response into `RawPayload.raw_data` as a Python dict
- `supports_resumable_extraction: False` — Tally XML pulls full dataset per request
  (Tally has no native pagination — the entire dataset is returned in one response)
- For large GL datasets: warn in logs if `line_count > 50000` — advise date-range narrowing
- `erp_control_totals`: extract from Tally's closing balance fields in TB/BS response
- All amounts from Tally come as strings with commas — convert to `Decimal` in `RawPayload.raw_data`
  (normalizer handles canonical conversion — connector only provides clean raw dict)
- Handle Tally's `-` prefix for credit amounts (Tally uses negative for credit in some reports)
- Character encoding: Tally XML may return in Windows-1252 — detect and re-encode to UTF-8

### TDL XML templates (implement one per supported dataset type)

Document each TDL query in comments within the connector file. Example structure:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>List of Ledgers</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <SVFROMDATE>{from_date}</SVFROMDATE>
        <SVTODATE>{to_date}</SVTODATE>
        <SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>
```

---

## CONNECTOR 2 — BUSY ACCOUNTING SOFTWARE

File: `infrastructure/connectors/busy.py`

### Protocol

Busy v21+ supports a REST API. Older versions require ODBC or direct DB access.
Support both modes via a `connection_mode` credential field.

### Credentials schema

```
connection_mode     str     "REST_API" or "ODBC"
# REST API mode:
busy_host           str     e.g. "localhost" or remote IP
busy_port           int     default 8080
api_key             str
company_code        str
# ODBC mode:
odbc_dsn            str
odbc_username       str
odbc_password       str
company_name        str
```

### Supported dataset types

```
CHART_OF_ACCOUNTS, TRIAL_BALANCE, GENERAL_LEDGER,
ACCOUNTS_RECEIVABLE, ACCOUNTS_PAYABLE, AR_AGEING, AP_AGEING,
INVOICE_REGISTER, PURCHASE_REGISTER, BANK_STATEMENT,
GST_RETURN_GSTR1, EINVOICE_REGISTER,
VENDOR_MASTER, CUSTOMER_MASTER
```

### Implementation requirements

- REST API mode: all calls via `async httpx`
- ODBC mode: use `pyodbc` (add to `pyproject.toml`) — wrap in `asyncio.run_in_executor`
  to avoid blocking the event loop
- `supports_resumable_extraction: True` in REST mode; `False` in ODBC mode
- Checkpoint format (REST mode): `{"page": N, "page_size": 100}`
- `erp_control_totals`: available from Busy's summary endpoint in REST mode

---

## CONNECTOR 3 — MARG ERP

File: `infrastructure/connectors/marg.py`

### Protocol

Marg ERP does not have a public REST API. The extraction model is:
**file-based** — the user exports reports from Marg as CSV files and uploads them
to FinanceOps. This connector is a specialised variant of `GenericFileConnector`
with Marg-specific column name mappings baked in.

### Credentials schema

```
marg_version        str     e.g. "9.0", "9.5", "10.0"
# No API credentials — file-based extraction only
```

### Supported dataset types

```
CHART_OF_ACCOUNTS, TRIAL_BALANCE, GENERAL_LEDGER,
INVOICE_REGISTER, PURCHASE_REGISTER,
INVENTORY_REGISTER, INVENTORY_MOVEMENT,
TDS_REGISTER, GST_RETURN_GSTR1
```

### Implementation requirements

- Extend `GenericFileConnector` — do not duplicate file parsing logic
- Add Marg-specific column mapping dictionary per dataset type and per Marg version
  (Marg changes column names between versions — handle v9.x and v10.x mappings)
- `supports_resumable_extraction: True` (same as Generic File chunking)
- `erp_control_totals`: if Marg export includes a totals row at bottom, extract it
- Document expected column names per dataset type per version in connector comments

Example column mapping for Trial Balance:
```python
MARG_TB_COLUMNS = {
    "v9": {
        "Account Name": "account_name",
        "Account Code": "account_code",
        "Opening Dr": "opening_debit",
        "Opening Cr": "opening_credit",
        "Closing Dr": "closing_debit",
        "Closing Cr": "closing_credit",
    },
    "v10": {
        "Ledger Name": "account_name",
        "Ledger Code": "account_code",
        # ...
    }
}
```

---

## CONNECTOR 4 — MUNIM / VYAPAR

File: `infrastructure/connectors/munim.py`

### Protocol

Munim and Vyapar are micro-SMB tools. Neither has a public REST API for third-party
integration. Extraction model: **file-based** (CSV/Excel export from the app).

### Credentials schema

```
app_variant         str     "MUNIM" or "VYAPAR"
app_version         str     e.g. "2.0", "3.0"
```

### Supported dataset types

```
CHART_OF_ACCOUNTS, TRIAL_BALANCE, GENERAL_LEDGER,
ACCOUNTS_RECEIVABLE, ACCOUNTS_PAYABLE,
INVOICE_REGISTER, PURCHASE_REGISTER
```

### Implementation requirements

- Extend `GenericFileConnector` — same pattern as Marg
- Column mappings per app variant and version
- `supports_resumable_extraction: True`
- Note in connector docstring: Vyapar and Munim are separate apps that merged —
  handle both column name conventions

---

## STEP 1 — IMPLEMENTATION ORDER

Build and test in this exact order. Do not proceed to the next connector until
the current one has zero test failures.

1. Tally connector unit tests (mock XML responses) → pass
2. Tally connector integration test → pass
3. Busy connector unit tests (mock REST + mock ODBC) → pass
4. Busy connector integration test → pass
5. Marg connector unit tests (sample CSV files per version) → pass
6. Marg connector integration test → pass
7. Munim connector unit tests → pass
8. Munim connector integration test → pass
9. Full test suite → zero failures

---

## STEP 2 — DEPENDENCIES

Add to `pyproject.toml` if not already present:
```toml
lxml = ">=4.9,<6.0"        # Tally XML parsing
pyodbc = ">=4.0,<5.0"      # Busy ODBC mode
```

Run after adding:
```bash
pip install lxml pyodbc --break-system-packages
pytest tests/ -x -q
```

---

## STEP 3 — TESTS

```
tests/unit/erp_sync/connectors/
  test_tally_connector.py
    # - XML request generation per dataset type
    # - XML response parsing (mock responses with sample Tally XML)
    # - Amount conversion (string with commas → Decimal)
    # - Credit amount sign handling (Tally negative prefix)
    # - Windows-1252 encoding detection and re-encoding
    # - company_name mismatch → ConnectionTestResult failure
    # - erp_control_totals extracted from TB response

  test_busy_connector.py
    # - REST mode: mock httpx responses per dataset type
    # - ODBC mode: mock pyodbc cursor
    # - connection_mode routing
    # - resumable extraction checkpoint
    # - erp_control_totals from summary endpoint

  test_marg_connector.py
    # - v9.x column mapping → canonical field names
    # - v10.x column mapping → canonical field names
    # - totals row detection and extraction
    # - missing required column → ExtractionError with clear message

  test_munim_connector.py
    # - MUNIM variant column mapping
    # - VYAPAR variant column mapping
    # - version-specific column handling

tests/integration/erp_sync/connectors/
  test_tally_connector_integration.py
    # - full extraction flow: scope → raw payload → normalizer → canonical → validation
    # - test with COA, TB, GL mock responses

  test_busy_connector_integration.py
  test_marg_connector_integration.py
  test_munim_connector_integration.py
```

All mock responses must be realistic samples — not minimal empty structures.
Create fixture files in `tests/fixtures/connectors/tally/`, `busy/`, `marg/`, `munim/`.

---

## STEP 4 — UPDATE REGISTRY CAPABILITY STATUS

After all 4 connectors are implemented and tested, update `registry.py` comments
and `declare_capabilities()` in each connector:

```python
# In each connector's declare_capabilities():
implementation_status=ConnectorImplementationStatus.LIVE,
available_in_phase="4D",  # leave as record of when it was implemented
```

---

## DEFINITION OF DONE

- [ ] Tally connector implemented for all 17 supported dataset types
- [ ] Tally XML templates documented in connector file
- [ ] Busy connector implemented for both REST and ODBC modes
- [ ] Marg connector implemented with v9.x and v10.x column mappings
- [ ] Munim connector implemented for both MUNIM and VYAPAR variants
- [ ] All 4 connectors have `implementation_status = LIVE`
- [ ] All 4 connectors declare accurate `supported_datasets` in capability matrix
- [ ] `lxml` and `pyodbc` added to `pyproject.toml`
- [ ] Unit test fixtures contain realistic sample data (not minimal stubs)
- [ ] All 8 new test files passing
- [ ] All Phase 4C tests still passing
- [ ] All prior phase tests still passing
- [ ] `pytest` zero failures
- [ ] Grep: no source system name in any frozen engine
- [ ] Grep: no raw credential in any log or JSONB

---

## CRITICAL RULES

- Python 3.11 only
- `async def` everywhere — ODBC calls wrapped in `run_in_executor`
- `Decimal` not `float`
- No UPDATE / DELETE on any financial table
- All secrets from `.env`
- No changes to any canonical schema, model, migration, or frozen engine
- `WindowsSelectorEventLoopPolicy()` stays untouched
- `asyncio_default_test_loop_scope = "session"` stays untouched
- Run `pytest` after each connector — zero failures throughout

---

*4 Indian SMB connectors. Zero kernel changes. Then open Phase 4E.*
