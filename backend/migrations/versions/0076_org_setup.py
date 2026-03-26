"""org setup wizard gateway and data model.

Revision ID: 0076_org_setup
Revises: 0075_coa_framework
Create Date: 2026-03-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0076_org_setup"
down_revision: str | None = "0075_coa_framework"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_expr() -> str:
    return (
        "COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), "
        "NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid"
    )


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar_one_or_none()
    return value is not None


def _enable_tenant_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table_name}_tenant_isolation ON {table_name} "
        f"USING (tenant_id = {_tenant_expr()})"
    )


def upgrade() -> None:
    op.add_column(
        "iam_tenants",
        sa.Column("org_setup_complete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "iam_tenants",
        sa.Column("org_setup_step", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    if _table_exists("onboarding_state"):
        op.execute(
            """
            UPDATE iam_tenants
            SET org_setup_complete = true,
                org_setup_step = 7
            WHERE id IN (
                SELECT DISTINCT tenant_id
                FROM onboarding_state
                WHERE completed = true
            )
            """
        )

    op.create_table(
        "org_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_name", sa.String(length=300), nullable=False),
        sa.Column("country_of_incorp", sa.String(length=100), nullable=False),
        sa.Column("country_code", sa.String(length=3), nullable=False),
        sa.Column("functional_currency", sa.String(length=10), nullable=False),
        sa.Column("reporting_currency", sa.String(length=10), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("website", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_org_groups_tenant_id"),
    )
    op.create_index("idx_org_groups_tenant_id", "org_groups", ["tenant_id"], unique=False)

    op.create_table(
        "org_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cp_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("legal_name", sa.String(length=300), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("country_code", sa.String(length=3), nullable=False),
        sa.Column("state_code", sa.String(length=10), nullable=True),
        sa.Column("functional_currency", sa.String(length=10), nullable=False),
        sa.Column("reporting_currency", sa.String(length=10), nullable=False),
        sa.Column("fiscal_year_start", sa.Integer(), nullable=False),
        sa.Column("applicable_gaap", sa.String(length=20), nullable=False),
        sa.Column("industry_template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("incorporation_number", sa.String(length=100), nullable=True),
        sa.Column("pan", sa.String(length=20), nullable=True),
        sa.Column("tan", sa.String(length=20), nullable=True),
        sa.Column("cin", sa.String(length=30), nullable=True),
        sa.Column("gstin", sa.String(length=20), nullable=True),
        sa.Column("lei", sa.String(length=30), nullable=True),
        sa.Column("tax_jurisdiction", sa.String(length=100), nullable=True),
        sa.Column("tax_rate", sa.Numeric(5, 4), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.CheckConstraint("fiscal_year_start >= 1 AND fiscal_year_start <= 12", name="ck_org_entities_fiscal_year_start"),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_group_id"], ["org_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cp_entity_id"], ["cp_entities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["industry_template_id"], ["coa_industry_templates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_org_entities_tenant_id", "org_entities", ["tenant_id"], unique=False)
    op.create_index("idx_org_entities_org_group_id", "org_entities", ["org_group_id"], unique=False)
    op.create_index("idx_org_entities_cp_entity_id", "org_entities", ["cp_entity_id"], unique=False)

    op.create_table(
        "org_ownership",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ownership_pct", sa.Numeric(7, 4), nullable=False),
        sa.Column("consolidation_method", sa.String(length=30), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_entity_id"], ["org_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["child_entity_id"], ["org_entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "parent_entity_id",
            "child_entity_id",
            "effective_from",
            name="uq_org_ownership_scope_effective_from",
        ),
    )
    op.create_index("idx_org_ownership_tenant_id", "org_ownership", ["tenant_id"], unique=False)
    op.create_index("idx_org_ownership_parent_entity_id", "org_ownership", ["parent_entity_id"], unique=False)
    op.create_index("idx_org_ownership_child_entity_id", "org_ownership", ["child_entity_id"], unique=False)

    op.create_table(
        "org_entity_erp_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("erp_type", sa.String(length=50), nullable=False),
        sa.Column("erp_version", sa.String(length=50), nullable=True),
        sa.Column("connection_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("connection_tested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("connection_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_entity_id"], ["org_entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_org_entity_erp_configs_tenant_id", "org_entity_erp_configs", ["tenant_id"], unique=False)
    op.create_index("idx_org_entity_erp_configs_org_entity_id", "org_entity_erp_configs", ["org_entity_id"], unique=False)

    op.create_table(
        "org_setup_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("step1_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("step2_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("step3_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("step4_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("step5_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("step6_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_org_setup_progress_tenant_id"),
    )
    op.create_index("idx_org_setup_progress_tenant_id", "org_setup_progress", ["tenant_id"], unique=False)

    _enable_tenant_rls("org_groups")
    _enable_tenant_rls("org_entities")
    _enable_tenant_rls("org_ownership")
    _enable_tenant_rls("org_entity_erp_configs")
    _enable_tenant_rls("org_setup_progress")


def downgrade() -> None:
    op.drop_index("idx_org_setup_progress_tenant_id", table_name="org_setup_progress")
    op.drop_table("org_setup_progress")

    op.drop_index("idx_org_entity_erp_configs_org_entity_id", table_name="org_entity_erp_configs")
    op.drop_index("idx_org_entity_erp_configs_tenant_id", table_name="org_entity_erp_configs")
    op.drop_table("org_entity_erp_configs")

    op.drop_index("idx_org_ownership_child_entity_id", table_name="org_ownership")
    op.drop_index("idx_org_ownership_parent_entity_id", table_name="org_ownership")
    op.drop_index("idx_org_ownership_tenant_id", table_name="org_ownership")
    op.drop_table("org_ownership")

    op.drop_index("idx_org_entities_cp_entity_id", table_name="org_entities")
    op.drop_index("idx_org_entities_org_group_id", table_name="org_entities")
    op.drop_index("idx_org_entities_tenant_id", table_name="org_entities")
    op.drop_table("org_entities")

    op.drop_index("idx_org_groups_tenant_id", table_name="org_groups")
    op.drop_table("org_groups")

    op.drop_column("iam_tenants", "org_setup_step")
    op.drop_column("iam_tenants", "org_setup_complete")
