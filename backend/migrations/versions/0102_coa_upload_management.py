"""coa_upload_management

Revision ID: 0102_coa_upload_management
Revises: 0101_accounting_rbac_seed_final
Create Date: 2026-04-01

Extends CoA for admin/tenant upload management:
- Adds source/version/scope metadata to coa_ledger_accounts
- Adds upload batch + staging tables
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0102_coa_upload_management"
down_revision = "0101_accounting_rbac_seed_final"
branch_labels = None
depends_on = None


SOURCE_TYPE_ENUM = sa.Enum(
    "SYSTEM",
    "ADMIN_TEMPLATE",
    "TENANT_CUSTOM",
    name="coa_source_type_enum",
)
UPLOAD_STATUS_ENUM = sa.Enum(
    "PENDING",
    "PROCESSING",
    "SUCCESS",
    "FAILED",
    name="coa_upload_status_enum",
)
UPLOAD_MODE_ENUM = sa.Enum(
    "APPEND",
    "REPLACE",
    "VALIDATE_ONLY",
    name="coa_upload_mode_enum",
)


def upgrade() -> None:
    bind = op.get_bind()
    SOURCE_TYPE_ENUM.create(bind, checkfirst=True)
    UPLOAD_STATUS_ENUM.create(bind, checkfirst=True)
    UPLOAD_MODE_ENUM.create(bind, checkfirst=True)

    op.add_column(
        "coa_ledger_accounts",
        sa.Column(
            "source_type",
            SOURCE_TYPE_ENUM,
            nullable=False,
            server_default=sa.text("'SYSTEM'::coa_source_type_enum"),
        ),
    )
    op.add_column(
        "coa_ledger_accounts",
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "coa_ledger_accounts",
        sa.Column(
            "version",
            sa.Integer,
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "coa_ledger_accounts",
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.drop_constraint(
        "uq_coa_ledger_accounts_template_code",
        "coa_ledger_accounts",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_coa_ledger_accounts_tenant_code",
        "coa_ledger_accounts",
        ["tenant_id", "code"],
    )

    op.create_index(
        "idx_coa_ledger_accounts_tenant_id",
        "coa_ledger_accounts",
        ["tenant_id"],
    )
    op.create_index(
        "idx_coa_ledger_accounts_source_type",
        "coa_ledger_accounts",
        ["source_type"],
    )
    op.create_index(
        "uq_coa_ledger_accounts_global_code_ver",
        "coa_ledger_accounts",
        ["industry_template_id", "source_type", "version", "code"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
    )
    op.create_index(
        "uq_coa_ledger_accounts_tenant_code_ver",
        "coa_ledger_accounts",
        ["industry_template_id", "tenant_id", "source_type", "version", "code"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NOT NULL"),
    )

    op.create_table(
        "coa_upload_batches",
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
            sa.ForeignKey("iam_tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "template_id",
            UUID(as_uuid=True),
            sa.ForeignKey("coa_industry_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_type", SOURCE_TYPE_ENUM, nullable=False),
        sa.Column(
            "upload_mode",
            UPLOAD_MODE_ENUM,
            nullable=False,
            server_default=sa.text("'APPEND'::coa_upload_mode_enum"),
        ),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column(
            "upload_status",
            UPLOAD_STATUS_ENUM,
            nullable=False,
            server_default=sa.text("'PENDING'::coa_upload_status_enum"),
        ),
        sa.Column("error_log", JSONB, nullable=True),
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
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_coa_upload_batches_tenant_id",
        "coa_upload_batches",
        ["tenant_id"],
    )
    op.create_index(
        "idx_coa_upload_batches_template_id",
        "coa_upload_batches",
        ["template_id"],
    )
    op.create_index(
        "idx_coa_upload_batches_source_type",
        "coa_upload_batches",
        ["source_type"],
    )
    op.create_index(
        "idx_coa_upload_batches_upload_status",
        "coa_upload_batches",
        ["upload_status"],
    )

    op.create_table(
        "coa_upload_staging_rows",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "batch_id",
            UUID(as_uuid=True),
            sa.ForeignKey("coa_upload_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "template_id",
            UUID(as_uuid=True),
            sa.ForeignKey("coa_industry_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("row_number", sa.Integer, nullable=False),
        sa.Column("group_code", sa.String(50), nullable=False),
        sa.Column("group_name", sa.String(300), nullable=False),
        sa.Column("subgroup_code", sa.String(50), nullable=False),
        sa.Column("subgroup_name", sa.String(300), nullable=False),
        sa.Column("ledger_code", sa.String(50), nullable=False),
        sa.Column("ledger_name", sa.String(300), nullable=False),
        sa.Column("ledger_type", sa.String(20), nullable=False),
        sa.Column(
            "is_control_account",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("validation_errors", JSONB, nullable=True),
        sa.Column(
            "is_valid",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_coa_upload_staging_rows_batch_id",
        "coa_upload_staging_rows",
        ["batch_id"],
    )
    op.create_index(
        "idx_coa_upload_staging_rows_is_valid",
        "coa_upload_staging_rows",
        ["is_valid"],
    )


def downgrade() -> None:
    op.drop_index("idx_coa_upload_staging_rows_is_valid", table_name="coa_upload_staging_rows")
    op.drop_index("idx_coa_upload_staging_rows_batch_id", table_name="coa_upload_staging_rows")
    op.drop_table("coa_upload_staging_rows")

    op.drop_index("idx_coa_upload_batches_upload_status", table_name="coa_upload_batches")
    op.drop_index("idx_coa_upload_batches_source_type", table_name="coa_upload_batches")
    op.drop_index("idx_coa_upload_batches_template_id", table_name="coa_upload_batches")
    op.drop_index("idx_coa_upload_batches_tenant_id", table_name="coa_upload_batches")
    op.drop_table("coa_upload_batches")

    op.drop_index("uq_coa_ledger_accounts_tenant_code_ver", table_name="coa_ledger_accounts")
    op.drop_index("uq_coa_ledger_accounts_global_code_ver", table_name="coa_ledger_accounts")
    op.drop_index("idx_coa_ledger_accounts_source_type", table_name="coa_ledger_accounts")
    op.drop_index("idx_coa_ledger_accounts_tenant_id", table_name="coa_ledger_accounts")
    op.drop_constraint("uq_coa_ledger_accounts_tenant_code", "coa_ledger_accounts", type_="unique")

    op.create_unique_constraint(
        "uq_coa_ledger_accounts_template_code",
        "coa_ledger_accounts",
        ["industry_template_id", "code"],
    )

    op.drop_column("coa_ledger_accounts", "created_by")
    op.drop_column("coa_ledger_accounts", "version")
    op.drop_column("coa_ledger_accounts", "tenant_id")
    op.drop_column("coa_ledger_accounts", "source_type")

    bind = op.get_bind()
    UPLOAD_MODE_ENUM.drop(bind, checkfirst=True)
    UPLOAD_STATUS_ENUM.drop(bind, checkfirst=True)
    SOURCE_TYPE_ENUM.drop(bind, checkfirst=True)
