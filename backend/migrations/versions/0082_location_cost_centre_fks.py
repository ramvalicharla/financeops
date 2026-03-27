"""add location and cost-centre foreign keys to key modules.

Revision ID: 0082_location_cost_centre_fks
Revises: 0081_entity_id_backfill
Create Date: 2026-03-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0082_location_cost_centre_fks"
down_revision: str | None = "0081_entity_id_backfill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _add_column_if_missing(table_name: str, column_name: str) -> None:
    if not _column_exists(table_name, column_name):
        op.add_column(
            table_name,
            sa.Column(column_name, postgresql.UUID(as_uuid=True), nullable=True),
        )


def _create_fk_if_missing(
    table_name: str,
    fk_name: str,
    local_column: str,
    remote_table: str,
    remote_column: str,
    *,
    ondelete: str | None = "SET NULL",
) -> None:
    if _constraint_exists(fk_name):
        return
    op.create_foreign_key(
        fk_name,
        table_name,
        remote_table,
        [local_column],
        [remote_column],
        ondelete=ondelete,
    )


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if not _index_exists(index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if _index_exists(index_name):
        op.drop_index(index_name, table_name=table_name)


def _drop_fk_if_exists(table_name: str, fk_name: str) -> None:
    if _constraint_exists(fk_name):
        op.drop_constraint(fk_name, table_name, type_="foreignkey")


def _drop_column_if_exists(table_name: str, column_name: str) -> None:
    if _column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def _apply_columns(table_name: str, *, ondelete: str | None = "SET NULL") -> None:
    _add_column_if_missing(table_name, "location_id")
    _add_column_if_missing(table_name, "cost_centre_id")

    _create_fk_if_missing(
        table_name,
        f"fk_{table_name}_location_id_cp_locations",
        "location_id",
        "cp_locations",
        "id",
        ondelete=ondelete,
    )
    _create_fk_if_missing(
        table_name,
        f"fk_{table_name}_cost_centre_id_cp_cost_centres",
        "cost_centre_id",
        "cp_cost_centres",
        "id",
        ondelete=ondelete,
    )


def _revert_columns(table_name: str) -> None:
    _drop_fk_if_exists(table_name, f"fk_{table_name}_cost_centre_id_cp_cost_centres")
    _drop_fk_if_exists(table_name, f"fk_{table_name}_location_id_cp_locations")
    _drop_column_if_exists(table_name, "cost_centre_id")
    _drop_column_if_exists(table_name, "location_id")


def upgrade() -> None:
    _apply_columns("expense_claims", ondelete="SET NULL")
    _create_index_if_missing("expense_claims", "idx_expense_claims_location_id", ["location_id"])
    _create_index_if_missing("expense_claims", "idx_expense_claims_cost_centre_id", ["cost_centre_id"])

    _apply_columns("fa_assets", ondelete="SET NULL")
    _create_index_if_missing("fa_assets", "idx_fa_assets_location_id", ["location_id"])
    _create_index_if_missing("fa_assets", "idx_fa_assets_cost_centre_id", ["cost_centre_id"])

    _apply_columns("prepaid_schedules", ondelete="SET NULL")
    _create_index_if_missing("prepaid_schedules", "idx_prepaid_schedules_location_id", ["location_id"])
    _create_index_if_missing("prepaid_schedules", "idx_prepaid_schedules_cost_centre_id", ["cost_centre_id"])

    _apply_columns("gst_returns", ondelete="SET NULL")
    _apply_columns("bank_statements", ondelete="SET NULL")

    _apply_columns("cash_flow_forecast_runs", ondelete="SET NULL")
    _create_index_if_missing(
        "cash_flow_forecast_runs",
        "idx_cash_flow_forecast_runs_location_id",
        ["location_id"],
    )
    _create_index_if_missing(
        "cash_flow_forecast_runs",
        "idx_cash_flow_forecast_runs_cost_centre_id",
        ["cost_centre_id"],
    )


def downgrade() -> None:
    _drop_index_if_exists("cash_flow_forecast_runs", "idx_cash_flow_forecast_runs_cost_centre_id")
    _drop_index_if_exists("cash_flow_forecast_runs", "idx_cash_flow_forecast_runs_location_id")
    _revert_columns("cash_flow_forecast_runs")

    _revert_columns("bank_statements")
    _revert_columns("gst_returns")

    _drop_index_if_exists("prepaid_schedules", "idx_prepaid_schedules_cost_centre_id")
    _drop_index_if_exists("prepaid_schedules", "idx_prepaid_schedules_location_id")
    _revert_columns("prepaid_schedules")

    _drop_index_if_exists("fa_assets", "idx_fa_assets_cost_centre_id")
    _drop_index_if_exists("fa_assets", "idx_fa_assets_location_id")
    _revert_columns("fa_assets")

    _drop_index_if_exists("expense_claims", "idx_expense_claims_cost_centre_id")
    _drop_index_if_exists("expense_claims", "idx_expense_claims_location_id")
    _revert_columns("expense_claims")
