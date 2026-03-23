"""FDD module tables for advisory due diligence engagements.

Revision ID: 0049_fdd
Revises: 0048_platform_bootstrap
Create Date: 2026-03-24 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0049_fdd"
down_revision: str | None = "0048_platform_bootstrap"
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
    if not _table_exists("fdd_engagements"):
        op.create_table(
            "fdd_engagements",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("engagement_name", sa.String(length=300), nullable=False),
            sa.Column("target_company_name", sa.String(length=300), nullable=False),
            sa.Column("analysis_period_start", sa.Date(), nullable=False),
            sa.Column("analysis_period_end", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'draft'")),
            sa.Column("credit_cost", sa.Integer(), nullable=False, server_default=sa.text("2500")),
            sa.Column("credits_reserved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("credits_deducted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sections_requested", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("sections_completed", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("iam_users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("status IN ('draft','running','completed','failed','archived')", name="ck_fdd_engagements_status"),
        )

    if not _table_exists("fdd_sections"):
        op.create_table(
            "fdd_sections",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("engagement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fdd_engagements.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("section_name", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("result_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("ai_narrative", sa.Text(), nullable=True),
            sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("duration_seconds", sa.Numeric(8, 2), nullable=True),
            sa.CheckConstraint(
                "section_name IN ('quality_of_earnings','working_capital','debt_liability','headcount','revenue_quality')",
                name="ck_fdd_sections_name",
            ),
            sa.CheckConstraint("status IN ('running','completed','failed')", name="ck_fdd_sections_status"),
        )

    if not _table_exists("fdd_findings"):
        op.create_table(
            "fdd_findings",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("engagement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fdd_engagements.id", ondelete="CASCADE"), nullable=False),
            sa.Column("section_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("fdd_sections.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("finding_type", sa.String(length=30), nullable=False),
            sa.Column("severity", sa.String(length=20), nullable=False),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("financial_impact", sa.Numeric(20, 2), nullable=True),
            sa.Column("financial_impact_currency", sa.String(length=3), nullable=False, server_default=sa.text("'INR'")),
            sa.Column("recommended_action", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "finding_type IN ('risk','adjustment','normalisation','information','positive')",
                name="ck_fdd_findings_type",
            ),
            sa.CheckConstraint(
                "severity IN ('critical','high','medium','low','informational')",
                name="ck_fdd_findings_severity",
            ),
        )

    if not _index_exists("idx_fdd_engagements_tenant_status"):
        op.execute("CREATE INDEX idx_fdd_engagements_tenant_status ON fdd_engagements (tenant_id, status)")
    if not _index_exists("idx_fdd_sections_engagement_section"):
        op.execute("CREATE INDEX idx_fdd_sections_engagement_section ON fdd_sections (engagement_id, section_name)")
    if not _index_exists("idx_fdd_findings_engagement_severity_type"):
        op.execute("CREATE INDEX idx_fdd_findings_engagement_severity_type ON fdd_findings (engagement_id, severity, finding_type)")

    for table_name in ("fdd_engagements", "fdd_sections", "fdd_findings"):
        if _table_exists(table_name):
            _enable_rls_with_policies(table_name)

    for append_only_table in ("fdd_sections", "fdd_findings"):
        if _table_exists(append_only_table):
            op.execute(append_only_function_sql())
            op.execute(drop_trigger_sql(append_only_table))
            op.execute(create_trigger_sql(append_only_table))


def downgrade() -> None:
    for table_name in ("fdd_findings", "fdd_sections"):
        if _table_exists(table_name):
            op.execute(drop_trigger_sql(table_name))

    if _index_exists("idx_fdd_findings_engagement_severity_type") and _table_exists("fdd_findings"):
        op.drop_index("idx_fdd_findings_engagement_severity_type", table_name="fdd_findings")
    if _index_exists("idx_fdd_sections_engagement_section") and _table_exists("fdd_sections"):
        op.drop_index("idx_fdd_sections_engagement_section", table_name="fdd_sections")
    if _index_exists("idx_fdd_engagements_tenant_status") and _table_exists("fdd_engagements"):
        op.drop_index("idx_fdd_engagements_tenant_status", table_name="fdd_engagements")

    if _table_exists("fdd_findings"):
        op.drop_table("fdd_findings")
    if _table_exists("fdd_sections"):
        op.drop_table("fdd_sections")
    if _table_exists("fdd_engagements"):
        op.drop_table("fdd_engagements")
