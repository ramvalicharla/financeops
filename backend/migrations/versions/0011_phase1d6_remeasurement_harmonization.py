"""phase1d6 remeasurement harmonization

Revision ID: 0011_phase1d6_remeasurement
Revises: 0010_phase1d5_fixed_assets_core
Create Date: 2026-03-07 13:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0011_phase1d6_remeasurement"
down_revision = "0010_phase1d5_fixed_assets_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "revenue_schedules",
        sa.Column("period_seq", sa.Integer(), nullable=True),
    )
    op.add_column(
        "revenue_schedules",
        sa.Column("schedule_version_token", sa.String(length=64), nullable=False, server_default="root"),
    )
    op.execute(
        """
        UPDATE revenue_schedules
        SET period_seq = ranked.rn
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY run_id, contract_id
                ORDER BY recognition_date, created_at, id
            ) AS rn
            FROM revenue_schedules
        ) AS ranked
        WHERE revenue_schedules.id = ranked.id
        """
    )
    op.alter_column("revenue_schedules", "period_seq", nullable=False)
    op.drop_constraint("uq_revenue_schedules_natural", "revenue_schedules", type_="unique")
    op.create_unique_constraint(
        "uq_revenue_schedules_natural",
        "revenue_schedules",
        ["run_id", "contract_id", "recognition_date", "schedule_version_token"],
    )
    op.create_unique_constraint(
        "uq_revenue_schedules_contract_period_version",
        "revenue_schedules",
        ["run_id", "contract_id", "period_seq", "schedule_version_token"],
    )

    op.add_column(
        "revenue_adjustments",
        sa.Column("idempotency_key", sa.String(length=128), nullable=False, server_default="migrated"),
    )
    op.add_column(
        "revenue_adjustments",
        sa.Column("prior_schedule_version_token", sa.String(length=64), nullable=False, server_default="root"),
    )
    op.add_column(
        "revenue_adjustments",
        sa.Column("new_schedule_version_token", sa.String(length=64), nullable=False, server_default="root"),
    )
    op.create_unique_constraint(
        "uq_revenue_adjustments_idempotent",
        "revenue_adjustments",
        ["run_id", "contract_id", "effective_date", "adjustment_type", "idempotency_key"],
    )

    op.add_column(
        "lease_liability_schedule",
        sa.Column("period_seq", sa.Integer(), nullable=True),
    )
    op.add_column(
        "lease_liability_schedule",
        sa.Column("schedule_version_token", sa.String(length=64), nullable=False, server_default="root"),
    )
    op.execute(
        """
        UPDATE lease_liability_schedule
        SET period_seq = ranked.rn
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY run_id, lease_id
                ORDER BY schedule_date, created_at, id
            ) AS rn
            FROM lease_liability_schedule
        ) AS ranked
        WHERE lease_liability_schedule.id = ranked.id
        """
    )
    op.alter_column("lease_liability_schedule", "period_seq", nullable=False)
    op.drop_constraint("uq_lease_liability_schedule_natural", "lease_liability_schedule", type_="unique")
    op.create_unique_constraint(
        "uq_lease_liability_schedule_natural",
        "lease_liability_schedule",
        ["run_id", "lease_id", "schedule_date", "schedule_version_token"],
    )
    op.create_unique_constraint(
        "uq_lease_liability_schedule_period_version",
        "lease_liability_schedule",
        ["run_id", "lease_id", "period_seq", "schedule_version_token"],
    )

    op.add_column(
        "lease_rou_schedule",
        sa.Column("period_seq", sa.Integer(), nullable=True),
    )
    op.add_column(
        "lease_rou_schedule",
        sa.Column("schedule_version_token", sa.String(length=64), nullable=False, server_default="root"),
    )
    op.execute(
        """
        UPDATE lease_rou_schedule
        SET period_seq = ranked.rn
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY run_id, lease_id
                ORDER BY schedule_date, created_at, id
            ) AS rn
            FROM lease_rou_schedule
        ) AS ranked
        WHERE lease_rou_schedule.id = ranked.id
        """
    )
    op.alter_column("lease_rou_schedule", "period_seq", nullable=False)
    op.drop_constraint("uq_lease_rou_schedule_natural", "lease_rou_schedule", type_="unique")
    op.create_unique_constraint(
        "uq_lease_rou_schedule_natural",
        "lease_rou_schedule",
        ["run_id", "lease_id", "schedule_date", "schedule_version_token"],
    )
    op.create_unique_constraint(
        "uq_lease_rou_schedule_period_version",
        "lease_rou_schedule",
        ["run_id", "lease_id", "period_seq", "schedule_version_token"],
    )

    op.add_column(
        "lease_modifications",
        sa.Column("idempotency_key", sa.String(length=128), nullable=False, server_default="migrated"),
    )
    op.add_column(
        "lease_modifications",
        sa.Column("prior_schedule_version_token", sa.String(length=64), nullable=False, server_default="root"),
    )
    op.add_column(
        "lease_modifications",
        sa.Column("new_schedule_version_token", sa.String(length=64), nullable=False, server_default="root"),
    )
    op.create_unique_constraint(
        "uq_lease_modifications_idempotent",
        "lease_modifications",
        ["run_id", "lease_id", "effective_date", "modification_type", "idempotency_key"],
    )
    op.create_check_constraint(
        "ck_lease_journal_exactly_one_source",
        "lease_journal_entries",
        "(CASE WHEN liability_schedule_id IS NOT NULL THEN 1 ELSE 0 END + "
        " CASE WHEN rou_schedule_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_lease_journal_exactly_one_source", "lease_journal_entries", type_="check")

    op.drop_constraint("uq_lease_modifications_idempotent", "lease_modifications", type_="unique")
    op.drop_column("lease_modifications", "new_schedule_version_token")
    op.drop_column("lease_modifications", "prior_schedule_version_token")
    op.drop_column("lease_modifications", "idempotency_key")

    op.drop_constraint("uq_lease_rou_schedule_period_version", "lease_rou_schedule", type_="unique")
    op.drop_constraint("uq_lease_rou_schedule_natural", "lease_rou_schedule", type_="unique")
    op.create_unique_constraint(
        "uq_lease_rou_schedule_natural",
        "lease_rou_schedule",
        ["run_id", "lease_id", "schedule_date"],
    )
    op.drop_column("lease_rou_schedule", "schedule_version_token")
    op.drop_column("lease_rou_schedule", "period_seq")

    op.drop_constraint("uq_lease_liability_schedule_period_version", "lease_liability_schedule", type_="unique")
    op.drop_constraint("uq_lease_liability_schedule_natural", "lease_liability_schedule", type_="unique")
    op.create_unique_constraint(
        "uq_lease_liability_schedule_natural",
        "lease_liability_schedule",
        ["run_id", "lease_id", "schedule_date"],
    )
    op.drop_column("lease_liability_schedule", "schedule_version_token")
    op.drop_column("lease_liability_schedule", "period_seq")

    op.drop_constraint("uq_revenue_adjustments_idempotent", "revenue_adjustments", type_="unique")
    op.drop_column("revenue_adjustments", "new_schedule_version_token")
    op.drop_column("revenue_adjustments", "prior_schedule_version_token")
    op.drop_column("revenue_adjustments", "idempotency_key")

    op.drop_constraint("uq_revenue_schedules_contract_period_version", "revenue_schedules", type_="unique")
    op.drop_constraint("uq_revenue_schedules_natural", "revenue_schedules", type_="unique")
    op.create_unique_constraint(
        "uq_revenue_schedules_natural",
        "revenue_schedules",
        ["run_id", "contract_line_item_id", "recognition_date"],
    )
    op.drop_column("revenue_schedules", "schedule_version_token")
    op.drop_column("revenue_schedules", "period_seq")
