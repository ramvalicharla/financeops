"""Closing checklist templates, runs, and tasks.

Revision ID: 0039_closing_checklist
Revises: 0038_ai_cost_ledger
Create Date: 2026-03-23 00:00:00.000000
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0039_closing_checklist"
down_revision: str | None = "0038_ai_cost_ledger"
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


def _enable_rls_with_policies(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    if not _policy_exists(table_name, "tenant_isolation"):
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table_name} "
            "USING (tenant_id = COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid)"
        )


def _seed_default_templates() -> None:
    bind = op.get_bind()
    tenants = bind.execute(sa.text("SELECT id FROM iam_tenants")).fetchall()

    task_defs = [
        {
            "task_name": "ERP data sync complete",
            "auto_trigger_event": "erp_sync_complete",
            "days_relative": -3,
            "assigned_role": None,
            "depends_on": [],
        },
        {
            "task_name": "GL/TB reconciliation",
            "auto_trigger_event": "recon_complete",
            "days_relative": -2,
            "assigned_role": None,
            "depends_on": [1],
        },
        {
            "task_name": "Intercompany reconciliation",
            "auto_trigger_event": None,
            "days_relative": -2,
            "assigned_role": None,
            "depends_on": [2],
        },
        {
            "task_name": "Payroll upload and reconciliation",
            "auto_trigger_event": None,
            "days_relative": -1,
            "assigned_role": "data_entry_payroll",
            "depends_on": [],
        },
        {
            "task_name": "Prepaid and accrual adjustments",
            "auto_trigger_event": None,
            "days_relative": 0,
            "assigned_role": "manager",
            "depends_on": [2],
        },
        {
            "task_name": "Fixed asset depreciation run",
            "auto_trigger_event": None,
            "days_relative": 0,
            "assigned_role": None,
            "depends_on": [2],
        },
        {
            "task_name": "Multi-entity consolidation",
            "auto_trigger_event": "consolidation_complete",
            "days_relative": 1,
            "assigned_role": None,
            "depends_on": [3, 5, 6],
        },
        {
            "task_name": "FX rate confirmation",
            "auto_trigger_event": None,
            "days_relative": 0,
            "assigned_role": None,
            "depends_on": [],
        },
        {
            "task_name": "MIS review and approval",
            "auto_trigger_event": None,
            "days_relative": 2,
            "assigned_role": "finance_leader",
            "depends_on": [7],
        },
        {
            "task_name": "Anomaly detection review",
            "auto_trigger_event": "anomaly_detection_complete",
            "days_relative": 2,
            "assigned_role": None,
            "depends_on": [7],
        },
        {
            "task_name": "Board pack generation",
            "auto_trigger_event": "board_pack_generated",
            "days_relative": 3,
            "assigned_role": None,
            "depends_on": [9, 10],
        },
        {
            "task_name": "Finance Leader sign-off",
            "auto_trigger_event": None,
            "days_relative": 4,
            "assigned_role": "finance_leader",
            "depends_on": [11],
        },
    ]

    for tenant in tenants:
        tenant_id = tenant[0]
        existing_default = bind.execute(
            sa.text(
                "SELECT id FROM checklist_templates WHERE tenant_id = :tenant_id AND is_default = true LIMIT 1"
            ),
            {"tenant_id": tenant_id},
        ).scalar_one_or_none()
        if existing_default is not None:
            continue

        created_by = bind.execute(
            sa.text("SELECT id FROM iam_users WHERE tenant_id = :tenant_id ORDER BY created_at ASC LIMIT 1"),
            {"tenant_id": tenant_id},
        ).scalar_one_or_none() or tenant_id

        template_id = uuid.uuid4()
        bind.execute(
            sa.text(
                """
                INSERT INTO checklist_templates (
                    id, tenant_id, name, description, is_default,
                    created_by, created_at, updated_at
                ) VALUES (
                    :id, :tenant_id, :name, :description, true,
                    :created_by, now(), now()
                )
                """
            ),
            {
                "id": template_id,
                "tenant_id": tenant_id,
                "name": "Default Month-End Close Checklist",
                "description": "System-seeded 12-step close checklist",
                "created_by": created_by,
            },
        )

        task_ids: dict[int, uuid.UUID] = {index + 1: uuid.uuid4() for index in range(len(task_defs))}
        for index, task in enumerate(task_defs, start=1):
            depends_ids = [str(task_ids[item]) for item in task["depends_on"]]
            bind.execute(
                sa.text(
                    """
                    INSERT INTO checklist_template_tasks (
                        id, template_id, tenant_id, task_name, description,
                        assigned_role, days_relative_to_period_end,
                        depends_on_task_ids, auto_trigger_event, order_index,
                        created_at, updated_at
                    ) VALUES (
                        :id, :template_id, :tenant_id, :task_name, :description,
                        :assigned_role, :days_relative,
                        CAST(:depends_on_task_ids AS jsonb), :auto_trigger_event,
                        :order_index, now(), now()
                    )
                    """
                ),
                {
                    "id": task_ids[index],
                    "template_id": template_id,
                    "tenant_id": tenant_id,
                    "task_name": task["task_name"],
                    "description": None,
                    "assigned_role": task["assigned_role"],
                    "days_relative": task["days_relative"],
                    "depends_on_task_ids": json.dumps(depends_ids),
                    "auto_trigger_event": task["auto_trigger_event"],
                    "order_index": index,
                },
            )


def upgrade() -> None:
    if not _table_exists("checklist_templates"):
        op.create_table(
            "checklist_templates",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    if not _table_exists("checklist_template_tasks"):
        op.create_table(
            "checklist_template_tasks",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("checklist_templates.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("task_name", sa.String(length=300), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("assigned_role", sa.String(length=50), nullable=True),
            sa.Column("days_relative_to_period_end", sa.Integer(), nullable=False),
            sa.Column("depends_on_task_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("auto_trigger_event", sa.String(length=100), nullable=True),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "assigned_role IS NULL OR assigned_role IN ('finance_leader','manager','reviewer','data_entry_gl','data_entry_payroll')",
                name="ck_checklist_template_tasks_assigned_role",
            ),
            sa.CheckConstraint(
                "auto_trigger_event IS NULL OR auto_trigger_event IN ('erp_sync_complete','recon_complete','consolidation_complete','board_pack_generated','anomaly_detection_complete')",
                name="ck_checklist_template_tasks_event",
            ),
        )

    if not _table_exists("checklist_runs"):
        op.create_table(
            "checklist_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("checklist_templates.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("period", sa.String(length=7), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'open'")),
            sa.Column("progress_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
            sa.Column("target_close_date", sa.Date(), nullable=True),
            sa.Column("actual_close_date", sa.Date(), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("status IN ('open','in_progress','completed','locked')", name="ck_checklist_runs_status"),
            sa.UniqueConstraint("tenant_id", "period", name="uq_checklist_runs_tenant_period"),
        )

    if not _table_exists("checklist_run_tasks"):
        op.create_table(
            "checklist_run_tasks",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("checklist_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("template_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("checklist_template_tasks.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("task_name", sa.String(length=300), nullable=False),
            sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("iam_users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("assigned_role", sa.String(length=50), nullable=True),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'not_started'")),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("is_auto_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("auto_completed_by_event", sa.String(length=100), nullable=True),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint(
                "status IN ('not_started','in_progress','completed','blocked','skipped')",
                name="ck_checklist_run_tasks_status",
            ),
        )

    if not _index_exists("idx_checklist_runs_tenant_period"):
        op.execute("CREATE INDEX idx_checklist_runs_tenant_period ON checklist_runs (tenant_id, period)")
    if not _index_exists("idx_checklist_run_tasks_run_status"):
        op.execute("CREATE INDEX idx_checklist_run_tasks_run_status ON checklist_run_tasks (run_id, status)")
    if not _index_exists("idx_checklist_templates_tenant"):
        op.execute("CREATE INDEX idx_checklist_templates_tenant ON checklist_templates (tenant_id)")
    if not _index_exists("idx_checklist_template_tasks_template_order"):
        op.execute("CREATE INDEX idx_checklist_template_tasks_template_order ON checklist_template_tasks (template_id, order_index)")

    _seed_default_templates()

    for table_name in (
        "checklist_templates",
        "checklist_template_tasks",
        "checklist_runs",
        "checklist_run_tasks",
    ):
        if _table_exists(table_name):
            _enable_rls_with_policies(table_name)

    if _table_exists("checklist_runs"):
        op.execute(append_only_function_sql())
        op.execute(drop_trigger_sql("checklist_runs"))
        op.execute(create_trigger_sql("checklist_runs"))


def downgrade() -> None:
    if _table_exists("checklist_runs"):
        op.execute(drop_trigger_sql("checklist_runs"))

    if _index_exists("idx_checklist_run_tasks_run_status") and _table_exists("checklist_run_tasks"):
        op.drop_index("idx_checklist_run_tasks_run_status", table_name="checklist_run_tasks")
    if _index_exists("idx_checklist_runs_tenant_period") and _table_exists("checklist_runs"):
        op.drop_index("idx_checklist_runs_tenant_period", table_name="checklist_runs")
    if _index_exists("idx_checklist_template_tasks_template_order") and _table_exists("checklist_template_tasks"):
        op.drop_index("idx_checklist_template_tasks_template_order", table_name="checklist_template_tasks")
    if _index_exists("idx_checklist_templates_tenant") and _table_exists("checklist_templates"):
        op.drop_index("idx_checklist_templates_tenant", table_name="checklist_templates")

    if _table_exists("checklist_run_tasks"):
        op.drop_table("checklist_run_tasks")
    if _table_exists("checklist_runs"):
        op.drop_table("checklist_runs")
    if _table_exists("checklist_template_tasks"):
        op.drop_table("checklist_template_tasks")
    if _table_exists("checklist_templates"):
        op.drop_table("checklist_templates")

