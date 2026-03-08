"""Phase 1F.6 Anomaly & Pattern Detection Engine

Revision ID: 0018_phase1f6_anomaly_pattern
Revises: 0017_phase1f5_financial_risk
Create Date: 2026-03-09 00:30:00.000000
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

revision: str = "0018_phase1f6_anomaly_pattern"
down_revision: str | None = "0017_phase1f5_financial_risk"
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
        "anomaly_definitions",
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
        sa.Column("anomaly_code", sa.String(length=128), nullable=False),
        sa.Column("anomaly_name", sa.String(length=255), nullable=False),
        sa.Column("anomaly_domain", sa.String(length=64), nullable=False),
        sa.Column(
            "signal_selector_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "definition_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["anomaly_definitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "anomaly_code",
            "version_token",
            name="uq_anomaly_definitions_version_token",
        ),
        sa.CheckConstraint(
            "anomaly_domain IN ('profitability','cost_structure','liquidity','working_capital','leverage','payroll','reconciliation_linked')",
            name="ck_anomaly_definitions_domain",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_anomaly_definitions_status",
        ),
    )
    op.create_index(
        "idx_anomaly_definitions_lookup",
        "anomaly_definitions",
        ["tenant_id", "organisation_id", "anomaly_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_anomaly_definitions_one_active",
        "anomaly_definitions",
        ["tenant_id", "organisation_id", "anomaly_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "anomaly_pattern_rules",
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
        sa.Column("rule_code", sa.String(length=128), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column(
            "pattern_signature_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "classification_behavior_json",
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
            ["supersedes_id"], ["anomaly_pattern_rules.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_anomaly_pattern_rules_version_token",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_anomaly_pattern_rules_status",
        ),
    )
    op.create_index(
        "idx_anomaly_pattern_rules_lookup",
        "anomaly_pattern_rules",
        ["tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_anomaly_pattern_rules_one_active",
        "anomaly_pattern_rules",
        ["tenant_id", "organisation_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "anomaly_persistence_rules",
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
        sa.Column("rule_code", sa.String(length=128), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("rolling_window", sa.Integer(), nullable=False),
        sa.Column("recurrence_threshold", sa.Integer(), nullable=False),
        sa.Column(
            "escalation_logic_json",
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
            ["supersedes_id"], ["anomaly_persistence_rules.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_anomaly_persistence_rules_version_token",
        ),
        sa.CheckConstraint(
            "rolling_window IN (3,6,12,24)",
            name="ck_anomaly_persistence_rules_rolling_window",
        ),
        sa.CheckConstraint(
            "recurrence_threshold >= 1",
            name="ck_anomaly_persistence_rules_recurrence_threshold",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_anomaly_persistence_rules_status",
        ),
    )
    op.create_index(
        "idx_anomaly_persistence_rules_lookup",
        "anomaly_persistence_rules",
        ["tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_anomaly_persistence_rules_one_active",
        "anomaly_persistence_rules",
        ["tenant_id", "organisation_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "anomaly_correlation_rules",
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
        sa.Column("rule_code", sa.String(length=128), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("correlation_window", sa.Integer(), nullable=False),
        sa.Column("min_signal_count", sa.Integer(), nullable=False),
        sa.Column(
            "correlation_logic_json",
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
            ["supersedes_id"], ["anomaly_correlation_rules.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_anomaly_correlation_rules_version_token",
        ),
        sa.CheckConstraint(
            "correlation_window IN (3,6,12,24)",
            name="ck_anomaly_correlation_rules_window",
        ),
        sa.CheckConstraint(
            "min_signal_count >= 2",
            name="ck_anomaly_correlation_rules_min_signal_count",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_anomaly_correlation_rules_status",
        ),
    )
    op.create_index(
        "idx_anomaly_correlation_rules_lookup",
        "anomaly_correlation_rules",
        ["tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_anomaly_correlation_rules_one_active",
        "anomaly_correlation_rules",
        ["tenant_id", "organisation_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "anomaly_statistical_rules",
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
        sa.Column("rule_code", sa.String(length=128), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("rolling_window", sa.Integer(), nullable=False),
        sa.Column("baseline_type", sa.String(length=64), nullable=False),
        sa.Column("z_threshold", sa.Numeric(12, 6), nullable=False),
        sa.Column("regime_shift_threshold_pct", sa.Numeric(12, 6), nullable=False),
        sa.Column("seasonal_period", sa.Integer(), nullable=True),
        sa.Column(
            "seasonal_adjustment_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("benchmark_group_id", sa.String(length=128), nullable=True),
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
            ["supersedes_id"], ["anomaly_statistical_rules.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_anomaly_statistical_rules_version_token",
        ),
        sa.CheckConstraint(
            "rolling_window IN (3,6,12,24)",
            name="ck_anomaly_statistical_rules_window",
        ),
        sa.CheckConstraint(
            "baseline_type IN ('rolling_mean','rolling_std','rolling_median','rolling_pct_change')",
            name="ck_anomaly_statistical_rules_baseline_type",
        ),
        sa.CheckConstraint(
            "z_threshold > 0",
            name="ck_anomaly_statistical_rules_z_threshold",
        ),
        sa.CheckConstraint(
            "regime_shift_threshold_pct >= 0",
            name="ck_anomaly_statistical_rules_regime_shift_threshold",
        ),
        sa.CheckConstraint(
            "seasonal_period IS NULL OR seasonal_period = 12",
            name="ck_anomaly_statistical_rules_seasonal_period",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_anomaly_statistical_rules_status",
        ),
    )
    op.create_index(
        "idx_anomaly_statistical_rules_lookup",
        "anomaly_statistical_rules",
        ["tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_anomaly_statistical_rules_one_active",
        "anomaly_statistical_rules",
        ["tenant_id", "organisation_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "anomaly_runs",
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
        sa.Column("anomaly_definition_version_token", sa.String(length=64), nullable=False),
        sa.Column("pattern_rule_version_token", sa.String(length=64), nullable=False),
        sa.Column("persistence_rule_version_token", sa.String(length=64), nullable=False),
        sa.Column("correlation_rule_version_token", sa.String(length=64), nullable=False),
        sa.Column("statistical_rule_version_token", sa.String(length=64), nullable=False),
        sa.Column(
            "source_metric_run_ids_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "source_variance_run_ids_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "source_trend_run_ids_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "source_risk_run_ids_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "source_reconciliation_session_ids_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("run_token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column(
            "validation_summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "run_token", name="uq_anomaly_runs_tenant_token"),
        sa.CheckConstraint(
            "status IN ('created','running','completed','failed')",
            name="ck_anomaly_runs_status",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_metric_run_ids_json) = 'array' AND jsonb_array_length(source_metric_run_ids_json) > 0",
            name="ck_anomaly_runs_metric_sources_required",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_variance_run_ids_json) = 'array' AND jsonb_array_length(source_variance_run_ids_json) > 0",
            name="ck_anomaly_runs_variance_sources_required",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_trend_run_ids_json) = 'array'",
            name="ck_anomaly_runs_trend_sources_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_risk_run_ids_json) = 'array'",
            name="ck_anomaly_runs_risk_sources_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_reconciliation_session_ids_json) = 'array'",
            name="ck_anomaly_runs_reconciliation_sources_array",
        ),
    )
    op.create_index(
        "idx_anomaly_runs_lookup",
        "anomaly_runs",
        ["tenant_id", "organisation_id", "reporting_period", "created_at"],
    )
    op.create_index(
        "idx_anomaly_runs_token",
        "anomaly_runs",
        ["tenant_id", "run_token"],
        unique=True,
    )

    op.create_table(
        "anomaly_results",
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
        sa.Column("anomaly_code", sa.String(length=128), nullable=False),
        sa.Column("anomaly_name", sa.String(length=255), nullable=False),
        sa.Column("anomaly_domain", sa.String(length=64), nullable=False),
        sa.Column("anomaly_score", sa.Numeric(12, 6), nullable=False),
        sa.Column("z_score", sa.Numeric(12, 6), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("persistence_classification", sa.String(length=32), nullable=False),
        sa.Column(
            "correlation_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "materiality_elevated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "risk_elevated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("board_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("confidence_score", sa.Numeric(12, 6), nullable=False),
        sa.Column(
            "seasonal_adjustment_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("seasonal_normalized_value", sa.Numeric(20, 6), nullable=True),
        sa.Column("benchmark_group_id", sa.String(length=128), nullable=True),
        sa.Column("benchmark_baseline_value", sa.Numeric(20, 6), nullable=True),
        sa.Column("benchmark_deviation_score", sa.Numeric(20, 6), nullable=True),
        sa.Column(
            "source_summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["anomaly_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "line_no", name="uq_anomaly_results_line_no"),
        sa.CheckConstraint(
            "anomaly_domain IN ('profitability','cost_structure','liquidity','working_capital','leverage','payroll','reconciliation_linked')",
            name="ck_anomaly_results_domain",
        ),
        sa.CheckConstraint(
            "severity IN ('info','low','medium','high','critical')",
            name="ck_anomaly_results_severity",
        ),
        sa.CheckConstraint(
            "anomaly_score >= 0 AND anomaly_score <= 1",
            name="ck_anomaly_results_score",
        ),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_anomaly_results_confidence",
        ),
        sa.CheckConstraint(
            "persistence_classification IN ('first_detected','recurring','sustained','escalating','resolved','reopened')",
            name="ck_anomaly_results_persistence",
        ),
    )
    op.create_index(
        "idx_anomaly_results_run",
        "anomaly_results",
        ["tenant_id", "run_id", "line_no"],
    )
    op.create_index(
        "idx_anomaly_results_domain_severity",
        "anomaly_results",
        ["tenant_id", "run_id", "anomaly_domain", "severity"],
    )

    op.create_table(
        "anomaly_contributing_signals",
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
        sa.Column("anomaly_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("signal_ref", sa.Text(), nullable=False),
        sa.Column("contribution_weight", sa.Numeric(12, 6), nullable=False),
        sa.Column("contribution_score", sa.Numeric(12, 6), nullable=False),
        sa.Column(
            "signal_payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["anomaly_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["anomaly_result_id"], ["anomaly_results.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "signal_type IN ('metric_ref','variance_ref','trend_ref','risk_ref','reconciliation_ref','statistical_baseline_ref','parent_anomaly_ref')",
            name="ck_anomaly_contributing_signals_type",
        ),
        sa.CheckConstraint(
            "contribution_weight >= 0 AND contribution_weight <= 10",
            name="ck_anomaly_contributing_signals_weight",
        ),
        sa.CheckConstraint(
            "contribution_score >= 0 AND contribution_score <= 1",
            name="ck_anomaly_contributing_signals_score",
        ),
    )
    op.create_index(
        "idx_anomaly_contributing_signals_run",
        "anomaly_contributing_signals",
        ["tenant_id", "run_id", "anomaly_result_id", "id"],
    )

    op.create_table(
        "anomaly_rollforward_events",
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
        sa.Column("anomaly_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "event_payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["anomaly_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["anomaly_result_id"], ["anomaly_results.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "event_type IN ('rolled_forward','escalated','deescalated','resolved','reopened','recurrence_detected','correlation_strengthened','correlation_weakened')",
            name="ck_anomaly_rollforward_events_type",
        ),
    )
    op.create_index(
        "idx_anomaly_rollforward_events_run",
        "anomaly_rollforward_events",
        ["tenant_id", "run_id", "anomaly_result_id", "created_at"],
    )

    op.create_table(
        "anomaly_evidence_links",
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
        sa.Column("anomaly_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("evidence_label", sa.String(length=255), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["anomaly_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["anomaly_result_id"], ["anomaly_results.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "evidence_type IN ('metric_result','variance_result','trend_result','risk_result','reconciliation_session','normalized_source','definition_token','statistical_rule_token','persistence_rule_token','correlation_rule_token','run_input')",
            name="ck_anomaly_evidence_links_type",
        ),
    )
    op.create_index(
        "idx_anomaly_evidence_links_run",
        "anomaly_evidence_links",
        ["tenant_id", "run_id", "created_at"],
    )
    op.create_index(
        "idx_anomaly_evidence_links_result",
        "anomaly_evidence_links",
        ["tenant_id", "run_id", "anomaly_result_id"],
    )

    op.execute(
        _definition_supersession_function_sql(
            table_name="anomaly_definitions",
            code_column="anomaly_code",
            fn_name="anomaly_definitions_validate_supersession",
            missing_error="supersedes_id must reference existing anomaly definition version",
            cross_error="supersession across anomaly codes is not allowed",
        )
    )
    op.execute(
        _definition_supersession_trigger_sql(
            table_name="anomaly_definitions",
            fn_name="anomaly_definitions_validate_supersession",
            trigger_name="trg_anomaly_definitions_validate_supersession",
        )
    )
    op.execute(
        _definition_supersession_function_sql(
            table_name="anomaly_pattern_rules",
            code_column="rule_code",
            fn_name="anomaly_pattern_rules_validate_supersession",
            missing_error="supersedes_id must reference existing anomaly pattern rule version",
            cross_error="supersession across anomaly pattern rule codes is not allowed",
        )
    )
    op.execute(
        _definition_supersession_trigger_sql(
            table_name="anomaly_pattern_rules",
            fn_name="anomaly_pattern_rules_validate_supersession",
            trigger_name="trg_anomaly_pattern_rules_validate_supersession",
        )
    )
    op.execute(
        _definition_supersession_function_sql(
            table_name="anomaly_persistence_rules",
            code_column="rule_code",
            fn_name="anomaly_persistence_rules_validate_supersession",
            missing_error="supersedes_id must reference existing anomaly persistence rule version",
            cross_error="supersession across anomaly persistence rule codes is not allowed",
        )
    )
    op.execute(
        _definition_supersession_trigger_sql(
            table_name="anomaly_persistence_rules",
            fn_name="anomaly_persistence_rules_validate_supersession",
            trigger_name="trg_anomaly_persistence_rules_validate_supersession",
        )
    )
    op.execute(
        _definition_supersession_function_sql(
            table_name="anomaly_correlation_rules",
            code_column="rule_code",
            fn_name="anomaly_correlation_rules_validate_supersession",
            missing_error="supersedes_id must reference existing anomaly correlation rule version",
            cross_error="supersession across anomaly correlation rule codes is not allowed",
        )
    )
    op.execute(
        _definition_supersession_trigger_sql(
            table_name="anomaly_correlation_rules",
            fn_name="anomaly_correlation_rules_validate_supersession",
            trigger_name="trg_anomaly_correlation_rules_validate_supersession",
        )
    )
    op.execute(
        _definition_supersession_function_sql(
            table_name="anomaly_statistical_rules",
            code_column="rule_code",
            fn_name="anomaly_statistical_rules_validate_supersession",
            missing_error="supersedes_id must reference existing anomaly statistical rule version",
            cross_error="supersession across anomaly statistical rule codes is not allowed",
        )
    )
    op.execute(
        _definition_supersession_trigger_sql(
            table_name="anomaly_statistical_rules",
            fn_name="anomaly_statistical_rules_validate_supersession",
            trigger_name="trg_anomaly_statistical_rules_validate_supersession",
        )
    )

    anomaly_tables = [
        "anomaly_definitions",
        "anomaly_pattern_rules",
        "anomaly_persistence_rules",
        "anomaly_correlation_rules",
        "anomaly_statistical_rules",
        "anomaly_runs",
        "anomaly_results",
        "anomaly_contributing_signals",
        "anomaly_rollforward_events",
        "anomaly_evidence_links",
    ]
    for table_name in anomaly_tables:
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
    for table_name in anomaly_tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_anomaly_definitions_validate_supersession ON anomaly_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS anomaly_definitions_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_anomaly_pattern_rules_validate_supersession ON anomaly_pattern_rules"
    )
    op.execute("DROP FUNCTION IF EXISTS anomaly_pattern_rules_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_anomaly_persistence_rules_validate_supersession ON anomaly_persistence_rules"
    )
    op.execute("DROP FUNCTION IF EXISTS anomaly_persistence_rules_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_anomaly_correlation_rules_validate_supersession ON anomaly_correlation_rules"
    )
    op.execute("DROP FUNCTION IF EXISTS anomaly_correlation_rules_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_anomaly_statistical_rules_validate_supersession ON anomaly_statistical_rules"
    )
    op.execute("DROP FUNCTION IF EXISTS anomaly_statistical_rules_validate_supersession()")

    drop_order = [
        "anomaly_evidence_links",
        "anomaly_rollforward_events",
        "anomaly_contributing_signals",
        "anomaly_results",
        "anomaly_runs",
        "anomaly_statistical_rules",
        "anomaly_correlation_rules",
        "anomaly_persistence_rules",
        "anomaly_pattern_rules",
        "anomaly_definitions",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
