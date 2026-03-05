from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class UUIDBase(Base):
    """Abstract base with UUID PK and created_at."""
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class FinancialBase(UUIDBase):
    """
    Abstract base for ALL financial tables.
    NON-NEGOTIABLE columns per spec:
      id (UUID), tenant_id (UUID), chain_hash (VARCHAR 64),
      previous_hash (VARCHAR 64), created_at (TIMESTAMPTZ)
    Rule: INSERT ONLY — no UPDATE, no DELETE on subclasses.
    """
    __abstract__ = True

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    chain_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    previous_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
