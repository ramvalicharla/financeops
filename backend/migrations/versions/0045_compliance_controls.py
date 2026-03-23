"""Compliance controls registry and immutable compliance event ledger.

Revision ID: 0045_compliance_controls
Revises: 0044_scenario_modelling
Create Date: 2026-03-23 20:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.modules.compliance.iso27001_controls import ISO27001_CONTROLS
from financeops.modules.compliance.soc2_controls import SOC2_CONTROLS

revision: str = "0045_compliance_controls"
down_revision: str | None = "0044_scenario_modelling"
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


def _seed_controls() -> None:
    bind = op.get_bind()
    tenants = bind.execute(sa.text("SELECT id FROM iam_tenants")).fetchall()
    definitions = [("SOC2", SOC2_CONTROLS), ("ISO27001", ISO27001_CONTROLS)]
    for tenant_row in tenants:
        tenant_id = tenant_row[0]
        for framework, controls in definitions:
            for control in controls:
                exists = bind.execute(
                    sa.text(
                        """
                        SELECT 1
                        FROM compliance_controls
                        WHERE tenant_id = :tenant_id
                          AND framework = :framework
                          AND control_id = :control_id
                        LIMIT 1
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "framework": framework,
                        "control_id": control["control_id"],
                    },
                ).scalar_one_or_none()
                if exists:
                    continue
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO compliance_controls (
                            id, tenant_id, framework, control_id, control_name,
                            control_description, category, status, rag_status,
                            auto_evaluable, created_at, updated_at
                        ) VALUES (
                            gen_random_uuid(), :tenant_id, :framework, :control_id, :control_name,
                            :control_description, :category, 'not_evaluated', 'grey',
                            :auto_evaluable, now(), now()
                        )
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "framework": framework,
                        "control_id": str(control["control_id"]),
                        "control_name": str(control["control_name"]),
                        "control_description": str(control["control_description"]),
                        "category": str(control["category"]),
                        "auto_evaluable": bool(control["auto_evaluable"]),
                    },
                )


def upgrade() -> None:
    if not _table_exists("compliance_controls"):
        op.create_table(
            "compliance_controls",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("framework", sa.String(length=20), nullable=False),
            sa.Column("control_id", sa.String(length=30), nullable=False),
            sa.Column("control_name", sa.String(length=300), nullable=False),
            sa.Column("control_description", sa.Text(), nullable=True),
            sa.Column("category", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'not_evaluated'")),
            sa.Column("rag_status", sa.String(length=10), nullable=False, server_default=sa.text("'grey'")),
            sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_evaluation_due", sa.DateTime(timezone=True), nullable=True),
            sa.Column("evidence_summary", sa.Text(), nullable=True),
            sa.Column("auto_evaluable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("framework IN ('SOC2','ISO27001','GDPR')", name="ck_compliance_controls_framework"),
            sa.CheckConstraint("status IN ('not_evaluated','pass','fail','partial','not_applicable')", name="ck_compliance_controls_status"),
            sa.CheckConstraint("rag_status IN ('green','amber','red','grey')", name="ck_compliance_controls_rag_status"),
            sa.UniqueConstraint("tenant_id", "framework", "control_id", name="uq_compliance_controls_tenant_framework_control"),
        )

    if not _table_exists("compliance_events"):
        op.create_table(
            "compliance_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("framework", sa.String(length=20), nullable=False),
            sa.Column("control_id", sa.String(length=30), nullable=False),
            sa.Column("event_type", sa.String(length=50), nullable=False),
            sa.Column("previous_status", sa.String(length=20), nullable=True),
            sa.Column("new_status", sa.String(length=20), nullable=False),
            sa.Column("evidence_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("triggered_by", sa.String(length=100), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("framework IN ('SOC2','ISO27001','GDPR')", name="ck_compliance_events_framework"),
            sa.CheckConstraint(
                "event_type IN ('auto_pass','auto_fail','manual_pass','manual_fail','evidence_added','status_changed','evaluation_run')",
                name="ck_compliance_events_event_type",
            ),
            sa.CheckConstraint("new_status IN ('not_evaluated','pass','fail','partial','not_applicable')", name="ck_compliance_events_new_status"),
        )

    if not _index_exists("idx_compliance_controls_tenant_framework_category"):
        op.execute(
            "CREATE INDEX idx_compliance_controls_tenant_framework_category "
            "ON compliance_controls (tenant_id, framework, category)"
        )
    if not _index_exists("idx_compliance_events_tenant_framework_control_created"):
        op.execute(
            "CREATE INDEX idx_compliance_events_tenant_framework_control_created "
            "ON compliance_events (tenant_id, framework, control_id, created_at DESC)"
        )

    _seed_controls()

    for table_name in ("compliance_controls", "compliance_events"):
        if _table_exists(table_name):
            _enable_rls_with_policies(table_name)
    if _table_exists("compliance_events"):
        op.execute(append_only_function_sql())
        op.execute(drop_trigger_sql("compliance_events"))
        op.execute(create_trigger_sql("compliance_events"))


def downgrade() -> None:
    if _table_exists("compliance_events"):
        op.execute(drop_trigger_sql("compliance_events"))
    if _index_exists("idx_compliance_events_tenant_framework_control_created") and _table_exists("compliance_events"):
        op.drop_index("idx_compliance_events_tenant_framework_control_created", table_name="compliance_events")
    if _index_exists("idx_compliance_controls_tenant_framework_category") and _table_exists("compliance_controls"):
        op.drop_index("idx_compliance_controls_tenant_framework_category", table_name="compliance_controls")
    if _table_exists("compliance_events"):
        op.drop_table("compliance_events")
    if _table_exists("compliance_controls"):
        op.drop_table("compliance_controls")

