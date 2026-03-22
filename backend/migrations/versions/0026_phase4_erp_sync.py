"""Phase 4C ERP Sync Kernel

Revision ID: 0026_phase4_erp_sync
Revises: 0025_phase3_observability_engine
Create Date: 2026-03-11 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql

revision: str = "0026_phase4_erp_sync"
down_revision: str | None = "0025_phase3_observability_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base_cols() -> list[sa.Column]:
    return [
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
    ]


def _create(name: str, extra: list[sa.Column], *args: sa.Constraint) -> None:
    op.create_table(name, *_base_cols(), *extra, sa.PrimaryKeyConstraint("id"), *args)


def upgrade() -> None:
    _create(
        "external_connections",
        [
            sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("connector_type", sa.String(length=64), nullable=False),
            sa.Column("connection_code", sa.String(length=128), nullable=False),
            sa.Column("connection_name", sa.String(length=255), nullable=False),
            sa.Column("source_system_instance_id", sa.String(length=255), nullable=False),
            sa.Column("data_residency_region", sa.String(length=64), nullable=False, server_default="in"),
            sa.Column("pii_masking_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("consent_reference", sa.String(length=255), nullable=True),
            sa.Column("pinned_connector_version", sa.String(length=64), nullable=True),
            sa.Column("connection_status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("secret_ref", sa.String(length=255), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.UniqueConstraint("tenant_id", "connection_code", name="uq_external_connections_code"),
        sa.CheckConstraint(
            "connection_status IN ('draft','active','suspended','revoked')",
            name="ck_external_connections_status",
        ),
    )
    op.create_index(
        "idx_external_connections_lookup",
        "external_connections",
        ["tenant_id", "organisation_id", "connection_status", "created_at"],
    )

    _create(
        "external_connection_versions",
        [
            sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("version_token", sa.String(length=64), nullable=False),
            sa.Column(
                "config_snapshot_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["connection_id"], ["external_connections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["external_connection_versions.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "tenant_id",
            "connection_id",
            "version_no",
            name="uq_external_connection_versions_number",
        ),
    )

    _create(
        "external_sync_definitions",
        [
            sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("definition_code", sa.String(length=128), nullable=False),
            sa.Column("definition_name", sa.String(length=255), nullable=False),
            sa.Column("dataset_type", sa.String(length=128), nullable=False),
            sa.Column("sync_mode", sa.String(length=32), nullable=False, server_default="full"),
            sa.Column("definition_status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["connection_id"], ["external_connections.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "definition_code",
            name="uq_external_sync_definitions_code",
        ),
    )

    _create(
        "external_sync_definition_versions",
        [
            sa.Column("sync_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("version_token", sa.String(length=64), nullable=False),
            sa.Column(
                "period_resolution_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column(
                "extraction_scope_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(
            ["sync_definition_id"], ["external_sync_definitions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["external_sync_definition_versions.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "sync_definition_id",
            "version_no",
            name="uq_external_sync_definition_versions_number",
        ),
    )

    _create(
        "external_sync_runs",
        [
            sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("sync_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("sync_definition_version_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("dataset_type", sa.String(length=128), nullable=False),
            sa.Column("reporting_period_label", sa.String(length=64), nullable=True),
            sa.Column("run_token", sa.String(length=64), nullable=False),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("run_status", sa.String(length=32), nullable=False, server_default="created"),
            sa.Column("raw_snapshot_payload_hash", sa.String(length=64), nullable=True),
            sa.Column("mapping_version_token", sa.String(length=64), nullable=True),
            sa.Column("normalization_version", sa.String(length=64), nullable=True),
            sa.Column(
                "validation_summary_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("extraction_total_records", sa.Integer(), nullable=True),
            sa.Column("extraction_fetched_records", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("extraction_checkpoint", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("extraction_chunk_size", sa.Integer(), nullable=False, server_default="500"),
            sa.Column("is_resumable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("resumed_from_run_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["connection_id"], ["external_connections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["sync_definition_id"], ["external_sync_definitions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["sync_definition_version_id"],
            ["external_sync_definition_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["resumed_from_run_id"], ["external_sync_runs.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "run_token", name="uq_external_sync_runs_run_token"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_external_sync_runs_idempotency"),
    )

    _create(
        "external_raw_snapshots",
        [
            sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("snapshot_token", sa.String(length=64), nullable=False),
            sa.Column("storage_ref", sa.String(length=512), nullable=False),
            sa.Column("payload_hash", sa.String(length=64), nullable=False),
            sa.Column("payload_size_bytes", sa.Integer(), nullable=False),
            sa.Column("frozen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["sync_run_id"], ["external_sync_runs.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "snapshot_token", name="uq_external_raw_snapshots_token"),
    )

    _create(
        "external_normalized_snapshots",
        [
            sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("dataset_type", sa.String(length=128), nullable=False),
            sa.Column("snapshot_token", sa.String(length=64), nullable=False),
            sa.Column("storage_ref", sa.String(length=512), nullable=False),
            sa.Column("canonical_payload_hash", sa.String(length=64), nullable=False),
            sa.Column("frozen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["sync_run_id"], ["external_sync_runs.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "tenant_id", "snapshot_token", name="uq_external_normalized_snapshots_token"
        ),
    )

    _create(
        "external_mapping_definitions",
        [
            sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("mapping_code", sa.String(length=128), nullable=False),
            sa.Column("mapping_name", sa.String(length=255), nullable=False),
            sa.Column("dataset_type", sa.String(length=128), nullable=False),
            sa.Column("mapping_status", sa.String(length=32), nullable=False, server_default="draft"),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "mapping_code",
            name="uq_external_mapping_definitions_code",
        ),
    )

    _create(
        "external_mapping_versions",
        [
            sa.Column("mapping_definition_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("version_token", sa.String(length=64), nullable=False),
            sa.Column(
                "mapping_payload_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="candidate"),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(
            ["mapping_definition_id"], ["external_mapping_definitions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["supersedes_id"], ["external_mapping_versions.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "tenant_id",
            "mapping_definition_id",
            "version_no",
            name="uq_external_mapping_versions_no",
        ),
    )

    _create(
        "external_sync_evidence_links",
        [
            sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("evidence_type", sa.String(length=64), nullable=False),
            sa.Column("evidence_ref", sa.Text(), nullable=False),
            sa.Column("evidence_label", sa.String(length=255), nullable=False),
            sa.Column(
                "evidence_payload_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["sync_run_id"], ["external_sync_runs.id"], ondelete="RESTRICT"),
    )

    _create(
        "external_sync_errors",
        [
            sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("error_code", sa.String(length=128), nullable=False),
            sa.Column("severity", sa.String(length=16), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column(
                "details_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["sync_run_id"], ["external_sync_runs.id"], ondelete="RESTRICT"),
    )

    _create(
        "external_sync_publish_events",
        [
            sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("event_status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["sync_run_id"], ["external_sync_runs.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "tenant_id",
            "sync_run_id",
            "idempotency_key",
            name="uq_external_sync_publish_events_idempotency",
        ),
    )

    _create(
        "external_connector_capability_registry",
        [
            sa.Column("connector_type", sa.String(length=64), nullable=False),
            sa.Column("dataset_type", sa.String(length=128), nullable=False),
            sa.Column("supports_full_sync", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "supports_incremental_sync",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "supports_resumable_extraction",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.UniqueConstraint(
            "tenant_id",
            "connector_type",
            "dataset_type",
            name="uq_external_connector_capability_registry",
        ),
    )

    _create(
        "external_connector_version_registry",
        [
            sa.Column("connector_type", sa.String(length=64), nullable=False),
            sa.Column("version", sa.String(length=64), nullable=False),
            sa.Column("checksum", sa.String(length=64), nullable=False),
            sa.Column("release_notes", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("deprecation_date", sa.Date(), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.UniqueConstraint(
            "tenant_id",
            "connector_type",
            "version",
            name="uq_external_connector_version_registry",
        ),
    )

    _create(
        "external_period_locks",
        [
            sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("dataset_type", sa.String(length=128), nullable=False),
            sa.Column("period_key", sa.String(length=64), nullable=False),
            sa.Column("lock_status", sa.String(length=32), nullable=False, server_default="locked"),
            sa.Column("lock_reason", sa.Text(), nullable=True),
            sa.Column("source_sync_run_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["source_sync_run_id"], ["external_sync_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["external_period_locks.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "entity_id",
            "dataset_type",
            "period_key",
            name="uq_external_period_locks_scope_period",
        ),
    )

    _create(
        "external_backdated_modification_alerts",
        [
            sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("period_lock_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("severity", sa.String(length=16), nullable=False),
            sa.Column("alert_status", sa.String(length=16), nullable=False, server_default="open"),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column(
                "details_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["sync_run_id"], ["external_sync_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["period_lock_id"], ["external_period_locks.id"], ondelete="RESTRICT"),
    )

    _create(
        "external_sync_drift_reports",
        [
            sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("drift_detected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("drift_severity", sa.String(length=16), nullable=False, server_default="none"),
            sa.Column("total_variances", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "metrics_checked_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["sync_run_id"], ["external_sync_runs.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "sync_run_id", name="uq_external_sync_drift_reports_run"),
    )

    _create(
        "external_sync_health_alerts",
        [
            sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("dataset_type", sa.String(length=128), nullable=True),
            sa.Column("alert_type", sa.String(length=64), nullable=False),
            sa.Column("alert_status", sa.String(length=16), nullable=False, server_default="open"),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column(
                "payload_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["connection_id"], ["external_connections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sync_run_id"], ["external_sync_runs.id"], ondelete="RESTRICT"),
    )

    _create(
        "external_data_consent_logs",
        [
            sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("consent_reference", sa.String(length=255), nullable=False),
            sa.Column("consent_action", sa.String(length=32), nullable=False),
            sa.Column(
                "consent_payload_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["connection_id"], ["external_connections.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sync_run_id"], ["external_sync_runs.id"], ondelete="RESTRICT"),
    )

    _create(
        "external_sync_sla_configs",
        [
            sa.Column("organisation_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("connection_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("dataset_type", sa.String(length=128), nullable=False),
            sa.Column("sla_hours", sa.Integer(), nullable=False),
            sa.Column("consecutive_failure_threshold", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        ],
        sa.ForeignKeyConstraint(["connection_id"], ["external_connections.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "tenant_id",
            "organisation_id",
            "connection_id",
            "dataset_type",
            name="uq_external_sync_sla_configs_scope",
        ),
    )

    tables = [
        "external_connections",
        "external_connection_versions",
        "external_sync_definitions",
        "external_sync_definition_versions",
        "external_sync_runs",
        "external_raw_snapshots",
        "external_normalized_snapshots",
        "external_mapping_definitions",
        "external_mapping_versions",
        "external_sync_evidence_links",
        "external_sync_errors",
        "external_sync_publish_events",
        "external_connector_capability_registry",
        "external_connector_version_registry",
        "external_period_locks",
        "external_backdated_modification_alerts",
        "external_sync_drift_reports",
        "external_sync_health_alerts",
        "external_data_consent_logs",
        "external_sync_sla_configs",
    ]

    op.execute("ALTER TABLE external_connections ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_connections FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_connections USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_connection_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_connection_versions FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_connection_versions USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_sync_definitions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_sync_definitions FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_sync_definitions USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_sync_definition_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_sync_definition_versions FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_sync_definition_versions USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_sync_runs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_sync_runs FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_sync_runs USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_raw_snapshots ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_raw_snapshots FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_raw_snapshots USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_normalized_snapshots ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_normalized_snapshots FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_normalized_snapshots USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_mapping_definitions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_mapping_definitions FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_mapping_definitions USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_mapping_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_mapping_versions FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_mapping_versions USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_sync_evidence_links ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_sync_evidence_links FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_sync_evidence_links USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_sync_errors ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_sync_errors FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_sync_errors USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_sync_publish_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_sync_publish_events FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_sync_publish_events USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_connector_capability_registry ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_connector_capability_registry FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_connector_capability_registry USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_connector_version_registry ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_connector_version_registry FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_connector_version_registry USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_period_locks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_period_locks FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_period_locks USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_backdated_modification_alerts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_backdated_modification_alerts FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_backdated_modification_alerts USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_sync_drift_reports ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_sync_drift_reports FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_sync_drift_reports USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_sync_health_alerts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_sync_health_alerts FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_sync_health_alerts USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_data_consent_logs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_data_consent_logs FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_data_consent_logs USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")
    op.execute("ALTER TABLE external_sync_sla_configs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE external_sync_sla_configs FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON external_sync_sla_configs USING (tenant_id = COALESCE(current_setting('app.tenant_id', true), current_setting('app.current_tenant_id', true))::uuid)")

    op.execute(append_only_function_sql())
    for table_name in tables:
        op.execute(drop_trigger_sql(table_name))
        op.execute(create_trigger_sql(table_name))

    op.execute(
        """
        INSERT INTO cp_module_registry (
          id, module_code, module_name, engine_context, is_financial_impacting, is_active, created_at
        )
        VALUES (
          'f5f8f2e7-94cc-47ad-a610-3de11c9ae426'::uuid,
          'erp_sync',
          'ERP Sync Kernel',
          'finance',
          true,
          true,
          now()
        )
        ON CONFLICT (module_code) DO NOTHING
        """
    )


def downgrade() -> None:
    tables = [
        "external_sync_sla_configs",
        "external_data_consent_logs",
        "external_sync_health_alerts",
        "external_sync_drift_reports",
        "external_backdated_modification_alerts",
        "external_period_locks",
        "external_connector_version_registry",
        "external_connector_capability_registry",
        "external_sync_publish_events",
        "external_sync_errors",
        "external_sync_evidence_links",
        "external_mapping_versions",
        "external_mapping_definitions",
        "external_normalized_snapshots",
        "external_raw_snapshots",
        "external_sync_runs",
        "external_sync_definition_versions",
        "external_sync_definitions",
        "external_connection_versions",
        "external_connections",
    ]

    for table_name in tables:
        op.execute(drop_trigger_sql(table_name))
        op.drop_table(table_name)

    op.execute("DELETE FROM cp_module_registry WHERE module_code = 'erp_sync'")
