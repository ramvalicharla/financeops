# reference implementation ERP Audit — Zoho Books & QuickBooks Online JV Patterns
<!-- Source: FinanceOps-native implementation | Audited: 2026-03-27 | Read-only audit -->
<!-- Purpose: Extract proven JV creation + attachment patterns for porting to FinanceOps (D:\finos) -->

---

## 1. Repository Inventory

### ERP Connector Files
| File | Purpose |
|------|---------|
| `backend/connectors/erp/base.py` | Abstract `ERPAdapter` base class + `ERPResponse` type |
| `backend/connectors/erp/zoho_auth.py` | Zoho OAuth 2.0 — authorize URL, code exchange, token refresh |
| `backend/connectors/erp/zoho_books.py` | `ZohoBooksAdapter` — JV post, COA sync, status poll |
| `backend/connectors/erp/quickbooks_auth.py` | QBO OAuth 2.0 — authorize URL, code exchange, token refresh |
| `backend/connectors/erp/quickbooks_online.py` | `QuickBooksOnlineAdapter` — JV post, COA sync, status poll |
| `backend/connectors/erp/tally_prime_xml.py` | Tally Prime XML connector (bonus — on-premises Indian ERP) |
| `backend/connectors/erp/tally_prime_odbc.py` | Tally Prime ODBC connector |
| `backend/connectors/erp/tally_xml_codec.py` | Tally XML serialization utilities |
| `backend/db/engine3/erp_posting_packet_builder.py` | `build_posting_packet()` + `compute_idempotency_key()` |
| `backend/tests/test_engine3_phase4c_zoho.py` | Zoho connector test suite |
| `backend/tests/test_engine3_phase4c_quickbooks.py` | QBO connector test suite |

### Architecture
- **Pattern**: `ERPAdapter` ABC → concrete adapters (`ZohoBooksAdapter`, `QuickBooksOnlineAdapter`)
- **Transport**: Synchronous `urllib.request` — **must be async-wrapped for FinanceOps** (asyncio + `run_in_executor`)
- **Response envelope**: `ERPResponse = dict[str, Any]` with keys `status`, `external_id`, `error_code`, `error_message`, `raw_response`

---

## 2. Zoho Books — Full Capability Audit

### 2a. Authentication (`zoho_auth.py`)

**OAuth flow**: Standard Authorization Code with optional PKCE (S256).

**Authorize URL**: `https://accounts.zoho.{region}/oauth/v2/auth`
- Default scope: `ZohoBooks.fullaccess.all`
- Supports `access_type=offline` for refresh tokens
- Region resolved from: `ZOHO_REGION` env → `connection_config["region"]` → `"com"`

**Token exchange**: POST to `https://accounts.zoho.{region}/oauth/v2/token`
- Form body: `grant_type=authorization_code`, `client_id`, `client_secret`, `redirect_uri`, `code`
- Optional: `code_verifier` (PKCE)
- **Auth**: Form body only (no Basic auth header) — credentials in POST body

**Token refresh**: Same URL, `grant_type=refresh_token`
- `client_id` + `client_secret` + `refresh_token` in form body

**Normalized token payload**:
```python
{
    "provider": "ZOHO_BOOKS",
    "access_token": str,
    "refresh_token": str,
    "token_type": "Bearer",
    "expires_in_seconds": int,            # typically 3600
    "refresh_expires_in_seconds": int,    # typically 86400
    "expires_at_utc": "2026-03-27T12:00:00Z",
    "refresh_expires_at_utc": "2026-03-28T12:00:00Z",
    "region": "com",                      # or "in", "eu", etc.
    "api_domain": "https://www.zohoapis.com",   # if returned by Zoho
    "organization_id": "12345678",        # if in connection_config
}
```

**Key gotcha**: `api_domain` is returned by Zoho in the token response and must be stored — it becomes the API base URL for all subsequent calls (takes priority over region-derived URL).

### 2b. JV Creation (`zoho_books.py` → `post_journal()`)

**Endpoint**: `POST https://www.zohoapis.{region}/books/v3/journals?organization_id={org_id}`

**Request headers**:
```
Authorization: Zoho-oauthtoken {access_token}
Content-Type: application/json;charset=UTF-8
Accept: application/json
```

**Request body**:
```json
{
    "journal_date": "2026-03-27",
    "notes": "memo text",
    "line_items": [
        {
            "account_id": "123456789012345",
            "debit_or_credit": "debit",
            "amount": "10000.00",
            "description": "optional line description"
        },
        {
            "account_id": "987654321098765",
            "debit_or_credit": "credit",
            "amount": "10000.00",
            "description": ""
        }
    ]
}
```

