"""allow_ppa_allocation_updates

Revision ID: 0118_ppa_alloc_mutable
Revises: 0117_cp_entities_mutable
Create Date: 2026-04-03

PPA allocations are updated during goodwill/deferred-tax recomputation in the
same lifecycle run. Drop default append-only trigger on ppa_allocations.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)


revision: str = "0118_ppa_alloc_mutable"
down_revision: str | None = "0117_cp_entities_mutable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(drop_trigger_sql("ppa_allocations"))


def downgrade() -> None:
    op.execute(append_only_function_sql())
    op.execute(drop_trigger_sql("ppa_allocations"))
    op.execute(create_trigger_sql("ppa_allocations"))

