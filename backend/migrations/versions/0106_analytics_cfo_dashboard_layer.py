"""analytics_cfo_dashboard_layer

Revision ID: 0106_analytics_cfo_dashboard
Revises: 0105_erp_integration_layer
Create Date: 2026-04-02

Phase 8:
- analytics snapshots / metrics / variances
- budget variance foundation table
- analytics alerts
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0106_analytics_cfo_dashboard"
down_revision = "0105_erp_integration_layer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_entity_id", UUID(as_uuid=True), sa.ForeignKey("cp_entities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("org_group_id", UUID(as_uuid=True), sa.ForeignKey("cp_groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("snapshot_type", sa.String(length=16), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("period_from", sa.Date(), nullable=True),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("data_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_analytics_snapshots_tenant", "analytics_snapshots", ["tenant_id"])
    op.create_index("ix_analytics_snapshots_entity", "analytics_snapshots", ["tenant_id", "org_entity_id"])
    op.create_index("ix_analytics_snapshots_group", "analytics_snapshots", ["tenant_id", "org_group_id"])
    op.create_index(
        "ix_analytics_snapshots_type_date",
        "analytics_snapshots",
        ["tenant_id", "snapshot_type", "as_of_date"],
    )

    op.create_table(
        "analytics_metrics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("metric_value", sa.Numeric(24, 6), nullable=False),
        sa.Column("dimension_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_analytics_metrics_tenant_metric", "analytics_metrics", ["tenant_id", "metric_name"])
    op.create_index("ix_analytics_metrics_tenant_created", "analytics_metrics", ["tenant_id", "created_at"])

    op.create_table(
        "analytics_variances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("current_value", sa.Numeric(24, 6), nullable=False),
        sa.Column("previous_value", sa.Numeric(24, 6), nullable=False),
        sa.Column("variance_value", sa.Numeric(24, 6), nullable=False),
        sa.Column("variance_percent", sa.Numeric(24, 6), nullable=True),
        sa.Column("dimension_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_analytics_variances_tenant_metric", "analytics_variances", ["tenant_id", "metric_name"])
    op.create_index("ix_analytics_variances_tenant_created", "analytics_variances", ["tenant_id", "created_at"])

    op.create_table(
        "budgets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_entity_id", UUID(as_uuid=True), sa.ForeignKey("cp_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("tenant_coa_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("budget_amount", sa.Numeric(24, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_budgets_tenant_entity_period", "budgets", ["tenant_id", "org_entity_id", "period"])
    op.create_index("ix_budgets_tenant_account", "budgets", ["tenant_id", "account_id"])
    op.create_unique_constraint(
        "uq_budgets_tenant_entity_period_account",
        "budgets",
        ["tenant_id", "org_entity_id", "period", "account_id"],
    )

    op.create_table(
        "analytics_alerts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("threshold", sa.Numeric(24, 6), nullable=False),
        sa.Column("condition", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_analytics_alerts_tenant_metric", "analytics_alerts", ["tenant_id", "metric_name"])
    op.create_index("ix_analytics_alerts_tenant_created", "analytics_alerts", ["tenant_id", "created_at"])

    for table in (
        "analytics_snapshots",
        "analytics_metrics",
        "analytics_variances",
        "budgets",
        "analytics_alerts",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_append_only_{table}
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION financeops_block_update_delete();
            """
        )


def downgrade() -> None:
    for table in (
        "analytics_alerts",
        "budgets",
        "analytics_variances",
        "analytics_metrics",
        "analytics_snapshots",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_append_only_{table} ON {table}")

    op.drop_index("ix_analytics_alerts_tenant_created", table_name="analytics_alerts")
    op.drop_index("ix_analytics_alerts_tenant_metric", table_name="analytics_alerts")
    op.drop_table("analytics_alerts")

    op.drop_constraint("uq_budgets_tenant_entity_period_account", "budgets", type_="unique")
    op.drop_index("ix_budgets_tenant_account", table_name="budgets")
    op.drop_index("ix_budgets_tenant_entity_period", table_name="budgets")
    op.drop_table("budgets")

    op.drop_index("ix_analytics_variances_tenant_created", table_name="analytics_variances")
    op.drop_index("ix_analytics_variances_tenant_metric", table_name="analytics_variances")
    op.drop_table("analytics_variances")

    op.drop_index("ix_analytics_metrics_tenant_created", table_name="analytics_metrics")
    op.drop_index("ix_analytics_metrics_tenant_metric", table_name="analytics_metrics")
    op.drop_table("analytics_metrics")

    op.drop_index("ix_analytics_snapshots_type_date", table_name="analytics_snapshots")
    op.drop_index("ix_analytics_snapshots_group", table_name="analytics_snapshots")
    op.drop_index("ix_analytics_snapshots_entity", table_name="analytics_snapshots")
    op.drop_index("ix_analytics_snapshots_tenant", table_name="analytics_snapshots")
    op.drop_table("analytics_snapshots")

