"""chart of accounts framework.

Revision ID: 0075_coa_framework
Revises: 0074_display_scale_preferences
Create Date: 2026-03-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0075_coa_framework"
down_revision: str | None = "0074_display_scale_preferences"
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


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname = :table_name
              AND c.conname = :constraint_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "constraint_name": constraint_name},
    ).scalar_one_or_none()
    return value is not None


def _mis_upload_template_fk_exists() -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attname = 'template_id'
            WHERE n.nspname = 'public'
              AND t.relname = 'mis_uploads'
              AND c.contype = 'f'
              AND c.confrelid = 'mis_templates'::regclass
              AND c.conkey = ARRAY[a.attnum]::smallint[]
            LIMIT 1
            """
        )
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
    if (
        _table_exists("mis_uploads")
        and _table_exists("mis_templates")
        and not _mis_upload_template_fk_exists()
    ):
        op.create_foreign_key(
            "fk_mis_uploads_template_id_mis_templates",
            "mis_uploads",
            "mis_templates",
            ["template_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    op.create_table(
        "coa_industry_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_coa_industry_templates_code"),
    )

    op.create_table(
        "coa_fs_classifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_coa_fs_classifications_code"),
    )

    op.create_table(
        "coa_fs_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("fs_classification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gaap", sa.String(length=20), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("schedule_number", sa.String(length=20), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["fs_classification_id"], ["coa_fs_classifications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gaap", "code", name="uq_coa_fs_schedules_gaap_code"),
    )

    op.create_table(
        "coa_fs_line_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("fs_schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("bs_pl_flag", sa.String(length=20), nullable=True),
        sa.Column("asset_liability_class", sa.String(length=20), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["fs_schedule_id"], ["coa_fs_schedules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fs_schedule_id", "code", name="uq_coa_fs_line_items_schedule_code"),
    )

    op.create_table(
        "coa_fs_sublines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("fs_line_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["fs_line_item_id"], ["coa_fs_line_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fs_line_item_id", "code", name="uq_coa_fs_sublines_line_code"),
    )

    op.create_table(
        "coa_account_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("industry_template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fs_subline_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["industry_template_id"], ["coa_industry_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fs_subline_id"], ["coa_fs_sublines.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("industry_template_id", "code", name="uq_coa_account_groups_template_code"),
    )

    op.create_table(
        "coa_account_subgroups",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_group_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_group_id"], ["coa_account_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_group_id", "code", name="uq_coa_account_subgroups_group_code"),
    )

    op.create_table(
        "coa_ledger_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_subgroup_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("industry_template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("normal_balance", sa.String(length=10), nullable=False),
        sa.Column("cash_flow_tag", sa.String(length=20), nullable=True),
        sa.Column("cash_flow_method", sa.String(length=10), nullable=True),
        sa.Column("bs_pl_flag", sa.String(length=20), nullable=True),
        sa.Column("asset_liability_class", sa.String(length=20), nullable=True),
        sa.Column("is_monetary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_related_party", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_tax_deductible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_control_account", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes_reference", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["account_subgroup_id"], ["coa_account_subgroups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["industry_template_id"], ["coa_industry_templates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("industry_template_id", "code", name="uq_coa_ledger_accounts_template_code"),
    )
    op.create_index("idx_coa_ledger_accounts_code", "coa_ledger_accounts", ["code"], unique=False)
    op.create_index(
        "idx_coa_ledger_accounts_industry_template_id",
        "coa_ledger_accounts",
        ["industry_template_id"],
        unique=False,
    )

    op.create_table(
        "coa_gaap_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ledger_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gaap", sa.String(length=20), nullable=False),
        sa.Column("fs_schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fs_line_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fs_subline_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("presentation_label", sa.String(length=300), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["ledger_account_id"], ["coa_ledger_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fs_line_item_id"], ["coa_fs_line_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fs_schedule_id"], ["coa_fs_schedules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fs_subline_id"], ["coa_fs_sublines.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ledger_account_id", "gaap", name="uq_coa_gaap_mappings_ledger_gaap"),
    )

    op.create_table(
        "tenant_coa_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ledger_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_subgroup_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("account_code", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=300), nullable=False),
        sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("default_cost_centre_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("default_location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["ledger_account_id"], ["coa_ledger_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["parent_subgroup_id"], ["coa_account_subgroups.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "account_code", name="uq_tenant_coa_accounts_tenant_code"),
    )
    op.create_index("idx_tenant_coa_accounts_tenant_id", "tenant_coa_accounts", ["tenant_id"], unique=False)
    op.create_index(
        "idx_tenant_coa_accounts_ledger_account_id",
        "tenant_coa_accounts",
        ["ledger_account_id"],
        unique=False,
    )

    op.create_table(
        "erp_account_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("erp_connector_type", sa.String(length=50), nullable=False),
        sa.Column("erp_account_code", sa.String(length=200), nullable=False),
        sa.Column("erp_account_name", sa.String(length=300), nullable=False),
        sa.Column("erp_account_type", sa.String(length=100), nullable=True),
        sa.Column("tenant_coa_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("mapping_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("is_auto_mapped", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("confirmed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["confirmed_by"], ["iam_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_coa_account_id"], ["tenant_coa_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "entity_id",
            "erp_connector_type",
            "erp_account_code",
            name="uq_erp_account_mappings_scope_code",
        ),
    )
    op.create_index("idx_erp_account_mappings_tenant_id", "erp_account_mappings", ["tenant_id"], unique=False)
    op.create_index("idx_erp_account_mappings_entity_id", "erp_account_mappings", ["entity_id"], unique=False)
    op.create_index(
        "idx_erp_account_mappings_erp_connector_type",
        "erp_account_mappings",
        ["erp_connector_type"],
        unique=False,
    )
    op.create_index("idx_erp_account_mappings_is_confirmed", "erp_account_mappings", ["is_confirmed"], unique=False)

    _enable_tenant_rls("tenant_coa_accounts")
    _enable_tenant_rls("erp_account_mappings")


def downgrade() -> None:
    if _constraint_exists("mis_uploads", "fk_mis_uploads_template_id_mis_templates"):
        op.drop_constraint(
            "fk_mis_uploads_template_id_mis_templates",
            "mis_uploads",
            type_="foreignkey",
        )

    op.drop_index("idx_erp_account_mappings_is_confirmed", table_name="erp_account_mappings")
    op.drop_index("idx_erp_account_mappings_erp_connector_type", table_name="erp_account_mappings")
    op.drop_index("idx_erp_account_mappings_entity_id", table_name="erp_account_mappings")
    op.drop_index("idx_erp_account_mappings_tenant_id", table_name="erp_account_mappings")
    op.drop_table("erp_account_mappings")

    op.drop_index("idx_tenant_coa_accounts_ledger_account_id", table_name="tenant_coa_accounts")
    op.drop_index("idx_tenant_coa_accounts_tenant_id", table_name="tenant_coa_accounts")
    op.drop_table("tenant_coa_accounts")

    op.drop_table("coa_gaap_mappings")

    op.drop_index("idx_coa_ledger_accounts_industry_template_id", table_name="coa_ledger_accounts")
    op.drop_index("idx_coa_ledger_accounts_code", table_name="coa_ledger_accounts")
    op.drop_table("coa_ledger_accounts")

    op.drop_table("coa_account_subgroups")
    op.drop_table("coa_account_groups")
    op.drop_table("coa_fs_sublines")
    op.drop_table("coa_fs_line_items")
    op.drop_table("coa_fs_schedules")
    op.drop_table("coa_fs_classifications")
    op.drop_table("coa_industry_templates")
