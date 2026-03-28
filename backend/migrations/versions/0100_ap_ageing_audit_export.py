"""ap_ageing_audit_export_support

Revision ID: 0100_ap_ageing_audit_export
Revises: 0099_notifications_reminder
Create Date: 2026-03-29

Creates:
  - accounting_ap_ageing_snapshots (append-only)
  - accounting_audit_export_runs (append-only)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, NUMERIC, UUID

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0100_ap_ageing_audit_export"
down_revision: str | None = "0099_notifications_reminder"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table_name} "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "accounting_ap_ageing_snapshots",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sa.Integer(), nullable=False),
        sa.Column("current_amount", NUMERIC(precision=20, scale=4), nullable=False, server_default=sa.text("0")),
        sa.Column("overdue_1_30", NUMERIC(precision=20, scale=4), nullable=False, server_default=sa.text("0")),
        sa.Column("overdue_31_60", NUMERIC(precision=20, scale=4), nullable=False, server_default=sa.text("0")),
        sa.Column("overdue_61_90", NUMERIC(precision=20, scale=4), nullable=False, server_default=sa.text("0")),
        sa.Column("overdue_90_plus", NUMERIC(precision=20, scale=4), nullable=False, server_default=sa.text("0")),
        sa.Column("total_outstanding", NUMERIC(precision=20, scale=4), nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column("data_source", sa.String(length=16), nullable=False, server_default="ERP_PULL"),
        sa.Column("connector_type", sa.String(length=32), nullable=True),
        sa.Column("raw_data", JSONB, nullable=True),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vendor_id"], ["accounting_vendors.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ap_ageing_snapshots_tenant_entity",
        "accounting_ap_ageing_snapshots",
        ["tenant_id", "entity_id"],
    )
    op.create_index(
        "ix_ap_ageing_snapshots_snapshot_date",
        "accounting_ap_ageing_snapshots",
        ["tenant_id", "snapshot_date"],
    )
    op.create_index(
        "ix_ap_ageing_snapshots_vendor",
        "accounting_ap_ageing_snapshots",
        ["vendor_id"],
    )

    op.create_table(
        "accounting_audit_export_runs",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("export_type", sa.String(length=32), nullable=False),
        sa.Column("export_format", sa.String(length=8), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_period_from", sa.Integer(), nullable=True),
        sa.Column("fiscal_period_to", sa.Integer(), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("filters", JSONB, nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("r2_key", sa.String(length=512), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_by", UUID(as_uuid=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by"], ["iam_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_export_runs_tenant", "accounting_audit_export_runs", ["tenant_id"])
    op.create_index("ix_audit_export_runs_entity", "accounting_audit_export_runs", ["entity_id"])
    op.create_index(
        "ix_audit_export_runs_requested_by",
        "accounting_audit_export_runs",
        ["requested_by"],
    )

    _enable_rls("accounting_ap_ageing_snapshots")
    _enable_rls("accounting_audit_export_runs")

    op.execute(append_only_function_sql())
    op.execute(drop_trigger_sql("accounting_ap_ageing_snapshots"))
    op.execute(create_trigger_sql("accounting_ap_ageing_snapshots"))
    op.execute(drop_trigger_sql("accounting_audit_export_runs"))
    op.execute(create_trigger_sql("accounting_audit_export_runs"))


def downgrade() -> None:
    op.execute(drop_trigger_sql("accounting_audit_export_runs"))
    op.execute(drop_trigger_sql("accounting_ap_ageing_snapshots"))

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON accounting_audit_export_runs")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON accounting_ap_ageing_snapshots")

    op.drop_index("ix_audit_export_runs_requested_by", table_name="accounting_audit_export_runs")
    op.drop_index("ix_audit_export_runs_entity", table_name="accounting_audit_export_runs")
    op.drop_index("ix_audit_export_runs_tenant", table_name="accounting_audit_export_runs")
    op.drop_table("accounting_audit_export_runs")

    op.drop_index("ix_ap_ageing_snapshots_vendor", table_name="accounting_ap_ageing_snapshots")
    op.drop_index("ix_ap_ageing_snapshots_snapshot_date", table_name="accounting_ap_ageing_snapshots")
    op.drop_index("ix_ap_ageing_snapshots_tenant_entity", table_name="accounting_ap_ageing_snapshots")
    op.drop_table("accounting_ap_ageing_snapshots")

