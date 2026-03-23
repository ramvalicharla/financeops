"""Backup and disaster recovery run log.

Revision ID: 0047_backup_dr
Revises: 0046_gdpr_operational
Create Date: 2026-03-23 21:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0047_backup_dr"
down_revision: str | None = "0046_gdpr_operational"
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


def upgrade() -> None:
    if not _table_exists("backup_run_log"):
        op.create_table(
            "backup_run_log",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("backup_type", sa.String(length=30), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("size_bytes", sa.BigInteger(), nullable=True),
            sa.Column("backup_location", sa.Text(), nullable=True),
            sa.Column("verification_passed", sa.Boolean(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("triggered_by", sa.String(length=100), nullable=False),
            sa.Column("retention_days", sa.Integer(), nullable=False, server_default=sa.text("30")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("backup_type IN ('full','incremental','wal','redis','r2_sync')", name="ck_backup_run_log_type"),
            sa.CheckConstraint("status IN ('started','completed','failed','verified')", name="ck_backup_run_log_status"),
            sa.CheckConstraint("triggered_by IN ('scheduled','manual','ci_pipeline')", name="ck_backup_run_log_triggered_by"),
        )

    if not _index_exists("idx_backup_run_log_type_started"):
        op.execute("CREATE INDEX idx_backup_run_log_type_started ON backup_run_log (backup_type, started_at DESC)")
    if not _index_exists("idx_backup_run_log_status_created"):
        op.execute("CREATE INDEX idx_backup_run_log_status_created ON backup_run_log (status, created_at DESC)")

    if _table_exists("backup_run_log"):
        op.execute(append_only_function_sql())
        op.execute(drop_trigger_sql("backup_run_log"))
        op.execute(create_trigger_sql("backup_run_log"))


def downgrade() -> None:
    if _table_exists("backup_run_log"):
        op.execute(drop_trigger_sql("backup_run_log"))
    if _index_exists("idx_backup_run_log_status_created") and _table_exists("backup_run_log"):
        op.drop_index("idx_backup_run_log_status_created", table_name="backup_run_log")
    if _index_exists("idx_backup_run_log_type_started") and _table_exists("backup_run_log"):
        op.drop_index("idx_backup_run_log_type_started", table_name="backup_run_log")
    if _table_exists("backup_run_log"):
        op.drop_table("backup_run_log")

