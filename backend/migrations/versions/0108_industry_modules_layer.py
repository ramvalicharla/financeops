"""industry_modules_layer

Revision ID: 0108_industry_modules
Revises: 0107_ai_cfo_layer
Create Date: 2026-04-02

Phase 10:
- Industry-specific accounting module framework
- Lease, revenue recognition, fixed assets, prepaid/accrual schedules
- Module to draft-journal traceability links
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0108_industry_modules"
down_revision = "0107_ai_cfo_layer"
branch_labels = None
depends_on = None


def _create_append_only_trigger(table_name: str) -> None:
    op.execute(
        f"""
        CREATE TRIGGER trg_append_only_{table_name}
        BEFORE UPDATE OR DELETE ON {table_name}
        FOR EACH ROW EXECUTE FUNCTION financeops_block_update_delete();
        """
    )


def _drop_append_only_trigger(table_name: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS trg_append_only_{table_name} ON {table_name}")


def upgrade() -> None:
    op.create_table(
        "finance_modules",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="DISABLED"),
        sa.Column(
            "configuration_json",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("tenant_id", "module_name", name="uq_finance_modules_tenant_module"),
    )
    op.create_index("ix_finance_modules_tenant", "finance_modules", ["tenant_id"])

    op.create_table(
        "industry_leases",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cp_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("lease_start_date", sa.Date(), nullable=False),
        sa.Column("lease_end_date", sa.Date(), nullable=False),
        sa.Column("lease_payment", sa.Numeric(20, 4), nullable=False),
        sa.Column("discount_rate", sa.Numeric(12, 8), nullable=False),
        sa.Column("lease_type", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_industry_leases_tenant_entity",
        "industry_leases",
        ["tenant_id", "entity_id"],
    )
    op.create_index(
        "ix_industry_leases_tenant_created",
        "industry_leases",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "industry_lease_schedules",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lease_id",
            UUID(as_uuid=True),
            sa.ForeignKey("industry_leases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_number", sa.Integer(), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("opening_liability", sa.Numeric(20, 4), nullable=False),
        sa.Column("interest_expense", sa.Numeric(20, 4), nullable=False),
        sa.Column("lease_payment", sa.Numeric(20, 4), nullable=False),
        sa.Column("closing_liability", sa.Numeric(20, 4), nullable=False),
        sa.Column("rou_asset_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("depreciation", sa.Numeric(20, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("lease_id", "period_number", name="uq_industry_lease_schedule_period"),
    )
    op.create_index(
        "ix_industry_lease_schedules_tenant_lease",
        "industry_lease_schedules",
        ["tenant_id", "lease_id"],
    )

    op.create_table(
        "industry_contracts",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cp_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("customer_id", sa.String(length=128), nullable=False),
        sa.Column("contract_start_date", sa.Date(), nullable=False),
        sa.Column("contract_end_date", sa.Date(), nullable=False),
        sa.Column("contract_value", sa.Numeric(20, 4), nullable=False),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_industry_contracts_tenant_entity",
        "industry_contracts",
        ["tenant_id", "entity_id"],
    )

    op.create_table(
        "industry_performance_obligations",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contract_id",
            UUID(as_uuid=True),
            sa.ForeignKey("industry_contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("obligation_type", sa.String(length=64), nullable=False),
        sa.Column("allocation_value", sa.Numeric(20, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_industry_obligations_tenant_contract",
        "industry_performance_obligations",
        ["tenant_id", "contract_id"],
    )

    op.create_table(
        "industry_revenue_schedules",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "obligation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("industry_performance_obligations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_number", sa.Integer(), nullable=False),
        sa.Column("recognition_date", sa.Date(), nullable=False),
        sa.Column("revenue_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "obligation_id",
            "period_number",
            name="uq_industry_revenue_schedules_period",
        ),
    )
    op.create_index(
        "ix_industry_revenue_schedules_tenant_obligation",
        "industry_revenue_schedules",
        ["tenant_id", "obligation_id"],
    )

    op.create_table(
        "industry_fixed_assets",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cp_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("asset_name", sa.String(length=256), nullable=False),
        sa.Column("cost", sa.Numeric(20, 4), nullable=False),
        sa.Column("useful_life_years", sa.Integer(), nullable=False),
        sa.Column("depreciation_method", sa.String(length=16), nullable=False),
        sa.Column("residual_value", sa.Numeric(20, 4), nullable=False, server_default="0"),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_industry_fixed_assets_tenant_entity",
        "industry_fixed_assets",
        ["tenant_id", "entity_id"],
    )

    op.create_table(
        "industry_asset_schedules",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            UUID(as_uuid=True),
            sa.ForeignKey("industry_fixed_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_number", sa.Integer(), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("depreciation", sa.Numeric(20, 4), nullable=False),
        sa.Column("net_book_value", sa.Numeric(20, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("asset_id", "period_number", name="uq_industry_asset_schedules_period"),
    )
    op.create_index(
        "ix_industry_asset_schedules_tenant_asset",
        "industry_asset_schedules",
        ["tenant_id", "asset_id"],
    )

    op.create_table(
        "industry_prepaid_schedules",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cp_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("schedule_batch_id", UUID(as_uuid=True), nullable=False),
        sa.Column("prepaid_name", sa.String(length=255), nullable=False),
        sa.Column("period_number", sa.Integer(), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("amortization_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("remaining_balance", sa.Numeric(20, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "schedule_batch_id",
            "period_number",
            name="uq_industry_prepaid_schedules_batch_period",
        ),
    )
    op.create_index(
        "ix_industry_prepaid_schedules_tenant_batch",
        "industry_prepaid_schedules",
        ["tenant_id", "schedule_batch_id"],
    )

    op.create_table(
        "industry_accrual_schedules",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cp_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("schedule_batch_id", UUID(as_uuid=True), nullable=False),
        sa.Column("accrual_name", sa.String(length=255), nullable=False),
        sa.Column("period_number", sa.Integer(), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("accrual_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("remaining_balance", sa.Numeric(20, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "schedule_batch_id",
            "period_number",
            name="uq_industry_accrual_schedules_batch_period",
        ),
    )
    op.create_index(
        "ix_industry_accrual_schedules_tenant_batch",
        "industry_accrual_schedules",
        ["tenant_id", "schedule_batch_id"],
    )

    op.create_table(
        "industry_subscriptions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cp_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("subscription_name", sa.String(length=255), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("billing_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column(
            "revenue_recognition_method",
            sa.String(length=32),
            nullable=False,
            server_default="STRAIGHT_LINE",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_industry_subscriptions_tenant_entity",
        "industry_subscriptions",
        ["tenant_id", "entity_id"],
    )

    op.create_table(
        "industry_billing_schedules",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            UUID(as_uuid=True),
            sa.ForeignKey("industry_subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_number", sa.Integer(), nullable=False),
        sa.Column("bill_date", sa.Date(), nullable=False),
        sa.Column("billing_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column("deferred_revenue_amount", sa.Numeric(20, 4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "subscription_id",
            "period_number",
            name="uq_industry_billing_schedules_period",
        ),
    )
    op.create_index(
        "ix_industry_billing_schedules_tenant_subscription",
        "industry_billing_schedules",
        ["tenant_id", "subscription_id"],
    )

    op.create_table(
        "industry_journal_links",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module_name", sa.String(length=64), nullable=False),
        sa.Column("module_record_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "journal_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounting_jv_aggregates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_industry_journal_links_tenant_reference",
        "industry_journal_links",
        ["tenant_id", "module_name", "module_record_id"],
    )

    for table in (
        "industry_leases",
        "industry_lease_schedules",
        "industry_contracts",
        "industry_performance_obligations",
        "industry_revenue_schedules",
        "industry_fixed_assets",
        "industry_asset_schedules",
        "industry_prepaid_schedules",
        "industry_accrual_schedules",
        "industry_subscriptions",
        "industry_billing_schedules",
        "industry_journal_links",
    ):
        _create_append_only_trigger(table)


def downgrade() -> None:
    for table in (
        "industry_journal_links",
        "industry_billing_schedules",
        "industry_subscriptions",
        "industry_accrual_schedules",
        "industry_prepaid_schedules",
        "industry_asset_schedules",
        "industry_fixed_assets",
        "industry_revenue_schedules",
        "industry_performance_obligations",
        "industry_contracts",
        "industry_lease_schedules",
        "industry_leases",
    ):
        _drop_append_only_trigger(table)

    op.drop_index("ix_industry_journal_links_tenant_reference", table_name="industry_journal_links")
    op.drop_table("industry_journal_links")

    op.drop_index(
        "ix_industry_billing_schedules_tenant_subscription",
        table_name="industry_billing_schedules",
    )
    op.drop_table("industry_billing_schedules")

    op.drop_index("ix_industry_subscriptions_tenant_entity", table_name="industry_subscriptions")
    op.drop_table("industry_subscriptions")

    op.drop_index("ix_industry_accrual_schedules_tenant_batch", table_name="industry_accrual_schedules")
    op.drop_table("industry_accrual_schedules")

    op.drop_index("ix_industry_prepaid_schedules_tenant_batch", table_name="industry_prepaid_schedules")
    op.drop_table("industry_prepaid_schedules")

    op.drop_index("ix_industry_asset_schedules_tenant_asset", table_name="industry_asset_schedules")
    op.drop_table("industry_asset_schedules")

    op.drop_index("ix_industry_fixed_assets_tenant_entity", table_name="industry_fixed_assets")
    op.drop_table("industry_fixed_assets")

    op.drop_index(
        "ix_industry_revenue_schedules_tenant_obligation",
        table_name="industry_revenue_schedules",
    )
    op.drop_table("industry_revenue_schedules")

    op.drop_index(
        "ix_industry_obligations_tenant_contract",
        table_name="industry_performance_obligations",
    )
    op.drop_table("industry_performance_obligations")

    op.drop_index("ix_industry_contracts_tenant_entity", table_name="industry_contracts")
    op.drop_table("industry_contracts")

    op.drop_index(
        "ix_industry_lease_schedules_tenant_lease",
        table_name="industry_lease_schedules",
    )
    op.drop_table("industry_lease_schedules")

    op.drop_index("ix_industry_leases_tenant_created", table_name="industry_leases")
    op.drop_index("ix_industry_leases_tenant_entity", table_name="industry_leases")
    op.drop_table("industry_leases")

    op.drop_index("ix_finance_modules_tenant", table_name="finance_modules")
    op.drop_table("finance_modules")
