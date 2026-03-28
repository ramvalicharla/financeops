"""notifications_reminder_workflow

Revision ID: 0099_notifications_reminder
Revises: 0096_entity_id_cat2_ops
Create Date: 2026-03-29

Creates:
  - accounting_notification_events (append-only)
  - approval_reminder_runs (append-only)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0099_notifications_reminder"
down_revision: str | None = "0096_entity_id_cat2_ops"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table_name} "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "accounting_notification_events",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("jv_id", UUID(as_uuid=True), nullable=True),
        sa.Column("recipient_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("notification_type", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=256), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["jv_id"], ["accounting_jv_aggregates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["iam_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_accounting_notification_events_tenant",
        "accounting_notification_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_accounting_notification_events_jv_id",
        "accounting_notification_events",
        ["jv_id"],
    )
    op.create_index(
        "ix_accounting_notification_events_recipient",
        "accounting_notification_events",
        ["recipient_user_id"],
    )

    op.create_table(
        "approval_reminder_runs",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("jv_id", UUID(as_uuid=True), nullable=False),
        sa.Column("reminder_type", sa.String(length=16), nullable=False),
        sa.Column("sent_to_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["jv_id"], ["accounting_jv_aggregates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sent_to_user_id"], ["iam_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_reminder_runs_tenant", "approval_reminder_runs", ["tenant_id"])
    op.create_index("ix_approval_reminder_runs_jv_id", "approval_reminder_runs", ["jv_id"])

    _enable_rls("accounting_notification_events")
    _enable_rls("approval_reminder_runs")

    op.execute(append_only_function_sql())
    op.execute(drop_trigger_sql("accounting_notification_events"))
    op.execute(create_trigger_sql("accounting_notification_events"))
    op.execute(drop_trigger_sql("approval_reminder_runs"))
    op.execute(create_trigger_sql("approval_reminder_runs"))


def downgrade() -> None:
    op.execute(drop_trigger_sql("approval_reminder_runs"))
    op.execute(drop_trigger_sql("accounting_notification_events"))

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON approval_reminder_runs")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON accounting_notification_events")

    op.drop_index("ix_approval_reminder_runs_jv_id", table_name="approval_reminder_runs")
    op.drop_index("ix_approval_reminder_runs_tenant", table_name="approval_reminder_runs")
    op.drop_table("approval_reminder_runs")

    op.drop_index(
        "ix_accounting_notification_events_recipient",
        table_name="accounting_notification_events",
    )
    op.drop_index(
        "ix_accounting_notification_events_jv_id",
        table_name="accounting_notification_events",
    )
    op.drop_index(
        "ix_accounting_notification_events_tenant",
        table_name="accounting_notification_events",
    )
    op.drop_table("accounting_notification_events")

