"""Phase 5B Scheduled Delivery

Revision ID: 0030_scheduled_delivery
Revises: 0029_custom_report_builder
Create Date: 2026-03-19 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0030_scheduled_delivery"
down_revision: str | None = "0029_custom_report_builder"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
    ).scalar_one_or_none()
    return value is not None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "column_name": column_name},
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


def _enable_rls_with_policy(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            "USING (tenant_id = current_setting('app.current_tenant_id')::uuid)"
        )


def _ensure_append_only_trigger(table_name: str) -> None:
    op.execute(drop_trigger_sql(table_name))
    op.execute(create_trigger_sql(table_name))


def upgrade() -> None:
    if not _table_exists("delivery_schedules"):
        op.create_table(
            "delivery_schedules",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("schedule_type", sa.String(length=50), nullable=False),
            sa.Column("source_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("cron_expression", sa.String(length=100), nullable=False),
            sa.Column(
                "timezone",
                sa.String(length=100),
                nullable=False,
                server_default=sa.text("'UTC'"),
            ),
            sa.Column(
                "recipients",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column(
                "export_format",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'PDF'"),
            ),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("true"),
            ),
            sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "config",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "schedule_type IN ('BOARD_PACK','REPORT')",
                name="ck_delivery_schedules_schedule_type",
            ),
            sa.CheckConstraint(
                "export_format IN ('PDF','EXCEL','CSV')",
                name="ck_delivery_schedules_export_format",
            ),
        )

    if not _table_exists("delivery_logs"):
        op.create_table(
            "delivery_logs",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("schedule_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "triggered_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "status",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'PENDING'"),
            ),
            sa.Column("channel_type", sa.String(length=20), nullable=False),
            sa.Column("recipient_address", sa.Text(), nullable=False),
            sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "retry_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "response_metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.CheckConstraint(
                "status IN ('PENDING','RUNNING','DELIVERED','FAILED')",
                name="ck_delivery_logs_status",
            ),
            sa.CheckConstraint(
                "channel_type IN ('EMAIL','WEBHOOK')",
                name="ck_delivery_logs_channel_type",
            ),
            sa.ForeignKeyConstraint(
                ["schedule_id"],
                ["delivery_schedules.id"],
                ondelete="RESTRICT",
            ),
        )

    if (
        _column_exists("delivery_schedules", "tenant_id")
        and _column_exists("delivery_schedules", "is_active")
        and not _index_exists("idx_delivery_schedules_tenant_active")
    ):
        op.create_index(
            "idx_delivery_schedules_tenant_active",
            "delivery_schedules",
            ["tenant_id", "is_active"],
        )

    if (
        _column_exists("delivery_schedules", "tenant_id")
        and _column_exists("delivery_schedules", "next_run_at")
        and not _index_exists("idx_delivery_schedules_tenant_next_run_at")
    ):
        op.create_index(
            "idx_delivery_schedules_tenant_next_run_at",
            "delivery_schedules",
            ["tenant_id", "next_run_at"],
        )

    if (
        _column_exists("delivery_logs", "schedule_id")
        and _column_exists("delivery_logs", "triggered_at")
        and not _index_exists("idx_delivery_logs_schedule_triggered_desc")
    ):
        op.execute(
            "CREATE INDEX idx_delivery_logs_schedule_triggered_desc "
            "ON delivery_logs (schedule_id, triggered_at DESC)"
        )

    if (
        _column_exists("delivery_logs", "tenant_id")
        and _column_exists("delivery_logs", "status")
        and not _index_exists("idx_delivery_logs_tenant_status")
    ):
        op.create_index(
            "idx_delivery_logs_tenant_status",
            "delivery_logs",
            ["tenant_id", "status"],
        )

    for table_name in ("delivery_schedules", "delivery_logs"):
        if _table_exists(table_name):
            _enable_rls_with_policy(table_name)

    op.execute(append_only_function_sql())
    if _table_exists("delivery_logs"):
        _ensure_append_only_trigger("delivery_logs")


def downgrade() -> None:
    if _table_exists("delivery_logs"):
        op.drop_table("delivery_logs")

    if (
        _table_exists("delivery_schedules")
        and _column_exists("delivery_schedules", "name")
        and _column_exists("delivery_schedules", "schedule_type")
    ):
        op.drop_table("delivery_schedules")
