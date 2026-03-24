"""Marketplace contributor, template, and commerce tables.

Revision ID: 0053_marketplace
Revises: 0052_service_registry
Create Date: 2026-03-24 20:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0053_marketplace"
down_revision: str | None = "0052_service_registry"
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


def _tenant_expr() -> str:
    return (
        "COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), "
        "NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid"
    )


def _enable_rls_with_tenant_policy(table_name: str, tenant_column: str = "tenant_id") -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            f"USING ({tenant_column} = {_tenant_expr()})"
        )


def _enable_rls_with_custom_policy(table_name: str, policy_sql: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} USING ({policy_sql})"
        )


def upgrade() -> None:
    if not _table_exists("marketplace_contributors"):
        op.create_table(
            "marketplace_contributors",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "tenant_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("iam_tenants.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("display_name", sa.String(length=200), nullable=False),
            sa.Column("bio", sa.Text(), nullable=True),
            sa.Column(
                "contributor_tier",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'community'"),
            ),
            sa.Column(
                "revenue_share_pct",
                sa.Numeric(5, 4),
                nullable=False,
                server_default=sa.text("0.6000"),
            ),
            sa.Column("stripe_account_id", sa.String(length=100), nullable=True),
            sa.Column(
                "total_earnings",
                sa.Numeric(20, 2),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "total_templates",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "total_downloads",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "rating_average",
                sa.Numeric(3, 2),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
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
            sa.CheckConstraint(
                "contributor_tier IN ('community','verified_partner','platform_official')",
                name="ck_marketplace_contributors_tier",
            ),
            sa.CheckConstraint(
                "revenue_share_pct >= 0 AND revenue_share_pct <= 1",
                name="ck_marketplace_contributors_revenue_share_pct",
            ),
            sa.UniqueConstraint("tenant_id", name="uq_marketplace_contributors_tenant_id"),
        )

    if not _table_exists("marketplace_templates"):
        op.create_table(
            "marketplace_templates",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "contributor_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("marketplace_contributors.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("template_type", sa.String(length=50), nullable=False),
            sa.Column("industry", sa.String(length=100), nullable=True),
            sa.Column("price_credits", sa.Integer(), nullable=False),
            sa.Column(
                "is_free",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "template_data",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("preview_image_url", sa.Text(), nullable=True),
            sa.Column(
                "tags",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "download_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "rating_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "rating_sum",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "rating_average",
                sa.Numeric(3, 2),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'draft'"),
            ),
            sa.Column("review_notes", sa.Text(), nullable=True),
            sa.Column(
                "is_featured",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
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
            sa.CheckConstraint(
                "template_type IN ("
                "'mis_template','report_template','board_pack','classification_mapping',"
                "'consolidation_template','paysheet_template','industry_pack','fdd_template',"
                "'budget_template','forecast_template'"
                ")",
                name="ck_marketplace_templates_template_type",
            ),
            sa.CheckConstraint(
                "industry IN ("
                "'saas','manufacturing','retail','professional_services','healthcare',"
                "'it_services','general','fsi','ecommerce'"
                ") OR industry IS NULL",
                name="ck_marketplace_templates_industry",
            ),
            sa.CheckConstraint(
                "status IN ('draft','pending_review','published','rejected','archived')",
                name="ck_marketplace_templates_status",
            ),
        )

    if not _table_exists("marketplace_purchases"):
        op.create_table(
            "marketplace_purchases",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "template_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("marketplace_templates.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("buyer_tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "contributor_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("marketplace_contributors.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("price_credits_paid", sa.Integer(), nullable=False),
            sa.Column("platform_share_credits", sa.Integer(), nullable=False),
            sa.Column("contributor_share_credits", sa.Integer(), nullable=False),
            sa.Column("platform_share_pct", sa.Numeric(5, 4), nullable=False),
            sa.Column("contributor_share_pct", sa.Numeric(5, 4), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'completed'"),
            ),
            sa.Column(
                "purchased_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )

    if not _table_exists("marketplace_payouts"):
        op.create_table(
            "marketplace_payouts",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "contributor_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("marketplace_contributors.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column("total_credits_earned", sa.Integer(), nullable=False),
            sa.Column("total_usd_amount", sa.Numeric(20, 2), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'pending'"),
            ),
            sa.Column("stripe_transfer_id", sa.String(length=100), nullable=True),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "status IN ('pending','processing','completed','failed')",
                name="ck_marketplace_payouts_status",
            ),
        )

    if not _table_exists("marketplace_ratings"):
        op.create_table(
            "marketplace_ratings",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "template_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("marketplace_templates.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("buyer_tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("review_text", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "rating BETWEEN 1 AND 5",
                name="ck_marketplace_ratings_rating",
            ),
            sa.UniqueConstraint(
                "template_id",
                "buyer_tenant_id",
                name="uq_marketplace_ratings_template_buyer",
            ),
        )

    if not _index_exists("idx_marketplace_templates_status_type_industry"):
        op.execute(
            "CREATE INDEX idx_marketplace_templates_status_type_industry "
            "ON marketplace_templates (status, template_type, industry)"
        )
    if not _index_exists("idx_marketplace_templates_contributor_id"):
        op.execute(
            "CREATE INDEX idx_marketplace_templates_contributor_id "
            "ON marketplace_templates (contributor_id)"
        )
    if not _index_exists("idx_marketplace_templates_featured_status"):
        op.execute(
            "CREATE INDEX idx_marketplace_templates_featured_status "
            "ON marketplace_templates (is_featured, status)"
        )
    if not _index_exists("idx_marketplace_purchases_buyer_purchased_at"):
        op.execute(
            "CREATE INDEX idx_marketplace_purchases_buyer_purchased_at "
            "ON marketplace_purchases (buyer_tenant_id, purchased_at DESC)"
        )
    if not _index_exists("idx_marketplace_purchases_contributor_purchased_at"):
        op.execute(
            "CREATE INDEX idx_marketplace_purchases_contributor_purchased_at "
            "ON marketplace_purchases (contributor_id, purchased_at DESC)"
        )

    if _table_exists("marketplace_contributors"):
        _enable_rls_with_tenant_policy("marketplace_contributors")
    if _table_exists("marketplace_templates"):
        _enable_rls_with_tenant_policy("marketplace_templates")
    if _table_exists("marketplace_purchases"):
        _enable_rls_with_custom_policy(
            "marketplace_purchases",
            "buyer_tenant_id = "
            + _tenant_expr()
            + " OR contributor_id IN ("
            "SELECT c.id FROM marketplace_contributors c "
            "WHERE c.tenant_id = "
            + _tenant_expr()
            + ")",
        )
    if _table_exists("marketplace_payouts"):
        _enable_rls_with_custom_policy(
            "marketplace_payouts",
            "contributor_id IN ("
            "SELECT c.id FROM marketplace_contributors c "
            "WHERE c.tenant_id = "
            + _tenant_expr()
            + ")",
        )
    if _table_exists("marketplace_ratings"):
        _enable_rls_with_custom_policy(
            "marketplace_ratings",
            "buyer_tenant_id = " + _tenant_expr(),
        )

    for append_only_table in (
        "marketplace_purchases",
        "marketplace_payouts",
        "marketplace_ratings",
    ):
        if _table_exists(append_only_table):
            op.execute(append_only_function_sql())
            op.execute(drop_trigger_sql(append_only_table))
            op.execute(create_trigger_sql(append_only_table))

    if _table_exists("marketplace_contributors"):
        bind = op.get_bind()
        bind.execute(
            sa.text(
                """
                INSERT INTO marketplace_contributors (
                    tenant_id,
                    display_name,
                    contributor_tier,
                    revenue_share_pct
                )
                VALUES (
                    CAST(:tenant_id AS uuid),
                    :display_name,
                    :contributor_tier,
                    :revenue_share_pct
                )
                ON CONFLICT (tenant_id) DO NOTHING
                """
            ),
            {
                "tenant_id": "00000000-0000-0000-0000-000000000000",
                "display_name": "FinanceOps Official",
                "contributor_tier": "platform_official",
                "revenue_share_pct": "1.0000",
            },
        )


def downgrade() -> None:
    for table_name in (
        "marketplace_ratings",
        "marketplace_payouts",
        "marketplace_purchases",
    ):
        if _table_exists(table_name):
            op.execute(drop_trigger_sql(table_name))

    if _index_exists("idx_marketplace_purchases_contributor_purchased_at") and _table_exists("marketplace_purchases"):
        op.drop_index(
            "idx_marketplace_purchases_contributor_purchased_at",
            table_name="marketplace_purchases",
        )
    if _index_exists("idx_marketplace_purchases_buyer_purchased_at") and _table_exists("marketplace_purchases"):
        op.drop_index(
            "idx_marketplace_purchases_buyer_purchased_at",
            table_name="marketplace_purchases",
        )
    if _index_exists("idx_marketplace_templates_featured_status") and _table_exists("marketplace_templates"):
        op.drop_index("idx_marketplace_templates_featured_status", table_name="marketplace_templates")
    if _index_exists("idx_marketplace_templates_contributor_id") and _table_exists("marketplace_templates"):
        op.drop_index("idx_marketplace_templates_contributor_id", table_name="marketplace_templates")
    if _index_exists("idx_marketplace_templates_status_type_industry") and _table_exists("marketplace_templates"):
        op.drop_index(
            "idx_marketplace_templates_status_type_industry",
            table_name="marketplace_templates",
        )

    if _table_exists("marketplace_ratings"):
        op.drop_table("marketplace_ratings")
    if _table_exists("marketplace_payouts"):
        op.drop_table("marketplace_payouts")
    if _table_exists("marketplace_purchases"):
        op.drop_table("marketplace_purchases")
    if _table_exists("marketplace_templates"):
        op.drop_table("marketplace_templates")
    if _table_exists("marketplace_contributors"):
        op.drop_table("marketplace_contributors")

