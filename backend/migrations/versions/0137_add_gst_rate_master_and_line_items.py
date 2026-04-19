"""add gst rate master and return line items

Revision ID: 0137_gst_rate_master
Revises: 0136_retarget_ext_ref
Create Date: 2026-04-16 03:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "0137_gst_rate_master"
down_revision: str | None = "0136_retarget_ext_ref"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gst_rate_master",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("rate", sa.Numeric(10, 4), nullable=False),
        sa.Column("description", sa.String(length=128), nullable=True),
        sa.UniqueConstraint("rate", name="uq_gst_rate_master_rate"),
    )
    op.create_index("idx_gst_rate_master_rate", "gst_rate_master", ["rate"], unique=False)

    rate_master = sa.table(
        "gst_rate_master",
        sa.column("rate", sa.Numeric(10, 4)),
        sa.column("description", sa.String(length=128)),
    )
    op.bulk_insert(
        rate_master,
        [
            {"rate": Decimal("0"), "description": "Zero rate"},
            {"rate": Decimal("1.5"), "description": "Cut and polished diamonds"},
            {"rate": Decimal("3"), "description": "Gold and jewellery"},
            {"rate": Decimal("5"), "description": "Reduced rate"},
            {"rate": Decimal("7.5"), "description": "Special reduced rate"},
            {"rate": Decimal("12"), "description": "Standard reduced rate"},
            {"rate": Decimal("18"), "description": "Standard rate"},
            {"rate": Decimal("28"), "description": "Highest slab"},
        ],
    )

    op.create_table(
        "gst_return_line_items",
        sa.Column("gst_return_id", sa.UUID(), sa.ForeignKey("gst_returns.id"), nullable=False),
        sa.Column("return_type", sa.String(length=20), nullable=False),
        sa.Column("supplier_gstin", sa.String(length=20), nullable=False),
        sa.Column("invoice_number", sa.String(length=128), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("taxable_value", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("igst_amount", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("cgst_amount", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("sgst_amount", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("cess_amount", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("total_tax", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("gst_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("payment_status", sa.String(length=32), nullable=True),
        sa.Column("expense_category", sa.String(length=64), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("chain_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_gst_return_line_items_return",
        "gst_return_line_items",
        ["tenant_id", "gst_return_id"],
        unique=False,
    )
    op.create_index(
        "idx_gst_return_line_items_invoice",
        "gst_return_line_items",
        ["tenant_id", "supplier_gstin", "invoice_number"],
        unique=False,
    )

    op.add_column("gst_recon_items", sa.Column("line_item_a_id", sa.UUID(), nullable=True))
    op.add_column("gst_recon_items", sa.Column("line_item_b_id", sa.UUID(), nullable=True))
    op.add_column("gst_recon_items", sa.Column("supplier_gstin", sa.String(length=20), nullable=True))
    op.add_column("gst_recon_items", sa.Column("invoice_number", sa.String(length=128), nullable=True))
    op.add_column("gst_recon_items", sa.Column("invoice_date", sa.Date(), nullable=True))
    op.add_column("gst_recon_items", sa.Column("gst_rate", sa.Numeric(10, 4), nullable=True))
    op.add_column(
        "gst_recon_items",
        sa.Column("rate_mismatch", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("gst_recon_items", sa.Column("match_type", sa.String(length=32), nullable=True))
    op.add_column("gst_recon_items", sa.Column("itc_eligible", sa.Boolean(), nullable=True))
    op.add_column("gst_recon_items", sa.Column("itc_blocked_reason", sa.String(length=128), nullable=True))
    op.add_column(
        "gst_recon_items",
        sa.Column("reverse_itc", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_foreign_key(
        "fk_gst_recon_items_line_item_a",
        "gst_recon_items",
        "gst_return_line_items",
        ["line_item_a_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_gst_recon_items_line_item_b",
        "gst_recon_items",
        "gst_return_line_items",
        ["line_item_b_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_gst_recon_items_line_item_b", "gst_recon_items", type_="foreignkey")
    op.drop_constraint("fk_gst_recon_items_line_item_a", "gst_recon_items", type_="foreignkey")
    op.drop_column("gst_recon_items", "reverse_itc")
    op.drop_column("gst_recon_items", "itc_blocked_reason")
    op.drop_column("gst_recon_items", "itc_eligible")
    op.drop_column("gst_recon_items", "match_type")
    op.drop_column("gst_recon_items", "rate_mismatch")
    op.drop_column("gst_recon_items", "gst_rate")
    op.drop_column("gst_recon_items", "invoice_date")
    op.drop_column("gst_recon_items", "invoice_number")
    op.drop_column("gst_recon_items", "supplier_gstin")
    op.drop_column("gst_recon_items", "line_item_b_id")
    op.drop_column("gst_recon_items", "line_item_a_id")

    op.drop_index("idx_gst_return_line_items_invoice", table_name="gst_return_line_items")
    op.drop_index("idx_gst_return_line_items_return", table_name="gst_return_line_items")
    op.drop_table("gst_return_line_items")

    op.drop_index("idx_gst_rate_master_rate", table_name="gst_rate_master")
    op.drop_table("gst_rate_master")
