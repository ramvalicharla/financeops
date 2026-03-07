"""Phase 1F.1 MIS Manager deterministic canonical layer

Revision ID: 0012_phase1f1_mis_manager
Revises: 0011_phase1d6_remeasurement
Create Date: 2026-03-07 19:30:00.000000
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0012_phase1f1_mis_manager"
down_revision: str | None = "0011_phase1d6_remeasurement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CANONICAL_METRICS: tuple[str, ...] = (
    "revenue_gross",
    "revenue_discounts",
    "revenue_net",
    "cogs_material",
    "cogs_service",
    "gross_profit",
    "employee_cost",
    "rent_expense",
    "software_subscription",
    "marketing_expense",
    "general_admin_expense",
    "ebitda",
    "depreciation",
    "finance_cost",
    "pbt",
    "tax_expense",
    "pat",
    "ar",
    "ap",
    "inventory",
    "capex",
    "cash",
    "debt",
)

CANONICAL_DIMENSIONS: tuple[str, ...] = (
    "business_unit",
    "cost_center",
    "department",
    "project",
    "customer",
    "vendor",
    "product_line",
    "geography",
    "legal_entity",
    "channel",
)


def upgrade() -> None:
    conn = op.get_bind()
    # Expand logical parent template table while retaining legacy columns.
    op.add_column(
        "mis_templates",
        sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "mis_templates",
        sa.Column("template_code", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "mis_templates",
        sa.Column("template_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "mis_templates",
        sa.Column(
            "template_type",
            sa.String(length=64),
            nullable=True,
            server_default="custom",
        ),
    )
    op.add_column(
        "mis_templates",
        sa.Column(
            "status", sa.String(length=32), nullable=True, server_default="active"
        ),
    )

    op.execute(
        "UPDATE mis_templates "
        "SET organisation_id = tenant_id "
        "WHERE organisation_id IS NULL"
    )
    op.execute(
        """
        UPDATE mis_templates
        SET template_code = CONCAT(
            'legacy_',
            REPLACE(id::text, '-', ''),
            '_',
            version::text
        )
        WHERE template_code IS NULL
        """
    )
    op.execute(
        "UPDATE mis_templates SET template_name = name WHERE template_name IS NULL"
    )
    op.execute(
        "UPDATE mis_templates SET template_type = 'custom' WHERE template_type IS NULL"
    )
    op.execute("UPDATE mis_templates SET status = 'active' WHERE status IS NULL")

    op.alter_column("mis_templates", "organisation_id", nullable=False)
    op.alter_column("mis_templates", "template_code", nullable=False)
    op.alter_column("mis_templates", "template_name", nullable=False)
    op.alter_column(
        "mis_templates", "template_type", nullable=False, server_default=None
    )
    op.alter_column("mis_templates", "status", nullable=False, server_default=None)

    op.create_unique_constraint(
        "uq_mis_templates_tenant_template_code",
        "mis_templates",
        ["tenant_id", "template_code"],
    )
    op.create_check_constraint(
        "ck_mis_templates_status",
        "mis_templates",
        "status IN ('active', 'inactive', 'archived')",
    )
    op.create_index(
        "idx_mis_templates_template_code",
        "mis_templates",
        ["tenant_id", "template_code"],
    )

    # Core deterministic version table.
    op.create_table(
        "mis_template_versions",
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
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("version_token", sa.String(length=64), nullable=False),
        sa.Column("based_on_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("structure_hash", sa.String(length=64), nullable=False),
        sa.Column("header_hash", sa.String(length=64), nullable=False),
        sa.Column("row_signature_hash", sa.String(length=64), nullable=False),
        sa.Column("column_signature_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "detection_summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("drift_reason", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="candidate"
        ),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"], ["mis_templates.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["based_on_version_id"], ["mis_template_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["mis_template_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id",
            "version_no",
            name="uq_mis_template_versions_template_version_no",
        ),
        sa.UniqueConstraint(
            "template_id",
            "version_token",
            name="uq_mis_template_versions_template_version_token",
        ),
        sa.CheckConstraint(
            "status IN ('candidate','active','superseded','rejected')",
            name="ck_mis_template_versions_status",
        ),
    )
    op.create_index(
        "idx_mis_template_versions_template_created",
        "mis_template_versions",
        ["tenant_id", "template_id", "created_at"],
    )
    op.create_index(
        "uq_mis_template_versions_one_active",
        "mis_template_versions",
        ["template_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION mis_template_versions_validate_supersession()
        RETURNS trigger AS $$
        DECLARE
            parent_template_id uuid;
            parent_based_template_id uuid;
        BEGIN
            IF NEW.supersedes_id IS NOT NULL THEN
                IF NEW.supersedes_id = NEW.id THEN
                    RAISE EXCEPTION 'self-supersession is not allowed';
                END IF;

                SELECT template_id INTO parent_template_id
                FROM mis_template_versions
                WHERE id = NEW.supersedes_id;

                IF parent_template_id IS NULL THEN
                    RAISE EXCEPTION 'supersedes_id must reference an existing version';
                END IF;

                IF parent_template_id <> NEW.template_id THEN
                    RAISE EXCEPTION 'supersession across templates is not allowed';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM mis_template_versions
                    WHERE supersedes_id = NEW.supersedes_id
                ) THEN
                    RAISE EXCEPTION 'supersession branching is not allowed';
                END IF;
            END IF;

            IF NEW.based_on_version_id IS NOT NULL THEN
                SELECT template_id INTO parent_based_template_id
                FROM mis_template_versions
                WHERE id = NEW.based_on_version_id;

                IF parent_based_template_id IS NULL THEN
                    RAISE EXCEPTION 'based_on_version_id missing parent';
                END IF;

                IF parent_based_template_id <> NEW.template_id THEN
                    RAISE EXCEPTION 'based_on_version_id cross-template';
                END IF;
            END IF;

            IF NEW.supersedes_id IS NOT NULL AND NEW.id IS NOT NULL THEN
                IF EXISTS (
                    WITH RECURSIVE chain(id, supersedes_id) AS (
                        SELECT id, supersedes_id
                        FROM mis_template_versions
                        WHERE id = NEW.supersedes_id
                        UNION ALL
                        SELECT v.id, v.supersedes_id
                        FROM mis_template_versions v
                        INNER JOIN chain c ON v.id = c.supersedes_id
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
    )
    op.execute(
        """
        CREATE TRIGGER trg_mis_template_versions_validate_supersession
        BEFORE INSERT ON mis_template_versions
        FOR EACH ROW
        EXECUTE FUNCTION mis_template_versions_validate_supersession();
        """
    )

    op.create_table(
        "mis_template_sections",
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
        sa.Column("template_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_code", sa.String(length=64), nullable=False),
        sa.Column("section_name", sa.String(length=255), nullable=False),
        sa.Column("section_order", sa.Integer(), nullable=False),
        sa.Column("start_row_signature", sa.String(length=128), nullable=False),
        sa.Column("end_row_signature", sa.String(length=128), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_version_id"], ["mis_template_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_version_id", "section_code", name="uq_mis_template_sections_code"
        ),
        sa.UniqueConstraint(
            "template_version_id",
            "section_order",
            name="uq_mis_template_sections_order",
        ),
    )
    op.create_index(
        "idx_mis_template_sections_version",
        "mis_template_sections",
        ["tenant_id", "template_version_id"],
    )

    op.create_table(
        "mis_template_columns",
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
        sa.Column("template_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_column_label", sa.Text(), nullable=False),
        sa.Column("normalized_column_label", sa.Text(), nullable=False),
        sa.Column("column_role", sa.String(length=32), nullable=False),
        sa.Column("data_type", sa.String(length=32), nullable=False),
        sa.Column("ordinal_position", sa.Integer(), nullable=False),
        sa.Column("canonical_dimension_code", sa.String(length=64), nullable=True),
        sa.Column("canonical_metric_code", sa.String(length=64), nullable=True),
        sa.Column(
            "is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "is_period_column",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_value_column",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_version_id"], ["mis_template_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_version_id",
            "ordinal_position",
            name="uq_mis_template_columns_ordinal",
        ),
        sa.CheckConstraint(
            "column_role IN "
            "('period','metric_name','value','dimension','subtotal_flag','formula_flag','notes')",
            name="ck_mis_template_columns_role",
        ),
        sa.CheckConstraint(
            "data_type IN ('string','numeric','date','boolean','json')",
            name="ck_mis_template_columns_data_type",
        ),
    )
    op.create_index(
        "idx_mis_template_columns_version",
        "mis_template_columns",
        ["tenant_id", "template_version_id"],
    )

    op.create_table(
        "mis_template_row_mappings",
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
        sa.Column("template_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_row_pattern", sa.Text(), nullable=False),
        sa.Column("normalized_row_label", sa.Text(), nullable=False),
        sa.Column("canonical_metric_code", sa.String(length=64), nullable=False),
        sa.Column("sign_rule", sa.String(length=32), nullable=False),
        sa.Column("aggregation_rule", sa.String(length=32), nullable=False),
        sa.Column("section_code", sa.String(length=64), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_version_id"], ["mis_template_versions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["template_version_id", "section_code"],
            [
                "mis_template_sections.template_version_id",
                "mis_template_sections.section_code",
            ],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_mis_template_row_mappings_confidence",
        ),
    )
    op.create_index(
        "idx_mis_template_row_mappings_version",
        "mis_template_row_mappings",
        ["tenant_id", "template_version_id"],
    )

    op.create_table(
        "mis_data_snapshots",
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
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reporting_period", sa.Date(), nullable=False),
        sa.Column("upload_artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_token", sa.String(length=64), nullable=False),
        sa.Column("source_file_hash", sa.String(length=64), nullable=False),
        sa.Column("sheet_name", sa.String(length=255), nullable=False),
        sa.Column(
            "snapshot_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "validation_summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"], ["mis_templates.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["template_version_id"], ["mis_template_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_version_id",
            "snapshot_token",
            name="uq_mis_data_snapshots_version_token",
        ),
        sa.CheckConstraint(
            "snapshot_status IN ('pending','validated','finalized','failed')",
            name="ck_mis_data_snapshots_status",
        ),
    )
    op.create_index(
        "idx_mis_data_snapshots_period",
        "mis_data_snapshots",
        ["tenant_id", "template_id", "reporting_period"],
    )

    op.create_table(
        "mis_normalized_lines",
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
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("canonical_metric_code", sa.String(length=64), nullable=False),
        sa.Column(
            "canonical_dimension_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("source_row_ref", sa.Text(), nullable=False),
        sa.Column("source_column_ref", sa.Text(), nullable=False),
        sa.Column("period_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("sign_applied", sa.String(length=32), nullable=False),
        sa.Column("validation_status", sa.String(length=16), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["mis_data_snapshots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id", "line_no", name="uq_mis_normalized_lines_snapshot_line_no"
        ),
        sa.CheckConstraint(
            "validation_status IN ('valid','warning','invalid')",
            name="ck_mis_normalized_lines_validation_status",
        ),
    )
    op.create_index(
        "idx_mis_normalized_lines_snapshot",
        "mis_normalized_lines",
        ["tenant_id", "snapshot_id", "line_no"],
    )

    op.create_table(
        "mis_ingestion_exceptions",
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
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exception_code", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "resolution_status",
            sa.String(length=24),
            nullable=False,
            server_default="open",
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["mis_data_snapshots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "severity IN ('info','warning','error')",
            name="ck_mis_ingestion_exceptions_severity",
        ),
        sa.CheckConstraint(
            "resolution_status IN ('open','acknowledged','resolved')",
            name="ck_mis_ingestion_exceptions_resolution_status",
        ),
    )
    op.create_index(
        "idx_mis_ingestion_exceptions_snapshot",
        "mis_ingestion_exceptions",
        ["tenant_id", "snapshot_id", "created_at"],
    )

    op.create_table(
        "mis_drift_events",
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
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "prior_template_version_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "candidate_template_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("drift_type", sa.String(length=64), nullable=False),
        sa.Column(
            "drift_details_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "decision_status",
            sa.String(length=32),
            nullable=False,
            server_default="pending_review",
        ),
        sa.Column("decided_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"], ["mis_templates.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["prior_template_version_id"],
            ["mis_template_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_template_version_id"],
            ["mis_template_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "drift_type IN "
            "('HEADER_CHANGE','SECTION_REORDER','PERIOD_AXIS_CHANGE','DIMENSION_CHANGE','ROW_PATTERN_CHANGE','MAJOR_LAYOUT_CHANGE')",
            name="ck_mis_drift_events_type",
        ),
        sa.CheckConstraint(
            "decision_status IN ('pending_review','accepted','rejected')",
            name="ck_mis_drift_events_decision_status",
        ),
    )
    op.create_index(
        "idx_mis_drift_events_template",
        "mis_drift_events",
        ["tenant_id", "template_id", "created_at"],
    )

    op.create_table(
        "mis_canonical_metric_dictionary",
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
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("metric_code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version_no",
            "metric_code",
            name="uq_mis_canonical_metric_dict_version_code",
        ),
        sa.CheckConstraint(
            "status IN ('active','deprecated')",
            name="ck_mis_canonical_metric_dict_status",
        ),
    )
    op.create_index(
        "idx_mis_canonical_metric_dict_code",
        "mis_canonical_metric_dictionary",
        ["tenant_id", "metric_code"],
    )

    op.create_table(
        "mis_canonical_dimension_dictionary",
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
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("dimension_code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "version_no",
            "dimension_code",
            name="uq_mis_canonical_dimension_dict_version_code",
        ),
        sa.CheckConstraint(
            "status IN ('active','deprecated')",
            name="ck_mis_canonical_dimension_dict_status",
        ),
    )
    op.create_index(
        "idx_mis_canonical_dimension_dict_code",
        "mis_canonical_dimension_dictionary",
        ["tenant_id", "dimension_code"],
    )

    # Seed canonical dictionary version 1.
    seed_tenant = "00000000-0000-0000-0000-000000000000"
    seed_user = "00000000-0000-0000-0000-000000000001"

    for metric in CANONICAL_METRICS:
        conn.execute(
            sa.text(
                """
                INSERT INTO mis_canonical_metric_dictionary
                (
                    id, tenant_id, chain_hash, previous_hash, created_at,
                    version_no, metric_code, display_name, description, status,
                    created_by
                )
                VALUES (
                    CAST(:id AS uuid),
                    CAST(:tenant_id AS uuid),
                    repeat('0', 64),
                    repeat('0', 64),
                    now(),
                    1,
                    :metric_code,
                    :display_name,
                    NULL,
                    'active',
                    CAST(:created_by AS uuid)
                )
                """
            ),
            {
                "tenant_id": seed_tenant,
                "id": str(uuid.uuid4()),
                "metric_code": metric,
                "display_name": metric.replace("_", " ").title(),
                "created_by": seed_user,
            },
        )

    for dimension in CANONICAL_DIMENSIONS:
        conn.execute(
            sa.text(
                """
                INSERT INTO mis_canonical_dimension_dictionary
                (
                    id, tenant_id, chain_hash, previous_hash, created_at,
                    version_no, dimension_code, display_name, description, status,
                    created_by
                )
                VALUES (
                    CAST(:id AS uuid),
                    CAST(:tenant_id AS uuid),
                    repeat('0', 64),
                    repeat('0', 64),
                    now(),
                    1,
                    :dimension_code,
                    :display_name,
                    NULL,
                    'active',
                    CAST(:created_by AS uuid)
                )
                """
            ),
            {
                "tenant_id": seed_tenant,
                "id": str(uuid.uuid4()),
                "dimension_code": dimension,
                "display_name": dimension.replace("_", " ").title(),
                "created_by": seed_user,
            },
        )

    rls_tables = [
        "mis_template_versions",
        "mis_template_sections",
        "mis_template_columns",
        "mis_template_row_mappings",
        "mis_data_snapshots",
        "mis_normalized_lines",
        "mis_ingestion_exceptions",
        "mis_drift_events",
        "mis_canonical_metric_dictionary",
        "mis_canonical_dimension_dictionary",
    ]
    for table_name in rls_tables:
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
    append_only_tables = [
        "mis_templates",
        "mis_uploads",
        "mis_template_versions",
        "mis_template_sections",
        "mis_template_columns",
        "mis_template_row_mappings",
        "mis_data_snapshots",
        "mis_normalized_lines",
        "mis_ingestion_exceptions",
        "mis_drift_events",
        "mis_canonical_metric_dictionary",
        "mis_canonical_dimension_dictionary",
    ]
    for table_name in append_only_tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_mis_template_versions_validate_supersession "
        "ON mis_template_versions"
    )
    op.execute("DROP FUNCTION IF EXISTS mis_template_versions_validate_supersession()")

    drop_order = [
        "mis_canonical_dimension_dictionary",
        "mis_canonical_metric_dictionary",
        "mis_drift_events",
        "mis_ingestion_exceptions",
        "mis_normalized_lines",
        "mis_data_snapshots",
        "mis_template_row_mappings",
        "mis_template_columns",
        "mis_template_sections",
        "mis_template_versions",
    ]
    for table_name in drop_order:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)

    op.drop_index("idx_mis_templates_template_code", table_name="mis_templates")
    op.drop_constraint("ck_mis_templates_status", "mis_templates", type_="check")
    op.drop_constraint(
        "uq_mis_templates_tenant_template_code", "mis_templates", type_="unique"
    )

    op.drop_column("mis_templates", "status")
    op.drop_column("mis_templates", "template_type")
    op.drop_column("mis_templates", "template_name")
    op.drop_column("mis_templates", "template_code")
    op.drop_column("mis_templates", "organisation_id")
