"""Allow anomaly statistical rule updates for threshold management.

Revision ID: 0110_anomaly_threshold_mutable
Revises: 0109_saas_platformization_layer
Create Date: 2026-04-03 00:15:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from financeops.db.append_only import (
    append_only_function_sql,
    create_trigger_sql,
    drop_trigger_sql,
)

revision: str = "0110_anomaly_threshold_mutable"
down_revision: str | None = "0109_saas_platformization_layer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(drop_trigger_sql("anomaly_statistical_rules"))


def downgrade() -> None:
    op.execute(append_only_function_sql())
    op.execute(create_trigger_sql("anomaly_statistical_rules"))
