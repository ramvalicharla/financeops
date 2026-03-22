"""Working capital dashboard snapshots and line items.

Revision ID: 0040_working_capital
Revises: 0039_closing_checklist
Create Date: 2026-03-23 00:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0040_working_capital"
down_revision: str | None = "0039_closing_checklist"
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
    if not _table_exists("wc_snapshots"):
        op.create_table(
            "wc_snapshots",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("period", sa.String(length=7), nullable=False),
            sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("snapshot_date", sa.Date(), nullable=False),
            sa.Column("ar_total", sa.Numeric(20, 2), nullable=False),
            sa.Column("ar_current", sa.Numeric(20, 2), nullable=False),
            sa.Column("ar_30", sa.Numeric(20, 2), nullable=False),
            sa.Column("ar_60", sa.Numeric(20, 2), nullable=False),
            sa.Column("ar_90", sa.Numeric(20, 2), nullable=False),
            sa.Column("dso_days", sa.Numeric(8, 2), nullable=False),
            sa.Column("ap_total", sa.Numeric(20, 2), nullable=False),
            sa.Column("ap_current", sa.Numeric(20, 2), nullable=False),
            sa.Column("ap_30", sa.Numeric(20, 2), nullable=False),
            sa.Column("ap_60", sa.Numeric(20, 2), nullable=False),
            sa.Column("ap_90", sa.Numeric(20, 2), nullable=False),
            sa.Column("dpo_days", sa.Numeric(8, 2), nullable=False),
            sa.Column("inventory_days", sa.Numeric(8, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("ccc_days", sa.Numeric(8, 2), nullable=False),
            sa.Column("net_working_capital", sa.Numeric(20, 2), nullable=False),
            sa.Column("current_ratio", sa.Numeric(8, 4), nullable=False),
            sa.Column("quick_ratio", sa.Numeric(8, 4), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("tenant_id", "period", "entity_id", name="uq_wc_snapshots_tenant_period_entity"),
        )

    if not _table_exists("ar_line_items"):
        op.create_table(
            "ar_line_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wc_snapshots.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("customer_name", sa.String(length=300), nullable=False),
            sa.Column("customer_id", sa.String(length=100), nullable=True),
            sa.Column("invoice_number", sa.String(length=100), nullable=True),
            sa.Column("invoice_date", sa.Date(), nullable=True),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("days_overdue", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("amount", sa.Numeric(20, 2), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'INR'")),
            sa.Column("amount_base_currency", sa.Numeric(20, 2), nullable=False),
            sa.Column("aging_bucket", sa.String(length=20), nullable=False),
            sa.Column("payment_probability_score", sa.Numeric(5, 4), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "aging_bucket IN ('current','days_30','days_60','days_90','over_90')",
                name="ck_ar_line_items_aging_bucket",
            ),
        )

    if not _table_exists("ap_line_items"):
        op.create_table(
            "ap_line_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("wc_snapshots.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("vendor_name", sa.String(length=300), nullable=False),
            sa.Column("vendor_id", sa.String(length=100), nullable=True),
            sa.Column("invoice_number", sa.String(length=100), nullable=True),
            sa.Column("invoice_date", sa.Date(), nullable=True),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("days_overdue", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("amount", sa.Numeric(20, 2), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default=sa.text("'INR'")),
            sa.Column("amount_base_currency", sa.Numeric(20, 2), nullable=False),
            sa.Column("aging_bucket", sa.String(length=20), nullable=False),
            sa.Column("early_payment_discount_available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("early_payment_discount_pct", sa.Numeric(5, 4), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "aging_bucket IN ('current','days_30','days_60','days_90','over_90')",
                name="ck_ap_line_items_aging_bucket",
            ),
        )

    if not _index_exists("idx_wc2_snapshots_tenant_period"):
        op.execute("CREATE INDEX idx_wc2_snapshots_tenant_period ON wc_snapshots (tenant_id, period)")
    if not _index_exists("idx_wc2_ar_line_items_snapshot_bucket"):
        op.execute("CREATE INDEX idx_wc2_ar_line_items_snapshot_bucket ON ar_line_items (snapshot_id, aging_bucket)")
    if not _index_exists("idx_wc2_ar_line_items_snapshot_overdue_desc"):
        op.execute("CREATE INDEX idx_wc2_ar_line_items_snapshot_overdue_desc ON ar_line_items (snapshot_id, days_overdue DESC)")
    if not _index_exists("idx_wc2_ap_line_items_snapshot_discount"):
        op.execute(
            "CREATE INDEX idx_wc2_ap_line_items_snapshot_discount ON ap_line_items (snapshot_id, early_payment_discount_available)"
        )

    for table_name in ("wc_snapshots", "ar_line_items", "ap_line_items"):
        if _table_exists(table_name):
            _enable_rls_with_policies(table_name)
            op.execute(append_only_function_sql())
            op.execute(drop_trigger_sql(table_name))
            op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    for table_name in ("ap_line_items", "ar_line_items", "wc_snapshots"):
        if _table_exists(table_name):
            op.execute(drop_trigger_sql(table_name))

    if _index_exists("idx_wc2_ap_line_items_snapshot_discount") and _table_exists("ap_line_items"):
        op.drop_index("idx_wc2_ap_line_items_snapshot_discount", table_name="ap_line_items")
    if _index_exists("idx_wc2_ar_line_items_snapshot_overdue_desc") and _table_exists("ar_line_items"):
        op.drop_index("idx_wc2_ar_line_items_snapshot_overdue_desc", table_name="ar_line_items")
    if _index_exists("idx_wc2_ar_line_items_snapshot_bucket") and _table_exists("ar_line_items"):
        op.drop_index("idx_wc2_ar_line_items_snapshot_bucket", table_name="ar_line_items")
    if _index_exists("idx_wc2_snapshots_tenant_period") and _table_exists("wc_snapshots"):
        op.drop_index("idx_wc2_snapshots_tenant_period", table_name="wc_snapshots")

    if _table_exists("ap_line_items"):
        op.drop_table("ap_line_items")
    if _table_exists("ar_line_items"):
        op.drop_table("ar_line_items")
    if _table_exists("wc_snapshots"):
        op.drop_table("wc_snapshots")

