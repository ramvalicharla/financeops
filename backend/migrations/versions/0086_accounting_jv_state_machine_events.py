"""accounting_jv_state_machine_events

Revision ID: 0086_accounting_jv_state_machine
Revises: 0085_accounting_jv_aggregate_v1
Create Date: 2026-03-28

Creates accounting_jv_state_events as an append-only transition log.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0086_accounting_jv_state_machine"
down_revision: str | None = "0085_accounting_jv_aggregate_v1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounting_jv_state_events",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("jv_id", UUID(as_uuid=True), nullable=False),
        sa.Column("jv_version", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("triggered_by", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_role", sa.String(length=64), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["jv_id"], ["accounting_jv_aggregates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["triggered_by"], ["iam_users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_accounting_jv_state_events_jv_id",
        "accounting_jv_state_events",
        ["jv_id"],
    )
    op.create_index(
        "ix_accounting_jv_state_events_tenant_id",
        "accounting_jv_state_events",
        ["tenant_id"],
    )
    op.create_index(
        "ix_accounting_jv_state_events_occurred_at",
        "accounting_jv_state_events",
        ["jv_id", "occurred_at"],
    )

    op.execute("ALTER TABLE accounting_jv_state_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE accounting_jv_state_events FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON accounting_jv_state_events "
        "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
        "current_setting('app.current_tenant_id', true))::uuid)"
    )

    op.execute(append_only_function_sql())
    op.execute(drop_trigger_sql("accounting_jv_state_events"))
    op.execute(create_trigger_sql("accounting_jv_state_events"))


def downgrade() -> None:
    op.execute(drop_trigger_sql("accounting_jv_state_events"))
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON accounting_jv_state_events")

    op.drop_index(
        "ix_accounting_jv_state_events_occurred_at",
        table_name="accounting_jv_state_events",
    )
    op.drop_index(
        "ix_accounting_jv_state_events_tenant_id",
        table_name="accounting_jv_state_events",
    )
    op.drop_index(
        "ix_accounting_jv_state_events_jv_id",
        table_name="accounting_jv_state_events",
    )
    op.drop_table("accounting_jv_state_events")
