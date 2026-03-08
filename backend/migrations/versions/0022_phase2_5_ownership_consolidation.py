"""Phase 2.5 Ownership / Minority Interest / Proportionate Consolidation Layer

Revision ID: 0022_phase2_5_ownership_consol
Revises: 0021_phase2_4_fx_translation
Create Date: 2026-03-12 10:00:00.000000
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

revision: str = "0022_phase2_5_ownership_consol"
down_revision: str | None = "0021_phase2_4_fx_translation"
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


def _ownership_relationship_integrity_function_sql() -> str:
    return """
    CREATE OR REPLACE FUNCTION ownership_relationships_validate_integrity()
    RETURNS trigger AS $$
    BEGIN
        IF NEW.parent_entity_id = NEW.child_entity_id THEN
            RAISE EXCEPTION 'parent and child entity cannot be identical';
        END IF;

        IF NEW.ownership_percentage < 0 OR NEW.ownership_percentage > 100 THEN
            RAISE EXCEPTION 'ownership_percentage must be between 0 and 100';
        END IF;

        IF NEW.voting_percentage_nullable IS NOT NULL
           AND (NEW.voting_percentage_nullable < 0 OR NEW.voting_percentage_nullable > 100) THEN
            RAISE EXCEPTION 'voting_percentage_nullable must be between 0 and 100';
        END IF;

        IF EXISTS (
            WITH RECURSIVE descendants(child_entity_id) AS (
                SELECT child_entity_id
                FROM ownership_relationships
                WHERE ownership_structure_id = NEW.ownership_structure_id
                  AND parent_entity_id = NEW.child_entity_id
                  AND status IN ('candidate', 'active')
                UNION ALL
                SELECT r.child_entity_id
                FROM ownership_relationships r
                JOIN descendants d ON r.parent_entity_id = d.child_entity_id
                WHERE r.ownership_structure_id = NEW.ownership_structure_id
                  AND r.status IN ('candidate', 'active')
            )
            SELECT 1
            FROM descendants
            WHERE child_entity_id = NEW.parent_entity_id
        ) THEN
            RAISE EXCEPTION 'ownership relationship cycle detected';
        END IF;

        IF NEW.supersedes_id IS NOT NULL THEN
            IF NEW.supersedes_id = NEW.id THEN
                RAISE EXCEPTION 'self-supersession is not allowed';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM ownership_relationships prev
                WHERE prev.id = NEW.supersedes_id
                  AND (
                    prev.tenant_id <> NEW.tenant_id
                    OR prev.organisation_id <> NEW.organisation_id
                    OR prev.ownership_structure_id <> NEW.ownership_structure_id
                    OR prev.parent_entity_id <> NEW.parent_entity_id
                    OR prev.child_entity_id <> NEW.child_entity_id
                  )
            ) THEN
                RAISE EXCEPTION 'relationship supersession must keep tenant/organisation/structure/parent/child identity';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM ownership_relationships
                WHERE supersedes_id = NEW.supersedes_id
            ) THEN
                RAISE EXCEPTION 'supersession branching is not allowed';
            END IF;

            IF EXISTS (
                WITH RECURSIVE chain(id, supersedes_id) AS (
                    SELECT id, supersedes_id
                    FROM ownership_relationships
                    WHERE id = NEW.supersedes_id
                    UNION ALL
                    SELECT t.id, t.supersedes_id
                    FROM ownership_relationships t
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


def upgrade() -> None:
    op.create_table(
        "ownership_structure_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ownership_structure_code", sa.String(length=128), nullable=False),
        sa.Column("ownership_structure_name", sa.String(length=255), nullable=False),
        sa.Column("hierarchy_scope_ref", sa.String(length=128), nullable=False),
        sa.Column("ownership_basis_type", sa.String(length=64), nullable=False),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["ownership_structure_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "ownership_structure_code",
            "version_token",
            name="uq_ownership_structure_definitions_version_token",
        ),
        sa.CheckConstraint(
            "ownership_basis_type IN ('equity_percentage','voting_percentage','manual_control')",
            name="ck_ownership_structure_definitions_basis_type",
        ),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_ownership_structure_definitions_status"),
    )
    op.create_index(
        "idx_ownership_structure_definitions_lookup",
        "ownership_structure_definitions",
        ["tenant_id", "organisation_id", "ownership_structure_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_ownership_structure_definitions_one_active",
        "ownership_structure_definitions",
        ["tenant_id", "organisation_id", "ownership_structure_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "ownership_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ownership_structure_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("child_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ownership_percentage", sa.Numeric(9, 6), nullable=False),
        sa.Column("voting_percentage_nullable", sa.Numeric(9, 6), nullable=True),
        sa.Column("control_indicator", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("minority_interest_indicator", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("proportionate_consolidation_indicator", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["ownership_structure_id"], ["ownership_structure_definitions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["ownership_relationships.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("ownership_percentage >= 0 AND ownership_percentage <= 100", name="ck_ownership_relationships_pct"),
        sa.CheckConstraint(
            "voting_percentage_nullable IS NULL OR (voting_percentage_nullable >= 0 AND voting_percentage_nullable <= 100)",
            name="ck_ownership_relationships_voting_pct",
        ),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_ownership_relationships_status"),
    )
    op.create_index(
        "idx_ownership_relationships_lookup",
        "ownership_relationships",
        ["tenant_id", "organisation_id", "ownership_structure_id", "parent_entity_id", "child_entity_id", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_ownership_relationships_one_active",
        "ownership_relationships",
        ["tenant_id", "ownership_structure_id", "parent_entity_id", "child_entity_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "idx_ownership_relationships_child_lookup",
        "ownership_relationships",
        ["tenant_id", "ownership_structure_id", "child_entity_id", "created_at"],
    )

    op.create_table(
        "ownership_consolidation_rule_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_code", sa.String(length=128), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("rule_type", sa.String(length=64), nullable=False),
        sa.Column("rule_logic_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attribution_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["ownership_consolidation_rule_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "organisation_id", "rule_code", "version_token", name="uq_ownership_consolidation_rule_definitions_version_token"),
        sa.CheckConstraint(
            "rule_type IN ('full_consolidation_rule','proportionate_consolidation_rule','minority_interest_rule','equity_attribution_placeholder','ownership_exclusion_rule')",
            name="ck_ownership_consolidation_rule_definitions_type",
        ),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_ownership_consolidation_rule_definitions_status"),
    )
    op.create_index(
        "idx_ownership_consolidation_rule_definitions_lookup",
        "ownership_consolidation_rule_definitions",
        ["tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_ownership_consolidation_rule_definitions_one_active",
        "ownership_consolidation_rule_definitions",
        ["tenant_id", "organisation_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "minority_interest_rule_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_code", sa.String(length=128), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("attribution_basis_type", sa.String(length=64), nullable=False),
        sa.Column("calculation_logic_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("presentation_logic_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["minority_interest_rule_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "organisation_id", "rule_code", "version_token", name="uq_minority_interest_rule_definitions_version_token"),
        sa.CheckConstraint("attribution_basis_type IN ('ownership_share','voting_share','explicit_policy')", name="ck_minority_interest_rule_definitions_basis_type"),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_minority_interest_rule_definitions_status"),
    )
    op.create_index(
        "idx_minority_interest_rule_definitions_lookup",
        "minority_interest_rule_definitions",
        ["tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"],
    )
    op.create_index(
        "uq_minority_interest_rule_definitions_one_active",
        "minority_interest_rule_definitions",
        ["tenant_id", "organisation_id", "rule_code"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "ownership_consolidation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporting_period", sa.Date(), nullable=False),
        sa.Column("hierarchy_version_token", sa.String(length=64), nullable=False),
        sa.Column("scope_version_token", sa.String(length=64), nullable=False),
        sa.Column("ownership_structure_version_token", sa.String(length=64), nullable=False),
        sa.Column("ownership_rule_version_token", sa.String(length=64), nullable=False),
        sa.Column("minority_interest_rule_version_token", sa.String(length=64), nullable=False),
        sa.Column("fx_translation_run_ref_nullable", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_consolidation_run_refs_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("run_token", sa.String(length=64), nullable=False),
        sa.Column("run_status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("validation_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["fx_translation_run_ref_nullable"], ["fx_translation_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "run_token", name="uq_ownership_consolidation_runs_tenant_token"),
        sa.CheckConstraint("run_status IN ('created','running','completed','failed')", name="ck_ownership_consolidation_runs_status"),
        sa.CheckConstraint(
            "jsonb_typeof(source_consolidation_run_refs_json) = 'array' AND jsonb_array_length(source_consolidation_run_refs_json) > 0",
            name="ck_ownership_consolidation_runs_sources_required",
        ),
    )
    op.create_index(
        "idx_ownership_consolidation_runs_lookup",
        "ownership_consolidation_runs",
        ["tenant_id", "organisation_id", "reporting_period", "created_at"],
    )
    op.create_index(
        "idx_ownership_consolidation_runs_token",
        "ownership_consolidation_runs",
        ["tenant_id", "run_token"],
        unique=True,
    )

    op.create_table(
        "ownership_consolidation_metric_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ownership_consolidation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("scope_code", sa.String(length=128), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("source_consolidated_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("ownership_weight_applied", sa.Numeric(9, 6), nullable=False),
        sa.Column("attributed_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("minority_interest_value_nullable", sa.Numeric(20, 6), nullable=True),
        sa.Column("reporting_currency_code_nullable", sa.String(length=3), nullable=True),
        sa.Column("lineage_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["ownership_consolidation_run_id"], ["ownership_consolidation_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ownership_consolidation_run_id", "line_no", name="uq_ownership_consolidation_metric_results_line_no"),
    )
    op.create_index(
        "idx_ownership_consolidation_metric_results_run",
        "ownership_consolidation_metric_results",
        ["tenant_id", "ownership_consolidation_run_id", "line_no"],
    )
    op.create_index(
        "idx_ownership_consolidation_metric_results_metric",
        "ownership_consolidation_metric_results",
        ["tenant_id", "ownership_consolidation_run_id", "metric_code"],
    )

    op.create_table(
        "ownership_consolidation_variance_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ownership_consolidation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("scope_code", sa.String(length=128), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("variance_code", sa.String(length=64), nullable=False),
        sa.Column("source_current_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("source_comparison_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("ownership_weight_applied", sa.Numeric(9, 6), nullable=False),
        sa.Column("attributed_current_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("attributed_comparison_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("attributed_variance_abs", sa.Numeric(20, 6), nullable=False),
        sa.Column("attributed_variance_pct", sa.Numeric(20, 6), nullable=True),
        sa.Column("attributed_variance_bps", sa.Numeric(20, 6), nullable=True),
        sa.Column("minority_interest_value_nullable", sa.Numeric(20, 6), nullable=True),
        sa.Column("lineage_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["ownership_consolidation_run_id"], ["ownership_consolidation_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ownership_consolidation_run_id", "line_no", name="uq_ownership_consolidation_variance_results_line_no"),
        sa.CheckConstraint("variance_code IN ('mom','yoy','actual_vs_budget','actual_vs_forecast')", name="ck_ownership_consolidation_variance_results_type"),
    )
    op.create_index(
        "idx_ownership_consolidation_variance_results_run",
        "ownership_consolidation_variance_results",
        ["tenant_id", "ownership_consolidation_run_id", "line_no"],
    )
    op.create_index(
        "idx_ownership_consolidation_variance_results_metric",
        "ownership_consolidation_variance_results",
        ["tenant_id", "ownership_consolidation_run_id", "metric_code"],
    )

    op.create_table(
        "ownership_consolidation_evidence_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ownership_consolidation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("variance_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("evidence_label", sa.String(length=255), nullable=False),
        sa.Column("evidence_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["ownership_consolidation_run_id"], ["ownership_consolidation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["metric_result_id"], ["ownership_consolidation_metric_results.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variance_result_id"], ["ownership_consolidation_variance_results.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "evidence_type IN ('source_metric_result','source_variance_result','ownership_relationship','ownership_rule_version','minority_interest_rule_version','fx_translation_run_ref')",
            name="ck_ownership_consolidation_evidence_links_type",
        ),
    )
    op.create_index(
        "idx_ownership_consolidation_evidence_links_run",
        "ownership_consolidation_evidence_links",
        ["tenant_id", "ownership_consolidation_run_id", "created_at"],
    )

    op.execute(
        _supersession_function_sql(
            table_name="ownership_structure_definitions",
            code_column="ownership_structure_code",
            fn_name="ownership_structure_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="ownership_structure_definitions",
            fn_name="ownership_structure_definitions_validate_supersession",
            trigger_name="trg_ownership_structure_definitions_validate_supersession",
        )
    )

    op.execute(_ownership_relationship_integrity_function_sql())
    op.execute(
        """
        CREATE TRIGGER trg_ownership_relationships_validate_integrity
        BEFORE INSERT ON ownership_relationships
        FOR EACH ROW
        EXECUTE FUNCTION ownership_relationships_validate_integrity();
        """
    )

    op.execute(
        _supersession_function_sql(
            table_name="ownership_consolidation_rule_definitions",
            code_column="rule_code",
            fn_name="ownership_consolidation_rule_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="ownership_consolidation_rule_definitions",
            fn_name="ownership_consolidation_rule_definitions_validate_supersession",
            trigger_name="trg_own_cons_rule_defs_validate_supersession",
        )
    )

    op.execute(
        _supersession_function_sql(
            table_name="minority_interest_rule_definitions",
            code_column="rule_code",
            fn_name="minority_interest_rule_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="minority_interest_rule_definitions",
            fn_name="minority_interest_rule_definitions_validate_supersession",
            trigger_name="trg_minority_rule_defs_validate_supersession",
        )
    )

    tables = [
        "ownership_structure_definitions",
        "ownership_relationships",
        "ownership_consolidation_rule_definitions",
        "minority_interest_rule_definitions",
        "ownership_consolidation_runs",
        "ownership_consolidation_metric_results",
        "ownership_consolidation_variance_results",
        "ownership_consolidation_evidence_links",
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
        "DROP TRIGGER IF EXISTS trg_ownership_structure_definitions_validate_supersession ON ownership_structure_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS ownership_structure_definitions_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_ownership_relationships_validate_integrity ON ownership_relationships"
    )
    op.execute("DROP FUNCTION IF EXISTS ownership_relationships_validate_integrity()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_own_cons_rule_defs_validate_supersession ON ownership_consolidation_rule_definitions"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS ownership_consolidation_rule_definitions_validate_supersession()"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_minority_rule_defs_validate_supersession ON minority_interest_rule_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS minority_interest_rule_definitions_validate_supersession()")

    drop_order = [
        "ownership_consolidation_evidence_links",
        "ownership_consolidation_variance_results",
        "ownership_consolidation_metric_results",
        "ownership_consolidation_runs",
        "minority_interest_rule_definitions",
        "ownership_consolidation_rule_definitions",
        "ownership_relationships",
        "ownership_structure_definitions",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
