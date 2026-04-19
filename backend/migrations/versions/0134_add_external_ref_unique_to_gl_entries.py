"""add external ref unique to gl entries

Revision ID: 0134_gl_src_ref_unique
Revises: 0133_coa_batch_confirm
Create Date: 2026-04-16 23:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0134_gl_src_ref_unique"
down_revision = "0133_coa_batch_confirm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_gl_entries_tenant_source_ref",
        "gl_entries",
        ["tenant_id", "source_ref"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_gl_entries_tenant_source_ref", "gl_entries", type_="unique")
