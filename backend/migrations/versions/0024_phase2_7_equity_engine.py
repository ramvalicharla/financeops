"""Phase 2.7 Equity / OCI / CTA Engine

Revision ID: 0024_phase2_7_equity_engine
Revises: 0023_phase2_6_cash_flow
Create Date: 2026-03-14 10:00:00.000000
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

revision: str = "0024_phase2_7_equity_engine"
down_revision: str | None = "0023_phase2_6_cash_flow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _supersession_function_sql(*, table_name: str, fn_name: str, family_predicate: str) -> str:
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
                  AND parent.organisation_id = NEW.organisation_id
                  AND ({family_predicate})
            ) THEN
                RAISE EXCEPTION 'supersession across different families is not allowed';
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
        "equity_statement_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_code", sa.String(length=128), nullable=False),
        sa.Column("statement_name", sa.String(length=255), nullable=False),
        sa.Column("reporting_currency_basis", sa.String(length=32), nullable=False),
        sa.Column("ownership_basis_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["equity_statement_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "statement_code",
            "version_token",
            name="uq_equity_statement_definitions_version_token",
        ),
        sa.CheckConstraint(
            "reporting_currency_basis IN ('source_currency','reporting_currency')",
            name="ck_equity_statement_definitions_currency_basis",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_equity_statement_definitions_status",
        ),
    )
    op.create_index(
        "idx_equity_statement_definitions_lookup",
        "equity_statement_definitions",
        ["tenant_id", "organisation_id", "statement_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_equity_statement_definitions_one_active",
        "equity_statement_definitions",
        ["tenant_id", "organisation_id", "statement_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "equity_line_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("statement_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_code", sa.String(length=128), nullable=False),
        sa.Column("line_name", sa.String(length=255), nullable=False),
        sa.Column("line_type", sa.String(length=64), nullable=False),
        sa.Column("presentation_order", sa.Integer(), nullable=False),
        sa.Column("rollforward_required_flag", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["statement_definition_id"], ["equity_statement_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["equity_line_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "statement_definition_id",
            "line_code",
            "version_token",
            name="uq_equity_line_definitions_version_token",
        ),
        sa.CheckConstraint("presentation_order >= 1", name="ck_equity_line_definitions_order"),
        sa.CheckConstraint(
            "line_type IN ('share_capital','share_premium','retained_earnings','other_reserves','oci_accumulated','cta_reserve','minority_interest','total_equity')",
            name="ck_equity_line_definitions_line_type",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_equity_line_definitions_status",
        ),
    )
    op.create_index(
        "idx_equity_line_definitions_lookup",
        "equity_line_definitions",
        ["tenant_id", "organisation_id", "statement_definition_id", "presentation_order", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_equity_line_definitions_one_active",
        "equity_line_definitions",
        ["tenant_id", "organisation_id", "statement_definition_id", "line_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "equity_rollforward_rule_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_code", sa.String(length=128), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("rule_type", sa.String(length=64), nullable=False),
        sa.Column("source_selector_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("derivation_logic_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("fx_interaction_logic_json_nullable", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ownership_interaction_logic_json_nullable", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["equity_rollforward_rule_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "rule_code",
            "version_token",
            name="uq_equity_rollforward_rule_definitions_version_token",
        ),
        sa.CheckConstraint(
            "rule_type IN ('opening_balance_rule','retained_earnings_bridge_rule','oci_accumulation_rule','cta_derivation_rule','ownership_attribution_rule','minority_interest_equity_rule','closing_balance_rule')",
            name="ck_equity_rollforward_rule_definitions_type",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_equity_rollforward_rule_definitions_status",
        ),
    )
    op.create_index(
        "idx_equity_rollforward_rule_definitions_lookup",
        "equity_rollforward_rule_definitions",
        ["tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_equity_rollforward_rule_definitions_one_active",
        "equity_rollforward_rule_definitions",
        ["tenant_id", "organisation_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "equity_source_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mapping_code", sa.String(length=128), nullable=False),
        sa.Column("line_code", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_selector_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("transformation_logic_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["equity_source_mappings.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "mapping_code",
            "line_code",
            "source_type",
            "version_token",
            name="uq_equity_source_mappings_version_token",
        ),
        sa.CheckConstraint(
            "source_type IN ('consolidation_result','fx_translation_result','ownership_result','pnl_result','adjustment_ref')",
            name="ck_equity_source_mappings_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_equity_source_mappings_status",
        ),
    )
    op.create_index(
        "idx_equity_source_mappings_lookup",
        "equity_source_mappings",
        ["tenant_id", "organisation_id", "mapping_code", "line_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_equity_source_mappings_one_active",
        "equity_source_mappings",
        ["tenant_id", "organisation_id", "mapping_code", "line_code", "source_type"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "equity_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporting_period", sa.Date(), nullable=False),
        sa.Column("statement_definition_version_token", sa.String(length=64), nullable=False),
        sa.Column("line_definition_version_token", sa.String(length=64), nullable=False),
        sa.Column("rollforward_rule_version_token", sa.String(length=64), nullable=False),
        sa.Column("source_mapping_version_token", sa.String(length=64), nullable=False),
        sa.Column("consolidation_run_ref_nullable", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fx_translation_run_ref_nullable", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ownership_consolidation_run_ref_nullable", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("run_token", sa.String(length=64), nullable=False),
        sa.Column("run_status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("validation_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["consolidation_run_ref_nullable"], ["multi_entity_consolidation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fx_translation_run_ref_nullable"], ["fx_translation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ownership_consolidation_run_ref_nullable"], ["ownership_consolidation_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "run_token", name="uq_equity_runs_tenant_token"),
        sa.CheckConstraint("run_status IN ('created','running','completed','failed')", name="ck_equity_runs_status"),
    )
    op.create_index(
        "idx_equity_runs_lookup",
        "equity_runs",
        ["tenant_id", "organisation_id", "reporting_period", "created_at"],
    )

    op.create_table(
        "equity_line_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("equity_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("line_code", sa.String(length=128), nullable=False),
        sa.Column("opening_balance", sa.Numeric(20, 6), nullable=False),
        sa.Column("movement_amount", sa.Numeric(20, 6), nullable=False),
        sa.Column("closing_balance", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_currency_amount_nullable", sa.Numeric(20, 6), nullable=True),
        sa.Column("reporting_currency_amount_nullable", sa.Numeric(20, 6), nullable=True),
        sa.Column("ownership_attributed_amount_nullable", sa.Numeric(20, 6), nullable=True),
        sa.Column("lineage_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["equity_run_id"], ["equity_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equity_run_id", "line_no", name="uq_equity_line_results_line_no"),
    )
    op.create_index("idx_equity_line_results_run", "equity_line_results", ["tenant_id", "equity_run_id", "line_no"])

    op.create_table(
        "equity_statement_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("equity_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("total_equity_opening", sa.Numeric(20, 6), nullable=False),
        sa.Column("total_equity_closing", sa.Numeric(20, 6), nullable=False),
        sa.Column("statement_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["equity_run_id"], ["equity_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equity_run_id", name="uq_equity_statement_results_run"),
    )
    op.create_index("idx_equity_statement_results_run", "equity_statement_results", ["tenant_id", "equity_run_id"])

    op.create_table(
        "equity_evidence_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("equity_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("evidence_label", sa.String(length=255), nullable=False),
        sa.Column("evidence_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["equity_run_id"], ["equity_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "evidence_type IN ('consolidation_result_ref','fx_translation_run_ref','ownership_run_ref','rule_version_ref','mapping_version_ref','line_mapping_ref')",
            name="ck_equity_evidence_links_type",
        ),
    )
    op.create_index("idx_equity_evidence_links_run", "equity_evidence_links", ["tenant_id", "equity_run_id", "created_at"])

    op.execute(
        _supersession_function_sql(
            table_name="equity_statement_definitions",
            fn_name="equity_stmt_defs_validate_supersession",
            family_predicate="parent.statement_code = NEW.statement_code",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="equity_statement_definitions",
            fn_name="equity_stmt_defs_validate_supersession",
            trigger_name="trg_equity_stmt_defs_validate_supersession",
        )
    )
    op.execute(
        _supersession_function_sql(
            table_name="equity_line_definitions",
            fn_name="equity_line_defs_validate_supersession",
            family_predicate="parent.statement_definition_id = NEW.statement_definition_id AND parent.line_code = NEW.line_code",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="equity_line_definitions",
            fn_name="equity_line_defs_validate_supersession",
            trigger_name="trg_equity_line_defs_validate_supersession",
        )
    )
    op.execute(
        _supersession_function_sql(
            table_name="equity_rollforward_rule_definitions",
            fn_name="equity_rule_defs_validate_supersession",
            family_predicate="parent.rule_code = NEW.rule_code",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="equity_rollforward_rule_definitions",
            fn_name="equity_rule_defs_validate_supersession",
            trigger_name="trg_equity_rule_defs_validate_supersession",
        )
    )
    op.execute(
        _supersession_function_sql(
            table_name="equity_source_mappings",
            fn_name="equity_source_maps_validate_supersession",
            family_predicate="parent.mapping_code = NEW.mapping_code AND parent.line_code = NEW.line_code AND parent.source_type = NEW.source_type",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="equity_source_mappings",
            fn_name="equity_source_maps_validate_supersession",
            trigger_name="trg_equity_source_maps_validate_supersession",
        )
    )

    tables = [
        "equity_statement_definitions",
        "equity_line_definitions",
        "equity_rollforward_rule_definitions",
        "equity_source_mappings",
        "equity_runs",
        "equity_line_results",
        "equity_statement_results",
        "equity_evidence_links",
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
        "DROP TRIGGER IF EXISTS trg_equity_stmt_defs_validate_supersession ON equity_statement_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS equity_stmt_defs_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_equity_line_defs_validate_supersession ON equity_line_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS equity_line_defs_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_equity_rule_defs_validate_supersession ON equity_rollforward_rule_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS equity_rule_defs_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_equity_source_maps_validate_supersession ON equity_source_mappings"
    )
    op.execute("DROP FUNCTION IF EXISTS equity_source_maps_validate_supersession()")

    drop_order = [
        "equity_evidence_links",
        "equity_statement_results",
        "equity_line_results",
        "equity_runs",
        "equity_source_mappings",
        "equity_rollforward_rule_definitions",
        "equity_line_definitions",
        "equity_statement_definitions",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
