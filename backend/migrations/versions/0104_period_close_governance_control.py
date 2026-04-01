"""period_close_governance_control

Revision ID: 0104_period_close_governance
Revises: 0103_fx_multi_currency_ias21
Create Date: 2026-04-01

Phase 6 foundation:
- accounting_periods for OPEN/SOFT/HARD close lifecycle
- close_checklists for close control evidence tracking
- approval_policies for maker-checker policy control
- accounting_governance_audit_events append-only governance events
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0104_period_close_governance"
down_revision = "0103_fx_multi_currency_ias21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "accounting_periods",
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
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("period_number", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'OPEN'"),
        ),
        sa.Column(
            "locked_by",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "reopened_by",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
            "fiscal_year",
            "period_number",
            name="uq_accounting_periods_tenant_entity_period",
        ),
    )
    op.create_index("ix_accounting_periods_tenant", "accounting_periods", ["tenant_id"])
    op.create_index(
        "ix_accounting_periods_tenant_entity_period",
        "accounting_periods",
        ["tenant_id", "org_entity_id", "fiscal_year", "period_number"],
    )
    op.create_index(
        "uq_accounting_periods_tenant_global_period",
        "accounting_periods",
        ["tenant_id", "fiscal_year", "period_number"],
        unique=True,
        postgresql_where=sa.text("org_entity_id IS NULL"),
    )

    op.create_table(
        "close_checklists",
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
            "period_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounting_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checklist_type", sa.String(length=64), nullable=False),
        sa.Column(
            "checklist_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("evidence_json", JSONB, nullable=True),
        sa.Column(
            "completed_by",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_close_checklists_tenant_period",
        "close_checklists",
        ["tenant_id", "period_id"],
    )
    op.create_index(
        "ix_close_checklists_tenant_entity_type",
        "close_checklists",
        ["tenant_id", "org_entity_id", "checklist_type"],
    )

    op.create_table(
        "approval_policies",
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
        sa.Column(
            "require_reviewer",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "require_distinct_approver",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "require_distinct_poster",
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
            nullable=True,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "module_name",
            name="uq_approval_policies_tenant_module",
        ),
    )
    op.create_index(
        "ix_approval_policies_tenant_module",
        "approval_policies",
        ["tenant_id", "module_name"],
    )

    op.create_table(
        "accounting_governance_audit_events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "entity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cp_entities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column(
            "actor_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("iam_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("payload_json", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_accounting_governance_audit_events_tenant_id",
        "accounting_governance_audit_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_accounting_governance_audit_events_module",
        "accounting_governance_audit_events",
        ["tenant_id", "module"],
    )
    op.create_index(
        "ix_accounting_governance_audit_events_action",
        "accounting_governance_audit_events",
        ["tenant_id", "action"],
    )
    op.create_index(
        "ix_accounting_governance_audit_events_target",
        "accounting_governance_audit_events",
        ["tenant_id", "target_id"],
    )

    op.execute(
        """
        CREATE TRIGGER trg_append_only_accounting_governance_audit_events
        BEFORE UPDATE OR DELETE ON accounting_governance_audit_events
        FOR EACH ROW EXECUTE FUNCTION financeops_block_update_delete();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_append_only_accounting_governance_audit_events "
        "ON accounting_governance_audit_events"
    )
    op.drop_index(
        "ix_accounting_governance_audit_events_target",
        table_name="accounting_governance_audit_events",
    )
    op.drop_index(
        "ix_accounting_governance_audit_events_action",
        table_name="accounting_governance_audit_events",
    )
    op.drop_index(
        "ix_accounting_governance_audit_events_module",
        table_name="accounting_governance_audit_events",
    )
    op.drop_index(
        "ix_accounting_governance_audit_events_tenant_id",
        table_name="accounting_governance_audit_events",
    )
    op.drop_table("accounting_governance_audit_events")

    op.drop_index("ix_approval_policies_tenant_module", table_name="approval_policies")
    op.drop_table("approval_policies")

    op.drop_index("ix_close_checklists_tenant_entity_type", table_name="close_checklists")
    op.drop_index("ix_close_checklists_tenant_period", table_name="close_checklists")
    op.drop_table("close_checklists")

    op.drop_index("uq_accounting_periods_tenant_global_period", table_name="accounting_periods")
    op.drop_index("ix_accounting_periods_tenant_entity_period", table_name="accounting_periods")
    op.drop_index("ix_accounting_periods_tenant", table_name="accounting_periods")
    op.drop_table("accounting_periods")
