"""Phase 2.3 Multi-Entity / Consolidation Extension

Revision ID: 0020_phase2_3_multi_entity_con
Revises: 0019_phase1f7_board_pack
Create Date: 2026-03-10 10:00:00.000000
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

revision: str = "0020_phase2_3_multi_entity_con"
down_revision: str | None = "0019_phase1f7_board_pack"
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


def _hierarchy_node_integrity_function_sql() -> str:
    return """
    CREATE OR REPLACE FUNCTION entity_hierarchy_nodes_validate_integrity()
    RETURNS trigger AS $$
    DECLARE
        parent_hierarchy_id uuid;
        parent_tenant_id uuid;
        parent_level integer;
    BEGIN
        IF NEW.parent_node_id IS NOT NULL THEN
            IF NEW.parent_node_id = NEW.id THEN
                RAISE EXCEPTION 'node cannot be its own parent';
            END IF;

            SELECT hierarchy_id, tenant_id, node_level
            INTO parent_hierarchy_id, parent_tenant_id, parent_level
            FROM entity_hierarchy_nodes
            WHERE id = NEW.parent_node_id;

            IF parent_hierarchy_id IS NULL THEN
                RAISE EXCEPTION 'parent node must exist';
            END IF;

            IF parent_tenant_id <> NEW.tenant_id OR parent_hierarchy_id <> NEW.hierarchy_id THEN
                RAISE EXCEPTION 'parent node must belong to same tenant and hierarchy';
            END IF;

            IF NEW.node_level <= parent_level THEN
                RAISE EXCEPTION 'node_level must be greater than parent node level';
            END IF;

            IF EXISTS (
                WITH RECURSIVE ancestors(id, parent_node_id) AS (
                    SELECT id, parent_node_id
                    FROM entity_hierarchy_nodes
                    WHERE id = NEW.parent_node_id
                    UNION ALL
                    SELECT n.id, n.parent_node_id
                    FROM entity_hierarchy_nodes n
                    INNER JOIN ancestors a ON n.id = a.parent_node_id
                    WHERE a.parent_node_id IS NOT NULL
                )
                SELECT 1 FROM ancestors WHERE id = NEW.id
            ) THEN
                RAISE EXCEPTION 'hierarchy cycle detected';
            END IF;
        END IF;

        IF NEW.supersedes_id IS NOT NULL THEN
            IF NEW.supersedes_id = NEW.id THEN
                RAISE EXCEPTION 'self-supersession is not allowed';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM entity_hierarchy_nodes prev
                WHERE prev.id = NEW.supersedes_id
                  AND (
                    prev.tenant_id <> NEW.tenant_id
                    OR prev.hierarchy_id <> NEW.hierarchy_id
                    OR prev.entity_id <> NEW.entity_id
                  )
            ) THEN
                RAISE EXCEPTION 'node supersession must keep tenant/hierarchy/entity identity';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM entity_hierarchy_nodes
                WHERE supersedes_id = NEW.supersedes_id
            ) THEN
                RAISE EXCEPTION 'supersession branching is not allowed';
            END IF;

            IF EXISTS (
                WITH RECURSIVE chain(id, supersedes_id) AS (
                    SELECT id, supersedes_id
                    FROM entity_hierarchy_nodes
                    WHERE id = NEW.supersedes_id
                    UNION ALL
                    SELECT t.id, t.supersedes_id
                    FROM entity_hierarchy_nodes t
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
        "entity_hierarchies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hierarchy_code", sa.String(length=128), nullable=False),
        sa.Column("hierarchy_name", sa.String(length=255), nullable=False),
        sa.Column("hierarchy_type", sa.String(length=64), nullable=False),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["entity_hierarchies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "organisation_id", "hierarchy_code", "version_token", name="uq_entity_hierarchies_version_token"),
        sa.CheckConstraint("hierarchy_type IN ('legal','management','custom')", name="ck_entity_hierarchies_type"),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_entity_hierarchies_status"),
    )
    op.create_index("idx_entity_hierarchies_lookup", "entity_hierarchies", ["tenant_id", "organisation_id", "hierarchy_code", "effective_from", "created_at"])
    op.create_index("uq_entity_hierarchies_one_active", "entity_hierarchies", ["tenant_id", "organisation_id", "hierarchy_code"], unique=True, postgresql_where=sa.text("status = 'active'"))

    op.create_table(
        "entity_hierarchy_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("hierarchy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_node_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("node_level", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["hierarchy_id"], ["entity_hierarchies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_node_id"], ["entity_hierarchy_nodes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["entity_hierarchy_nodes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("node_level >= 0", name="ck_entity_hierarchy_nodes_level"),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_entity_hierarchy_nodes_status"),
    )
    op.create_index("idx_entity_hierarchy_nodes_lookup", "entity_hierarchy_nodes", ["tenant_id", "hierarchy_id", "entity_id", "node_level", "created_at"])
    op.create_index("uq_entity_hierarchy_nodes_one_active", "entity_hierarchy_nodes", ["tenant_id", "hierarchy_id", "entity_id"], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_index("idx_entity_hierarchy_nodes_parent", "entity_hierarchy_nodes", ["tenant_id", "hierarchy_id", "parent_node_id"])

    op.create_table(
        "consolidation_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_code", sa.String(length=128), nullable=False),
        sa.Column("scope_name", sa.String(length=255), nullable=False),
        sa.Column("hierarchy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_selector_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["hierarchy_id"], ["entity_hierarchies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["consolidation_scopes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "organisation_id", "scope_code", "version_token", name="uq_consolidation_scopes_version_token"),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_consolidation_scopes_status"),
    )
    op.create_index("idx_consolidation_scopes_lookup", "consolidation_scopes", ["tenant_id", "organisation_id", "scope_code", "effective_from", "created_at"])
    op.create_index("uq_consolidation_scopes_one_active", "consolidation_scopes", ["tenant_id", "organisation_id", "scope_code"], unique=True, postgresql_where=sa.text("status = 'active'"))

    op.create_table(
        "consolidation_rule_definitions",
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
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["consolidation_rule_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "organisation_id", "rule_code", "version_token", name="uq_consolidation_rule_definitions_version_token"),
        sa.CheckConstraint("rule_type IN ('aggregation_rule','inclusion_rule','intercompany_rule','adjustment_rule','ownership_placeholder','currency_placeholder')", name="ck_consolidation_rule_definitions_type"),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_consolidation_rule_definitions_status"),
    )
    op.create_index("idx_consolidation_rule_definitions_lookup", "consolidation_rule_definitions", ["tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"])
    op.create_index("uq_consolidation_rule_definitions_one_active", "consolidation_rule_definitions", ["tenant_id", "organisation_id", "rule_code"], unique=True, postgresql_where=sa.text("status = 'active'"))

    op.create_table(
        "intercompany_mapping_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_code", sa.String(length=128), nullable=False),
        sa.Column("source_selector_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("counterpart_selector_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("treatment_rule_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["intercompany_mapping_rules.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "organisation_id", "rule_code", "version_token", name="uq_intercompany_mapping_rules_version_token"),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_intercompany_mapping_rules_status"),
    )
    op.create_index("idx_intercompany_mapping_rules_lookup", "intercompany_mapping_rules", ["tenant_id", "organisation_id", "rule_code", "effective_from", "created_at"])
    op.create_index("uq_intercompany_mapping_rules_one_active", "intercompany_mapping_rules", ["tenant_id", "organisation_id", "rule_code"], unique=True, postgresql_where=sa.text("status = 'active'"))

    op.create_table(
        "consolidation_adjustment_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("adjustment_code", sa.String(length=128), nullable=False),
        sa.Column("adjustment_name", sa.String(length=255), nullable=False),
        sa.Column("adjustment_type", sa.String(length=64), nullable=False),
        sa.Column("logic_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["supersedes_id"], ["consolidation_adjustment_definitions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "organisation_id", "adjustment_code", "version_token", name="uq_consolidation_adjustment_definitions_version_token"),
        sa.CheckConstraint("adjustment_type IN ('analytic_adjustment','intercompany_placeholder','manual_grouping','presentation_reclass')", name="ck_consolidation_adjustment_definitions_type"),
        sa.CheckConstraint("status IN ('candidate','active','superseded','rejected')", name="ck_consolidation_adjustment_definitions_status"),
    )
    op.create_index("idx_consolidation_adjustment_definitions_lookup", "consolidation_adjustment_definitions", ["tenant_id", "organisation_id", "adjustment_code", "effective_from", "created_at"])
    op.create_index("uq_consolidation_adjustment_definitions_one_active", "consolidation_adjustment_definitions", ["tenant_id", "organisation_id", "adjustment_code"], unique=True, postgresql_where=sa.text("status = 'active'"))

    op.create_table(
        "multi_entity_consolidation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporting_period", sa.Date(), nullable=False),
        sa.Column("hierarchy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hierarchy_version_token", sa.String(length=64), nullable=False),
        sa.Column("scope_version_token", sa.String(length=64), nullable=False),
        sa.Column("rule_version_token", sa.String(length=64), nullable=False),
        sa.Column("intercompany_version_token", sa.String(length=64), nullable=False),
        sa.Column("adjustment_version_token", sa.String(length=64), nullable=False),
        sa.Column("source_run_refs_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("run_token", sa.String(length=64), nullable=False),
        sa.Column("run_status", sa.String(length=32), nullable=False, server_default="created"),
        sa.Column("validation_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["hierarchy_id"], ["entity_hierarchies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["scope_id"], ["consolidation_scopes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "run_token", name="uq_multi_entity_consolidation_runs_tenant_token"),
        sa.CheckConstraint("run_status IN ('created','running','completed','failed')", name="ck_multi_entity_consolidation_runs_status"),
        sa.CheckConstraint("jsonb_typeof(source_run_refs_json) = 'array' AND jsonb_array_length(source_run_refs_json) > 0", name="ck_multi_entity_consolidation_runs_sources_required"),
    )
    op.create_index("idx_multi_entity_consolidation_runs_lookup", "multi_entity_consolidation_runs", ["tenant_id", "organisation_id", "reporting_period", "created_at"])
    op.create_index("idx_multi_entity_consolidation_runs_token", "multi_entity_consolidation_runs", ["tenant_id", "run_token"], unique=True)

    op.create_table(
        "multi_entity_consolidation_metric_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("scope_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("aggregated_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("entity_count", sa.Integer(), nullable=False),
        sa.Column("materiality_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["multi_entity_consolidation_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "line_no", name="uq_multi_entity_consolidation_metric_results_line_no"),
        sa.CheckConstraint("entity_count >= 1", name="ck_multi_entity_consolidation_metric_results_entity_count"),
    )
    op.create_index("idx_multi_entity_consolidation_metric_results_run", "multi_entity_consolidation_metric_results", ["tenant_id", "run_id", "line_no"])
    op.create_index("idx_multi_entity_consolidation_metric_results_metric", "multi_entity_consolidation_metric_results", ["tenant_id", "run_id", "metric_code"])

    op.create_table(
        "multi_entity_consolidation_variance_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("metric_code", sa.String(length=128), nullable=False),
        sa.Column("comparison_type", sa.String(length=32), nullable=False),
        sa.Column("base_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("current_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("variance_value", sa.Numeric(20, 6), nullable=False),
        sa.Column("variance_pct", sa.Numeric(20, 6), nullable=True),
        sa.Column("materiality_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["multi_entity_consolidation_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "line_no", name="uq_multi_entity_consolidation_variance_results_line_no"),
        sa.CheckConstraint("comparison_type IN ('mom','yoy','actual_vs_budget','actual_vs_forecast')", name="ck_multi_entity_consolidation_variance_results_type"),
    )
    op.create_index("idx_multi_entity_consolidation_variance_results_run", "multi_entity_consolidation_variance_results", ["tenant_id", "run_id", "line_no"])
    op.create_index("idx_multi_entity_consolidation_variance_results_metric", "multi_entity_consolidation_variance_results", ["tenant_id", "run_id", "metric_code"])

    op.create_table(
        "multi_entity_consolidation_evidence_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("variance_result_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("evidence_ref", sa.Text(), nullable=False),
        sa.Column("evidence_label", sa.String(length=255), nullable=False),
        sa.Column("evidence_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["multi_entity_consolidation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["metric_result_id"], ["multi_entity_consolidation_metric_results.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["variance_result_id"], ["multi_entity_consolidation_variance_results.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("evidence_type IN ('entity_metric_result','entity_variance_result','intercompany_decision','adjustment_reference','hierarchy_version','scope_version','rule_version','source_run_ref')", name="ck_multi_entity_consolidation_evidence_links_type"),
    )
    op.create_index("idx_multi_entity_consolidation_evidence_links_run", "multi_entity_consolidation_evidence_links", ["tenant_id", "run_id", "created_at"])
    op.create_index("idx_multi_entity_consolidation_evidence_links_metric", "multi_entity_consolidation_evidence_links", ["tenant_id", "run_id", "metric_result_id"])

    op.execute(
        _supersession_function_sql(
            table_name="entity_hierarchies",
            code_column="hierarchy_code",
            fn_name="entity_hierarchies_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="entity_hierarchies",
            fn_name="entity_hierarchies_validate_supersession",
            trigger_name="trg_entity_hierarchies_validate_supersession",
        )
    )
    op.execute(_hierarchy_node_integrity_function_sql())
    op.execute(
        """
        CREATE TRIGGER trg_entity_hierarchy_nodes_validate_integrity
        BEFORE INSERT ON entity_hierarchy_nodes
        FOR EACH ROW
        EXECUTE FUNCTION entity_hierarchy_nodes_validate_integrity();
        """
    )
    op.execute(
        _supersession_function_sql(
            table_name="consolidation_scopes",
            code_column="scope_code",
            fn_name="consolidation_scopes_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="consolidation_scopes",
            fn_name="consolidation_scopes_validate_supersession",
            trigger_name="trg_consolidation_scopes_validate_supersession",
        )
    )
    op.execute(
        _supersession_function_sql(
            table_name="consolidation_rule_definitions",
            code_column="rule_code",
            fn_name="consolidation_rule_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="consolidation_rule_definitions",
            fn_name="consolidation_rule_definitions_validate_supersession",
            trigger_name="trg_consolidation_rule_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_function_sql(
            table_name="intercompany_mapping_rules",
            code_column="rule_code",
            fn_name="intercompany_mapping_rules_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="intercompany_mapping_rules",
            fn_name="intercompany_mapping_rules_validate_supersession",
            trigger_name="trg_intercompany_mapping_rules_validate_supersession",
        )
    )
    op.execute(
        _supersession_function_sql(
            table_name="consolidation_adjustment_definitions",
            code_column="adjustment_code",
            fn_name="consolidation_adjustment_definitions_validate_supersession",
        )
    )
    op.execute(
        _supersession_trigger_sql(
            table_name="consolidation_adjustment_definitions",
            fn_name="consolidation_adjustment_definitions_validate_supersession",
            trigger_name="trg_consolidation_adjustment_definitions_validate_supersession",
        )
    )

    tables = [
        "entity_hierarchies",
        "entity_hierarchy_nodes",
        "consolidation_scopes",
        "consolidation_rule_definitions",
        "intercompany_mapping_rules",
        "consolidation_adjustment_definitions",
        "multi_entity_consolidation_runs",
        "multi_entity_consolidation_metric_results",
        "multi_entity_consolidation_variance_results",
        "multi_entity_consolidation_evidence_links",
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
        "DROP TRIGGER IF EXISTS trg_entity_hierarchies_validate_supersession ON entity_hierarchies"
    )
    op.execute("DROP FUNCTION IF EXISTS entity_hierarchies_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_entity_hierarchy_nodes_validate_integrity ON entity_hierarchy_nodes"
    )
    op.execute("DROP FUNCTION IF EXISTS entity_hierarchy_nodes_validate_integrity()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_consolidation_scopes_validate_supersession ON consolidation_scopes"
    )
    op.execute("DROP FUNCTION IF EXISTS consolidation_scopes_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_consolidation_rule_definitions_validate_supersession ON consolidation_rule_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS consolidation_rule_definitions_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_intercompany_mapping_rules_validate_supersession ON intercompany_mapping_rules"
    )
    op.execute("DROP FUNCTION IF EXISTS intercompany_mapping_rules_validate_supersession()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_consolidation_adjustment_definitions_validate_supersession ON consolidation_adjustment_definitions"
    )
    op.execute("DROP FUNCTION IF EXISTS consolidation_adjustment_definitions_validate_supersession()")

    drop_order = [
        "multi_entity_consolidation_evidence_links",
        "multi_entity_consolidation_variance_results",
        "multi_entity_consolidation_metric_results",
        "multi_entity_consolidation_runs",
        "consolidation_adjustment_definitions",
        "intercompany_mapping_rules",
        "consolidation_rule_definitions",
        "consolidation_scopes",
        "entity_hierarchy_nodes",
        "entity_hierarchies",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)
