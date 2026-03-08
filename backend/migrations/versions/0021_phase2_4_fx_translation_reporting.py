"""Phase 2.4 FX Translation & Reporting Currency Layer

Revision ID: 0021_phase2_4_fx_translation
Revises: 0020_phase2_3_multi_entity_con
Create Date: 2026-03-10 16:30:00.000000
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

revision: str = "0021_phase2_4_fx_translation"
down_revision: str | None = "0020_phase2_3_multi_entity_con"
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
        "reporting_currency_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporting_currency_code", sa.String(length=3), nullable=False),
        sa.Column("reporting_currency_name", sa.String(length=128), nullable=False),
        sa.Column("reporting_scope_type", sa.String(length=64), nullable=False),
        sa.Column("reporting_scope_ref", sa.String(length=128), nullable=False),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["reporting_currency_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "reporting_currency_code",
            "reporting_scope_type",
            "reporting_scope_ref",
            "version_token",
            name="uq_reporting_currency_definitions_version_token",
        ),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_reporting_currency_definitions_status"),
    )
    op.create_index(
        "idx_reporting_currency_definitions_lookup",
        "reporting_currency_definitions",
        ["tenant_id", "organisation_id", "reporting_scope_type", "reporting_scope_ref", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_reporting_currency_definitions_one_active_scope",
        "reporting_currency_definitions",
        ["tenant_id", "organisation_id", "reporting_scope_type", "reporting_scope_ref"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "fx_translation_rule_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_code", sa.String(length=128), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("translation_scope_type", sa.String(length=64), nullable=False),
        sa.Column("translation_scope_ref", sa.String(length=128), nullable=False),
        sa.Column("source_currency_selector_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("target_reporting_currency_code", sa.String(length=3), nullable=False),
        sa.Column("rule_logic_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("rate_policy_ref", sa.String(length=128), nullable=False),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["fx_translation_rule_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_fx_translation_rule_definitions_version_token",
        ),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_fx_translation_rule_definitions_status"),
    )
    op.create_index(
        "idx_fx_translation_rule_definitions_lookup",
        "fx_translation_rule_definitions",
        ["tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_fx_translation_rule_definitions_one_active",
        "fx_translation_rule_definitions",
        ["tenant_id", "organisation_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "fx_rate_selection_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_code", sa.String(length=128), nullable=False),
        sa.Column("policy_name", sa.String(length=255), nullable=False),
        sa.Column("rate_type", sa.String(length=32), nullable=False),
        sa.Column("date_selector_logic_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("fallback_behavior_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("locked_rate_requirement_flag", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("source_rate_provider_ref", sa.String(length=128), nullable=False, server_default="fx_rate_tables_v1"),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["fx_rate_selection_policies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "policy_code",
            "version_token",
            name="uq_fx_rate_selection_policies_version_token",
        ),
        sa.CheckConstraint("rate_type IN ('closing','average','historical')", name="ck_fx_rate_selection_policies_rate_type"),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_fx_rate_selection_policies_status"),
    )
    op.create_index(
        "idx_fx_rate_selection_policies_lookup",
        "fx_rate_selection_policies",
        ["tenant_id", "organisation_id", "policy_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_fx_rate_selection_policies_one_active",
        "fx_rate_selection_policies",
        ["tenant_id", "organisation_id", "policy_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "fx_translation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporting_period", sa.Date(), nullable=False),
        sa.Column("reporting_currency_code", sa.String(length=3), nullable=False),
        sa.Column("reporting_currency_version_token", sa.String(length=64), nullable=False),
        sa.Column("translation_rule_version_token", sa.String(length=64), nullable=False),
        sa.Column("rate_policy_version_token", sa.String(length=64), nullable=False),
        sa.Column("rate_source_version_token", sa.String(length=64), nullable=False),
        sa.Column("source_consolidation_run_refs_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("run_token", sa.String(length=64), nullable=False),
        sa.Column("run_status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("validation_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "run_token", name="uq_fx_translation_runs_tenant_token"),
        sa.CheckConstraint("run_status IN ('created','running','completed','failed')", name="ck_fx_translation_runs_status"),
        sa.CheckConstraint("jsonb_typeof(source_consolidation_run_refs_json) = 'array' AND jsonb_array_length(source_consolidation_run_refs_json) > 0", name="ck_fx_translation_runs_sources_required"),
    )
    op.create_index("idx_fx_translation_runs_lookup", "fx_translation_runs", ["tenant_id", "organisation_id", "reporting_period", "created_at"])
    op.create_index("idx_fx_translation_runs_token", "fx_translation_runs", ["tenant_id", "run_token"], unique=True)

    op.create_table(
        "fx_translated_metric_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("source_metric_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("source_currency_code", sa.String(length=3), nullable=False),
        sa.Column("reporting_currency_code", sa.String(length=3), nullable=False),
        sa.Column("applied_rate_type", sa.String(length=32), nullable=False),
        sa.Column("applied_rate_ref", sa.String(length=255), nullable=False),
        sa.Column("applied_rate_value", sa.Numeric(20, 8), nullable=False),
        sa.Column("source_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("translated_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("lineage_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["fx_translation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_metric_result_id"], ["multi_entity_consolidation_metric_results.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "line_no", name="uq_fx_translated_metric_results_line_no"),
    )
    op.create_index("idx_fx_translated_metric_results_run", "fx_translated_metric_results", ["tenant_id", "run_id", "line_no"])
    op.create_index("idx_fx_translated_metric_results_source", "fx_translated_metric_results", ["tenant_id", "run_id", "source_metric_result_id"])

    op.create_table(
        "fx_translated_variance_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("source_variance_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("comparison_type", sa.String(length=32), nullable=False),
        sa.Column("source_currency_code", sa.String(length=3), nullable=False),
        sa.Column("reporting_currency_code", sa.String(length=3), nullable=False),
        sa.Column("applied_rate_type", sa.String(length=32), nullable=False),
        sa.Column("applied_rate_ref", sa.String(length=255), nullable=False),
        sa.Column("applied_rate_value", sa.Numeric(20, 8), nullable=False),
        sa.Column("source_base_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_current_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_variance_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("translated_base_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("translated_current_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("translated_variance_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("variance_pct", sa.Numeric(20, 6), nullable=True),
        sa.Column("lineage_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["fx_translation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_variance_result_id"], ["multi_entity_consolidation_variance_results.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "line_no", name="uq_fx_translated_variance_results_line_no"),
        sa.CheckConstraint("comparison_type IN ('mom','yoy','actual_vs_budget','actual_vs_forecast')", name="ck_fx_translated_variance_results_type"),
    )
    op.create_index("idx_fx_translated_variance_results_run", "fx_translated_variance_results", ["tenant_id", "run_id", "line_no"])
    op.create_index("idx_fx_translated_variance_results_source", "fx_translated_variance_results", ["tenant_id", "run_id", "source_variance_result_id"])

    op.create_table(
        "fx_translation_evidence_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("translated_metric_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("translated_variance_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("evidence_label", sa.String(length=255), nullable=False),
        sa.Column("evidence_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["fx_translation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["translated_metric_result_id"], ["fx_translated_metric_results.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["translated_variance_result_id"], ["fx_translated_variance_results.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("evidence_type IN ('source_result','applied_rate','rate_type','rule_version','policy_version','rate_source','consolidation_run_ref')", name="ck_fx_translation_evidence_links_type"),
    )
    op.create_index("idx_fx_translation_evidence_links_run", "fx_translation_evidence_links", ["tenant_id", "run_id", "created_at"])

    op.execute(
        _supersession_function_sql(
            table_name="reporting_currency_definitions",
            code_column="reporting_currency_code",
            fn_name="reporting_currency_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="reporting_currency_definitions",
            fn_name="reporting_currency_definitions_validate_supersession",
            trigger_name="trg_reporting_currency_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_function_sql(
            table_name="fx_translation_rule_definitions",
            code_column="rule_code",
            fn_name="fx_translation_rule_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="fx_translation_rule_definitions",
            fn_name="fx_translation_rule_definitions_validate_supersession",
            trigger_name="trg_fx_translation_rule_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_function_sql(
            table_name="fx_rate_selection_policies",
            code_column="policy_code",
            fn_name="fx_rate_selection_policies_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="fx_rate_selection_policies",
            fn_name="fx_rate_selection_policies_validate_supersession",
            trigger_name="trg_fx_rate_selection_policies_validate_supersession",
        )
    )

    tables = [
        "reporting_currency_definitions",
        "fx_translation_rule_definitions",
        "fx_rate_selection_policies",
        "fx_translation_runs",
        "fx_translated_metric_results",
        "fx_translated_variance_results",
        "fx_translation_evidence_links",
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
        "DROP TRIGGER IF EXISTS trg_reporting_currency_definitions_validate_supersession ON reporting_currency_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS reporting_currency_definitions_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_fx_translation_rule_definitions_validate_supersession ON fx_translation_rule_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS fx_translation_rule_definitions_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_fx_rate_selection_policies_validate_supersession ON fx_rate_selection_policies"
    )
    op.execute("DROP FUNCTION IF EXISTS fx_rate_selection_policies_validate_supersession()")

    drop_order = [
        "fx_translation_evidence_links",
        "fx_translated_variance_results",
        "fx_translated_metric_results",
        "fx_translation_runs",
        "fx_rate_selection_policies",
        "fx_translation_rule_definitions",
        "reporting_currency_definitions",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)

