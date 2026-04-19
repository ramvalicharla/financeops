"""add approval sla breach runs

Revision ID: 0139_approval_sla_breach_runs
Revises: 0138_notification_delivery_state
Create Date: 2026-04-16 17:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0139_approval_sla_breach_runs"
down_revision: str | None = "0138_notification_delivery_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval_sla_breach_runs",
        sa.Column("jv_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("breach_type", sa.String(length=16), nullable=False),
        sa.Column("sent_to_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("breached_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["jv_id"],
            ["accounting_jv_aggregates.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sent_to_user_id"],
            ["iam_users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "jv_id",
            "breach_type",
            name="uq_approval_sla_breach_runs_tenant_jv_type",
        ),
    )
    op.create_index(
        "ix_approval_sla_breach_runs_tenant",
        "approval_sla_breach_runs",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_approval_sla_breach_runs_jv_id",
        "approval_sla_breach_runs",
        ["jv_id"],
        unique=False,
    )
    op.create_index(
        "ix_approval_sla_breach_runs_type",
        "approval_sla_breach_runs",
        ["tenant_id", "breach_type"],
        unique=False,
    )
    op.create_index(
        "ix_approval_sla_breach_runs_breached_at",
        "approval_sla_breach_runs",
        ["tenant_id", "breached_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_approval_sla_breach_runs_breached_at", table_name="approval_sla_breach_runs")
    op.drop_index("ix_approval_sla_breach_runs_type", table_name="approval_sla_breach_runs")
    op.drop_index("ix_approval_sla_breach_runs_jv_id", table_name="approval_sla_breach_runs")
    op.drop_index("ix_approval_sla_breach_runs_tenant", table_name="approval_sla_breach_runs")
    op.drop_table("approval_sla_breach_runs")
