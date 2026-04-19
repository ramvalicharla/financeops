"""add delivery state to notification read state

Revision ID: 0138_notification_delivery_state
Revises: 0137_gst_rate_master
Create Date: 2026-04-16 13:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0138_notification_delivery_state"
down_revision: str | None = "0137_gst_rate_master"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_read_state",
        sa.Column(
            "channels_sent",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "notification_read_state",
        sa.Column(
            "delivery_status",
            sa.String(length=20),
            nullable=False,
            server_default="queued",
        ),
    )


def downgrade() -> None:
    op.drop_column("notification_read_state", "delivery_status")
    op.drop_column("notification_read_state", "channels_sent")
