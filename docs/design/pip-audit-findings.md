# pip-audit Findings — Finqor Backend
**Audited:** 2026-04-13
**Tool:** `pip-audit --desc on` against Python 3.11 install
**Total vulnerabilities found:** 55 in 15 packages

---

## PATCHED IN THIS AUDIT

| Package | Old Version | New Version | CVEs Fixed |
|---------|-------------|-------------|------------|
| `jinja2` | 3.1.4 | **3.1.6** | CVE-2024-56201, CVE-2024-56326, CVE-2025-27516 |
| `python-jose` | 3.3.0 | **3.4.0** | PYSEC-2024-232 (alg confusion), PYSEC-2024-233 (key confusion) |
| `cryptography` | 43.0.0 | **43.0.1** | GHSA-h4gh-qq45-vh27 (timing attack) |

---

## CANNOT PATCH WITHOUT COORDINATED UPGRADE — DOCUMENT ONLY

### 1. `python-multipart 0.0.9` — HIGH
**CVEs:** CVE-2024-53981 (fix: 0.0.18), CVE-2026-24486 (fix: 0.0.22)
**Why not patched:** `python-multipart >=0.0.17` renamed the Python import from
`multipart` to `python_multipart`. `starlette 0.38.6` (bundled with FastAPI 0.115.0)
still does `import multipart` — this triggers a `PendingDeprecationWarning` that
pytest treats as an error (filterwarnings = ["error"]).
**Required fix:** Upgrade `fastapi` → 0.115.x with `starlette >=0.40.0` +
`python-multipart >=0.0.18` as a coordinated triple-upgrade. Test all form
parsing endpoints (file upload, multipart form submissions) after the upgrade.
**Mitigation:** FastAPI's own request size limiter and the Airlock content-type
validation reduce exploitability. Deploy behind a reverse proxy (nginx/caddy) with
client_max_body_size set.

### 2. `aiohttp 3.10.0` — HIGH/MODERATE (21 CVEs)
**CVEs:** CVE-2024-42367, CVE-2024-52304, CVE-2025-53643, CVE-2026-34513 through
CVE-2026-34525, CVE-2025-69223 through CVE-2025-69230, CVE-2026-22815
**Fix version:** 3.13.4 (latest)
**Why not patched:** `aiohttp 3.10 → 3.13` is a 3-minor-version jump with
potential breaking changes in the connector layer (ERP sync connectors use aiohttp
for HTTP requests to external APIs). All 23 ERP connectors need regression testing.
**Required fix:** Upgrade in a dedicated branch. Test all 23 ERP connectors against
their sandbox APIs. Pay particular attention to auth header handling changes in 3.11.x.
**Mitigation:** aiohttp is used only for outbound requests from worker processes
(ERP sync), not as the web server (uvicorn handles inbound). DoS vectors require
an attacker to control the ERP server response. NTLMv2 path exposure (CVE-2026-34515)
is Windows-only and only applies to static file serving (not used in production).

### 3. `cryptography 43.0.1` — MEDIUM/HIGH (remaining 3 CVEs)
**CVEs:** CVE-2024-12797 (fix: 44.0.1), CVE-2026-26007 (fix: 46.0.5), CVE-2026-34073 (fix: 46.0.6)
**Why not patched:** `cryptography 43.0.1 → 46.0.6` crosses 3 major versions.
`python-jose 3.4.0` and `passlib 1.7.4` both pin to the 43.x cryptography API.
Upgrading to 44+ risks breaking AES-256-GCM field encryption and JWT signing.
**Required fix:** Upgrade as part of a coordinated `cryptography + python-jose +
passlib` upgrade. Test the full auth flow (JWT, field encryption, TOTP) after.
CVE-2024-12797 (client cert verification bypass in TLS) — not applicable since we
are the server, not performing client cert verification.

### 4. `starlette 0.38.6` — MODERATE/HIGH (2 CVEs, transitive dep)
**CVEs:** CVE-2024-47874 (fix: 0.40.0), CVE-2025-54121 (fix: 0.47.2)
**Why not patched:** Starlette is a transitive dep of FastAPI 0.115.0 which requires
`starlette>=0.38.4,<0.40.0`. Cannot upgrade without upgrading FastAPI.
**Required fix:** Upgrade `fastapi` to a version that bundles starlette 0.47.x.
CVE-2024-47874 is a DoS via specially crafted multipart form body. Mitigated by
`RequestSizeLimitMiddleware` already in place in `main.py`.

### 5. `protobuf 4.25.8` — MODERATE (transitive dep)
**CVE:** CVE-2026-0994 (fix: 5.29.6 or 6.33.5)
**Why not patched:** Protobuf is a transitive dependency (comes from OpenTelemetry
instrumentation). Major version jump (4 → 5) may break OpenTelemetry OTLP export.
**Required fix:** Upgrade `opentelemetry-*` packages as a group after checking
their protobuf compatibility matrix.

### 6. `requests 2.32.5` — LOW (transitive dep)
**CVE:** CVE-2026-25645 (fix: 2.33.0)
**Why not patched:** `requests` is a transitive dependency (boto3, anthropic, others).
Upgrading transitive deps directly in pyproject.toml is fragile. If needed, add
`requests>=2.33.0` as a direct constraint.
**Mitigation:** CVE-2026-25645 relates to proxy credentials exposure — we use
requests only for AWS S3/R2 and AI provider calls where proxies are not configured.

### 7. `tornado` (transitive dep via celery/flower)
**CVEs:** CVE-2026-31958, CVE-2026-35536, GHSA-78cv-mqj4-43f7 (fix: 6.5.5)
**Why not patched:** Transitive dep — pinning tornado directly would require adding
it as an explicit project dependency.
**Mitigation:** Tornado is used by `flower` (Celery monitoring UI). It's not exposed
to public internet traffic — flower should be behind VPN/auth proxy in production.

### 8. `ecdsa 0.19.1` — NOTE
**CVEs:** CVE-2024-23342 (no fix in ecdsa, fix via alternative library),
CVE-2026-33936 (fix: 0.19.2)
**Note:** CVE-2024-23342 is a Minerva side-channel attack. `ecdsa` is a transitive
dep of `python-jose`. When `python-jose 3.4.0` is installed, verify if ecdsa is
still a runtime dependency — python-jose uses the `cryptography` backend for most
operations, and ecdsa may only be used for legacy EC key handling.
**Action:** Monitor python-jose 3.5.x for ecdsa dependency removal.

---

## RECOMMENDED UPGRADE ORDER (Next Sprint)

1. `fastapi 0.115.x → latest` + `starlette 0.47.x` + `python-multipart 0.0.22`
   (coordinate as a single PR, test all auth + form upload endpoints)
2. `aiohttp 3.10.0 → 3.13.4`
   (dedicated PR, test all 23 ERP connectors)
3. `cryptography → 46.0.6` + `python-jose → latest` + `passlib → latest`
   (coordinate as single PR, test full auth flow)
4. `opentelemetry-* → latest` + `protobuf upgrade` (single PR)