**Critical detail**: `account_id` is the Zoho internal numeric ID, NOT the account code. Must map from COA sync first.

**Line validation rules**:
- A line cannot have both debit and credit > 0
- Lines with both debit and credit = 0 are silently skipped
- Amounts are quantized to `Decimal("0.01")`

**Success response** — Zoho wraps the created journal in `response["journal"]`:
```json
{
    "code": 0,
    "journal": {
        "journal_id": "12345678901234567",
        "journal_number": "JNL-001234"
    }
}
```
- `external_id` = `journal["journal_id"]` (preferred) or `journal["journal_number"]`

**Error response codes** (Zoho-layer):
- `code=57` or `code=1001` → `ZOHO_AUTH_INVALID_TOKEN`
- Any other non-zero → `ZOHO_PAYLOAD_INVALID`

**HTTP-level error codes**:
- 401/403 → `ZOHO_AUTH_INVALID_TOKEN`
- 429 → `ZOHO_RATE_LIMIT`
- 5xx → `ZOHO_NETWORK`
- 400/404/422 → `ZOHO_PAYLOAD_INVALID`

**Simulation mode**: Packet can include `simulation_mode: "timeout" | "hard_fail" | "soft_fail" | "auth_fail"` — adapter returns deterministic simulated responses. Useful for testing retry logic.

**Live mode detection**: Adapter checks for `ZOHO_CLIENT_ID` + `ZOHO_CLIENT_SECRET` env vars AND valid `access_token` AND `organization_id`. If any missing → simulated mode (returns fake `zoho_{uuid}` external_id).

### 2c. JV Status Poll (`get_journal_status()`)

**Endpoint**: `GET /books/v3/journals/{journal_id}?organization_id={org_id}`

**Response mapping**:
- Zoho status `DRAFT` or `PENDING` → normalized `PENDING`
- Everything else → `SUCCESS`

### 2d. Journal Reversal (`reverse_journal()`)

Currently **stubbed** — returns simulated `zoho_rev_{uuid}`. Not implemented for live API.

### 2e. COA Sync (`sync_chart_of_accounts()`)

**Endpoint**: `GET /books/v3/chartofaccounts?organization_id={org_id}`

**Response parsing**: `response["chartofaccounts"]` → list of account dicts.

**Normalized item shape**:
```python
{
    "object_type": "ACCOUNT",
    "object_key": account_id,        # Zoho internal numeric ID (primary key for line_items)
    "payload": {
        "account_id": str,
        "account_code": str,         # Human-readable code (e.g., "1000")
        "account_name": str,
        "account_type": str,         # e.g., "expense", "income", "asset"
        "status": str,               # "active" / "inactive"
    },
    "source_timestamp": str | None,  # last_modified_time from Zoho
}
```

### 2f. Attachment Support

**None.** No `upload_attachment()` or `link_attachment_to_journal()` methods exist in reference implementation. Must be built from scratch for FinanceOps using:
- `POST /books/v3/journals/{journal_id}/documents` (multipart/form-data)
- Zoho returns `document_id` to confirm attachment linkage

### 2g. Error Handling Patterns

**Error class**: `_ZohoApiError(RuntimeError)` with `code: str`, `message: str`, `raw_response: dict`

**Error extraction**: `payload.get("message") or payload.get("error_description") or payload.get("error") or "Zoho API error"`

**Pattern**: All API calls wrapped in `try/_ZohoApiError/except` → converted to `normalize_response(status="FAILED", error_code=..., error_message=...)`

---

## 3. QuickBooks Online — Full Capability Audit

### 3a. Authentication (`quickbooks_auth.py`)

**OAuth flow**: Standard Authorization Code with optional PKCE (S256).

**Authorize URL**: `https://appcenter.intuit.com/connect/oauth2`
- Default scope: `com.intuit.quickbooks.accounting`
- **Redirect URI**: Must exactly match `QBO_REDIRECT_URI` env var — adapter raises `ERP_AUTH_QBO_REDIRECT_URI_MISMATCH` if they differ

**Token exchange**: POST to `https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer`
- Same URL for both sandbox and production
- Form body: `grant_type=authorization_code`, `code`, `redirect_uri`
- **Auth**: `Authorization: Basic base64(client_id:client_secret)` header — **different from Zoho which uses form body**

**Token refresh**: Same URL, `grant_type=refresh_token`, `refresh_token` in form body + Basic auth header

