"""retarget external ref uniqueness

Revision ID: 0136_retarget_ext_ref
Revises: 0135_delivery_log_idem
Create Date: 2026-04-16 01:08:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "0136_retarget_ext_ref"
down_revision = "0135_delivery_log_idem"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_gl_entries_tenant_source_ref", "gl_entries", type_="unique")
    op.create_unique_constraint(
        "uq_accounting_jv_external_ref_per_tenant",
        "accounting_jv_aggregates",
        ["tenant_id", "external_reference_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_accounting_jv_external_ref_per_tenant",
        "accounting_jv_aggregates",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_gl_entries_tenant_source_ref",
        "gl_entries",
        ["tenant_id", "source_ref"],
    )
