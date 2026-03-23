"""M&A workspace tables for advisory deal management.

Revision ID: 0051_ma_workspace
Revises: 0050_ppa
Create Date: 2026-03-24 10:15:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0051_ma_workspace"
down_revision: str | None = "0050_ppa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar_one_or_none()
    return value is not None


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'i'
              AND n.nspname = 'public'
              AND c.relname = :index_name
            LIMIT 1
            """
        ),
        {"index_name": index_name},
    ).scalar_one_or_none()
    return value is not None


def _policy_exists(table_name: str, policy_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_policies
            WHERE schemaname = 'public'
              AND tablename = :table_name
              AND policyname = :policy_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "policy_name": policy_name},
    ).scalar_one_or_none()
    return value is not None


def _enable_rls_with_policies(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            "USING (tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid)"
        )


def upgrade() -> None:
    if not _table_exists("ma_workspaces"):
        op.create_table(
            "ma_workspaces",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("workspace_name", sa.String(length=300), nullable=False),
            sa.Column("deal_codename", sa.String(length=100), nullable=False),
            sa.Column("deal_type", sa.String(length=30), nullable=False),
            sa.Column("target_company_name", sa.String(length=300), nullable=False),
            sa.Column("deal_status", sa.String(length=30), nullable=False, server_default=sa.text("'active'")),
            sa.Column("indicative_deal_value", sa.Numeric(20, 2), nullable=True),
            sa.Column("deal_value_currency", sa.String(length=3), nullable=False, server_default=sa.text("'INR'")),
            sa.Column("credit_cost_monthly", sa.Integer(), nullable=False, server_default=sa.text("1000")),
            sa.Column("credit_charged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("iam_users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "deal_type IN ('acquisition','merger','divestiture','minority_investment','joint_venture')",
                name="ck_ma_workspaces_deal_type",
            ),
            sa.CheckConstraint(
                "deal_status IN ('active','paused','closed_won','closed_lost','on_hold')",
                name="ck_ma_workspaces_deal_status",
            ),
        )

    if not _table_exists("ma_workspace_members"):
        op.create_table(
            "ma_workspace_members",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ma_workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("iam_users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("member_role", sa.String(length=30), nullable=False),
            sa.Column("added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "member_role IN ('lead_advisor','analyst','observer','external_advisor')",
                name="ck_ma_workspace_members_role",
            ),
            sa.UniqueConstraint("workspace_id", "user_id", name="uq_ma_workspace_members_workspace_user"),
        )

    if not _table_exists("ma_valuations"):
        op.create_table(
            "ma_valuations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ma_workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("valuation_name", sa.String(length=200), nullable=False),
            sa.Column("valuation_method", sa.String(length=30), nullable=False),
            sa.Column("assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("enterprise_value", sa.Numeric(20, 2), nullable=False),
            sa.Column("equity_value", sa.Numeric(20, 2), nullable=False),
            sa.Column("net_debt_used", sa.Numeric(20, 2), nullable=False),
            sa.Column("ev_ebitda_multiple", sa.Numeric(8, 4), nullable=False),
            sa.Column("ev_revenue_multiple", sa.Numeric(8, 4), nullable=False),
            sa.Column("valuation_range_low", sa.Numeric(20, 2), nullable=False),
            sa.Column("valuation_range_high", sa.Numeric(20, 2), nullable=False),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("computed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("iam_users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.CheckConstraint(
                "valuation_method IN ('dcf','comparable_companies','precedent_transactions','asset_based','lbo')",
                name="ck_ma_valuations_method",
            ),
        )

    if not _table_exists("ma_dd_items"):
        op.create_table(
            "ma_dd_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ma_workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("item_name", sa.String(length=300), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'open'")),
            sa.Column("priority", sa.String(length=10), nullable=False, server_default=sa.text("'medium'")),
            sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("iam_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("response_notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "category IN ('financial','legal','tax','commercial','technical','hr','regulatory','environmental')",
                name="ck_ma_dd_items_category",
            ),
            sa.CheckConstraint(
                "status IN ('open','in_progress','completed','flagged','waived')",
                name="ck_ma_dd_items_status",
            ),
            sa.CheckConstraint(
                "priority IN ('critical','high','medium','low')",
                name="ck_ma_dd_items_priority",
            ),
        )

    if not _table_exists("ma_documents"):
        op.create_table(
            "ma_documents",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("workspace_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ma_workspaces.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("document_name", sa.String(length=300), nullable=False),
            sa.Column("document_type", sa.String(length=50), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("file_url", sa.Text(), nullable=True),
            sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
            sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("iam_users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("is_confidential", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "document_type IN ('nda','loi','spa','sha','disclosure_schedule','financial_model','dd_report','board_presentation','regulatory_filing','other')",
                name="ck_ma_documents_type",
            ),
        )

    if not _index_exists("idx_ma_workspaces_tenant_status"):
        op.execute("CREATE INDEX idx_ma_workspaces_tenant_status ON ma_workspaces (tenant_id, deal_status)")
    if not _index_exists("idx_ma_workspace_members_workspace"):
        op.execute("CREATE INDEX idx_ma_workspace_members_workspace ON ma_workspace_members (workspace_id)")
    if not _index_exists("idx_ma_valuations_workspace_computed"):
        op.execute("CREATE INDEX idx_ma_valuations_workspace_computed ON ma_valuations (workspace_id, computed_at DESC)")
    if not _index_exists("idx_ma_dd_items_workspace_status"):
        op.execute("CREATE INDEX idx_ma_dd_items_workspace_status ON ma_dd_items (workspace_id, status)")
    if not _index_exists("idx_ma_documents_workspace_type"):
        op.execute("CREATE INDEX idx_ma_documents_workspace_type ON ma_documents (workspace_id, document_type)")

    for table_name in (
        "ma_workspaces",
        "ma_workspace_members",
        "ma_valuations",
        "ma_dd_items",
        "ma_documents",
    ):
        if _table_exists(table_name):
            _enable_rls_with_policies(table_name)

    for append_only_table in ("ma_valuations", "ma_documents"):
        if _table_exists(append_only_table):
            op.execute(append_only_function_sql())
            op.execute(drop_trigger_sql(append_only_table))
            op.execute(create_trigger_sql(append_only_table))


def downgrade() -> None:
    for table_name in ("ma_documents", "ma_valuations"):
        if _table_exists(table_name):
            op.execute(drop_trigger_sql(table_name))

    if _index_exists("idx_ma_documents_workspace_type") and _table_exists("ma_documents"):
        op.drop_index("idx_ma_documents_workspace_type", table_name="ma_documents")
    if _index_exists("idx_ma_dd_items_workspace_status") and _table_exists("ma_dd_items"):
        op.drop_index("idx_ma_dd_items_workspace_status", table_name="ma_dd_items")
    if _index_exists("idx_ma_valuations_workspace_computed") and _table_exists("ma_valuations"):
        op.drop_index("idx_ma_valuations_workspace_computed", table_name="ma_valuations")
    if _index_exists("idx_ma_workspace_members_workspace") and _table_exists("ma_workspace_members"):
        op.drop_index("idx_ma_workspace_members_workspace", table_name="ma_workspace_members")
    if _index_exists("idx_ma_workspaces_tenant_status") and _table_exists("ma_workspaces"):
        op.drop_index("idx_ma_workspaces_tenant_status", table_name="ma_workspaces")

    if _table_exists("ma_documents"):
        op.drop_table("ma_documents")
    if _table_exists("ma_dd_items"):
        op.drop_table("ma_dd_items")
    if _table_exists("ma_valuations"):
        op.drop_table("ma_valuations")
    if _table_exists("ma_workspace_members"):
        op.drop_table("ma_workspace_members")
    if _table_exists("ma_workspaces"):
        op.drop_table("ma_workspaces")
