"""PPA module tables for purchase price allocation engagements.

Revision ID: 0050_ppa
Revises: 0049_fdd
Create Date: 2026-03-24 09:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0050_ppa"
down_revision: str | None = "0049_fdd"
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
    if not _table_exists("ppa_engagements"):
        op.create_table(
            "ppa_engagements",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("engagement_name", sa.String(length=300), nullable=False),
            sa.Column("target_company_name", sa.String(length=300), nullable=False),
            sa.Column("acquisition_date", sa.Date(), nullable=False),
            sa.Column("purchase_price", sa.Numeric(20, 2), nullable=False),
            sa.Column("purchase_price_currency", sa.String(length=3), nullable=False, server_default=sa.text("'INR'")),
            sa.Column("accounting_standard", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'draft'")),
            sa.Column("credit_cost", sa.Integer(), nullable=False, server_default=sa.text("2000")),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("iam_users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("accounting_standard IN ('IFRS3','ASC805','INDAS103')", name="ck_ppa_engagements_standard"),
            sa.CheckConstraint("status IN ('draft','running','completed','failed')", name="ck_ppa_engagements_status"),
        )

    if not _table_exists("ppa_allocations"):
        op.create_table(
            "ppa_allocations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("engagement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ppa_engagements.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("allocation_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("net_identifiable_assets", sa.Numeric(20, 2), nullable=False),
            sa.Column("total_intangibles_identified", sa.Numeric(20, 2), nullable=False),
            sa.Column("goodwill", sa.Numeric(20, 2), nullable=False),
            sa.Column("deferred_tax_liability", sa.Numeric(20, 2), nullable=False),
            sa.Column("purchase_price_reconciliation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _table_exists("ppa_intangibles"):
        op.create_table(
            "ppa_intangibles",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("engagement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ppa_engagements.id", ondelete="CASCADE"), nullable=False),
            sa.Column("allocation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ppa_allocations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("intangible_name", sa.String(length=200), nullable=False),
            sa.Column("intangible_category", sa.String(length=50), nullable=False),
            sa.Column("fair_value", sa.Numeric(20, 2), nullable=False),
            sa.Column("useful_life_years", sa.Numeric(5, 2), nullable=False),
            sa.Column("amortisation_method", sa.String(length=20), nullable=False),
            sa.Column("annual_amortisation", sa.Numeric(20, 2), nullable=False),
            sa.Column("tax_basis", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("deferred_tax_liability", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("valuation_method", sa.String(length=50), nullable=False),
            sa.Column("valuation_assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "intangible_category IN ('customer_relationships','technology','brand','contracts','non_compete','in_process_rd','other')",
                name="ck_ppa_intangibles_category",
            ),
            sa.CheckConstraint(
                "amortisation_method IN ('straight_line','accelerated','unit_of_production')",
                name="ck_ppa_intangibles_amortisation",
            ),
            sa.CheckConstraint(
                "valuation_method IN ('relief_from_royalty','excess_earnings','cost_approach','market_approach','with_without')",
                name="ck_ppa_intangibles_valuation_method",
            ),
        )

    if not _index_exists("idx_ppa_engagements_tenant_status"):
        op.execute("CREATE INDEX idx_ppa_engagements_tenant_status ON ppa_engagements (tenant_id, status)")
    if not _index_exists("idx_ppa_allocations_engagement"):
        op.execute("CREATE INDEX idx_ppa_allocations_engagement ON ppa_allocations (engagement_id)")
    if not _index_exists("idx_ppa_intangibles_engagement_category"):
        op.execute("CREATE INDEX idx_ppa_intangibles_engagement_category ON ppa_intangibles (engagement_id, intangible_category)")

    for table_name in ("ppa_engagements", "ppa_allocations", "ppa_intangibles"):
        if _table_exists(table_name):
            _enable_rls_with_policies(table_name)

    for append_only_table in ("ppa_allocations", "ppa_intangibles"):
        if _table_exists(append_only_table):
            op.execute(append_only_function_sql())
            op.execute(drop_trigger_sql(append_only_table))
            op.execute(create_trigger_sql(append_only_table))


def downgrade() -> None:
    for table_name in ("ppa_intangibles", "ppa_allocations"):
        if _table_exists(table_name):
            op.execute(drop_trigger_sql(table_name))

    if _index_exists("idx_ppa_intangibles_engagement_category") and _table_exists("ppa_intangibles"):
        op.drop_index("idx_ppa_intangibles_engagement_category", table_name="ppa_intangibles")
    if _index_exists("idx_ppa_allocations_engagement") and _table_exists("ppa_allocations"):
        op.drop_index("idx_ppa_allocations_engagement", table_name="ppa_allocations")
    if _index_exists("idx_ppa_engagements_tenant_status") and _table_exists("ppa_engagements"):
        op.drop_index("idx_ppa_engagements_tenant_status", table_name="ppa_engagements")

    if _table_exists("ppa_intangibles"):
        op.drop_table("ppa_intangibles")
    if _table_exists("ppa_allocations"):
        op.drop_table("ppa_allocations")
    if _table_exists("ppa_engagements"):
        op.drop_table("ppa_engagements")
