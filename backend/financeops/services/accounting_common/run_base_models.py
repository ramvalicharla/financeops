from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from financeops.db.base import FinancialBase

TRunModel = TypeVar("TRunModel", bound=FinancialBase)
TRunEventModel = TypeVar("TRunEventModel", bound=FinancialBase)


class AccountingRunHeaderBase(FinancialBase):
    """
    Abstract run header shape for accounting engines.
    Concrete engine models add period/domain-specific fields and table names.
    """

    __abstract__ = True

    request_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_id: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    configuration_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    initiated_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)


class AccountingRunEventBase(FinancialBase):
    """
    Abstract append-only lifecycle event shape for accounting engines.
    Concrete models should add engine-specific FK constraints and table args.
    """

    __abstract__ = True

    run_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    event_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


@dataclass(frozen=True)
class RunCreateResult:
    run_id: UUID
    workflow_id: str
    request_signature: str
    status: str
    created_new: bool


@dataclass(frozen=True)
class RunStatusSnapshot:
    run_id: UUID
    status: str
    event_seq: int
    event_time: datetime
    metadata: dict[str, Any] | None

