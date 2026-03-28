"""entity_id backfill: accounting layer pre-blockers

Adds entity_id (nullable, indexed, FK to cp_entities)
to ERP sync source tables and reconciliation tables
that will be referenced by the accounting layer.

All columns: nullable=True - no data backfill required.

Revision ID: 0083_entity_id_blockers
Revises: 0082_location_cost_centre_fks
Create Date: 2026-03-28
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0083_entity_id_blockers"
down_revision: str | None = "0082_location_cost_centre_fks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ERP_SYNC_TABLES: list[str] = [
    "external_raw_snapshots",
    "external_normalized_snapshots",
    "external_mapping_definitions",
    "external_mapping_versions",
    "external_sync_errors",
    "external_sync_publish_events",
    "external_sync_evidence_links",
]

RECON_TABLES: list[str] = [
    "gl_entries",
    "trial_balance_rows",
    "recon_items",
    "reconciliation_lines",
    "reconciliation_exceptions",
]


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    return (
        bind.execute(sa.text("SELECT to_regclass(:name)"), {"name": index_name}).scalar_one_or_none()
        is not None
    )


def _constraint_exists(constraint_name: str) -> bool:
    bind = op.get_bind()
    return (
        bind.execute(
            sa.text("SELECT 1 FROM pg_constraint WHERE conname = :name LIMIT 1"),
            {"name": constraint_name},
        ).scalar_one_or_none()
        is not None
    )


def _has_tenant_id(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(col["name"] == "tenant_id" for col in inspector.get_columns(table_name))


def _add_entity_scope(table_name: str) -> None:
    if not _table_exists(table_name):
        # Table name mismatch guard: skip this table safely.
        return

    if not _column_exists(table_name, "entity_id"):
        op.add_column(
            table_name,
            sa.Column(
                "entity_id",
                UUID(as_uuid=True),
                nullable=True,
                comment="Entity scope for multi-entity tenants",
            ),
        )
    else:
        # entity_id already present on this table; skip add_column.
        return

    entity_idx = f"ix_{table_name}_entity_id"
    if not _index_exists(entity_idx):
        op.create_index(entity_idx, table_name, ["entity_id"])

    tenant_entity_idx = f"ix_{table_name}_tenant_entity"
    if _has_tenant_id(table_name) and not _index_exists(tenant_entity_idx):
        op.create_index(tenant_entity_idx, table_name, ["tenant_id", "entity_id"])
    # If tenant_id is absent, intentionally skip composite index.

    fk_name = f"fk_{table_name[:45]}_entity_id"
    if not _constraint_exists(fk_name):
        op.create_foreign_key(
            fk_name,
            table_name,
            "cp_entities",
            ["entity_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def _drop_entity_scope(table_name: str) -> None:
    if not _table_exists(table_name):
        return

    if not _column_exists(table_name, "entity_id"):
        return

    fk_name = f"fk_{table_name[:45]}_entity_id"
    if _constraint_exists(fk_name):
        op.drop_constraint(fk_name, table_name, type_="foreignkey")

    tenant_entity_idx = f"ix_{table_name}_tenant_entity"
    if _index_exists(tenant_entity_idx):
        op.drop_index(tenant_entity_idx, table_name=table_name)

    entity_idx = f"ix_{table_name}_entity_id"
    if _index_exists(entity_idx):
        op.drop_index(entity_idx, table_name=table_name)

    op.drop_column(table_name, "entity_id")


def upgrade() -> None:
    # ERP sync source tables
    for table in ERP_SYNC_TABLES:
        _add_entity_scope(table)

    # Reconciliation tables
    for table in RECON_TABLES:
        _add_entity_scope(table)


def downgrade() -> None:
    for table in [
        "reconciliation_exceptions",
        "reconciliation_lines",
        "recon_items",
        "trial_balance_rows",
        "gl_entries",
        "external_sync_evidence_links",
        "external_sync_publish_events",
        "external_sync_errors",
        "external_mapping_versions",
        "external_mapping_definitions",
        "external_normalized_snapshots",
        "external_raw_snapshots",
    ]:
        _drop_entity_scope(table)
