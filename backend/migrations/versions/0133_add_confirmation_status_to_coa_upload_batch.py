"""add confirmation status to coa upload batches

Revision ID: 0133_coa_batch_confirm
Revises: 0132_webhook_secret_sched
Create Date: 2026-04-16 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0133_coa_batch_confirm"
down_revision: str | None = "0132_webhook_secret_sched"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENUM_NAME = "coa_batch_confirmation_status_enum"


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    value = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
            LIMIT 1
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).scalar_one_or_none()
    return value is not None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = '{_ENUM_NAME}'
              ) THEN
                CREATE TYPE {_ENUM_NAME} AS ENUM ('PENDING', 'CONFIRMED');
              END IF;
            END $$;
            """
        )
    )

    if not _column_exists("coa_upload_batches", "confirmation_status"):
        op.add_column(
            "coa_upload_batches",
            sa.Column(
                "confirmation_status",
                sa.Enum(
                    "PENDING",
                    "CONFIRMED",
                    name=_ENUM_NAME,
                    create_type=False,
                ),
                nullable=False,
                server_default=sa.text(f"'PENDING'::{_ENUM_NAME}"),
            ),
        )


def downgrade() -> None:
    if _column_exists("coa_upload_batches", "confirmation_status"):
        op.drop_column("coa_upload_batches", "confirmation_status")
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = '{_ENUM_NAME}'
              ) THEN
                DROP TYPE {_ENUM_NAME};
              END IF;
            END $$;
            """
        )
    )
