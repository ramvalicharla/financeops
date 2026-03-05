# SCHEMA_LEDGER

Purpose: Track database schema evolution.

Policy:
- Append-only migration history.
- Log only concrete schema changes from migration/model evidence.

| Date | Schema Change | Tables Affected | Columns Added/Removed | Migration File | Backward Compatibility | Notes |
|---|---|---|---|---|---|---|
| 2026-03-03 | Initial platform schema bootstrap | iam_tenants, iam_workspaces, iam_users, iam_sessions, audit_trail, credit_balances, credit_transactions, credit_reservations, ai_prompt_versions | Added all columns for newly created tables (no column removals). | backend/migrations/versions/0001_initial_schema.py | N/A (initial schema) | Introduced core IAM, audit, credits, and prompt versioning tables; enabled RLS for audit_trail and credit_transactions. |
| 2026-03-04 | Phase 1 core finance schema expansion | mis_templates, mis_uploads, gl_entries, trial_balance_rows, recon_items, bank_statements, bank_transactions, bank_recon_items, working_capital_snapshots, gst_returns, gst_recon_items, monthend_checklists, monthend_tasks, auditor_grants, auditor_access_logs | Added all columns for newly created tables (no column removals). | backend/migrations/versions/0002_phase1_core_finance.py | Additive migration; backward compatible for existing tables. | Added MIS, reconciliation, bank recon, working capital, GST, month-end, and auditor access modules with tenant RLS policies. |
| 2026-03-05 | Governance ledger initialization | None | None | N/A | No schema change | Ledger setup updated documentation only. |

