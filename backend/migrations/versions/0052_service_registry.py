"""Service registry platform tables.

Revision ID: 0052_service_registry
Revises: 0051_ma_workspace
Create Date: 2026-03-24 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0052_service_registry"
down_revision: str | None = "0051_ma_workspace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MODULE_SEED_ROWS = [
    ("mis_manager", "MIS upload and template management", "/api/v1/mis", []),
    ("reconciliation", "GL/TB reconciliation engine", "/api/v1/reconciliation", ["mis_manager"]),
    ("consolidation", "Multi-entity consolidation", "/api/v1/consolidation", ["reconciliation"]),
    ("fixed_assets", "IAS 16 fixed asset register", "/api/v1/fixed-assets", []),
    ("lease", "IFRS 16 lease accounting", "/api/v1/leases", []),
    ("revenue", "IFRS 15 revenue recognition", "/api/v1/revenue", []),
    ("payroll_gl", "Payroll GL normalisation", "/api/v1/payroll", []),
    ("board_pack", "Board pack generator", "/api/v1/board-pack", ["mis_manager"]),
    ("custom_reports", "Custom report builder", "/api/v1/reports", ["mis_manager"]),
    (
        "scheduled_delivery",
        "Report delivery scheduler",
        "/api/v1/delivery",
        ["board_pack", "custom_reports"],
    ),
    ("anomaly_detection", "Anomaly pattern engine", "/api/v1/anomalies", ["mis_manager"]),
    ("erp_sync", "ERP connector and sync", "/api/v1/erp", []),
    (
        "closing_checklist",
        "Month-end close checklist",
        "/api/v1/close",
        ["erp_sync", "reconciliation"],
    ),
    (
        "working_capital",
        "Working capital dashboard",
        "/api/v1/working-capital",
        ["mis_manager"],
    ),
    ("expense_management", "Expense claims and approvals", "/api/v1/expenses", []),
    ("budgeting", "Annual budget management", "/api/v1/budget", ["mis_manager"]),
    ("forecasting", "Rolling financial forecast", "/api/v1/forecast", ["budgeting"]),
    (
        "scenario_modelling",
        "What-if scenario engine",
        "/api/v1/scenarios",
        ["forecasting"],
    ),
    (
        "fdd",
        "Financial due diligence",
        "/api/v1/advisory/fdd",
        ["mis_manager", "working_capital"],
    ),
    ("ppa", "Purchase price allocation", "/api/v1/advisory/ppa", ["mis_manager"]),
    ("ma_workspace", "M&A workspace", "/api/v1/advisory/ma", ["fdd", "ppa"]),
    (
        "compliance",
        "SOC2 + ISO27001 + GDPR controls",
        "/api/v1/compliance",
        [],
    ),
    ("backup", "Backup and DR management", "/api/v1/backup", []),
]

_TASK_SEED_ROWS = [
    (
        "auto_trigger.trigger_post_sync_pipeline",
        "erp_sync",
        "erp_sync",
        "Trigger post-sync automation pipeline",
        False,
        None,
    ),
    (
        "board_pack_generator.generate",
        "board_pack",
        "report_gen",
        "Generate board pack workbook and narrative",
        False,
        None,
    ),
    (
        "scheduled_delivery.poll_due",
        "scheduled_delivery",
        "email",
        "Poll due report schedules and enqueue deliveries",
        True,
        "*/1 * * * *",
    ),
    (
        "auto_trigger.run_anomaly_detection",
        "anomaly_detection",
        "ai_inference",
        "Run anomaly detection step in pipeline",
        False,
        None,
    ),
    (
        "metrics.update_queue_depths",
        "observability",
        "default",
        "Update queue depth Prometheus metrics",
        True,
        "*/0.5 * * * *",
    ),
    (
        "metrics.update_active_tenants",
        "observability",
        "default",
        "Update active tenant metrics from sessions",
        True,
        "*/5 * * * *",
    ),
    (
        "backup.backup_postgres_daily",
        "backup",
        "default",
        "Run daily PostgreSQL backup workflow",
        True,
        "0 2 * * *",
    ),
]


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
    if not _table_exists("module_registry"):
        op.create_table(
            "module_registry",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("module_name", sa.String(length=100), nullable=False, unique=True),
            sa.Column("module_version", sa.String(length=20), nullable=False, server_default=sa.text("'1.0.0'")),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("health_status", sa.String(length=20), nullable=False, server_default=sa.text("'unknown'")),
            sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
            sa.Column("route_prefix", sa.String(length=100), nullable=True),
            sa.Column("depends_on", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "health_status IN ('healthy','degraded','unhealthy','unknown')",
                name="ck_module_registry_health_status",
            ),
        )

    if not _table_exists("task_registry"):
        op.create_table(
            "task_registry",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                nullable=False,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("task_name", sa.String(length=200), nullable=False, unique=True),
            sa.Column("module_name", sa.String(length=100), nullable=False),
            sa.Column("queue_name", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("avg_duration_seconds", sa.Numeric(8, 2), nullable=True),
            sa.Column("success_rate_7d", sa.Numeric(5, 4), nullable=True),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_run_status", sa.String(length=20), nullable=True),
            sa.Column("is_scheduled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("schedule_cron", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "queue_name IN ('file_scan','parse','erp_sync','report_gen','email','ai_inference','notification','default')",
                name="ck_task_registry_queue_name",
            ),
            sa.CheckConstraint(
                "last_run_status IN ('success','failure','timeout') OR last_run_status IS NULL",
                name="ck_task_registry_last_run_status",
            ),
        )

    if _table_exists("module_registry"):
        bind = op.get_bind()
        for module_name, description, route_prefix, depends_on in _MODULE_SEED_ROWS:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO module_registry (
                        module_name,
                        description,
                        route_prefix,
                        depends_on
                    )
                    VALUES (:module_name, :description, :route_prefix, CAST(:depends_on AS jsonb))
                    ON CONFLICT (module_name) DO NOTHING
                    """
                ),
                {
                    "module_name": module_name,
                    "description": description,
                    "route_prefix": route_prefix,
                    "depends_on": json.dumps(depends_on),
                },
            )

    if _table_exists("task_registry"):
        bind = op.get_bind()
        for (
            task_name,
            module_name,
            queue_name,
            description,
            is_scheduled,
            schedule_cron,
        ) in _TASK_SEED_ROWS:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO task_registry (
                        task_name,
                        module_name,
                        queue_name,
                        description,
                        is_scheduled,
                        schedule_cron
                    )
                    VALUES (
                        :task_name,
                        :module_name,
                        :queue_name,
                        :description,
                        :is_scheduled,
                        :schedule_cron
                    )
                    ON CONFLICT (task_name) DO NOTHING
                    """
                ),
                {
                    "task_name": task_name,
                    "module_name": module_name,
                    "queue_name": queue_name,
                    "description": description,
                    "is_scheduled": is_scheduled,
                    "schedule_cron": schedule_cron,
                },
            )

    if not _index_exists("idx_module_registry_module_name") and _table_exists("module_registry"):
        op.execute("CREATE INDEX idx_module_registry_module_name ON module_registry (module_name)")
    if not _index_exists("idx_task_registry_task_name") and _table_exists("task_registry"):
        op.execute("CREATE INDEX idx_task_registry_task_name ON task_registry (task_name)")
    if not _index_exists("idx_task_registry_queue_name") and _table_exists("task_registry"):
        op.execute("CREATE INDEX idx_task_registry_queue_name ON task_registry (queue_name)")


def downgrade() -> None:
    if _index_exists("idx_task_registry_queue_name") and _table_exists("task_registry"):
        op.drop_index("idx_task_registry_queue_name", table_name="task_registry")
    if _index_exists("idx_task_registry_task_name") and _table_exists("task_registry"):
        op.drop_index("idx_task_registry_task_name", table_name="task_registry")
    if _index_exists("idx_module_registry_module_name") and _table_exists("module_registry"):
        op.drop_index("idx_module_registry_module_name", table_name="module_registry")

    if _table_exists("task_registry"):
        op.drop_table("task_registry")
    if _table_exists("module_registry"):
        op.drop_table("module_registry")