**Normalized token payload**:
```python
{
    "provider": "QUICKBOOKS_ONLINE",
    "access_token": str,
    "refresh_token": str,
    "token_type": "Bearer",
    "expires_in_seconds": int,             # typically 3600
    "refresh_expires_in_seconds": int,     # x_refresh_token_expires_in (typically 8726400 = ~101 days)
    "expires_at_utc": "2026-03-27T12:00:00Z",
    "refresh_expires_at_utc": "2026-05-07T12:00:00Z",
    "realm_id": "1234567890",              # company identifier — from token response "realmId"
}
```

**Key gotcha**: QBO returns `realmId` (camelCase) in the token response — must be saved as `realm_id` (snake_case). All API calls require `realm_id` in the URL path.

### 3b. JV Creation (`quickbooks_online.py` → `post_journal()`)

**Endpoint**: `POST https://quickbooks.api.intuit.com/v3/company/{realm_id}/journalentry?minorversion=75`
- Sandbox: `https://sandbox-quickbooks.api.intuit.com/...`
- `minorversion=75` added automatically by `_request_json()` unless overridden in `connection_config["minor_version"]`

**Request headers**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
Accept: application/json
```

**Request body**:
```json
{
    "TxnDate": "2026-03-27",
    "PrivateNote": "memo text",
    "Line": [
        {
            "Id": "1",
            "Amount": "10000.00",
            "DetailType": "JournalEntryLineDetail",
            "Description": "optional line description",
            "JournalEntryLineDetail": {
                "PostingType": "Debit",
                "AccountRef": {
                    "value": "84",
                    "name": "84"
                }
            }
        },
        {
            "Id": "2",
            "Amount": "10000.00",
            "DetailType": "JournalEntryLineDetail",
            "Description": "",
            "JournalEntryLineDetail": {
                "PostingType": "Credit",
                "AccountRef": {
                    "value": "33",
                    "name": "33"
                }
            }
        }
    ]
}
```

**Critical detail**: `AccountRef.value` is the QBO **numeric account ID** (e.g., `"84"`), not the account code or name. Must map from COA sync first.

**Dimensions support** (built-in):
```json
"JournalEntryLineDetail": {
    "PostingType": "Debit",
    "AccountRef": {"value": "84"},
    "ClassRef": {"value": "class_id"},       // optional
    "DepartmentRef": {"value": "dept_id"}    // optional
}
```
- Dimensions extracted from `line["dimensions"]["class_id"]` and `line["dimensions"]["department_id"]`

**Success response** — QBO wraps the created entry in `response["JournalEntry"]`:
```json
{
    "JournalEntry": {
        "Id": "146",
        "SyncToken": "0",
        "TxnDate": "2026-03-27"
    },
    "time": "2026-03-27T12:00:00.000-07:00"
}
```
- `external_id` = `JournalEntry["Id"]`

**Error extraction**: QBO errors are in `response["Fault"]["Error"][0]["Detail"]` or `["Message"]`

**HTTP-level error codes**:
- 401/403 → `QBO_AUTH_INVALID_TOKEN`
- 429 → `QBO_RATE_LIMIT`
- 5xx → `QBO_NETWORK`
- 400/422 → `QBO_PAYLOAD_INVALID`
- 404 → `QBO_NOT_FOUND`

**Live mode detection**: Checks `QBO_CLIENT_ID` + `QBO_CLIENT_SECRET` env vars AND valid `access_token` AND numeric `realm_id` (`realm_id.isdigit()`). Non-numeric realm IDs (e.g., test placeholders) stay on simulated path.

### 3c. JV Status Poll (`get_journal_status()`)

**Endpoint**: `GET /v3/company/{realm_id}/journalentry/{external_id}?minorversion=75`

**Note**: QBO does not return a status field on journal entries — the adapter normalizes any successful GET as `SUCCESS / POSTED`.

### 3d. COA Sync (`sync_chart_of_accounts()`)

**Endpoint**: `GET /v3/company/{realm_id}/query?query=select+*+from+Account&minorversion=75`

**Response parsing**: `response["QueryResponse"]["Account"]` → list of account dicts.

**Normalized item shape**:
```python
{
    "object_type": "ACCOUNT",
    "object_key": account["Id"],              # QBO numeric ID — use as AccountRef.value
    "payload": {
        "id": str,                            # numeric string e.g. "84"
        "name": str,
        "fully_qualified_name": str,          # e.g. "Accounts Payable:Trade AP"
        "account_type": str,                  # e.g. "Liability", "Expense"
        "account_sub_type": str,
        "classification": str,               # "Liability", "Revenue", etc.
        "active": bool | None,
    },
    "source_timestamp": str | None,           # MetaData.LastUpdatedTime
}
```

### 3e. Attachment Support

**None.** No attachment methods exist in reference implementation. Must be built from scratch for FinanceOps using:
- `POST /v3/company/{realm_id}/upload` (multipart/form-data, Content-Type: multipart/form-data)
- Link via `POST /v3/company/{realm_id}/attachable` with `AttachableRef: [{EntityRef: {type: "JournalEntry", value: journal_id}}]`

### 3f. Company Info (`get_company_info()`)

**Endpoint**: `GET /v3/company/{realm_id}/companyinfo/{realm_id}?minorversion=75`

Returns `CompanyInfo.CompanyName` / `CompanyInfo.LegalName`.

---

## 4. JE Data Model (Canonical Internal Format)

### Root Keys (`ENGINE3_JE_ROOT_KEYS`)
```python
("journal_date", "currency", "lines", "memo")
```

### Line Keys (`ENGINE3_JE_LINE_KEYS`)
```python
("account_code", "debit", "credit", "memo", "dimensions")
```

### Full JE Draft JSON Structure
```json
{
    "journal_date": "2026-03-27",
    "currency": "INR",
    "memo": "Vendor invoice — ABC Supplies",
    "lines": [
        {
            "account_code": "5100",
            "debit": "10000.00",
            "credit": "0.00",
            "memo": "Purchase of raw materials",
            "dimensions": {
                "class_id": "",
                "department_id": ""
            }
        },
        {
            "account_code": "2100",
            "credit": "10000.00",
            "debit": "0.00",
            "memo": "Accounts payable",
            "dimensions": {}
        }
    ]
}
```

### Amount Rules
- All amounts: `Decimal` type, quantized to `Decimal("0.01")`
- Debit and credit are separate fields (not signed)
- A line cannot have both debit > 0 AND credit > 0
- Lines with both = 0 are silently dropped

---

## 5. ERP Posting Packet Structure (`erp_posting_packet_builder.py`)

The posting packet is the normalized data structure passed to `adapter.post_journal()`:

```python
{
    "packet_id": str,                  # UUID4 — unique per posting attempt
    "tenant_id": str,
    "workspace_id": str,
    "je_draft_id": str,
    "workflow_state": "READY_TO_POST", # enforced — raises if not READY_TO_POST
    "header_status": "APPROVED",       # enforced — raises if JE not APPROVED
    "posting_intent": "NEW_JOURNAL",
    "approval_context": {
        "approved_by": str,            # user id of approver
        "approval_decision_id": str,
        "narrative_hash": str,         # SHA256 of the approval narrative
        "evidence_hash": str,          # SHA256 of supporting evidence
    },
    "provenance": dict,                # canonicalized
    "journal_header": {
        "posting_date": str,           # YYYY-MM-DD
        "document_date": str,
        "currency": str,               # e.g. "INR"
        "entity": str,
        "memo": str,
        "reference": str,
    },
    "journal_lines": [
        {
            "line_no": int,            # 1-indexed
            "account_code": str,
            "debit": str,             # Decimal("0.01") quantized
            "credit": str,
            "description": str,
            "dimensions": dict,        # canonicalized
        }
    ],
    "lineage_contract": dict,          # canonicalized
    "governance_export_ref": str,
    "simulation_mode": str | None,
    "created_at": str,                 # ISO UTC timestamp
    "idempotency_key": str,            # SHA256 of deterministic subset (see below)
}
```

### Idempotency Key Computation

The `idempotency_key` is SHA256 of a canonical JSON subset:
```python
{
    "tenant_id", "workspace_id", "je_draft_id",
    "posting_intent", "approval_context",
    "journal_header", "journal_lines",
    "lineage_contract", "provenance"
}
```
- `packet_id` and `created_at` are **excluded** — ensures same packet re-computed at different times produces identical key
- Canonical JSON: keys sorted, `Decimal` → string, `None` → empty string

---

## 6. Adapter Contract (`base.py`)

### Abstract Methods (must implement)
| Method | Signature |
|--------|-----------|
| `validate_connection()` | `(*, connection_config, credentials_ref, credentials) → ERPResponse` |
| `get_capabilities()` | `() → dict` |
| `post_journal()` | `(packet, *, connection_config, credentials) → ERPResponse` |
| `reverse_journal()` | `(packet, *, connection_config, credentials) → ERPResponse` |
| `get_journal_status()` | `(external_id, *, connection_config, credentials) → ERPResponse` |

### Optional Methods (raise `RuntimeError("ERP_OAUTH_NOT_SUPPORTED")` if not implemented)
- `get_oauth_authorize_url()`
- `exchange_oauth_code()`
- `refresh_oauth_tokens()`
- `sync_chart_of_accounts()`
- `sync_dimensions()`
- `sync_trial_balance()`
- `sync_journal_status()`

### `ERPResponse` envelope
```python
{
    "status": "SUCCESS" | "FAILED" | "PENDING",
    "external_id": str | None,          # ERP-side journal ID on success
    "error_code": str | None,
    "error_message": str | None,
    "raw_response": dict,               # full ERP response for audit/debug
}
```

---

## 7. Portability Assessment for FinanceOps

### What Can Be Ported Directly (LOW effort — 4–8 hrs each)

#### Zoho OAuth (`zoho_auth.py`)
- **Port as-is** — pure Python stdlib, no external deps
- Replace `urllib.request` with `httpx.AsyncClient` for async compatibility
- All token normalization logic reusable verbatim
- Add encrypted credential storage (AES-256-GCM) for token payloads

#### QBO OAuth (`quickbooks_auth.py`)
- **Port as-is** — pure Python stdlib
- Replace `urllib.request` with `httpx.AsyncClient`
- **Critical diff from Zoho**: QBO uses `Authorization: Basic base64(client_id:secret)` header for token exchange; Zoho puts credentials in form body
- Add encrypted credential storage

#### Zoho JV Post (`ZohoBooksAdapter.post_journal()`)
- **Port logic directly**
- Replace `_request_json()` urllib call with async httpx
- Simulation mode pattern is reusable for test environments
- Idempotency: add `idempotency_key` check before calling API

#### QBO JV Post (`QuickBooksOnlineAdapter.post_journal()`)
- **Port logic directly**
- Replace `_request_json()` urllib call with async httpx
- Same line validation logic, different payload shape
- `dimensions` → `ClassRef`/`DepartmentRef` support is already built

#### COA Sync (both adapters)
- Port directly
- Used in FinanceOps for account_code → account_id mapping before posting

#### `ERPAdapter` base class
- Port directly as abstract base
- Keep `normalize_response()` static method — it's the canonical response envelope

#### `compute_idempotency_key()` pattern
- Port and adapt — replace reference implementation's `canonicalization.compute_sha256_for_canonical_payload()` with FinanceOps's `utils/chain_hash.py` SHA256 utilities

### What Must Be Built from Scratch (HIGH effort)

#### Document Attachment
- **Zoho**: ~12 hrs — multipart POST to `/books/v3/journals/{id}/documents`
- **QBO**: ~20 hrs — two-step: upload to `/upload`, then `POST /attachable` with `AttachableRef`
- Both: Add attachment `document_id` to FinanceOps JV record after successful link

#### GST/TDS Line Splitting
- **~16 hrs** — No tax handling in reference implementation at all
- Must build: detect IGST vs CGST+SGST (compare supplier GSTIN state code to buyer state code)
- Must build: TDS deduction lines by section (194C/194J/194I) as separate JE lines
- Must build: tax account mapping table (IGST Payable, CGST Payable, SGST Payable, TDS Payable 194C, etc.)

#### Async Wrapper
- **~4 hrs per adapter** — wrap `urllib.request` calls with `asyncio.get_event_loop().run_in_executor(None, ...)`
- OR replace urllib with `httpx.AsyncClient` (preferred for FinanceOps stack)

### What Is Missing from Both reference implementation and FinanceOps

| Capability | Status | Notes |
|-----------|--------|-------|
| Attachment upload | MISSING both | Build for FinanceOps |
| GST/TDS line auto-split | MISSING both | Build for FinanceOps |
| Tally Prime | EXISTS reference implementation only | Port if India on-prem ERP needed |
| Outbound webhook (ERP push notification) | MISSING both | Build: HMAC-SHA256 sig |
| ERP push retry / dead-letter queue | MISSING reference implementation | Build on Celery |
| Token auto-refresh on 401 | MISSING reference implementation | Build: intercept 401, refresh, retry once |

---

## 8. Tally Prime (Bonus Finding)

The reference implementation contains a full Tally Prime connector not described in any requirements:

| File | Description |
|------|-------------|
| `tally_prime_xml.py` | XML-over-HTTP connector — Tally's native integration method |
| `tally_prime_odbc.py` | ODBC connector for direct database access |
| `tally_xml_codec.py` | XML serialization/deserialization for Tally voucher format |

**Relevance for FinanceOps**: Tally Prime is the dominant SME accounting software in India (estimated 75%+ market share for small businesses). If FinanceOps targets Indian SMEs, porting this connector would be high strategic value. The XML connector requires Tally to be running locally with the HTTP XML server enabled (TCP port 9000 by default).

---

## 9. Key Integration Constraints for FinanceOps

### Idempotency (CRITICAL)
The reference implementation uses `idempotency_key` (SHA256 of packet subset) but does NOT write it to the DB before calling the ERP API. For FinanceOps, the sequence MUST be:

```
1. Compute idempotency_key
2. BEGIN TRANSACTION
3. INSERT jv record with status=PUSH_IN_PROGRESS + idempotency_key
4. COMMIT
5. Call ERP API (adapter.post_journal())
6. BEGIN TRANSACTION
7. UPDATE jv: status=POSTED, external_id=..., external_ref=...
8. COMMIT
```

If step 5 crashes after commit of step 4, the retry will find `idempotency_key` already in DB and can re-use the `external_id` by re-polling the ERP (via `get_journal_status()`).

FinanceOps is INSERT-ONLY — step 7 means inserting a new version row, not UPDATE.

### Account Code vs Account ID
- Both Zoho and QBO use internal numeric IDs in API calls, NOT human-readable account codes
- COA sync must run first to populate `erp_account_id` mapping
- FinanceOps COA table should store: `{account_code, account_name, zoho_account_id, qbo_account_id}`

### Async Transport
Both connectors use synchronous `urllib.request`. For FinanceOps (FastAPI async):
```python
# Option A — run_in_executor (minimal change)
result = await asyncio.get_event_loop().run_in_executor(
    None, adapter.post_journal, packet, ...
)

