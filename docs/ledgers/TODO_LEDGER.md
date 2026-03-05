# TODO_LEDGER

Purpose: Maintain active development backlog.

Policy:
- Append-only task history (update status, do not delete rows).
- Keep task IDs stable.

| Task ID | Task Description | Priority | Module | Dependencies | Status | Owner | Notes |
|---|---|---|---|---|---|---|---|
| TODO-001 | Enforce ledger updates via a repeatable Codex execution checklist (pre/post edit) | High | Governance | docs/ledgers/* | Open | Codex | Required to operationalize automatic update expectations for future prompts. |
| TODO-002 | Fix legacy import paths in financeops/utils/findings.py and financeops/utils/quality_signals.py (KI-001) | High | Backend Utils | financeops.utils.determinism, financeops.utils.formatting | Open | Backend Team | Known issue blocks direct module imports. |
| TODO-003 | Rewrite quality_signals.py DB access for async SQLAlchemy/PostgreSQL (KI-002) | High | Backend Utils | TODO-002; DB session patterns | Open | Backend Team | Existing implementation references old synchronous DB interface. |
| TODO-004 | Implement production ClamAV scan flow in storage/airlock.py (KI-004) | Medium | Storage Security | ClamAV deployment in infra | Open | Platform Team | Current scan status is stubbed (SCAN_SKIPPED). |
| TODO-005 | Build generic ERP adapter interface (typed connector contract + retries + idempotency keys) | High | ERP Integration | Task engine + auth + audit | Open | Integration Team | Flagged as missing in earlier repo audit. |
| TODO-006 | Add ERP connectors (SAP, Oracle, NetSuite, QuickBooks, generic API adapters) | Medium | ERP Integration | TODO-005 | Open | Integration Team | Documented target capability not fully present in repo implementation. |
| TODO-007 | Implement lease accounting module (tables, services, APIs, jobs) | High | Finance Domain | Posting pipeline + finance data model extensions | Open | Finance Engine Team | Identified as missing in earlier repo audit. |
| TODO-008 | Implement revenue recognition module (policy rules + schedules + journal outputs) | High | Finance Domain | TODO-007 baseline financial events | Open | Finance Engine Team | Identified as missing in earlier repo audit. |
| TODO-009 | Add NLQ + document ingestion + vector memory pipeline for AI layer | Medium | AI Intelligence | LLM gateway + storage + embeddings schema | Open | AI Platform Team | Current LLM provider integration exists; higher-level intelligence workflow remains partial. |
| TODO-010 | Add approval workflow + dual authorization for financial posting pipeline | High | Finance Posting | RBAC + audit + job engine | Open | Finance Controls Team | Required for controlled ERP push and posting governance. |

| TODO-011 | Provision prompt-engine runtime dependencies in CI/dev image (pytest, sqlalchemy and backend test stack) and execute full prompt_engine test suite | High | Prompt Engine | backend/pyproject.toml; test environment setup | Open | Platform Team | Required to validate engine end-to-end and satisfy mandatory pytest gates in real execution runs. |
