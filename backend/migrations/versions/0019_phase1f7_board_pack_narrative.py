"""Phase 1F.7 Board Pack & Narrative Engine

Revision ID: 0019_phase1f7_board_pack
Revises: 0018_phase1f6_anomaly_pattern
Create Date: 2026-03-09 14:00:00.000000
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

revision: str = "0019_phase1f7_board_pack"
down_revision: str | None = "0018_phase1f6_anomaly_pattern"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _supersession_function_sql(*, table_name: str, code_column: str, fn_name: str) -> str:
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
                RAISE EXCEPTION 'supersedes_id must reference existing version';
            END IF;

            IF parent_code <> NEW.{code_column}
               OR parent_tenant_id <> NEW.tenant_id
               OR parent_org_id <> NEW.organisation_id THEN
                RAISE EXCEPTION 'supersession across different codes is not allowed';
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


def _supersession_trigger_sql(*, table_name: str, fn_name: str, trigger_name: str) -> str:
    return f"""
    CREATE TRIGGER {trigger_name}
    BEFORE INSERT ON {table_name}
    FOR EACH ROW
    EXECUTE FUNCTION {fn_name}();
    """


def upgrade() -> None:
    op.create_table(
        "board_pack_definitions",
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
        sa.Column("board_pack_code", sa.String(length=128), nullable=False),
        sa.Column("board_pack_name", sa.String(length=255), nullable=False),
        sa.Column("audience_scope", sa.String(length=64), nullable=False, server_default="board"),
        sa.Column(
            "section_order_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "inclusion_config_json",
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
            ["supersedes_id"], ["board_pack_definitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "board_pack_code",
            "version_token",
            name="uq_board_pack_definitions_version_token",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_board_pack_definitions_status",
        ),
    )
    op.create_index(
        "idx_board_pack_definitions_lookup",
        "board_pack_definitions",
        ["tenant_id", "organisation_id", "board_pack_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_board_pack_definitions_one_active",
        "board_pack_definitions",
        ["tenant_id", "organisation_id", "board_pack_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "board_pack_section_definitions",
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
        sa.Column("section_code", sa.String(length=128), nullable=False),
        sa.Column("section_name", sa.String(length=255), nullable=False),
        sa.Column("section_type", sa.String(length=64), nullable=False),
        sa.Column(
            "render_logic_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("section_order_default", sa.Integer(), nullable=False),
        sa.Column("narrative_template_ref", sa.String(length=128), nullable=True),
        sa.Column(
            "risk_inclusion_rule_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "anomaly_inclusion_rule_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "metric_inclusion_rule_json",
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
            ["supersedes_id"], ["board_pack_section_definitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "section_code",
            "version_token",
            name="uq_board_pack_section_definitions_version_token",
        ),
        sa.CheckConstraint(
            "section_type IN ('executive_summary','financial_performance','profitability_summary','liquidity_summary','payroll_summary','working_capital_summary','key_risks','anomaly_watchlist','reconciliations_and_controls','outlook_placeholder','board_attention_items')",
            name="ck_board_pack_section_definitions_type",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_board_pack_section_definitions_status",
        ),
    )
    op.create_index(
        "idx_board_pack_section_definitions_lookup",
        "board_pack_section_definitions",
        ["tenant_id", "organisation_id", "section_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_board_pack_section_definitions_one_active",
        "board_pack_section_definitions",
        ["tenant_id", "organisation_id", "section_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "narrative_templates",
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
        sa.Column("template_code", sa.String(length=128), nullable=False),
        sa.Column("template_name", sa.String(length=255), nullable=False),
        sa.Column("template_type", sa.String(length=64), nullable=False),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column(
            "template_body_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "placeholder_schema_json",
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
            ["supersedes_id"], ["narrative_templates.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "template_code",
            "version_token",
            name="uq_narrative_templates_version_token",
        ),
        sa.CheckConstraint(
            "template_type IN ('executive_summary_template','metric_commentary_template','variance_commentary_template','risk_commentary_template','anomaly_commentary_template','board_attention_template','period_close_summary_template')",
            name="ck_narrative_templates_type",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_narrative_templates_status",
        ),
    )
    op.create_index(
        "idx_narrative_templates_lookup",
        "narrative_templates",
        ["tenant_id", "organisation_id", "template_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_narrative_templates_one_active",
        "narrative_templates",
        ["tenant_id", "organisation_id", "template_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "board_pack_inclusion_rules",
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
        sa.Column("rule_type", sa.String(length=64), nullable=False),
        sa.Column(
            "inclusion_logic_json",
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
            ["supersedes_id"], ["board_pack_inclusion_rules.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_board_pack_inclusion_rules_version_token",
        ),
        sa.CheckConstraint(
            "rule_type IN ('material_variance_only','high_critical_risks','sustained_anomalies','top_severity_issues','conditional_section')",
            name="ck_board_pack_inclusion_rules_type",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_board_pack_inclusion_rules_status",
        ),
    )
    op.create_index(
        "idx_board_pack_inclusion_rules_lookup",
        "board_pack_inclusion_rules",
        ["tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_board_pack_inclusion_rules_one_active",
        "board_pack_inclusion_rules",
        ["tenant_id", "organisation_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "board_pack_runs",
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
        sa.Column("board_pack_definition_version_token", sa.String(length=64), nullable=False),
        sa.Column("section_definition_version_token", sa.String(length=64), nullable=False),
        sa.Column("narrative_template_version_token", sa.String(length=64), nullable=False),
        sa.Column("inclusion_rule_version_token", sa.String(length=64), nullable=False),
        sa.Column(
            "source_metric_run_ids_json",
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
            "source_anomaly_run_ids_json",
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
        sa.UniqueConstraint("tenant_id", "run_token", name="uq_board_pack_runs_tenant_token"),
        sa.CheckConstraint(
            "status IN ('created','running','completed','failed')",
            name="ck_board_pack_runs_status",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_metric_run_ids_json) = 'array' AND jsonb_array_length(source_metric_run_ids_json) > 0",
            name="ck_board_pack_runs_metric_sources_required",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_risk_run_ids_json) = 'array' AND jsonb_array_length(source_risk_run_ids_json) > 0",
            name="ck_board_pack_runs_risk_sources_required",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_anomaly_run_ids_json) = 'array' AND jsonb_array_length(source_anomaly_run_ids_json) > 0",
            name="ck_board_pack_runs_anomaly_sources_required",
        ),
    )
    op.create_index(
        "idx_board_pack_runs_lookup",
        "board_pack_runs",
        ["tenant_id", "organisation_id", "reporting_period", "created_at"],
    )
    op.create_index(
        "idx_board_pack_runs_token",
        "board_pack_runs",
        ["tenant_id", "run_token"],
        unique=True,
    )

    op.create_table(
        "board_pack_results",
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
        sa.Column("board_pack_code", sa.String(length=128), nullable=False),
        sa.Column("reporting_period", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="generated"),
        sa.Column("executive_summary_text", sa.Text(), nullable=False),
        sa.Column("overall_health_classification", sa.String(length=32), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["board_pack_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_board_pack_results_run_id"),
        sa.CheckConstraint(
            "overall_health_classification IN ('healthy','watch','stressed','critical')",
            name="ck_board_pack_results_health",
        ),
        sa.CheckConstraint(
            "status IN ('generated','finalized','failed')",
            name="ck_board_pack_results_status",
        ),
    )
    op.create_index(
        "idx_board_pack_results_run",
        "board_pack_results",
        ["tenant_id", "run_id", "created_at"],
    )

    op.create_table(
        "board_pack_section_results",
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
        sa.Column("section_code", sa.String(length=128), nullable=False),
        sa.Column("section_order", sa.Integer(), nullable=False),
        sa.Column("section_title", sa.String(length=255), nullable=False),
        sa.Column("section_summary_text", sa.Text(), nullable=False),
        sa.Column(
            "section_payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["board_pack_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "section_order",
            name="uq_board_pack_section_results_order",
        ),
    )
    op.create_index(
        "idx_board_pack_section_results_run",
        "board_pack_section_results",
        ["tenant_id", "run_id", "section_order"],
    )

    op.create_table(
        "board_pack_narrative_blocks",
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
        sa.Column("section_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("narrative_template_code", sa.String(length=128), nullable=False),
        sa.Column("narrative_text", sa.Text(), nullable=False),
        sa.Column(
            "narrative_payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("block_order", sa.Integer(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["board_pack_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["section_result_id"], ["board_pack_section_results.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "section_result_id",
            "block_order",
            name="uq_board_pack_narrative_blocks_order",
        ),
    )
    op.create_index(
        "idx_board_pack_narrative_blocks_run",
        "board_pack_narrative_blocks",
        ["tenant_id", "run_id", "section_result_id", "block_order"],
    )

    op.create_table(
        "board_pack_evidence_links",
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
        sa.Column("section_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("narrative_block_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("evidence_label", sa.String(length=255), nullable=False),
        sa.Column(
            "evidence_payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("board_attention_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("severity_rank", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["board_pack_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["section_result_id"], ["board_pack_section_results.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["narrative_block_id"], ["board_pack_narrative_blocks.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "evidence_type IN ('metric_result','variance_result','trend_result','risk_result','anomaly_result','reconciliation_result','normalized_source_ref','narrative_template','definition_token','run_input')",
            name="ck_board_pack_evidence_links_type",
        ),
    )
    op.create_index(
        "idx_board_pack_evidence_links_run",
        "board_pack_evidence_links",
        ["tenant_id", "run_id", "created_at"],
    )
    op.create_index(
        "idx_board_pack_evidence_links_section",
        "board_pack_evidence_links",
        ["tenant_id", "run_id", "section_result_id"],
    )

    op.execute(
        _supersession_function_sql(
            table_name="board_pack_definitions",
            code_column="board_pack_code",
            fn_name="board_pack_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="board_pack_definitions",
            fn_name="board_pack_definitions_validate_supersession",
            trigger_name="trg_board_pack_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_function_sql(
            table_name="board_pack_section_definitions",
            code_column="section_code",
            fn_name="board_pack_section_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="board_pack_section_definitions",
            fn_name="board_pack_section_definitions_validate_supersession",
            trigger_name="trg_board_pack_section_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_function_sql(
            table_name="narrative_templates",
            code_column="template_code",
            fn_name="narrative_templates_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="narrative_templates",
            fn_name="narrative_templates_validate_supersession",
            trigger_name="trg_narrative_templates_validate_supersession",
        )
    )
    op.execute(
        _supersession_function_sql(
            table_name="board_pack_inclusion_rules",
            code_column="rule_code",
            fn_name="board_pack_inclusion_rules_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="board_pack_inclusion_rules",
            fn_name="board_pack_inclusion_rules_validate_supersession",
            trigger_name="trg_board_pack_inclusion_rules_validate_supersession",
        )
    )

    tables = [
        "board_pack_definitions",
        "board_pack_section_definitions",
        "narrative_templates",
        "board_pack_inclusion_rules",
        "board_pack_runs",
        "board_pack_results",
        "board_pack_section_results",
        "board_pack_narrative_blocks",
        "board_pack_evidence_links",
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
        "DROP TRIGGER IF EXISTS trg_board_pack_definitions_validate_supersession ON board_pack_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS board_pack_definitions_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_board_pack_section_definitions_validate_supersession ON board_pack_section_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS board_pack_section_definitions_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_narrative_templates_validate_supersession ON narrative_templates"
    )
    op.execute("DROP FUNCTION IF EXISTS narrative_templates_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_board_pack_inclusion_rules_validate_supersession ON board_pack_inclusion_rules"
    )
    op.execute("DROP FUNCTION IF EXISTS board_pack_inclusion_rules_validate_supersession()")

    drop_order = [
        "board_pack_evidence_links",
        "board_pack_narrative_blocks",
        "board_pack_section_results",
        "board_pack_results",
        "board_pack_runs",
        "board_pack_inclusion_rules",
        "narrative_templates",
        "board_pack_section_definitions",
        "board_pack_definitions",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