# Option B — rewrite _request_json with httpx.AsyncClient (preferred)
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.post(url, json=body, headers=headers)
```

### Token Storage
reference implementation stores tokens in a generic credentials store. For FinanceOps:
- Encrypt token payload with AES-256-GCM (already in `core/security.py`)
- Store in `erp_connections` table with `encrypted_token_blob` + `token_expires_at`
- Auto-refresh: check `expires_at_utc` before each API call; if within 5 min, refresh first

### Rate Limits
- Zoho Books: 100 API calls/minute per org (enforced) — `429 → ZOHO_RATE_LIMIT`
- QBO: 500 API calls/minute per app (enforced) — `429 → QBO_RATE_LIMIT`
- Both: exponential backoff via Celery `task_default_retry_delay` with jitter

---

## 10. Summary Table

| Capability | Zoho (reference implementation) | QBO (reference implementation) | FinanceOps gap |
|-----------|-----------------|----------------|----------------|
| OAuth authorize URL | ✅ Full | ✅ Full | Port + async |
| OAuth code exchange | ✅ Full | ✅ Full | Port + async |
| OAuth token refresh | ✅ Full | ✅ Full | Port + async |
| JV creation | ✅ Full | ✅ Full | Port + async |
| JV status poll | ✅ Full | ✅ Partial (no status field) | Port + async |
| JV reversal | ⚠️ Stub only | ⚠️ Stub only | Build |
| COA sync | ✅ Full | ✅ Full | Port + async |
| Dimension sync | ⚠️ Stub only | ⚠️ Stub only | Build |
| Trial balance sync | ⚠️ Stub only | ⚠️ Stub only | Build |
| Document attachment | ❌ Missing | ❌ Missing | Build from scratch |
| GST/TDS line split | ❌ Missing | ❌ Missing | Build from scratch |
| Idempotency key | ✅ Computed | ✅ Computed | Port + DB integration |
| Token auto-refresh on 401 | ❌ Missing | ❌ Missing | Build |
| Simulation mode | ✅ Full | ✅ Full | Port |

**Effort summary for FinanceOps ERP layer**:
- Async OAuth + JV post for Zoho: **~6 hrs**
- Async OAuth + JV post for QBO: **~6 hrs**
- COA sync + account mapping layer: **~4 hrs**
- Document attachment (both providers): **~32 hrs**
- GST/TDS auto-split engine: **~16 hrs**
- Token auto-refresh + encrypted storage: **~8 hrs**
- Tally Prime port (optional): **~16 hrs**
- **Total (without Tally)**: ~72 hrs / ~9 engineering days

