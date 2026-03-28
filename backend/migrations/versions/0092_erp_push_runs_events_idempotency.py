"""erp_push_runs_events_idempotency

Revision ID: 0092_erp_push_runs_events
Revises: 0093_acct_tax_gst_tds_rules
Create Date: 2026-03-29

Creates:
  erp_push_runs
  erp_push_events
  erp_push_idempotency_keys

All three tables are append-only.
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

revision: str = "0092_erp_push_runs_events"
down_revision: str | None = "0093_acct_tax_gst_tds_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "erp_push_runs",
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
        sa.Column("connection_id", UUID(as_uuid=True), nullable=False),
        sa.Column("connector_type", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("external_journal_id", sa.String(length=256), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_category", sa.String(length=16), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("erp_response", JSONB, nullable=True),
        sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["jv_id"], ["accounting_jv_aggregates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["connection_id"], ["external_connections.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('PUSH_IN_PROGRESS','PUSHED','PUSH_FAILED','DEAD_LETTER')",
            name="ck_erp_push_runs_status",
        ),
        sa.CheckConstraint(
            "error_category IS NULL OR error_category IN ('HARD','SOFT')",
            name="ck_erp_push_runs_error_category",
        ),
    )
    op.create_index("ix_erp_push_runs_jv_id", "erp_push_runs", ["jv_id"])
    op.create_index("ix_erp_push_runs_tenant_id", "erp_push_runs", ["tenant_id"])
    op.create_index(
        "ix_erp_push_runs_idempotency_key",
        "erp_push_runs",
        ["tenant_id", "idempotency_key"],
    )
    op.create_index(
        "ix_erp_push_runs_status",
        "erp_push_runs",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_erp_push_runs_connection_id",
        "erp_push_runs",
        ["connection_id"],
    )

    op.create_table(
        "erp_push_events",
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
        sa.Column("push_run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("jv_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_data", JSONB, nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["push_run_id"], ["erp_push_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["jv_id"], ["accounting_jv_aggregates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_erp_push_events_push_run_id", "erp_push_events", ["push_run_id"])
    op.create_index("ix_erp_push_events_jv_id", "erp_push_events", ["jv_id"])
    op.create_index("ix_erp_push_events_tenant_id", "erp_push_events", ["tenant_id"])

    op.create_table(
        "erp_push_idempotency_keys",
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
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("jv_id", UUID(as_uuid=True), nullable=False),
        sa.Column("push_run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("external_journal_id", sa.String(length=256), nullable=True),
        sa.ForeignKeyConstraint(["jv_id"], ["accounting_jv_aggregates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["push_run_id"], ["erp_push_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('PUSH_IN_PROGRESS','PUSHED','PUSH_FAILED','DEAD_LETTER')",
            name="ck_erp_push_idempotency_keys_status",
        ),
    )
    op.create_index(
        "ix_erp_push_idempotency_keys_lookup",
        "erp_push_idempotency_keys",
        ["tenant_id", "idempotency_key", "created_at"],
    )
    op.create_index(
        "ix_erp_push_idempotency_keys_jv_id",
        "erp_push_idempotency_keys",
        ["jv_id"],
    )

    for table in (
        "erp_push_runs",
        "erp_push_events",
        "erp_push_idempotency_keys",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            "USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), "
            "current_setting('app.current_tenant_id', true))::uuid)"
        )

    op.execute(append_only_function_sql())
    for table in (
        "erp_push_runs",
        "erp_push_events",
        "erp_push_idempotency_keys",
    ):
        op.execute(drop_trigger_sql(table))
        op.execute(create_trigger_sql(table))


def downgrade() -> None:
    for table in (
        "erp_push_idempotency_keys",
        "erp_push_events",
        "erp_push_runs",
    ):
        op.execute(drop_trigger_sql(table))
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")

    op.drop_index(
        "ix_erp_push_idempotency_keys_jv_id",
        table_name="erp_push_idempotency_keys",
    )
    op.drop_index(
        "ix_erp_push_idempotency_keys_lookup",
        table_name="erp_push_idempotency_keys",
    )
    op.drop_table("erp_push_idempotency_keys")

    op.drop_index("ix_erp_push_events_tenant_id", table_name="erp_push_events")
    op.drop_index("ix_erp_push_events_jv_id", table_name="erp_push_events")
    op.drop_index("ix_erp_push_events_push_run_id", table_name="erp_push_events")
    op.drop_table("erp_push_events")

    op.drop_index("ix_erp_push_runs_connection_id", table_name="erp_push_runs")
    op.drop_index("ix_erp_push_runs_status", table_name="erp_push_runs")
    op.drop_index("ix_erp_push_runs_idempotency_key", table_name="erp_push_runs")
    op.drop_index("ix_erp_push_runs_tenant_id", table_name="erp_push_runs")
    op.drop_index("ix_erp_push_runs_jv_id", table_name="erp_push_runs")
    op.drop_table("erp_push_runs")
