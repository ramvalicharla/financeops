"""Phase 5D Anomaly UI Layer

Revision ID: 0031_anomaly_ui_layer
Revises: 0030_scheduled_delivery
Create Date: 2026-03-21 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031_anomaly_ui_layer"
down_revision: str | None = "0030_scheduled_delivery"
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


def _constraint_exists(table_name: str, constraint_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class t ON c.conrelid = t.oid
            JOIN pg_namespace n ON t.relnamespace = n.oid
            WHERE n.nspname = 'public'
              AND t.relname = :table_name
              AND c.conname = :constraint_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "constraint_name": constraint_name},
    ).scalar_one_or_none()
    return value is not None


def upgrade() -> None:
    table_name = "anomaly_results"
    if not _table_exists(table_name):
        return

    if not _column_exists(table_name, "alert_status"):
        op.add_column(
            table_name,
            sa.Column(
                "alert_status",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'OPEN'"),
            ),
        )

    if not _column_exists(table_name, "snoozed_until"):
        op.add_column(
            table_name,
            sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        )

    if not _column_exists(table_name, "resolved_at"):
        op.add_column(
            table_name,
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _column_exists(table_name, "escalated_at"):
        op.add_column(
            table_name,
            sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _column_exists(table_name, "status_note"):
        op.add_column(table_name, sa.Column("status_note", sa.Text(), nullable=True))

    if not _column_exists(table_name, "status_updated_by"):
        op.add_column(
            table_name,
            sa.Column("status_updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        )

    if not _constraint_exists(table_name, "ck_anomaly_results_alert_status"):
        op.create_check_constraint(
            "ck_anomaly_results_alert_status",
            table_name,
            "alert_status IN ('OPEN','SNOOZED','RESOLVED','ESCALATED')",
        )


def downgrade() -> None:
    table_name = "anomaly_results"
    if not _table_exists(table_name):
        return

    if _constraint_exists(table_name, "ck_anomaly_results_alert_status"):
        op.drop_constraint("ck_anomaly_results_alert_status", table_name, type_="check")

    if _column_exists(table_name, "status_updated_by"):
        op.drop_column(table_name, "status_updated_by")

    if _column_exists(table_name, "status_note"):
        op.drop_column(table_name, "status_note")

    if _column_exists(table_name, "escalated_at"):
        op.drop_column(table_name, "escalated_at")

    if _column_exists(table_name, "resolved_at"):
        op.drop_column(table_name, "resolved_at")

    if _column_exists(table_name, "snoozed_until"):
        op.drop_column(table_name, "snoozed_until")

    if _column_exists(table_name, "alert_status"):
        op.drop_column(table_name, "alert_status")
