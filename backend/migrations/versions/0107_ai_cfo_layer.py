"""ai_cfo_layer

Revision ID: 0107_ai_cfo_layer
Revises: 0106_analytics_cfo_dashboard
Create Date: 2026-04-02

Phase 9:
- AI CFO anomaly events (append-only)
- AI CFO recommendations (append-only)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0107_ai_cfo_layer"
down_revision = "0106_analytics_cfo_dashboard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_anomalies",
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
            "org_entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cp_entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "org_group_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cp_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("anomaly_type", sa.String(length=64), nullable=False),
        sa.Column("deviation_value", sa.Numeric(24, 6), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("fact_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("lineage_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
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
        "ix_analytics_anomalies_tenant_metric",
        "analytics_anomalies",
        ["tenant_id", "metric_name"],
    )
    op.create_index(
        "ix_analytics_anomalies_tenant_created",
        "analytics_anomalies",
        ["tenant_id", "created_at"],
    )

    op.create_table(
        "analytics_recommendations",
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
            "org_entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cp_entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "org_group_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cp_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("recommendation_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("evidence_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
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
        "ix_analytics_recommendations_tenant_type",
        "analytics_recommendations",
        ["tenant_id", "recommendation_type"],
    )
    op.create_index(
        "ix_analytics_recommendations_tenant_created",
        "analytics_recommendations",
        ["tenant_id", "created_at"],
    )

    for table in ("analytics_anomalies", "analytics_recommendations"):
        op.execute(
            f"""
            CREATE TRIGGER trg_append_only_{table}
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION financeops_block_update_delete();
            """
        )


def downgrade() -> None:
    for table in ("analytics_recommendations", "analytics_anomalies"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_append_only_{table} ON {table}")

    op.drop_index(
        "ix_analytics_recommendations_tenant_created",
        table_name="analytics_recommendations",
    )
    op.drop_index(
        "ix_analytics_recommendations_tenant_type",
        table_name="analytics_recommendations",
    )
    op.drop_table("analytics_recommendations")

    op.drop_index("ix_analytics_anomalies_tenant_created", table_name="analytics_anomalies")
    op.drop_index("ix_analytics_anomalies_tenant_metric", table_name="analytics_anomalies")
    op.drop_table("analytics_anomalies")

