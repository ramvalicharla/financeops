"""Phase 2.6 Cash Flow Engine (Ownership + FX aware)

Revision ID: 0023_phase2_6_cash_flow
Revises: 0022_phase2_5_ownership_consol
Create Date: 2026-03-12 16:30:00.000000
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

revision: str = "0023_phase2_6_cash_flow"
down_revision: str | None = "0022_phase2_5_ownership_consol"
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
        "cash_flow_statement_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("definition_code", sa.String(length=128), nullable=False),
        sa.Column("definition_name", sa.String(length=255), nullable=False),
        sa.Column("method_type", sa.String(length=32), nullable=False),
        sa.Column("layout_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["cash_flow_statement_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "definition_code",
            "version_token",
            name="uq_cash_flow_statement_definitions_version_token",
        ),
        sa.CheckConstraint("method_type IN ('indirect','direct')", name="ck_cash_flow_statement_definitions_method_type"),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_cash_flow_statement_definitions_status"),
    )
    op.create_index(
        "idx_cash_flow_statement_definitions_lookup",
        "cash_flow_statement_definitions",
        ["tenant_id", "organisation_id", "definition_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_cash_flow_statement_definitions_one_active",
        "cash_flow_statement_definitions",
        ["tenant_id", "organisation_id", "definition_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "cash_flow_line_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mapping_code", sa.String(length=128), nullable=False),
        sa.Column("line_code", sa.String(length=128), nullable=False),
        sa.Column("line_name", sa.String(length=255), nullable=False),
        sa.Column("section_code", sa.String(length=64), nullable=False),
        sa.Column("line_order", sa.Integer(), nullable=False),
        sa.Column("method_type", sa.String(length=32), nullable=False),
        sa.Column("source_metric_code", sa.String(length=128), nullable=False),
        sa.Column("sign_multiplier", sa.Numeric(9, 6), nullable=False, server_default=sa.text("1.000000")),
        sa.Column("aggregation_type", sa.String(length=32), nullable=False, server_default="sum"),
        sa.Column("ownership_applicability", sa.String(length=32), nullable=False, server_default="any"),
        sa.Column("fx_applicability", sa.String(length=32), nullable=False, server_default="any"),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["cash_flow_line_mappings.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "mapping_code",
            "line_code",
            "version_token",
            name="uq_cash_flow_line_mappings_version_token",
        ),
        sa.CheckConstraint("line_order >= 1", name="ck_cash_flow_line_mappings_line_order"),
        sa.CheckConstraint("method_type IN ('indirect','direct')", name="ck_cash_flow_line_mappings_method_type"),
        sa.CheckConstraint("aggregation_type IN ('sum')", name="ck_cash_flow_line_mappings_aggregation_type"),
        sa.CheckConstraint("ownership_applicability IN ('any','ownership_only','non_ownership_only')", name="ck_cash_flow_line_mappings_ownership_applicability"),
        sa.CheckConstraint("fx_applicability IN ('any','fx_only','non_fx_only')", name="ck_cash_flow_line_mappings_fx_applicability"),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_cash_flow_line_mappings_status"),
    )
    op.create_index(
        "idx_cash_flow_line_mappings_lookup",
        "cash_flow_line_mappings",
        ["tenant_id", "organisation_id", "mapping_code", "line_order", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_cash_flow_line_mappings_one_active",
        "cash_flow_line_mappings",
        ["tenant_id", "organisation_id", "mapping_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "cash_flow_bridge_rule_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_code", sa.String(length=128), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("bridge_logic_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ownership_logic_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("fx_logic_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["cash_flow_bridge_rule_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_cash_flow_bridge_rule_definitions_version_token",
        ),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_cash_flow_bridge_rule_definitions_status"),
    )
    op.create_index(
        "idx_cash_flow_bridge_rule_definitions_lookup",
        "cash_flow_bridge_rule_definitions",
        ["tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_cash_flow_bridge_rule_definitions_one_active",
        "cash_flow_bridge_rule_definitions",
        ["tenant_id", "organisation_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "cash_flow_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporting_period", sa.Date(), nullable=False),
        sa.Column("statement_definition_version_token", sa.String(length=64), nullable=False),
        sa.Column("line_mapping_version_token", sa.String(length=64), nullable=False),
        sa.Column("bridge_rule_version_token", sa.String(length=64), nullable=False),
        sa.Column("source_consolidation_run_ref", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_fx_translation_run_ref_nullable", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_ownership_consolidation_run_ref_nullable", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("run_token", sa.String(length=64), nullable=False),
        sa.Column("run_status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("validation_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["source_consolidation_run_ref"], ["multi_entity_consolidation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_fx_translation_run_ref_nullable"], ["fx_translation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_ownership_consolidation_run_ref_nullable"], ["ownership_consolidation_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "run_token", name="uq_cash_flow_runs_tenant_token"),
        sa.CheckConstraint("run_status IN ('created','running','completed','failed')", name="ck_cash_flow_runs_status"),
    )
    op.create_index(
        "idx_cash_flow_runs_lookup",
        "cash_flow_runs",
        ["tenant_id", "organisation_id", "reporting_period", "created_at"],
    )
    op.create_index(
        "idx_cash_flow_runs_token",
        "cash_flow_runs",
        ["tenant_id", "run_token"],
        unique=True,
    )

    op.create_table(
        "cash_flow_line_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("line_code", sa.String(length=128), nullable=False),
        sa.Column("line_name", sa.String(length=255), nullable=False),
        sa.Column("section_code", sa.String(length=64), nullable=False),
        sa.Column("line_order", sa.Integer(), nullable=False),
        sa.Column("method_type", sa.String(length=32), nullable=False),
        sa.Column("source_metric_code", sa.String(length=128), nullable=False),
        sa.Column("source_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("sign_multiplier", sa.Numeric(9, 6), nullable=False),
        sa.Column("computed_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("ownership_basis_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fx_basis_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("lineage_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["cash_flow_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "line_no", name="uq_cash_flow_line_results_line_no"),
    )
    op.create_index(
        "idx_cash_flow_line_results_run",
        "cash_flow_line_results",
        ["tenant_id", "run_id", "line_no"],
    )
    op.create_index(
        "idx_cash_flow_line_results_section",
        "cash_flow_line_results",
        ["tenant_id", "run_id", "section_code", "line_order"],
    )

    op.create_table(
        "cash_flow_evidence_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("evidence_label", sa.String(length=255), nullable=False),
        sa.Column("evidence_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["cash_flow_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["line_result_id"], ["cash_flow_line_results.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("evidence_type IN ('source_consolidation_metric','source_fx_metric','source_ownership_metric','line_mapping','bridge_rule','ownership_run_ref','fx_run_ref')", name="ck_cash_flow_evidence_links_type"),
    )
    op.create_index(
        "idx_cash_flow_evidence_links_run",
        "cash_flow_evidence_links",
        ["tenant_id", "run_id", "created_at"],
    )

    op.execute(
        _supersession_function_sql(
            table_name="cash_flow_statement_definitions",
            code_column="definition_code",
            fn_name="cash_flow_stmt_defs_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="cash_flow_statement_definitions",
            fn_name="cash_flow_stmt_defs_validate_supersession",
            trigger_name="trg_cash_flow_stmt_defs_validate_supersession",
        )
    )
    op.execute(
        _supersession_function_sql(
            table_name="cash_flow_line_mappings",
            code_column="mapping_code",
            fn_name="cash_flow_line_maps_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="cash_flow_line_mappings",
            fn_name="cash_flow_line_maps_validate_supersession",
            trigger_name="trg_cash_flow_line_maps_validate_supersession",
        )
    )
    op.execute(
        _supersession_function_sql(
            table_name="cash_flow_bridge_rule_definitions",
            code_column="rule_code",
            fn_name="cash_flow_bridge_rules_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="cash_flow_bridge_rule_definitions",
            fn_name="cash_flow_bridge_rules_validate_supersession",
            trigger_name="trg_cash_flow_bridge_rules_validate_supersession",
        )
    )

    tables = [
        "cash_flow_statement_definitions",
        "cash_flow_line_mappings",
        "cash_flow_bridge_rule_definitions",
        "cash_flow_runs",
        "cash_flow_line_results",
        "cash_flow_evidence_links",
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
        "DROP TRIGGER IF EXISTS trg_cash_flow_stmt_defs_validate_supersession ON cash_flow_statement_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS cash_flow_stmt_defs_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_cash_flow_line_maps_validate_supersession ON cash_flow_line_mappings"
    )
    op.execute("DROP FUNCTION IF EXISTS cash_flow_line_maps_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_cash_flow_bridge_rules_validate_supersession ON cash_flow_bridge_rule_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS cash_flow_bridge_rules_validate_supersession()")

    drop_order = [
        "cash_flow_evidence_links",
        "cash_flow_line_results",
        "cash_flow_runs",
        "cash_flow_bridge_rule_definitions",
        "cash_flow_line_mappings",
        "cash_flow_statement_definitions",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
