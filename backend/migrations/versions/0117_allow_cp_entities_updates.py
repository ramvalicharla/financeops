"""allow_cp_entities_updates

Revision ID: 0117_cp_entities_mutable
Revises: 0116_invoice_cls_mutable
Create Date: 2026-04-03

cp_entities are updated during onboarding profile completion (for example GSTIN).
Drop default append-only trigger on cp_entities.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)


revision: str = "0117_cp_entities_mutable"
down_revision: str | None = "0116_invoice_cls_mutable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(drop_trigger_sql("cp_entities"))


def downgrade() -> None:
    op.execute(append_only_function_sql())
    op.execute(drop_trigger_sql("cp_entities"))
    op.execute(create_trigger_sql("cp_entities"))

