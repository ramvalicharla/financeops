"""Notification engine tables.

Revision ID: 0056_notifications
Revises: 0055_partner_program
Create Date: 2026-03-24 23:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0056_notifications"
down_revision: str | None = "0055_partner_program"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text("SELECT to_regclass(:table_name)"),
        {"table_name": f"public.{table_name}"},
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


def _tenant_expr() -> str:
    return (
        "COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), "
        "NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid"
    )


def _enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            f"USING (tenant_id = {_tenant_expr()})"
        )


def upgrade() -> None:
    if not _table_exists("notification_events"):
        op.create_table(
            "notification_events",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "recipient_user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("iam_users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("notification_type", sa.String(length=50), nullable=False),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("action_url", sa.Text(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("channels_sent", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "notification_type IN ("
                "'anomaly_detected','anomaly_escalated',"
                "'close_deadline_approaching','close_overdue',"
                "'task_assigned','task_completed','task_blocked',"
                "'approval_required','approval_completed','approval_rejected',"
                "'budget_variance_alert','budget_approved',"
                "'expense_approved','expense_rejected',"
                "'report_ready','board_pack_ready',"
                "'erp_sync_complete','erp_sync_failed',"
                "'fdd_complete','ppa_complete',"
                "'marketplace_template_approved','marketplace_payout_processed',"
                "'partner_commission_earned','system_alert'"
                ")",
                name="ck_notification_events_type",
            ),
        )

    if not _table_exists("notification_read_state"):
        op.create_table(
            "notification_read_state",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "notification_event_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("notification_events.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_dismissed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _table_exists("notification_preferences"):
        op.create_table(
            "notification_preferences",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
            sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("inapp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("quiet_hours_start", sa.Time(timezone=False), nullable=True),
            sa.Column("quiet_hours_end", sa.Time(timezone=False), nullable=True),
            sa.Column("timezone", sa.String(length=50), nullable=False, server_default=sa.text("'Asia/Kolkata'")),
            sa.Column("type_preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _index_exists("idx_notification_events_tenant_user_created"):
        op.execute(
            "CREATE INDEX idx_notification_events_tenant_user_created "
            "ON notification_events (tenant_id, recipient_user_id, created_at DESC)"
        )
    if not _index_exists("idx_notification_events_tenant_type_created"):
        op.execute(
            "CREATE INDEX idx_notification_events_tenant_type_created "
            "ON notification_events (tenant_id, notification_type, created_at DESC)"
        )
    if not _index_exists("idx_notification_read_state_tenant_user"):
        op.execute(
            "CREATE INDEX idx_notification_read_state_tenant_user "
            "ON notification_read_state (tenant_id, user_id, updated_at DESC)"
        )
    if not _index_exists("idx_notification_preferences_tenant_user"):
        op.execute(
            "CREATE INDEX idx_notification_preferences_tenant_user "
            "ON notification_preferences (tenant_id, user_id)"
        )

    for table_name in (
        "notification_events",
        "notification_read_state",
        "notification_preferences",
    ):
        if _table_exists(table_name):
            _enable_rls(table_name)

    if _table_exists("notification_events"):
        op.execute(append_only_function_sql())
        op.execute(drop_trigger_sql("notification_events"))
        op.execute(create_trigger_sql("notification_events"))


def downgrade() -> None:
    if _table_exists("notification_events"):
        op.execute(drop_trigger_sql("notification_events"))

    if _index_exists("idx_notification_preferences_tenant_user") and _table_exists("notification_preferences"):
        op.drop_index("idx_notification_preferences_tenant_user", table_name="notification_preferences")
    if _index_exists("idx_notification_read_state_tenant_user") and _table_exists("notification_read_state"):
        op.drop_index("idx_notification_read_state_tenant_user", table_name="notification_read_state")
    if _index_exists("idx_notification_events_tenant_type_created") and _table_exists("notification_events"):
        op.drop_index("idx_notification_events_tenant_type_created", table_name="notification_events")
    if _index_exists("idx_notification_events_tenant_user_created") and _table_exists("notification_events"):
        op.drop_index("idx_notification_events_tenant_user_created", table_name="notification_events")

    if _table_exists("notification_preferences"):
        op.drop_table("notification_preferences")
    if _table_exists("notification_read_state"):
        op.drop_table("notification_read_state")
    if _table_exists("notification_events"):
        op.drop_table("notification_events")

