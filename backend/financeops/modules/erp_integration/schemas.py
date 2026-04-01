from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from financeops.db.models.erp_integration import (
    ErpAuthType,
    ErpMasterEntityType,
    ErpSyncModule,
    ErpSyncStatus,
    ErpSyncType,
)


class ConnectorCreateRequest(BaseModel):
    org_entity_id: uuid.UUID
    erp_type: str = Field(..., min_length=2, max_length=32)
    auth_type: ErpAuthType
    connection_config: dict[str, Any] = Field(default_factory=dict)


class ConnectorStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(ACTIVE|INACTIVE|ERROR)$")


class ConnectorResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    org_entity_id: uuid.UUID
    erp_type: str
    auth_type: ErpAuthType
    status: str
    last_sync_at: datetime | None
    created_at: datetime


class ConnectorTestResponse(BaseModel):
    connector_id: uuid.UUID
    ok: bool
    result: dict[str, Any]


class SyncRunRequest(BaseModel):
    erp_connector_id: uuid.UUID
    sync_type: ErpSyncType
    module: ErpSyncModule
    payload: dict[str, Any] = Field(default_factory=dict)
    retry_of_job_id: uuid.UUID | None = None


class SyncJobResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    org_entity_id: uuid.UUID
    erp_connector_id: uuid.UUID
    sync_type: ErpSyncType
    module: ErpSyncModule
    status: ErpSyncStatus
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    retry_count: int
    result_summary: dict[str, Any] | None
    created_at: datetime


class CoaImportRequest(BaseModel):
    erp_connector_id: uuid.UUID


class CoaMapItem(BaseModel):
    erp_account_id: str = Field(..., min_length=1, max_length=256)
    internal_account_id: uuid.UUID


class CoaMapRequest(BaseModel):
    erp_connector_id: uuid.UUID
    mappings: list[CoaMapItem] = Field(default_factory=list)


class JournalImportLine(BaseModel):
    account_code: str = Field(..., min_length=1, max_length=50)
    debit: Decimal = Field(default=Decimal("0"))
    credit: Decimal = Field(default=Decimal("0"))
    memo: str | None = None

    @field_validator("debit", "credit", mode="before")
    @classmethod
    def _coerce_decimal(cls, value: object) -> Decimal:
        if value is None:
            return Decimal("0")
        return Decimal(str(value))


class JournalImportTransaction(BaseModel):
    external_reference_id: str = Field(..., min_length=1, max_length=256)
    journal_date: datetime | str
    reference: str | None = Field(default=None, max_length=128)
    narration: str | None = None
    lines: list[JournalImportLine] = Field(..., min_length=2)


class JournalImportRequest(BaseModel):
    erp_connector_id: uuid.UUID
    transactions: list[JournalImportTransaction] | None = None


class JournalExportRequest(BaseModel):
    erp_connector_id: uuid.UUID
    journal_ids: list[uuid.UUID] | None = None


class MasterSyncRequest(BaseModel):
    erp_connector_id: uuid.UUID
    rows: list[dict[str, Any]] | None = None
    entity_type: ErpMasterEntityType


class MasterRowsRequest(BaseModel):
    erp_connector_id: uuid.UUID
    rows: list[dict[str, Any]] | None = None
