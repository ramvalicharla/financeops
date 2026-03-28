"""coa_crosswalk_external_ref_extension

Revision ID: 0091_coa_crosswalk_external_ref
Revises: 0090_entity_id_cat1_remaining
Create Date: 2026-03-28

Creates erp_account_external_refs for connector-specific external account references.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0091_coa_crosswalk_external_ref"
down_revision: str | None = "0090_entity_id_cat1_remaining"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "erp_account_external_refs",
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("mapping_id", UUID(as_uuid=True), nullable=False),
        sa.Column("connector_type", sa.String(length=32), nullable=False),
        sa.Column("external_account_id", sa.String(length=256), nullable=False),
        sa.Column("external_account_code", sa.String(length=128), nullable=True),
        sa.Column("external_account_name", sa.String(length=256), nullable=True),
        sa.Column("internal_account_code", sa.String(length=32), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_version_token", sa.String(length=256), nullable=True),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("stale_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("chain_hash", sa.String(length=64), nullable=True),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["mapping_id"],
            ["external_mapping_definitions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "mapping_id",
            "connector_type",
            "external_account_id",
            name="uq_erp_account_ref_per_connector",
        ),
    )

    op.create_index(
        "ix_erp_account_external_refs_tenant",
        "erp_account_external_refs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_erp_account_external_refs_mapping",
        "erp_account_external_refs",
        ["mapping_id"],
    )
    op.create_index(
        "ix_erp_account_external_refs_connector",
        "erp_account_external_refs",
        ["tenant_id", "connector_type"],
    )
    op.create_index(
        "ix_erp_account_external_refs_stale",
        "erp_account_external_refs",
        ["tenant_id", "is_stale"],
        postgresql_where=sa.text("is_stale = true"),
    )
    op.create_index(
        "ix_erp_account_external_refs_internal_code",
        "erp_account_external_refs",
        ["tenant_id", "connector_type", "internal_account_code"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_erp_account_external_refs_internal_code",
        table_name="erp_account_external_refs",
    )
    op.drop_index(
        "ix_erp_account_external_refs_stale",
        table_name="erp_account_external_refs",
    )
    op.drop_index(
        "ix_erp_account_external_refs_connector",
        table_name="erp_account_external_refs",
    )
    op.drop_index(
        "ix_erp_account_external_refs_mapping",
        table_name="erp_account_external_refs",
    )
    op.drop_index(
        "ix_erp_account_external_refs_tenant",
        table_name="erp_account_external_refs",
    )
    op.drop_table("erp_account_external_refs")
