# Known Issues — FinanceOps Phase 0

## KI-001: Utility File Import Paths (findings.py, quality_signals.py)

**Status:** Open
**Severity:** Non-blocking (files are utility references only)
**Affects:** `financeops/utils/findings.py`, `financeops/utils/quality_signals.py`

### Description

Two of the four utility files copied verbatim from the old repo contain
imports that reference the old project's package structure:

**findings.py** (line 7):
```python
from workbench.backend import determinism
```

**quality_signals.py** (lines 8-9):
```python
from workbench.backend import db
from workbench.backend import determinism
```

These imports will raise `ModuleNotFoundError` if `findings.py` or
`quality_signals.py` are imported directly. They were copied verbatim
per the Phase 0 specification ("copy them verbatim — do not modify them").

### Resolution Options

**Option A (Recommended for Phase 1):** Update imports to:
```python
# findings.py
from financeops.utils import determinism

# quality_signals.py
from financeops.utils import determinism
# Replace db.utc_now_iso() calls with:
from financeops.utils.formatting import utc_now_iso
# Replace db.get_conn() calls with the async session pattern
```

**Option B:** Create a compatibility shim at `financeops/utils/workbench/backend/`
that re-exports from `financeops/utils/`.

### Current Impact

- `determinism.py` and `replay_models.py` are fully functional — no import issues.
- `findings.py` and `quality_signals.py` are available as reference implementations.
  Their logic can be used by importing the functions after fixing imports.

---

## KI-002: quality_signals.py References Synchronous DB Module

**Status:** Open
**Severity:** Non-blocking
**Affects:** `financeops/utils/quality_signals.py`

### Description

`quality_signals.py` imports `from workbench.backend import db` and calls
`db.get_conn()` (synchronous SQLite connection) and `db.utc_now_iso()`.

The new platform uses async PostgreSQL via SQLAlchemy + asyncpg.
The `record_quality_signal()` and `list_quality_signals()` functions
will require complete rewrites for Phase 1.

### Current State

The file is present as a reference implementation. The `build_quality_signal()`
function (pure data transformation, no DB calls) can be extracted and used
as-is once the import is fixed per KI-001.

---

## KI-003: python-magic Requires libmagic Native Library

**Status:** Open
**Severity:** Non-blocking in Docker (libmagic included via apt-get)
**Affects:** `financeops/storage/airlock.py`

### Description

`python-magic` requires the native `libmagic` library. The Dockerfile installs
it via `apt-get`. On Windows development machines, a separate installation
is required:

```
pip install python-magic-bin  # Windows only
```

### Workaround

`airlock.py` gracefully falls back to filename extension-based MIME detection
if `python-magic` fails to import.

---

## KI-004: ClamAV AV Scanning Stubbed in Phase 0

**Status:** Expected — Deferred to Phase 6
**Severity:** Low (security hardening deferred)
**Affects:** `financeops/storage/airlock.py`

### Description

ClamAV antivirus scanning is stubbed. Files receive `status="SCAN_SKIPPED"`
with a log warning. Production deployments must configure ClamAV before
processing untrusted file uploads.

### Phase 6 Implementation

```python
import clamd
cd = clamd.ClamdUnixSocket()
scan_result = cd.instream(io.BytesIO(file_bytes))
```

---

## KI-005: R2 Storage Requires Configured Credentials

**Status:** Expected
**Severity:** Non-blocking (returns empty config at Phase 0)
**Affects:** `financeops/storage/r2.py`

### Description

R2 storage operations will fail if `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`,
or `R2_SECRET_ACCESS_KEY` are not configured in `.env`. The deep health
check reports `status: "not_configured"` when these are absent.

Set the values in `.env` before testing file upload/download endpoints.
