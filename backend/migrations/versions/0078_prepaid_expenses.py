"""prepaid expenses module.

Revision ID: 0078_prepaid_expenses
Revises: 0077_fixed_assets
Create Date: 2026-03-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0078_prepaid_expenses"
down_revision: str | None = "0077_fixed_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_expr() -> str:
    return (
        "COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), "
        "NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid"
    )


def _enable_tenant_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table_name}_tenant_isolation ON {table_name} "
        f"USING (tenant_id = {_tenant_expr()})"
    )


def upgrade() -> None:
    op.create_table(
        "prepaid_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reference_number", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("prepaid_type", sa.String(length=30), nullable=False),
        sa.Column("vendor_name", sa.String(length=200), nullable=True),
        sa.Column("invoice_number", sa.String(length=100), nullable=True),
        sa.Column("total_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("amortised_amount", sa.Numeric(20, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("remaining_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("coverage_start", sa.Date(), nullable=False),
        sa.Column("coverage_end", sa.Date(), nullable=False),
        sa.Column("amortisation_method", sa.String(length=20), nullable=False, server_default=sa.text("'SLM'")),
        sa.Column("coa_prepaid_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("coa_expense_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'ACTIVE'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["coa_prepaid_account_id"], ["tenant_coa_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["coa_expense_account_id"], ["tenant_coa_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "entity_id",
            "reference_number",
            name="uq_prepaid_schedules_tenant_entity_reference",
        ),
    )
    op.create_index("idx_prepaid_schedules_tenant_id", "prepaid_schedules", ["tenant_id"], unique=False)
    op.create_index("idx_prepaid_schedules_entity_id", "prepaid_schedules", ["entity_id"], unique=False)
    op.create_index("idx_prepaid_schedules_reference_number", "prepaid_schedules", ["reference_number"], unique=False)
    op.create_index("idx_prepaid_schedules_status", "prepaid_schedules", ["status"], unique=False)

    op.create_table(
        "prepaid_amortisation_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("amortisation_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("is_last_period", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("run_reference", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["schedule_id"], ["prepaid_schedules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_reference", name="uq_prepaid_amortisation_entries_run_reference"),
    )
    op.create_index(
        "idx_prepaid_amortisation_entries_tenant_id",
        "prepaid_amortisation_entries",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "idx_prepaid_amortisation_entries_entity_id",
        "prepaid_amortisation_entries",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        "idx_prepaid_amortisation_entries_schedule_id",
        "prepaid_amortisation_entries",
        ["schedule_id"],
        unique=False,
    )
    op.create_index(
        "idx_prepaid_amortisation_entries_period_start",
        "prepaid_amortisation_entries",
        ["period_start"],
        unique=False,
    )

    _enable_tenant_rls("prepaid_schedules")
    _enable_tenant_rls("prepaid_amortisation_entries")

    op.execute(sa.text(append_only_function_sql()))
    op.execute(sa.text(create_trigger_sql("prepaid_amortisation_entries")))


def downgrade() -> None:
    op.execute(sa.text(drop_trigger_sql("prepaid_amortisation_entries")))

    op.drop_index("idx_prepaid_amortisation_entries_period_start", table_name="prepaid_amortisation_entries")
    op.drop_index("idx_prepaid_amortisation_entries_schedule_id", table_name="prepaid_amortisation_entries")
    op.drop_index("idx_prepaid_amortisation_entries_entity_id", table_name="prepaid_amortisation_entries")
    op.drop_index("idx_prepaid_amortisation_entries_tenant_id", table_name="prepaid_amortisation_entries")
    op.drop_table("prepaid_amortisation_entries")

    op.drop_index("idx_prepaid_schedules_status", table_name="prepaid_schedules")
    op.drop_index("idx_prepaid_schedules_reference_number", table_name="prepaid_schedules")
    op.drop_index("idx_prepaid_schedules_entity_id", table_name="prepaid_schedules")
    op.drop_index("idx_prepaid_schedules_tenant_id", table_name="prepaid_schedules")
    op.drop_table("prepaid_schedules")
