"""Phase 3 Observability & Governance Layer

Revision ID: 0025_phase3_observability_engine
Revises: 0024_phase2_7_equity_engine
Create Date: 2026-03-09 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0025_phase3_observability_engine"
down_revision: str | None = "0024_phase2_7_equity_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _supersession_function_sql(*, table_name: str, fn_name: str) -> str:
    return f"""
    CREATE OR REPLACE FUNCTION {fn_name}()
    RETURNS trigger AS $$
    BEGIN
        IF NEW.supersedes_id IS NOT NULL THEN
            IF NEW.supersedes_id = NEW.id THEN
                RAISE EXCEPTION 'self-supersession is not allowed';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM {table_name} parent
                WHERE parent.id = NEW.supersedes_id
                  AND parent.tenant_id = NEW.tenant_id
                  AND parent.comparison_type = NEW.comparison_type
            ) THEN
                RAISE EXCEPTION 'supersession across different comparison_type is not allowed';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM {table_name} child
                WHERE child.supersedes_id = NEW.supersedes_id
            ) THEN
                RAISE EXCEPTION 'supersession branching is not allowed';
            END IF;

            IF EXISTS (
                WITH RECURSIVE chain(id, supersedes_id) AS (
                    SELECT id, supersedes_id
                    FROM {table_name}
                    WHERE id = NEW.supersedes_id
                    UNION ALL
                    SELECT t.id, t.supersedes_id
                    FROM {table_name} t
                    INNER JOIN chain c ON t.id = c.supersedes_id
                    WHERE c.supersedes_id IS NOT NULL
                )
                SELECT 1 FROM chain WHERE id = NEW.id
            ) THEN
                RAISE EXCEPTION 'supersession cycle detected';
            END IF;
        END IF;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """


def _supersession_trigger_sql(*, table_name: str, fn_name: str, trigger_name: str) -> str:
    return f"""
    CREATE TRIGGER {trigger_name}
    BEFORE INSERT ON {table_name}
    FOR EACH ROW
    EXECUTE FUNCTION {fn_name}();
    """


def upgrade() -> None:
    op.create_table(
        "observability_run_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("module_code", sa.String(length=64), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_token", sa.String(length=64), nullable=False),
        sa.Column("version_token_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("upstream_dependencies_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="discovered"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "module_code", "run_id", "run_token", name="uq_observability_run_registry_run"),
        sa.CheckConstraint("execution_time_ms >= 0", name="ck_observability_run_registry_execution_time"),
        sa.CheckConstraint("status IN ('discovered','validated','drift_detected','missing_dependency')", name="ck_observability_run_registry_status"),
    )
    op.create_index("idx_observability_run_registry_lookup", "observability_run_registry", ["tenant_id", "module_code", "created_at"])
    op.create_index("idx_observability_run_registry_run", "observability_run_registry", ["tenant_id", "run_id", "created_at"])

    op.create_table(
        "run_token_diff_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("comparison_type", sa.String(length=64), nullable=False),
        sa.Column("allowed_modules_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["run_token_diff_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "comparison_type", "version_token", name="uq_run_token_diff_definitions_version_token"),
        sa.CheckConstraint("comparison_type IN ('intra_module','cross_module','cross_period')", name="ck_run_token_diff_definitions_type"),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_run_token_diff_definitions_status"),
    )
    op.create_index("idx_run_token_diff_definitions_lookup", "run_token_diff_definitions", ["tenant_id", "comparison_type", "effective_from", "created_at"])
    op.create_index(
        "uq_run_token_diff_definitions_one_active",
        "run_token_diff_definitions",
        ["tenant_id", "comparison_type"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "run_token_diff_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("base_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("compare_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("diff_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("drift_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "base_run_id", "compare_run_id", "chain_hash", name="uq_run_token_diff_results_pair_chain"),
    )
    op.create_index("idx_run_token_diff_results_lookup", "run_token_diff_results", ["tenant_id", "base_run_id", "compare_run_id", "created_at"])

    op.create_table(
        "lineage_graph_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("root_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("graph_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("deterministic_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "root_run_id", "deterministic_hash", name="uq_lineage_graph_snapshots_hash"),
    )
    op.create_index("idx_lineage_graph_snapshots_lookup", "lineage_graph_snapshots", ["tenant_id", "root_run_id", "created_at"])

    op.create_table(
        "governance_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("module_code", sa.String(length=64), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("event_type IN ('rule_application_trace','supersession_trace','version_resolution_trace','diff_computed','replay_validated','graph_snapshot_created')", name="ck_governance_events_type"),
    )
    op.create_index("idx_governance_events_lookup", "governance_events", ["tenant_id", "module_code", "run_id", "created_at"])

    op.create_table(
        "run_performance_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("module_code", sa.String(length=64), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_time_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dependency_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("query_count >= 0", name="ck_run_performance_metrics_query_count"),
        sa.CheckConstraint("execution_time_ms >= 0", name="ck_run_performance_metrics_execution_time"),
        sa.CheckConstraint("dependency_depth >= 0", name="ck_run_performance_metrics_dependency_depth"),
    )
    op.create_index("idx_run_performance_metrics_lookup", "run_performance_metrics", ["tenant_id", "module_code", "run_id", "created_at"])

    op.create_table(
        "observability_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("input_ref_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("operation_token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "operation_token", name="uq_observability_runs_operation_token"),
        sa.CheckConstraint("operation_type IN ('diff','replay_validate','graph_snapshot','dependency_explore','registry_sync')", name="ck_observability_runs_type"),
        sa.CheckConstraint("status IN ('created','completed','failed')", name="ck_observability_runs_status"),
    )
    op.create_index("idx_observability_runs_lookup", "observability_runs", ["tenant_id", "operation_type", "created_at"])

    op.create_table(
        "observability_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("observability_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["observability_run_id"], ["observability_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_observability_results_lookup", "observability_results", ["tenant_id", "observability_run_id", "created_at"])

    op.create_table(
        "observability_evidence_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("observability_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("evidence_label", sa.String(length=255), nullable=False),
        sa.Column("evidence_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["observability_run_id"], ["observability_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["result_id"], ["observability_results.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("evidence_type IN ('upstream_run','diff_result','graph_snapshot','governance_event','performance_metric')", name="ck_observability_evidence_links_type"),
    )
    op.create_index("idx_observability_evidence_links_lookup", "observability_evidence_links", ["tenant_id", "observability_run_id", "created_at"])

    op.execute(
        _supersession_function_sql(
            table_name="run_token_diff_definitions",
            fn_name="obs_diff_defs_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="run_token_diff_definitions",
            fn_name="obs_diff_defs_validate_supersession",
            trigger_name="trg_obs_diff_defs_validate_supersession",
        )
    )

    tables = [
        "observability_run_registry",
        "run_token_diff_definitions",
        "run_token_diff_results",
        "lineage_graph_snapshots",
        "governance_events",
        "run_performance_metrics",
        "observability_runs",
        "observability_results",
        "observability_evidence_links",
    ]
    for table_name in tables:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table_name}_tenant_isolation
            ON {table_name}
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            """
        )

    op.execute(append_only_function_sql())
    for table_name in tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_obs_diff_defs_validate_supersession ON run_token_diff_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS obs_diff_defs_validate_supersession()")

    drop_order = [
        "observability_evidence_links",
        "observability_results",
        "observability_runs",
        "run_performance_metrics",
        "governance_events",
        "lineage_graph_snapshots",
        "run_token_diff_results",
        "run_token_diff_definitions",
        "observability_run_registry",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
