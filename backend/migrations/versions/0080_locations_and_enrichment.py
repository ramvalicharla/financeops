"""locations master + tenant/entity enrichment.

Revision ID: 0080_locations_and_enrichment
Revises: 0079_invoice_classifier
Create Date: 2026-03-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0080_locations_and_enrichment"
down_revision: str | None = "0079_invoice_classifier"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_expr() -> str:
    return (
        "COALESCE(NULLIF(current_setting('app.tenant_id', true), ''), "
        "NULLIF(current_setting('app.current_tenant_id', true), ''))::uuid"
    )


def _enable_tenant_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table_name}_tenant_isolation ON {table_name} "
        f"USING (tenant_id = {_tenant_expr()})"
    )


def upgrade() -> None:
    op.add_column("iam_tenants", sa.Column("pan", sa.String(length=20), nullable=True))
    op.add_column("iam_tenants", sa.Column("gstin", sa.String(length=20), nullable=True))
    op.add_column("iam_tenants", sa.Column("state_code", sa.String(length=5), nullable=True))

    op.add_column("cp_entities", sa.Column("pan", sa.String(length=20), nullable=True))
    op.add_column("cp_entities", sa.Column("tan", sa.String(length=20), nullable=True))
    op.add_column("cp_entities", sa.Column("cin", sa.String(length=30), nullable=True))
    op.add_column("cp_entities", sa.Column("gstin", sa.String(length=20), nullable=True))
    op.add_column("cp_entities", sa.Column("lei", sa.String(length=30), nullable=True))
    op.add_column("cp_entities", sa.Column("fiscal_year_start", sa.Integer(), nullable=True))
    op.add_column("cp_entities", sa.Column("applicable_gaap", sa.String(length=20), nullable=True))
    op.add_column("cp_entities", sa.Column("tax_rate", sa.Numeric(5, 4), nullable=True))
    op.add_column("cp_entities", sa.Column("state_code", sa.String(length=5), nullable=True))
    op.add_column("cp_entities", sa.Column("registered_address", sa.Text(), nullable=True))
    op.add_column("cp_entities", sa.Column("city", sa.String(length=100), nullable=True))
    op.add_column("cp_entities", sa.Column("pincode", sa.String(length=10), nullable=True))

    op.create_table(
        "cp_locations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_name", sa.String(length=200), nullable=False),
        sa.Column("location_code", sa.String(length=50), nullable=False),
        sa.Column("gstin", sa.String(length=20), nullable=True),
        sa.Column("state_code", sa.String(length=5), nullable=True),
        sa.Column("address_line1", sa.String(length=300), nullable=True),
        sa.Column("address_line2", sa.String(length=300), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("pincode", sa.String(length=10), nullable=True),
        sa.Column("country_code", sa.String(length=3), nullable=False, server_default=sa.text("'IND'")),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "entity_id",
            "location_code",
            name="uq_cp_locations_tenant_entity_code",
        ),
    )
    op.create_index("idx_cp_locations_tenant_id", "cp_locations", ["tenant_id"], unique=False)
    op.create_index("idx_cp_locations_entity_id", "cp_locations", ["entity_id"], unique=False)

    op.create_table(
        "cp_cost_centres",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cost_centre_code", sa.String(length=50), nullable=False),
        sa.Column("cost_centre_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["iam_tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["cp_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["cp_cost_centres.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "entity_id",
            "cost_centre_code",
            name="uq_cp_cost_centres_tenant_entity_code",
        ),
    )
    op.create_index("idx_cp_cost_centres_tenant_id", "cp_cost_centres", ["tenant_id"], unique=False)
    op.create_index("idx_cp_cost_centres_entity_id", "cp_cost_centres", ["entity_id"], unique=False)
    op.create_index("idx_cp_cost_centres_parent_id", "cp_cost_centres", ["parent_id"], unique=False)

    # Tenant/entity state code backfill from existing GSTIN values.
    op.execute(
        """
        UPDATE iam_tenants
        SET state_code = SUBSTRING(gstin FROM 1 FOR 2)
        WHERE gstin IS NOT NULL
          AND LENGTH(gstin) = 15
          AND (state_code IS NULL OR state_code = '')
        """
    )
    op.execute(
        """
        UPDATE cp_entities
        SET state_code = SUBSTRING(gstin FROM 1 FOR 2)
        WHERE gstin IS NOT NULL
          AND LENGTH(gstin) = 15
          AND (state_code IS NULL OR state_code = '')
        """
    )

    # Copy enrichment data from org_entities where cp_entity_id linkage exists.
    op.execute(
        """
        UPDATE cp_entities AS c
        SET
            pan = COALESCE(c.pan, o.pan),
            tan = COALESCE(c.tan, o.tan),
            cin = COALESCE(c.cin, o.cin),
            gstin = COALESCE(c.gstin, o.gstin),
            lei = COALESCE(c.lei, o.lei),
            fiscal_year_start = COALESCE(c.fiscal_year_start, o.fiscal_year_start),
            applicable_gaap = COALESCE(c.applicable_gaap, o.applicable_gaap),
            tax_rate = COALESCE(c.tax_rate, o.tax_rate),
            state_code = COALESCE(c.state_code, o.state_code, SUBSTRING(o.gstin FROM 1 FOR 2))
        FROM org_entities AS o
        WHERE c.id = o.cp_entity_id
          AND c.tenant_id = o.tenant_id
        """
    )

    _enable_tenant_rls("cp_locations")
    _enable_tenant_rls("cp_cost_centres")


def downgrade() -> None:
    op.drop_index("idx_cp_cost_centres_parent_id", table_name="cp_cost_centres")
    op.drop_index("idx_cp_cost_centres_entity_id", table_name="cp_cost_centres")
    op.drop_index("idx_cp_cost_centres_tenant_id", table_name="cp_cost_centres")
    op.drop_table("cp_cost_centres")

    op.drop_index("idx_cp_locations_entity_id", table_name="cp_locations")
    op.drop_index("idx_cp_locations_tenant_id", table_name="cp_locations")
    op.drop_table("cp_locations")

    op.drop_column("cp_entities", "pincode")
    op.drop_column("cp_entities", "city")
    op.drop_column("cp_entities", "registered_address")
    op.drop_column("cp_entities", "state_code")
    op.drop_column("cp_entities", "tax_rate")
    op.drop_column("cp_entities", "applicable_gaap")
    op.drop_column("cp_entities", "fiscal_year_start")
    op.drop_column("cp_entities", "lei")
    op.drop_column("cp_entities", "gstin")
    op.drop_column("cp_entities", "cin")
    op.drop_column("cp_entities", "tan")
    op.drop_column("cp_entities", "pan")

    op.drop_column("iam_tenants", "state_code")
    op.drop_column("iam_tenants", "gstin")
    op.drop_column("iam_tenants", "pan")

