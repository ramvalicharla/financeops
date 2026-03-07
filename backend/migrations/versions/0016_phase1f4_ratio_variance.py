"""Phase 1F.4 Ratio & Variance Engine

Revision ID: 0016_phase1f4_ratio_variance
Revises: 0015_phase1f3_1_pg_gl_recon
Create Date: 2026-03-08 22:30:00.000000
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

revision: str = "0016_phase1f4_ratio_variance"
down_revision: str | None = "0015_phase1f3_1_pg_gl_recon"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _definition_supersession_function_sql(
    *,
    table_name: str,
    code_column: str,
    fn_name: str,
    missing_error: str,
    cross_error: str,
) -> str:
    return f"""
    CREATE OR REPLACE FUNCTION {fn_name}()
    RETURNS trigger AS $$
    DECLARE
        parent_code text;
        parent_tenant_id uuid;
        parent_org_id uuid;
    BEGIN
        IF NEW.supersedes_id IS NOT NULL THEN
            IF NEW.supersedes_id = NEW.id THEN
                RAISE EXCEPTION 'self-supersession is not allowed';
            END IF;

            SELECT {code_column}, tenant_id, organisation_id
            INTO parent_code, parent_tenant_id, parent_org_id
            FROM {table_name}
            WHERE id = NEW.supersedes_id;

            IF parent_code IS NULL THEN
                RAISE EXCEPTION '{missing_error}';
            END IF;

            IF parent_code <> NEW.{code_column}
               OR parent_tenant_id <> NEW.tenant_id
               OR parent_org_id <> NEW.organisation_id THEN
                RAISE EXCEPTION '{cross_error}';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM {table_name}
                WHERE supersedes_id = NEW.supersedes_id
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


def _definition_supersession_trigger_sql(
    *, table_name: str, fn_name: str, trigger_name: str
) -> str:
    return f"""
    CREATE TRIGGER {trigger_name}
    BEFORE INSERT ON {table_name}
    FOR EACH ROW
    EXECUTE FUNCTION {fn_name}();
    """


