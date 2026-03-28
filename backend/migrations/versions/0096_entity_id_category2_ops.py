"""entity_id_category2_ops_batch3

Revision ID: 0096_entity_id_cat2_ops
Revises: 0094_entity_id_cat2_consolidatn
Create Date: 2026-03-29

Adds nullable entity_id UUID FK (cp_entities.id) to:
  - anomaly_runs
  - anomaly_results
  - monthend_checklists

Skipped by design:
  anomaly_* rule/config/child tables and monthend_tasks.
  equity.py, fx.py, payroll.py are not present in this codebase.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0096_entity_id_cat2_ops"
down_revision: str | None = "0094_entity_id_cat2_consolidatn"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES: tuple[str, ...] = (
    "anomaly_runs",
    "anomaly_results",
    "monthend_checklists",
)


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    return (
        bind.execute(sa.text("SELECT to_regclass(:name)"), {"name": index_name}).scalar_one_or_none()
        is not None
    )


def upgrade() -> None:
    for table_name in _TABLES:
        if not _column_exists(table_name, "entity_id"):
            op.add_column(
                table_name,
                sa.Column(
                    "entity_id",
                    UUID(as_uuid=True),
                    sa.ForeignKey("cp_entities.id", ondelete="SET NULL"),
                    nullable=True,
                ),
            )

        index_name = f"ix_{table_name}_entity_id"
        if not _index_exists(index_name):
            op.create_index(index_name, table_name, ["entity_id"])


def downgrade() -> None:
    for table_name in reversed(_TABLES):
        index_name = f"ix_{table_name}_entity_id"
        if _index_exists(index_name):
            op.drop_index(index_name, table_name=table_name)
        if _column_exists(table_name, "entity_id"):
            op.drop_column(table_name, "entity_id")

