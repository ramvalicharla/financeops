"""accounting_jv_aggregate_core

Revision ID: 0085_accounting_jv_aggregate_v1
Revises: 0084_erp_oauth_sessions_and_conn
Create Date: 2026-03-28

Creates:
  accounting_jv_aggregates - mutable current state of a Journal Voucher
  accounting_jv_lines - append-only line items across JV versions
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, NUMERIC

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0085_accounting_jv_aggregate_v1"
down_revision: str | None = "0084_erp_oauth_sessions_and_conn"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounting_jv_aggregates",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), nullable=True),
        sa.Column("cost_centre_id", UUID(as_uuid=True), nullable=True),
        sa.Column("jv_number", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DRAFT"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("total_debit", NUMERIC(precision=20, scale=4), nullable=False, server_default="0"),
        sa.Column("total_credit", NUMERIC(precision=20, scale=4), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column("workflow_instance_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column("resubmission_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("voided_by", UUID(as_uuid=True), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["cp_locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cost_centre_id"], ["cp_cost_centres.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_instance_id"], ["cp_workflow_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["iam_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "jv_number", name="uq_jv_number_per_tenant"),
    )

    op.create_index("ix_accounting_jv_aggregates_tenant_id", "accounting_jv_aggregates", ["tenant_id"])
    op.create_index("ix_accounting_jv_aggregates_entity_id", "accounting_jv_aggregates", ["entity_id"])
    op.create_index("ix_accounting_jv_aggregates_status", "accounting_jv_aggregates", ["status"])
    op.create_index(
        "ix_accounting_jv_aggregates_period",
        "accounting_jv_aggregates",
        ["tenant_id", "fiscal_year", "fiscal_period"],
    )

    op.create_table(
        "accounting_jv_lines",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("jv_id", UUID(as_uuid=True), nullable=False),
        sa.Column("jv_version", sa.Integer(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("account_code", sa.String(length=32), nullable=False),
        sa.Column("account_name", sa.String(length=256), nullable=True),
        sa.Column("entry_type", sa.String(length=6), nullable=False),
        sa.Column("amount", NUMERIC(precision=20, scale=4), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column("fx_rate", NUMERIC(precision=20, scale=8), nullable=True),
        sa.Column("amount_inr", NUMERIC(precision=20, scale=4), nullable=True),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True), nullable=True),
        sa.Column("cost_centre_id", UUID(as_uuid=True), nullable=True),
        sa.Column("narration", sa.Text(), nullable=True),
        sa.Column("tax_code", sa.String(length=32), nullable=True),
        sa.Column("is_tax_line", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["jv_id"], ["accounting_jv_aggregates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["cp_locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cost_centre_id"], ["cp_cost_centres.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("entry_type IN ('DEBIT','CREDIT')", name="ck_accounting_jv_lines_entry_type"),
    )

    op.create_index("ix_accounting_jv_lines_jv_id", "accounting_jv_lines", ["jv_id"])
    op.create_index("ix_accounting_jv_lines_jv_version", "accounting_jv_lines", ["jv_id", "jv_version"])
    op.create_index("ix_accounting_jv_lines_tenant_id", "accounting_jv_lines", ["tenant_id"])
    op.create_index(
        "ix_accounting_jv_lines_account_code",
        "accounting_jv_lines",
        ["tenant_id", "account_code"],
    )

    op.execute("ALTER TABLE accounting_jv_aggregates ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE accounting_jv_aggregates FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON accounting_jv_aggregates "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )

    op.execute("ALTER TABLE accounting_jv_lines ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE accounting_jv_lines FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON accounting_jv_lines "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )

    op.execute(append_only_function_sql())
    op.execute(drop_trigger_sql("accounting_jv_lines"))
    op.execute(create_trigger_sql("accounting_jv_lines"))


def downgrade() -> None:
    op.execute(drop_trigger_sql("accounting_jv_lines"))

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON accounting_jv_lines")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON accounting_jv_aggregates")

    op.drop_index("ix_accounting_jv_lines_account_code", table_name="accounting_jv_lines")
    op.drop_index("ix_accounting_jv_lines_tenant_id", table_name="accounting_jv_lines")
    op.drop_index("ix_accounting_jv_lines_jv_version", table_name="accounting_jv_lines")
    op.drop_index("ix_accounting_jv_lines_jv_id", table_name="accounting_jv_lines")
    op.drop_table("accounting_jv_lines")

    op.drop_index("ix_accounting_jv_aggregates_period", table_name="accounting_jv_aggregates")
    op.drop_index("ix_accounting_jv_aggregates_status", table_name="accounting_jv_aggregates")
    op.drop_index("ix_accounting_jv_aggregates_entity_id", table_name="accounting_jv_aggregates")
    op.drop_index("ix_accounting_jv_aggregates_tenant_id", table_name="accounting_jv_aggregates")
    op.drop_table("accounting_jv_aggregates")
