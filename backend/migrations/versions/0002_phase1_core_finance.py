"""Phase 1 — Core Finance Engine tables

Revision ID: 0002_phase1
Revises: 0001_initial
Create Date: 2026-03-04 00:00:00.000000

Modules:
  1. MIS Manager        — mis_templates, mis_uploads
  2. GL/TB Recon        — gl_entries, trial_balance_rows, recon_items
  3. Bank Recon         — bank_statements, bank_transactions, bank_recon_items
  4. Working Capital    — working_capital_snapshots
  5. GST Reconciliation — gst_returns, gst_recon_items
  6. Month-End          — monthend_checklists, monthend_tasks
  7. Auditor Access     — auditor_grants, auditor_access_logs

RLS applied to all FinancialBase tables.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase1"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── MODULE 1: MIS Manager ──────────────────────────────────────────────

    op.create_table(
        "mis_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("is_master", sa.Boolean, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("template_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("sheet_count", sa.Integer, nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_mis_templates_tenant_created", "mis_templates", ["tenant_id", "created_at"])
    op.create_index("idx_mis_templates_entity", "mis_templates", ["tenant_id", "entity_name"])

    op.create_table(
        "mis_uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("upload_notes", sa.Text, nullable=True),
        sa.Column("parsed_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["mis_templates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_mis_uploads_tenant_created", "mis_uploads", ["tenant_id", "created_at"])
    op.create_index("idx_mis_uploads_period", "mis_uploads", ["tenant_id", "period_year", "period_month"])

    # ── MODULE 2: GL/TB Reconciliation ────────────────────────────────────

    op.create_table(
        "gl_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("account_code", sa.String(50), nullable=False),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("debit_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("credit_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gl_entries_tenant_period", "gl_entries", ["tenant_id", "period_year", "period_month"])
    op.create_index("idx_gl_entries_account", "gl_entries", ["tenant_id", "account_code"])

    op.create_table(
        "trial_balance_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("account_code", sa.String(50), nullable=False),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("opening_balance", sa.Numeric(20, 6), nullable=False),
        sa.Column("period_debit", sa.Numeric(20, 6), nullable=False),
        sa.Column("period_credit", sa.Numeric(20, 6), nullable=False),
        sa.Column("closing_balance", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tb_rows_tenant_period", "trial_balance_rows", ["tenant_id", "period_year", "period_month"])
    op.create_index("idx_tb_rows_account", "trial_balance_rows", ["tenant_id", "account_code"])

    op.create_table(
        "recon_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("account_code", sa.String(50), nullable=False),
        sa.Column("account_name", sa.String(255), nullable=False),
        sa.Column("gl_total", sa.Numeric(20, 6), nullable=False),
        sa.Column("tb_closing_balance", sa.Numeric(20, 6), nullable=False),
        sa.Column("difference", sa.Numeric(20, 6), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("recon_type", sa.String(50), nullable=False),
        sa.Column("run_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_recon_items_tenant_period", "recon_items", ["tenant_id", "period_year", "period_month"])
    op.create_index("idx_recon_items_status", "recon_items", ["tenant_id", "status"])

    # ── MODULE 3: Bank Reconciliation ─────────────────────────────────────

    op.create_table(
        "bank_statements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bank_name", sa.String(255), nullable=False),
        sa.Column("account_number_masked", sa.String(50), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("opening_balance", sa.Numeric(20, 6), nullable=False),
        sa.Column("closing_balance", sa.Numeric(20, 6), nullable=False),
        sa.Column("transaction_count", sa.Integer, nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_bank_stmts_tenant_period", "bank_statements", ["tenant_id", "period_year", "period_month"])
    op.create_index("idx_bank_stmts_entity", "bank_statements", ["tenant_id", "entity_name"])

    op.create_table(
        "bank_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("statement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_date", sa.Date, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("debit_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("credit_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("balance", sa.Numeric(20, 6), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("match_status", sa.String(50), nullable=False),
        sa.ForeignKeyConstraint(["statement_id"], ["bank_statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_bank_txns_statement", "bank_transactions", ["tenant_id", "statement_id"])
    op.create_index("idx_bank_txns_match", "bank_transactions", ["tenant_id", "match_status"])

    op.create_table(
        "bank_recon_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("statement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("item_type", sa.String(50), nullable=False),
        sa.Column("bank_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("gl_reference", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("run_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["statement_id"], ["bank_statements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_bank_recon_tenant_period", "bank_recon_items", ["tenant_id", "period_year", "period_month"])
    op.create_index("idx_bank_recon_status", "bank_recon_items", ["tenant_id", "status"])

    # ── MODULE 4: Working Capital ──────────────────────────────────────────

    op.create_table(
        "working_capital_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("cash_and_equivalents", sa.Numeric(20, 6), nullable=False),
        sa.Column("accounts_receivable", sa.Numeric(20, 6), nullable=False),
        sa.Column("inventory", sa.Numeric(20, 6), nullable=False),
        sa.Column("prepaid_expenses", sa.Numeric(20, 6), nullable=False),
        sa.Column("other_current_assets", sa.Numeric(20, 6), nullable=False),
        sa.Column("total_current_assets", sa.Numeric(20, 6), nullable=False),
        sa.Column("accounts_payable", sa.Numeric(20, 6), nullable=False),
        sa.Column("accrued_liabilities", sa.Numeric(20, 6), nullable=False),
        sa.Column("short_term_debt", sa.Numeric(20, 6), nullable=False),
        sa.Column("other_current_liabilities", sa.Numeric(20, 6), nullable=False),
        sa.Column("total_current_liabilities", sa.Numeric(20, 6), nullable=False),
        sa.Column("working_capital", sa.Numeric(20, 6), nullable=False),
        sa.Column("current_ratio", sa.Numeric(10, 4), nullable=False),
        sa.Column("quick_ratio", sa.Numeric(10, 4), nullable=False),
        sa.Column("cash_ratio", sa.Numeric(10, 4), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_wc_snapshots_tenant_period", "working_capital_snapshots", ["tenant_id", "period_year", "period_month"])
    op.create_index("idx_wc_snapshots_entity", "working_capital_snapshots", ["tenant_id", "entity_name"])

    # ── MODULE 5: GST Reconciliation ──────────────────────────────────────

    op.create_table(
        "gst_returns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("gstin", sa.String(20), nullable=False),
        sa.Column("return_type", sa.String(20), nullable=False),
        sa.Column("taxable_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("igst_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("cgst_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("sgst_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("cess_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("total_tax", sa.Numeric(20, 6), nullable=False),
        sa.Column("filing_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("filed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gst_returns_tenant_period", "gst_returns", ["tenant_id", "period_year", "period_month"])
    op.create_index("idx_gst_returns_entity", "gst_returns", ["tenant_id", "entity_name"])
    op.create_index("idx_gst_returns_type", "gst_returns", ["tenant_id", "return_type"])

    op.create_table(
        "gst_recon_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("return_type_a", sa.String(20), nullable=False),
        sa.Column("return_type_b", sa.String(20), nullable=False),
        sa.Column("return_a_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("return_b_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(50), nullable=False),
        sa.Column("value_a", sa.Numeric(20, 6), nullable=False),
        sa.Column("value_b", sa.Numeric(20, 6), nullable=False),
        sa.Column("difference", sa.Numeric(20, 6), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("run_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["return_a_id"], ["gst_returns.id"]),
        sa.ForeignKeyConstraint(["return_b_id"], ["gst_returns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gst_recon_tenant_period", "gst_recon_items", ["tenant_id", "period_year", "period_month"])
    op.create_index("idx_gst_recon_status", "gst_recon_items", ["tenant_id", "status"])

    # ── MODULE 6: Month-End Closing Checklist ─────────────────────────────

    op.create_table(
        "monthend_checklists",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_month", sa.Integer, nullable=False),
        sa.Column("entity_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_monthend_cl_tenant_period", "monthend_checklists", ["tenant_id", "period_year", "period_month"])
    op.create_index("idx_monthend_cl_entity", "monthend_checklists", ["tenant_id", "entity_name"])

    # monthend_tasks uses UUIDBase (mutable status updates allowed)
    op.create_table(
        "monthend_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checklist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_name", sa.String(255), nullable=False),
        sa.Column("task_category", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False),
        sa.Column("is_required", sa.Boolean, nullable=False),
        sa.ForeignKeyConstraint(["checklist_id"], ["monthend_checklists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_monthend_tasks_checklist", "monthend_tasks", ["checklist_id"])
    op.create_index("idx_monthend_tasks_status", "monthend_tasks", ["checklist_id", "status"])

    # ── MODULE 7: Auditor Access ───────────────────────────────────────────

    op.create_table(
        "auditor_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("auditor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("allowed_modules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_auditor_grants_tenant", "auditor_grants", ["tenant_id"])
    op.create_index("idx_auditor_grants_auditor", "auditor_grants", ["auditor_user_id"])
    op.create_index("idx_auditor_grants_active", "auditor_grants", ["tenant_id", "auditor_user_id", "is_active"])

    op.create_table(
        "auditor_access_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("grant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("auditor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("accessed_resource", sa.String(255), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("access_result", sa.String(20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_auditor_logs_tenant", "auditor_access_logs", ["tenant_id", "created_at"])
    op.create_index("idx_auditor_logs_auditor", "auditor_access_logs", ["auditor_user_id", "created_at"])

    # ── Row Level Security — all FinancialBase tables ──────────────────────
    financial_tables = [
        "mis_templates",
        "mis_uploads",
        "gl_entries",
        "trial_balance_rows",
        "recon_items",
        "bank_statements",
        "bank_transactions",
        "bank_recon_items",
        "working_capital_snapshots",
        "gst_returns",
        "gst_recon_items",
        "monthend_checklists",
        "auditor_grants",
        "auditor_access_logs",
    ]
    for table in financial_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation
              ON {table}
              USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            """
        )


def downgrade() -> None:
    # Drop in reverse dependency order
    tables_in_order = [
        "auditor_access_logs",
        "auditor_grants",
        "monthend_tasks",
        "monthend_checklists",
        "gst_recon_items",
        "gst_returns",
        "working_capital_snapshots",
        "bank_recon_items",
        "bank_transactions",
        "bank_statements",
        "recon_items",
        "trial_balance_rows",
        "gl_entries",
        "mis_uploads",
        "mis_templates",
    ]
    for table in tables_in_order:
        op.drop_table(table)
