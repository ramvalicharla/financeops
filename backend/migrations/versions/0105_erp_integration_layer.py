"""erp_integration_layer

Revision ID: 0105_erp_integration_layer
Revises: 0104_period_close_governance
Create Date: 2026-04-01

Phase 7:
- Connector-based ERP integration framework
- Sync jobs/logs for import/export tracking
- ERP COA/journal/master mappings
- Journal ERP source traceability
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0105_erp_integration_layer"
down_revision = "0104_period_close_governance"
branch_labels = None
depends_on = None


erp_connector_status_enum = postgresql.ENUM(
    "ACTIVE",
    "INACTIVE",
    "ERROR",
    name="erp_connector_status_enum",
    create_type=False,
)
erp_auth_type_enum = postgresql.ENUM(
    "API_KEY",
    "OAUTH",
    "BASIC",
    name="erp_auth_type_enum",
    create_type=False,
)
erp_sync_type_enum = postgresql.ENUM(
    "IMPORT",
    "EXPORT",
    name="erp_sync_type_enum",
    create_type=False,
)
erp_sync_module_enum = postgresql.ENUM(
    "COA",
    "JOURNALS",
    "VENDORS",
    "CUSTOMERS",
    name="erp_sync_module_enum",
    create_type=False,
)
erp_sync_status_enum = postgresql.ENUM(
    "PENDING",
    "RUNNING",
    "SUCCESS",
    "FAILED",
    name="erp_sync_status_enum",
    create_type=False,
)
erp_master_entity_type_enum = postgresql.ENUM(
    "VENDOR",
    "CUSTOMER",
    name="erp_master_entity_type_enum",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    erp_connector_status_enum.create(bind, checkfirst=True)
    erp_auth_type_enum.create(bind, checkfirst=True)
    erp_sync_type_enum.create(bind, checkfirst=True)
    erp_sync_module_enum.create(bind, checkfirst=True)
    erp_sync_status_enum.create(bind, checkfirst=True)
    erp_master_entity_type_enum.create(bind, checkfirst=True)

    op.create_table(
        "erp_connectors",
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
            sa.ForeignKey("cp_entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("erp_type", sa.String(length=32), nullable=False),
        sa.Column(
            "connection_config",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("auth_type", erp_auth_type_enum, nullable=False),
        sa.Column(
            "status",
            erp_connector_status_enum,
            nullable=False,
            server_default=sa.text("'ACTIVE'::erp_connector_status_enum"),
        ),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
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
            nullable=True,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "org_entity_id",
            "erp_type",
            name="uq_erp_connectors_tenant_entity_type",
        ),
    )
    op.create_index("ix_erp_connectors_tenant", "erp_connectors", ["tenant_id"])
    op.create_index(
        "ix_erp_connectors_entity",
        "erp_connectors",
        ["tenant_id", "org_entity_id"],
    )
    op.create_index(
        "ix_erp_connectors_status",
        "erp_connectors",
        ["tenant_id", "status"],
    )

    op.create_table(
        "erp_sync_jobs",
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
            sa.ForeignKey("cp_entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "erp_connector_id",
            UUID(as_uuid=True),
            sa.ForeignKey("erp_connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sync_type", erp_sync_type_enum, nullable=False),
        sa.Column("module", erp_sync_module_enum, nullable=False),
        sa.Column(
            "status",
            erp_sync_status_enum,
            nullable=False,
            server_default=sa.text("'PENDING'::erp_sync_status_enum"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("request_payload", JSONB, nullable=True),
        sa.Column("result_summary", JSONB, nullable=True),
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
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_erp_sync_jobs_tenant", "erp_sync_jobs", ["tenant_id"])
    op.create_index(
        "ix_erp_sync_jobs_connector",
        "erp_sync_jobs",
        ["tenant_id", "erp_connector_id"],
    )
    op.create_index("ix_erp_sync_jobs_status", "erp_sync_jobs", ["tenant_id", "status"])
    op.create_index("ix_erp_sync_jobs_module", "erp_sync_jobs", ["tenant_id", "module"])

    op.create_table(
        "erp_sync_logs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("erp_sync_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("payload_json", JSONB, nullable=True),
        sa.Column("result_json", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_erp_sync_logs_job", "erp_sync_logs", ["job_id"])
    op.create_index("ix_erp_sync_logs_created", "erp_sync_logs", ["created_at"])

    op.create_table(
        "erp_coa_mappings",
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
            "erp_connector_id",
            UUID(as_uuid=True),
            sa.ForeignKey("erp_connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("erp_account_id", sa.String(length=256), nullable=False),
        sa.Column(
            "internal_account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenant_coa_accounts.id", ondelete="SET NULL"),
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
            nullable=True,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "erp_connector_id",
            "erp_account_id",
            name="uq_erp_coa_mappings_connector_account",
        ),
    )
    op.create_index("ix_erp_coa_mappings_tenant", "erp_coa_mappings", ["tenant_id"])
    op.create_index(
        "ix_erp_coa_mappings_internal",
        "erp_coa_mappings",
        ["tenant_id", "internal_account_id"],
    )

    op.create_table(
        "erp_journal_mappings",
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
            "erp_connector_id",
            UUID(as_uuid=True),
            sa.ForeignKey("erp_connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "internal_journal_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounting_jv_aggregates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("erp_journal_id", sa.String(length=256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "erp_connector_id",
            "erp_journal_id",
            name="uq_erp_journal_mappings_connector_external",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "internal_journal_id",
            name="uq_erp_journal_mappings_internal_journal",
        ),
    )
    op.create_index(
        "ix_erp_journal_mappings_tenant",
        "erp_journal_mappings",
        ["tenant_id"],
    )
    op.create_index(
        "ix_erp_journal_mappings_connector",
        "erp_journal_mappings",
        ["tenant_id", "erp_connector_id"],
    )

    op.create_table(
        "erp_master_mappings",
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
            sa.ForeignKey("cp_entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "erp_connector_id",
            UUID(as_uuid=True),
            sa.ForeignKey("erp_connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", erp_master_entity_type_enum, nullable=False),
        sa.Column("erp_id", sa.String(length=256), nullable=False),
        sa.Column("internal_id", sa.String(length=256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "erp_connector_id",
            "entity_type",
            "erp_id",
            name="uq_erp_master_mappings_connector_entity",
        ),
    )
    op.create_index(
        "ix_erp_master_mappings_tenant_type",
        "erp_master_mappings",
        ["tenant_id", "entity_type"],
    )
    op.create_index(
        "ix_erp_master_mappings_entity_scope",
        "erp_master_mappings",
        ["tenant_id", "org_entity_id"],
    )

    op.add_column(
        "accounting_jv_aggregates",
        sa.Column(
            "source",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'MANUAL'"),
        ),
    )
    op.add_column(
        "accounting_jv_aggregates",
        sa.Column("external_reference_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_accounting_jv_aggregates_source",
        "accounting_jv_aggregates",
        ["tenant_id", "source"],
    )
    op.create_index(
        "uq_accounting_jv_aggregates_external_reference",
        "accounting_jv_aggregates",
        ["tenant_id", "source", "external_reference_id"],
        unique=True,
        postgresql_where=sa.text("external_reference_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_accounting_jv_aggregates_external_reference",
        table_name="accounting_jv_aggregates",
    )
    op.drop_index("ix_accounting_jv_aggregates_source", table_name="accounting_jv_aggregates")
    op.drop_column("accounting_jv_aggregates", "external_reference_id")
    op.drop_column("accounting_jv_aggregates", "source")

    op.drop_index("ix_erp_master_mappings_entity_scope", table_name="erp_master_mappings")
    op.drop_index("ix_erp_master_mappings_tenant_type", table_name="erp_master_mappings")
    op.drop_table("erp_master_mappings")

    op.drop_index("ix_erp_journal_mappings_connector", table_name="erp_journal_mappings")
    op.drop_index("ix_erp_journal_mappings_tenant", table_name="erp_journal_mappings")
    op.drop_table("erp_journal_mappings")

    op.drop_index("ix_erp_coa_mappings_internal", table_name="erp_coa_mappings")
    op.drop_index("ix_erp_coa_mappings_tenant", table_name="erp_coa_mappings")
    op.drop_table("erp_coa_mappings")

    op.drop_index("ix_erp_sync_logs_created", table_name="erp_sync_logs")
    op.drop_index("ix_erp_sync_logs_job", table_name="erp_sync_logs")
    op.drop_table("erp_sync_logs")

    op.drop_index("ix_erp_sync_jobs_module", table_name="erp_sync_jobs")
    op.drop_index("ix_erp_sync_jobs_status", table_name="erp_sync_jobs")
    op.drop_index("ix_erp_sync_jobs_connector", table_name="erp_sync_jobs")
    op.drop_index("ix_erp_sync_jobs_tenant", table_name="erp_sync_jobs")
    op.drop_table("erp_sync_jobs")

    op.drop_index("ix_erp_connectors_status", table_name="erp_connectors")
    op.drop_index("ix_erp_connectors_entity", table_name="erp_connectors")
    op.drop_index("ix_erp_connectors_tenant", table_name="erp_connectors")
    op.drop_table("erp_connectors")

    bind = op.get_bind()
    erp_master_entity_type_enum.drop(bind, checkfirst=True)
    erp_sync_status_enum.drop(bind, checkfirst=True)
    erp_sync_module_enum.drop(bind, checkfirst=True)
    erp_sync_type_enum.drop(bind, checkfirst=True)
    erp_auth_type_enum.drop(bind, checkfirst=True)
    erp_connector_status_enum.drop(bind, checkfirst=True)
