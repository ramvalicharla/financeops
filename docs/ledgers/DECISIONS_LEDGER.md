# DECISIONS_LEDGER

Purpose: Record architectural or product decisions.

Policy:
- Append-only entries.
- Capture context and alternatives for traceability.

| Date | Decision Title | Context | Decision Taken | Alternatives Considered | Impact | Related Files |
|---|---|---|---|---|---|---|
| 2026-03-05 | Adopt append-only markdown governance ledgers | FINOS required traceability of all Codex/developer changes and prompts. | Create and maintain 8 ledgers under docs/ledgers/ with mandatory per-prompt updates. | Ad-hoc notes in docs; external ticketing only; DB-backed audit table for docs. | Creates deterministic governance trail in-repo and aligns prompt executions with file-level outcomes. | docs/ledgers/*.md |
| 2026-03-05 | Filtered repository tree policy for folder ledger | Folder snapshots must remain readable and exclude transient artifacts. | Include source/config/infra files; exclude cache/build/runtime artifact directories (
ode_modules, .venv, __pycache__, build outputs). | Full recursive listing including artifacts; directory-only snapshot. | Prevents noise and keeps structure snapshot useful for architecture and governance review. | docs/ledgers/FOLDERTREE_LEDGER.md |
| 2026-03-05 | Prompt engine uses callback-driven execution/rework adapters | FINOS execution orchestration is required now, but concrete AI patch application backend may vary by environment. | Implement PromptRunner and ReworkEngine with pluggable callbacks while enforcing fixed transaction and guardrail stages. | Hardcode a single executor transport; defer execution engine entirely until runtime provider finalized. | Keeps orchestration deterministic and testable while allowing environment-specific executor integration without redesign. | backend/financeops/prompt_engine/prompt_runner.py; backend/financeops/prompt_engine/rework_engine.py; backend/financeops/prompt_engine/executor.py |