def upgrade() -> None:
    op.create_table(
        "metric_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("definition_code", sa.String(length=128), nullable=False),
        sa.Column("definition_name", sa.String(length=255), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("formula_type", sa.String(length=64), nullable=False),
        sa.Column(
            "formula_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("unit_type", sa.String(length=32), nullable=False, server_default="amount"),
        sa.Column(
            "directionality",
            sa.String(length=32),
            nullable=False,
            server_default="neutral",
        ),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["metric_definitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "definition_code",
            "version_token",
            name="uq_metric_definitions_version_token",
        ),
        sa.CheckConstraint(
            "formula_type IN ('sum','ratio','difference','direct','custom_expression')",
            name="ck_metric_definitions_formula_type",
        ),
        sa.CheckConstraint(
            "directionality IN ('higher_is_better','lower_is_better','neutral','contextual')",
            name="ck_metric_definitions_directionality",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_metric_definitions_status",
        ),
    )
    op.create_index(
        "idx_metric_definitions_lookup",
        "metric_definitions",
        ["tenant_id", "organisation_id", "definition_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_metric_definitions_one_active",
        "metric_definitions",
        ["tenant_id", "organisation_id", "definition_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "metric_definition_components",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("metric_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("component_code", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_key", sa.String(length=255), nullable=False),
        sa.Column("operator", sa.String(length=16), nullable=False, server_default="add"),
        sa.Column("weight", sa.Numeric(20, 6), nullable=False, server_default="1"),
        sa.Column("ordinal_position", sa.Integer(), nullable=False),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["metric_definition_id"],
            ["metric_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "metric_definition_id",
            "component_code",
            name="uq_metric_definition_components_code",
        ),
        sa.UniqueConstraint(
            "metric_definition_id",
            "ordinal_position",
            name="uq_metric_definition_components_ordinal",
        ),
        sa.CheckConstraint(
            "source_type IN ('mis_metric','payroll_metric','gl_account_prefix','metric_ref','constant')",
            name="ck_metric_definition_components_source_type",
        ),
        sa.CheckConstraint(
            "operator IN ('add','subtract','multiply','divide','none')",
            name="ck_metric_definition_components_operator",
        ),
    )
    op.create_index(
        "idx_metric_definition_components_metric",
        "metric_definition_components",
        ["tenant_id", "metric_definition_id", "ordinal_position"],
    )

    op.create_table(
        "variance_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("definition_code", sa.String(length=128), nullable=False),
        sa.Column("definition_name", sa.String(length=255), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("comparison_type", sa.String(length=64), nullable=False),
        sa.Column(
            "configuration_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["variance_definitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "definition_code",
            "version_token",
            name="uq_variance_definitions_version_token",
        ),
        sa.CheckConstraint(
            "comparison_type IN ('mom_abs_pct','yoy_abs_pct','actual_vs_budget_abs_pct','actual_vs_forecast_abs_pct','basis_points_change','days_change')",
            name="ck_variance_definitions_comparison_type",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_variance_definitions_status",
        ),
    )
    op.create_index(
        "idx_variance_definitions_lookup",
        "variance_definitions",
        ["tenant_id", "organisation_id", "definition_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_variance_definitions_one_active",
        "variance_definitions",
        ["tenant_id", "organisation_id", "definition_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "trend_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("definition_code", sa.String(length=128), nullable=False),
        sa.Column("definition_name", sa.String(length=255), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("trend_type", sa.String(length=64), nullable=False),
        sa.Column("window_size", sa.Integer(), nullable=False),
        sa.Column(
            "configuration_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["trend_definitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "definition_code",
            "version_token",
            name="uq_trend_definitions_version_token",
        ),
        sa.CheckConstraint(
            "trend_type IN ('rolling_average','trailing_total','directional')",
            name="ck_trend_definitions_trend_type",
        ),
        sa.CheckConstraint(
            "window_size IN (3,6,12)",
            name="ck_trend_definitions_window_size",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_trend_definitions_status",
        ),
    )
    op.create_index(
        "idx_trend_definitions_lookup",
        "trend_definitions",
        ["tenant_id", "organisation_id", "definition_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_trend_definitions_one_active",
        "trend_definitions",
        ["tenant_id", "organisation_id", "definition_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "materiality_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("definition_code", sa.String(length=128), nullable=False),
        sa.Column("definition_name", sa.String(length=255), nullable=False),
        sa.Column(
            "rule_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["materiality_rules.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "definition_code",
            "version_token",
            name="uq_materiality_rules_version_token",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_materiality_rules_status",
        ),
    )
    op.create_index(
        "idx_materiality_rules_lookup",
        "materiality_rules",
        ["tenant_id", "organisation_id", "definition_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_materiality_rules_one_active",
        "materiality_rules",
        ["tenant_id", "organisation_id", "definition_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "metric_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporting_period", sa.Date(), nullable=False),
        sa.Column(
            "scope_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("mis_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payroll_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("gl_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reconciliation_session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payroll_gl_reconciliation_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("metric_definition_version_token", sa.String(length=64), nullable=False),
        sa.Column("variance_definition_version_token", sa.String(length=64), nullable=False),
        sa.Column("trend_definition_version_token", sa.String(length=64), nullable=False),
        sa.Column("materiality_rule_version_token", sa.String(length=64), nullable=False),
        sa.Column("input_signature_hash", sa.String(length=64), nullable=False),
        sa.Column("run_token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["mis_snapshot_id"], ["mis_data_snapshots.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["payroll_run_id"], ["normalization_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["gl_run_id"], ["normalization_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["reconciliation_session_id"],
            ["reconciliation_sessions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payroll_gl_reconciliation_run_id"],
            ["payroll_gl_reconciliation_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "run_token", name="uq_metric_runs_tenant_token"),
        sa.CheckConstraint(
            "status IN ('created','running','completed','failed')",
            name="ck_metric_runs_status",
        ),
        sa.CheckConstraint(
            "(mis_snapshot_id IS NOT NULL OR payroll_run_id IS NOT NULL OR gl_run_id IS NOT NULL OR reconciliation_session_id IS NOT NULL OR payroll_gl_reconciliation_run_id IS NOT NULL)",
            name="ck_metric_runs_requires_input_reference",
        ),
    )
    op.create_index(
        "idx_metric_runs_lookup",
        "metric_runs",
        ["tenant_id", "organisation_id", "reporting_period", "created_at"],
    )
    op.create_index(
        "idx_metric_runs_token",
        "metric_runs",
        ["tenant_id", "run_token"],
        unique=True,
    )

    op.create_table(
        "metric_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("unit_type", sa.String(length=32), nullable=False),
        sa.Column(
            "dimension_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("metric_value", sa.Numeric(20, 6), nullable=False),
        sa.Column(
            "favorable_status",
            sa.String(length=16),
            nullable=False,
            server_default="neutral",
        ),
        sa.Column(
            "materiality_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "source_summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["metric_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "line_no", name="uq_metric_results_line_no"),
        sa.CheckConstraint(
            "unit_type IN ('amount','percentage','ratio','days','count','bps')",
            name="ck_metric_results_unit_type",
        ),
        sa.CheckConstraint(
            "favorable_status IN ('favorable','unfavorable','neutral')",
            name="ck_metric_results_favorable_status",
        ),
    )
    op.create_index(
        "idx_metric_results_run",
        "metric_results",
        ["tenant_id", "run_id", "line_no"],
    )
    op.create_index(
        "idx_metric_results_metric",
        "metric_results",
        ["tenant_id", "run_id", "metric_code"],
    )

    op.create_table(
        "variance_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("comparison_type", sa.String(length=64), nullable=False),
        sa.Column("base_period", sa.Date(), nullable=True),
        sa.Column("current_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("baseline_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("variance_abs", sa.Numeric(20, 6), nullable=False),
        sa.Column("variance_pct", sa.Numeric(20, 6), nullable=False),
        sa.Column("variance_bps", sa.Numeric(20, 6), nullable=False),
        sa.Column("days_change", sa.Numeric(20, 6), nullable=False),
        sa.Column(
            "favorable_status",
            sa.String(length=16),
            nullable=False,
            server_default="neutral",
        ),
        sa.Column(
            "materiality_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("explanation_hint", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["metric_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "line_no", name="uq_variance_results_line_no"),
        sa.CheckConstraint(
            "comparison_type IN ('mom_abs_pct','yoy_abs_pct','actual_vs_budget_abs_pct','actual_vs_forecast_abs_pct','basis_points_change','days_change')",
            name="ck_variance_results_comparison_type",
        ),
        sa.CheckConstraint(
            "favorable_status IN ('favorable','unfavorable','neutral')",
            name="ck_variance_results_favorable_status",
        ),
    )
    op.create_index(
        "idx_variance_results_run",
        "variance_results",
        ["tenant_id", "run_id", "line_no"],
    )
    op.create_index(
        "idx_variance_results_metric_comparison",
        "variance_results",
        ["tenant_id", "run_id", "metric_code", "comparison_type"],
    )

    op.create_table(
        "trend_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("trend_type", sa.String(length=64), nullable=False),
        sa.Column("window_size", sa.Integer(), nullable=False),
        sa.Column("trend_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("trend_direction", sa.String(length=16), nullable=False),
        sa.Column(
            "source_summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["metric_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "line_no", name="uq_trend_results_line_no"),
        sa.CheckConstraint(
            "trend_type IN ('rolling_average','trailing_total','directional')",
            name="ck_trend_results_trend_type",
        ),
        sa.CheckConstraint("window_size IN (3,6,12)", name="ck_trend_results_window_size"),
        sa.CheckConstraint(
            "trend_direction IN ('up','down','flat','na')",
            name="ck_trend_results_direction",
        ),
    )
    op.create_index(
        "idx_trend_results_run",
        "trend_results",
        ["tenant_id", "run_id", "line_no"],
    )
    op.create_index(
        "idx_trend_results_metric",
        "trend_results",
        ["tenant_id", "run_id", "metric_code"],
    )

    op.create_table(
        "metric_evidence_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result_type", sa.String(length=16), nullable=False),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("evidence_label", sa.String(length=255), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["metric_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "result_type IN ('metric','variance','trend')",
            name="ck_metric_evidence_links_result_type",
        ),
        sa.CheckConstraint(
            "evidence_type IN ('payroll_normalized_line','gl_normalized_line','mis_normalized_line','reconciliation_line','definition','run_input')",
            name="ck_metric_evidence_links_evidence_type",
        ),
    )
    op.create_index(
        "idx_metric_evidence_links_run",
        "metric_evidence_links",
        ["tenant_id", "run_id", "created_at"],
    )
    op.create_index(
        "idx_metric_evidence_links_result",
        "metric_evidence_links",
        ["tenant_id", "run_id", "result_type", "result_id"],
    )

    op.execute(
        _definition_supersession_function_sql(
            table_name="metric_definitions",
            code_column="definition_code",
            fn_name="ratio_metric_definitions_validate_supersession",
            missing_error="supersedes_id must reference existing metric definition version",
            cross_error="supersession across metric definition codes is not allowed",
        )
    )
    op.execute(
        _definition_supersession_trigger_sql(
            table_name="metric_definitions",
            fn_name="ratio_metric_definitions_validate_supersession",
            trigger_name="trg_ratio_metric_definitions_validate_supersession",
        )
    )
    op.execute(
        _definition_supersession_function_sql(
            table_name="variance_definitions",
            code_column="definition_code",
            fn_name="ratio_variance_definitions_validate_supersession",
            missing_error="supersedes_id must reference existing variance definition version",
            cross_error="supersession across variance definition codes is not allowed",
        )
    )
    op.execute(
        _definition_supersession_trigger_sql(
            table_name="variance_definitions",
            fn_name="ratio_variance_definitions_validate_supersession",
            trigger_name="trg_ratio_variance_definitions_validate_supersession",
        )
    )
    op.execute(
        _definition_supersession_function_sql(
            table_name="trend_definitions",
            code_column="definition_code",
            fn_name="ratio_trend_definitions_validate_supersession",
            missing_error="supersedes_id must reference existing trend definition version",
            cross_error="supersession across trend definition codes is not allowed",
        )
    )
    op.execute(
        _definition_supersession_trigger_sql(
            table_name="trend_definitions",
            fn_name="ratio_trend_definitions_validate_supersession",
            trigger_name="trg_ratio_trend_definitions_validate_supersession",
        )
    )
    op.execute(
        _definition_supersession_function_sql(
            table_name="materiality_rules",
            code_column="definition_code",
            fn_name="ratio_materiality_rules_validate_supersession",
            missing_error="supersedes_id must reference existing materiality rule version",
            cross_error="supersession across materiality rule definition codes is not allowed",
        )
    )
    op.execute(
        _definition_supersession_trigger_sql(
            table_name="materiality_rules",
            fn_name="ratio_materiality_rules_validate_supersession",
            trigger_name="trg_ratio_materiality_rules_validate_supersession",
        )
    )

    ratio_tables = [
        "metric_definitions",
        "metric_definition_components",
        "variance_definitions",
        "trend_definitions",
        "materiality_rules",
        "metric_runs",
        "metric_results",
        "variance_results",
        "trend_results",
        "metric_evidence_links",
    ]
    for table_name in ratio_tables:
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
    for table_name in ratio_tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_ratio_metric_definitions_validate_supersession ON metric_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS ratio_metric_definitions_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_ratio_variance_definitions_validate_supersession ON variance_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS ratio_variance_definitions_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_ratio_trend_definitions_validate_supersession ON trend_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS ratio_trend_definitions_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_ratio_materiality_rules_validate_supersession ON materiality_rules"
    )
    op.execute("DROP FUNCTION IF EXISTS ratio_materiality_rules_validate_supersession()")

    drop_order = [
        "metric_evidence_links",
        "trend_results",
        "variance_results",
        "metric_results",
        "metric_runs",
        "materiality_rules",
        "trend_definitions",
        "variance_definitions",
        "metric_definition_components",
        "metric_definitions",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
