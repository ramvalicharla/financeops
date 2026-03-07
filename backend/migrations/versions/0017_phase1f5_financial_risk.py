"""Phase 1F.5 Financial Risk & Materiality Propagation Engine

Revision ID: 0017_phase1f5_financial_risk
Revises: 0016_phase1f4_ratio_variance
Create Date: 2026-03-08 23:40:00.000000
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

revision: str = "0017_phase1f5_financial_risk"
down_revision: str | None = "0016_phase1f4_ratio_variance"
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


def _dependency_cycle_function_sql() -> str:
    return """
    CREATE OR REPLACE FUNCTION risk_definition_dependencies_validate()
    RETURNS trigger AS $$
    DECLARE
        owner_tenant uuid;
        depends_tenant uuid;
    BEGIN
        IF NEW.dependency_type = 'risk_result' THEN
            IF NEW.depends_on_risk_definition_id IS NULL THEN
                RAISE EXCEPTION 'depends_on_risk_definition_id required for risk_result dependency';
            END IF;
            IF NEW.depends_on_risk_definition_id = NEW.risk_definition_id THEN
                RAISE EXCEPTION 'risk dependency self-cycle is not allowed';
            END IF;

            SELECT tenant_id INTO owner_tenant
            FROM risk_definitions
            WHERE id = NEW.risk_definition_id;
            IF owner_tenant IS NULL THEN
                RAISE EXCEPTION 'risk_definition_id must reference existing definition';
            END IF;
            IF owner_tenant <> NEW.tenant_id THEN
                RAISE EXCEPTION 'risk_definition tenant mismatch';
            END IF;

            SELECT tenant_id INTO depends_tenant
            FROM risk_definitions
            WHERE id = NEW.depends_on_risk_definition_id;
            IF depends_tenant IS NULL THEN
                RAISE EXCEPTION 'depends_on_risk_definition_id must reference existing definition';
            END IF;
            IF depends_tenant <> NEW.tenant_id THEN
                RAISE EXCEPTION 'dependency tenant mismatch';
            END IF;

            IF EXISTS (
                WITH RECURSIVE walk(id) AS (
                    SELECT NEW.depends_on_risk_definition_id
                    UNION ALL
                    SELECT d.depends_on_risk_definition_id
                    FROM risk_definition_dependencies d
                    INNER JOIN walk w ON d.risk_definition_id = w.id
                    WHERE d.tenant_id = NEW.tenant_id
                      AND d.dependency_type = 'risk_result'
                      AND d.depends_on_risk_definition_id IS NOT NULL
                )
                SELECT 1
                FROM walk
                WHERE id = NEW.risk_definition_id
            ) THEN
                RAISE EXCEPTION 'risk dependency cycle detected';
            END IF;
        ELSE
            IF NEW.depends_on_risk_definition_id IS NOT NULL THEN
                RAISE EXCEPTION 'depends_on_risk_definition_id only allowed for risk_result dependency';
            END IF;
        END IF;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """


def upgrade() -> None:
    op.create_table(
        "risk_definitions",
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
        sa.Column("risk_code", sa.String(length=128), nullable=False),
        sa.Column("risk_name", sa.String(length=255), nullable=False),
        sa.Column("risk_domain", sa.String(length=64), nullable=False),
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
        sa.ForeignKeyConstraint(["supersedes_id"], ["risk_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "risk_code",
            "version_token",
            name="uq_risk_definitions_version_token",
        ),
        sa.CheckConstraint(
            "risk_domain IN ('profitability','liquidity','leverage','working_capital','cost_structure','payroll','confidence','reconciliation_dependency','board_critical')",
            name="ck_risk_definitions_domain",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_risk_definitions_status",
        ),
    )
    op.create_index(
        "idx_risk_definitions_lookup",
        "risk_definitions",
        ["tenant_id", "organisation_id", "risk_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_risk_definitions_one_active",
        "risk_definitions",
        ["tenant_id", "organisation_id", "risk_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "risk_definition_dependencies",
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
        sa.Column("risk_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dependency_type", sa.String(length=64), nullable=False),
        sa.Column("depends_on_risk_definition_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("signal_reference_code", sa.String(length=128), nullable=True),
        sa.Column("propagation_factor", sa.Numeric(12, 6), nullable=False, server_default="1"),
        sa.Column(
            "amplification_rule_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "attenuation_rule_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("cap_limit", sa.Numeric(12, 6), nullable=False, server_default="1"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["risk_definition_id"], ["risk_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["depends_on_risk_definition_id"], ["risk_definitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "dependency_type IN ('metric_result','variance_result','trend_result','reconciliation_exception','risk_result')",
            name="ck_risk_definition_dependencies_type",
        ),
        sa.CheckConstraint(
            "propagation_factor >= 0 AND propagation_factor <= 10",
            name="ck_risk_definition_dependencies_propagation_factor",
        ),
        sa.CheckConstraint(
            "cap_limit >= 0 AND cap_limit <= 10",
            name="ck_risk_definition_dependencies_cap_limit",
        ),
    )
    op.create_index(
        "idx_risk_definition_dependencies_risk",
        "risk_definition_dependencies",
        ["tenant_id", "risk_definition_id", "dependency_type", "id"],
    )
    op.create_index(
        "idx_risk_definition_dependencies_depends_on",
        "risk_definition_dependencies",
        ["tenant_id", "depends_on_risk_definition_id"],
    )
    op.create_table(
        "risk_weight_configurations",
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
        sa.Column("weight_code", sa.String(length=128), nullable=False),
        sa.Column("risk_code", sa.String(length=128), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False, server_default="global"),
        sa.Column("scope_value", sa.String(length=128), nullable=True),
        sa.Column("weight_value", sa.Numeric(12, 6), nullable=False),
        sa.Column(
            "board_critical_override",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
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
            ["supersedes_id"], ["risk_weight_configurations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "weight_code",
            "version_token",
            name="uq_risk_weight_configurations_version_token",
        ),
        sa.CheckConstraint(
            "scope_type IN ('global','metric','entity','domain','board_critical')",
            name="ck_risk_weight_configurations_scope_type",
        ),
        sa.CheckConstraint(
            "weight_value >= 0 AND weight_value <= 10",
            name="ck_risk_weight_configurations_weight_value",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_risk_weight_configurations_status",
        ),
    )
    op.create_index(
        "idx_risk_weight_configurations_lookup",
        "risk_weight_configurations",
        ["tenant_id", "organisation_id", "weight_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_risk_weight_configurations_one_active",
        "risk_weight_configurations",
        ["tenant_id", "organisation_id", "weight_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "risk_materiality_rules",
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
            "threshold_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "severity_mapping_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "propagation_behavior_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "escalation_rule_json",
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
            ["supersedes_id"], ["risk_materiality_rules.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_risk_materiality_rules_version_token",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_risk_materiality_rules_status",
        ),
    )
    op.create_index(
        "idx_risk_materiality_rules_lookup",
        "risk_materiality_rules",
        ["tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_risk_materiality_rules_one_active",
        "risk_materiality_rules",
        ["tenant_id", "organisation_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "risk_runs",
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
        sa.Column("risk_definition_version_token", sa.String(length=64), nullable=False),
        sa.Column("propagation_version_token", sa.String(length=64), nullable=False),
        sa.Column("weight_version_token", sa.String(length=64), nullable=False),
        sa.Column("materiality_version_token", sa.String(length=64), nullable=False),
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
        sa.UniqueConstraint("tenant_id", "run_token", name="uq_risk_runs_tenant_token"),
        sa.CheckConstraint(
            "status IN ('created','running','completed','failed')",
            name="ck_risk_runs_status",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_metric_run_ids_json) = 'array' AND jsonb_array_length(source_metric_run_ids_json) > 0",
            name="ck_risk_runs_metric_sources_required",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_variance_run_ids_json) = 'array' AND jsonb_array_length(source_variance_run_ids_json) > 0",
            name="ck_risk_runs_variance_sources_required",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_trend_run_ids_json) = 'array'",
            name="ck_risk_runs_trend_sources_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_reconciliation_session_ids_json) = 'array'",
            name="ck_risk_runs_reconciliation_sources_array",
        ),
    )
    op.create_index(
        "idx_risk_runs_lookup",
        "risk_runs",
        ["tenant_id", "organisation_id", "reporting_period", "created_at"],
    )
    op.create_index(
        "idx_risk_runs_token",
        "risk_runs",
        ["tenant_id", "run_token"],
        unique=True,
    )
    op.create_table(
        "risk_results",
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
        sa.Column("risk_code", sa.String(length=128), nullable=False),
        sa.Column("risk_name", sa.String(length=255), nullable=False),
        sa.Column("risk_domain", sa.String(length=64), nullable=False),
        sa.Column("risk_score", sa.Numeric(12, 6), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("confidence_score", sa.Numeric(12, 6), nullable=False),
        sa.Column("materiality_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "board_attention_flag",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("persistence_state", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column(
            "unresolved_dependency_flag",
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
        sa.ForeignKeyConstraint(["run_id"], ["risk_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "line_no", name="uq_risk_results_line_no"),
        sa.CheckConstraint(
            "risk_domain IN ('profitability','liquidity','leverage','working_capital','cost_structure','payroll','confidence','reconciliation_dependency','board_critical')",
            name="ck_risk_results_domain",
        ),
        sa.CheckConstraint(
            "severity IN ('info','low','medium','high','critical')",
            name="ck_risk_results_severity",
        ),
        sa.CheckConstraint(
            "risk_score >= 0 AND risk_score <= 1",
            name="ck_risk_results_score",
        ),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_risk_results_confidence",
        ),
        sa.CheckConstraint(
            "persistence_state IN ('new','repeated','escalating','deescalating','resolved','reopened')",
            name="ck_risk_results_persistence",
        ),
    )
    op.create_index(
        "idx_risk_results_run",
        "risk_results",
        ["tenant_id", "run_id", "line_no"],
    )
    op.create_index(
        "idx_risk_results_domain_severity",
        "risk_results",
        ["tenant_id", "run_id", "risk_domain", "severity"],
    )

    op.create_table(
        "risk_contributing_signals",
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
        sa.Column("risk_result_id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(["run_id"], ["risk_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["risk_result_id"], ["risk_results.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "signal_type IN ('metric_result','variance_result','trend_result','reconciliation_exception','parent_risk_result')",
            name="ck_risk_contributing_signals_type",
        ),
        sa.CheckConstraint(
            "contribution_weight >= 0 AND contribution_weight <= 10",
            name="ck_risk_contributing_signals_weight",
        ),
        sa.CheckConstraint(
            "contribution_score >= 0 AND contribution_score <= 1",
            name="ck_risk_contributing_signals_score",
        ),
    )
    op.create_index(
        "idx_risk_contributing_signals_run",
        "risk_contributing_signals",
        ["tenant_id", "run_id", "risk_result_id", "id"],
    )

    op.create_table(
        "risk_rollforward_events",
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
        sa.Column("risk_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "event_payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["risk_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["risk_result_id"], ["risk_results.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "event_type IN ('rolled_forward','escalated','deescalated','resolved','reopened','confidence_degraded','confidence_restored')",
            name="ck_risk_rollforward_events_type",
        ),
    )
    op.create_index(
        "idx_risk_rollforward_events_run",
        "risk_rollforward_events",
        ["tenant_id", "run_id", "risk_result_id", "created_at"],
    )

    op.create_table(
        "risk_evidence_links",
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
        sa.Column("risk_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("evidence_label", sa.String(length=255), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["risk_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["risk_result_id"], ["risk_results.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "evidence_type IN ('metric_result','variance_result','trend_result','reconciliation_session','normalized_source','definition_token','run_input')",
            name="ck_risk_evidence_links_type",
        ),
    )
    op.create_index(
        "idx_risk_evidence_links_run",
        "risk_evidence_links",
        ["tenant_id", "run_id", "created_at"],
    )
    op.create_index(
        "idx_risk_evidence_links_result",
        "risk_evidence_links",
        ["tenant_id", "run_id", "risk_result_id"],
    )

    op.execute(
        _definition_supersession_function_sql(
            table_name="risk_definitions",
            code_column="risk_code",
            fn_name="risk_definitions_validate_supersession",
            missing_error="supersedes_id must reference existing risk definition version",
            cross_error="supersession across risk codes is not allowed",
        )
    )
    op.execute(
        _definition_supersession_trigger_sql(
            table_name="risk_definitions",
            fn_name="risk_definitions_validate_supersession",
            trigger_name="trg_risk_definitions_validate_supersession",
        )
    )

    op.execute(
        _definition_supersession_function_sql(
            table_name="risk_weight_configurations",
            code_column="weight_code",
            fn_name="risk_weight_configurations_validate_supersession",
            missing_error="supersedes_id must reference existing risk weight configuration version",
            cross_error="supersession across risk weight codes is not allowed",
        )
    )
    op.execute(
        _definition_supersession_trigger_sql(
            table_name="risk_weight_configurations",
            fn_name="risk_weight_configurations_validate_supersession",
            trigger_name="trg_risk_weight_configurations_validate_supersession",
        )
    )

    op.execute(
        _definition_supersession_function_sql(
            table_name="risk_materiality_rules",
            code_column="rule_code",
            fn_name="risk_materiality_rules_validate_supersession",
            missing_error="supersedes_id must reference existing risk materiality rule version",
            cross_error="supersession across risk materiality rule codes is not allowed",
        )
    )
    op.execute(
        _definition_supersession_trigger_sql(
            table_name="risk_materiality_rules",
            fn_name="risk_materiality_rules_validate_supersession",
            trigger_name="trg_risk_materiality_rules_validate_supersession",
        )
    )

    op.execute(_dependency_cycle_function_sql())
    op.execute(
        """
        CREATE TRIGGER trg_risk_definition_dependencies_validate
        BEFORE INSERT ON risk_definition_dependencies
        FOR EACH ROW
        EXECUTE FUNCTION risk_definition_dependencies_validate();
        """
    )

    risk_tables = [
        "risk_definitions",
        "risk_definition_dependencies",
        "risk_weight_configurations",
        "risk_materiality_rules",
        "risk_runs",
        "risk_results",
        "risk_contributing_signals",
        "risk_rollforward_events",
        "risk_evidence_links",
    ]
    for table_name in risk_tables:
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
    for table_name in risk_tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_risk_definition_dependencies_validate ON risk_definition_dependencies"
    )
    op.execute("DROP FUNCTION IF EXISTS risk_definition_dependencies_validate()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_risk_definitions_validate_supersession ON risk_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS risk_definitions_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_risk_weight_configurations_validate_supersession ON risk_weight_configurations"
    )
    op.execute("DROP FUNCTION IF EXISTS risk_weight_configurations_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_risk_materiality_rules_validate_supersession ON risk_materiality_rules"
    )
    op.execute("DROP FUNCTION IF EXISTS risk_materiality_rules_validate_supersession()")

    drop_order = [
        "risk_evidence_links",
        "risk_rollforward_events",
        "risk_contributing_signals",
        "risk_results",
        "risk_runs",
        "risk_materiality_rules",
        "risk_weight_configurations",
        "risk_definition_dependencies",
        "risk_definitions",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
