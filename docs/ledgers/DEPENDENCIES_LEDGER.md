# DEPENDENCIES_LEDGER

Purpose: Track platform dependencies.

Policy:
- Append-only entries.
- Record explicit project dependencies from manifest files.

Source: backend/pyproject.toml

| Date | Dependency Name | Version | Purpose | Module Using It | Risk Notes |
|---|---|---|---|---|---|
| 2026-03-05 | fastapi | ==0.115.0 | API framework | backend/financeops/api | Framework vulnerabilities can expose endpoints if not patched. |
| 2026-03-05 | uvicorn[standard] | ==0.30.0 | ASGI server runtime | backend/financeops/main.py | Runtime regressions affect service availability. |
| 2026-03-05 | gunicorn | ==22.0.0 | Production process manager | backend deployment/runtime | Misconfiguration can reduce resiliency under load. |
| 2026-03-05 | python-multipart | ==0.0.9 | Multipart form parsing | file upload endpoints | Parser bugs can impact upload validation paths. |
| 2026-03-05 | sqlalchemy | ==2.0.35 | ORM and query layer | backend/financeops/db + services | ORM/query changes can introduce data correctness issues. |
| 2026-03-05 | asyncpg | ==0.30.0 | PostgreSQL async driver | database session layer | Driver upgrades can affect performance and transaction behavior. |
| 2026-03-05 | alembic | ==1.13.0 | Schema migration engine | backend/migrations | Migration mistakes can cause irreversible schema drift. |
| 2026-03-05 | pgvector | ==0.3.3 | Vector column support | AI/data persistence layer | Extension availability must match database environment. |
| 2026-03-05 | redis | ==5.0.8 | Cache and broker backend | Celery + caching paths | Broker outages can stall background jobs. |
| 2026-03-05 | celery[redis] | ==5.4.0 | Task queue engine | backend/financeops/tasks | Queue misconfiguration can cause duplicate or orphaned jobs. |
| 2026-03-05 | flower | ==2.0.1 | Celery monitoring UI | operations/worker observability | Exposed monitoring UI can leak operational metadata. |
| 2026-03-05 | pydantic | ==2.9.0 | Request/response validation | API schemas and config | Validation behavior changes can break API contracts. |
| 2026-03-05 | pydantic-settings | ==2.5.0 | Environment configuration | backend/financeops/config.py | Incorrect env parsing can cause unsafe defaults. |
| 2026-03-05 | email-validator | ==2.2.0 | Email format validation | authentication/user flows | Validation edge cases may reject valid users. |
| 2026-03-05 | python-jose[cryptography] | ==3.3.0 | JWT handling | auth service and middleware | Crypto/JWT library bugs directly affect auth security. |
| 2026-03-05 | passlib[bcrypt] | ==1.7.4 | Password hashing | auth service | Hash algorithm defaults must remain strong and maintained. |
| 2026-03-05 | pyotp | ==2.9.0 | TOTP MFA support | MFA flows | MFA drift can lock users out or weaken security. |
| 2026-03-05 | cryptography | ==43.0.0 | Cryptographic primitives | security and token handling | Critical security dependency; patch quickly for CVEs. |
| 2026-03-05 | slowapi | ==0.1.9 | Rate limiting | API middleware | Incorrect limits can either block users or allow abuse. |
| 2026-03-05 | openpyxl | ==3.1.5 | Excel ingestion/parsing | MIS/GST ingestion paths | Malformed workbook handling can impact ingestion safety. |
| 2026-03-05 | xlsxwriter | ==3.2.0 | Excel report generation | export/reporting modules | Version drift can alter file compatibility. |
| 2026-03-05 | pandas | ==2.2.3 | Dataframe transformations | finance analytics services | Memory-heavy operations can impact performance. |
| 2026-03-05 | numpy | ==2.1.0 | Numeric computation | analytics and reconciliation logic | Binary compatibility issues may break in some environments. |
| 2026-03-05 | python-magic | ==0.4.27 | MIME detection | storage airlock validation | Requires native libmagic; environment mismatch risk. |
| 2026-03-05 | python-docx | ==1.1.2 | DOCX parsing/generation | document processing | Untrusted document handling must remain sandboxed. |
| 2026-03-05 | boto3 | ==1.35.0 | Object storage client | R2/S3 storage integration | Credential leakage or policy misconfig is a security risk. |
| 2026-03-05 | httpx | ==0.27.0 | Async HTTP client | external integrations + tests | Timeout/retry defaults can cause partial failures. |
| 2026-03-05 | aiohttp | ==3.10.0 | Async HTTP client stack | integration and service calls | Connection management errors can degrade stability. |
| 2026-03-05 | anthropic | ==0.34.0 | LLM provider SDK | llm/providers/anthropic.py | External API changes can break inference paths. |
| 2026-03-05 | openai | ==1.51.0 | LLM provider SDK | llm/providers/openai.py | API schema/rate-limit changes require guarded handling. |
| 2026-03-05 | ollama | ==0.3.3 | Local model runtime client | llm/providers/ollama.py | Local model availability and version skew risk. |
| 2026-03-05 | tiktoken | ==0.7.0 | Token accounting | prompt and usage estimation | Tokenizer mismatch can produce inaccurate cost estimates. |
| 2026-03-05 | opentelemetry-sdk | ==1.27.0 | Tracing/metrics SDK | telemetry instrumentation | Incorrect exporter config can drop observability data. |
| 2026-03-05 | opentelemetry-api | ==1.27.0 | Telemetry API contracts | instrumented services | Version mismatch across OTel packages can break tracing. |
| 2026-03-05 | opentelemetry-exporter-otlp | ==1.27.0 | OTLP export pipeline | telemetry backend integration | Collector outages can cause blind spots. |
| 2026-03-05 | opentelemetry-instrumentation-fastapi | ==0.48b0 | FastAPI auto-instrumentation | API request tracing | Middleware order changes can break spans/context. |
| 2026-03-05 | opentelemetry-instrumentation-sqlalchemy | ==0.48b0 | DB query tracing | SQLAlchemy layer | High cardinality spans can increase telemetry cost. |
| 2026-03-05 | opentelemetry-instrumentation-redis | ==0.48b0 | Redis tracing | cache/broker layer | Instrumentation overhead under high throughput. |
| 2026-03-05 | opentelemetry-instrumentation-celery | ==0.48b0 | Worker/task tracing | Celery task execution | Missing context propagation hampers traceability. |
| 2026-03-05 | sentry-sdk[fastapi] | ==2.14.0 | Error monitoring | application exception capture | PII scrubbing and DSN security must be enforced. |
| 2026-03-05 | prometheus-client | ==0.21.0 | Prometheus metrics export | metrics endpoints | Metric cardinality explosion can impact performance. |
| 2026-03-05 | python-dateutil | ==2.9.0 | Date parsing utilities | finance date calculations | Locale/date parsing ambiguities can affect reporting. |
| 2026-03-05 | pytz | ==2024.2 | Timezone handling | tenant timezone logic | Timezone database drift can alter cut-off logic. |
| 2026-03-05 | babel | ==2.16.0 | Locale/formatting | presentation and reporting | Locale formatting changes may impact report expectations. |
| 2026-03-05 | pytest | ==8.3.0 | Development and testing | backend/tests + local tooling | Toolchain drift can break CI consistency; pin and review upgrades. |
| 2026-03-05 | pytest-asyncio | >=1.0.0 | Development and testing | backend/tests + local tooling | Toolchain drift can break CI consistency; pin and review upgrades. |
| 2026-03-05 | pytest-cov | ==5.0.0 | Development and testing | backend/tests + local tooling | Toolchain drift can break CI consistency; pin and review upgrades. |
| 2026-03-05 | httpx | ==0.27.0 | Development and testing | backend/tests + local tooling | Toolchain drift can break CI consistency; pin and review upgrades. |
| 2026-03-05 | faker | ==30.0.0 | Development and testing | backend/tests + local tooling | Toolchain drift can break CI consistency; pin and review upgrades. |
| 2026-03-05 | factory-boy | ==3.3.1 | Development and testing | backend/tests + local tooling | Toolchain drift can break CI consistency; pin and review upgrades. |
| 2026-03-05 | ruff | ==0.6.0 | Development and testing | backend/tests + local tooling | Toolchain drift can break CI consistency; pin and review upgrades. |
| 2026-03-05 | mypy | ==1.11.0 | Development and testing | backend/tests + local tooling | Toolchain drift can break CI consistency; pin and review upgrades. |

