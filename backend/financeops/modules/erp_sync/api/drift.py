from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.erp_sync import (
    ExternalBackdatedModificationAlert,
    ExternalConnectorVersionRegistry,
    ExternalPeriodLock,
    ExternalSyncDriftReport,
)
from financeops.db.models.users import IamUser
from financeops.modules.erp_sync.application.period_lock_service import PeriodLockService
from financeops.modules.erp_sync.domain.enums import ConnectorType
from financeops.modules.erp_sync.infrastructure.connectors.registry import CONNECTOR_REGISTRY, get_connector
from financeops.shared_kernel.response import ok

router = APIRouter()


@router.get("/drift-reports")
async def list_drift_reports(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(ExternalSyncDriftReport)
            .where(ExternalSyncDriftReport.tenant_id == user.tenant_id)
            .order_by(ExternalSyncDriftReport.created_at.desc(), ExternalSyncDriftReport.id.desc())
        )
    ).scalars().all()
    return ok(
        {
            "items": [
                {
                    "id": str(row.id),
                    "sync_run_id": str(row.sync_run_id),
                    "drift_detected": row.drift_detected,
                    "drift_severity": row.drift_severity,
                    "total_variances": row.total_variances,
                }
                for row in rows
            ]
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/drift-reports/{id}")
async def get_drift_report(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(ExternalSyncDriftReport).where(
                ExternalSyncDriftReport.tenant_id == user.tenant_id,
                ExternalSyncDriftReport.id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    return ok(
        {
            "id": str(row.id),
            "sync_run_id": str(row.sync_run_id),
            "drift_detected": row.drift_detected,
            "drift_severity": row.drift_severity,
            "total_variances": row.total_variances,
            "metrics_checked_json": row.metrics_checked_json,
            "generated_at": row.generated_at.isoformat(),
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/period-locks")
async def list_period_locks(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(ExternalPeriodLock)
            .where(ExternalPeriodLock.tenant_id == user.tenant_id)
            .order_by(ExternalPeriodLock.created_at.desc(), ExternalPeriodLock.id.desc())
        )
    ).scalars().all()
    return ok(
        {
            "items": [
                {
                    "id": str(row.id),
                    "organisation_id": str(row.organisation_id),
                    "entity_id": str(row.entity_id) if row.entity_id else None,
                    "dataset_type": row.dataset_type,
                    "period_key": row.period_key,
                    "lock_status": row.lock_status,
                    "source_sync_run_id": str(row.source_sync_run_id) if row.source_sync_run_id else None,
                }
                for row in rows
            ]
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/period-locks")
async def create_period_lock(
    request: Request,
    body: dict[str, Any],
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = PeriodLockService(session)
    result = await service.auto_lock_on_publish(
        tenant_id=user.tenant_id,
        sync_run_id=uuid.UUID(str(body["sync_run_id"])),
        created_by=user.id,
    )
    await session.flush()
    return ok(result, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/backdated-alerts/{id}/acknowledge")
async def acknowledge_backdated_alert(
    request: Request,
    id: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = (
        await session.execute(
            select(ExternalBackdatedModificationAlert).where(
                ExternalBackdatedModificationAlert.tenant_id == user.tenant_id,
                ExternalBackdatedModificationAlert.id == uuid.UUID(id),
            )
        )
    ).scalar_one()
    return ok(
        {
            "id": str(row.id),
            "status": "acknowledge_pending",
            "note": "append-only governance path; acknowledgement requires event-driven supersession",
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/connectors")
async def list_connectors(request: Request) -> dict[str, Any]:
    items = []
    for connector_type, cls in CONNECTOR_REGISTRY.items():
        connector = cls()
        items.append(
            {
                "connector_type": connector_type.value,
                "connector_version": connector.connector_version,
                "supports_resumable_extraction": connector.supports_resumable_extraction,
                "supported_datasets": sorted(item.value for item in connector.supported_datasets),
            }
        )
    items.sort(key=lambda item: item["connector_type"])
    return ok({"items": items}, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.get("/connectors/{connector_type}/capabilities")
async def get_connector_capabilities(request: Request, connector_type: str) -> dict[str, Any]:
    connector = get_connector(ConnectorType(connector_type))
    return ok(
        {
            "connector_type": connector_type,
            "connector_version": connector.connector_version,
            "supports_resumable_extraction": connector.supports_resumable_extraction,
            "supported_datasets": sorted(item.value for item in connector.supported_datasets),
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/connectors/{connector_type}/versions")
async def get_connector_versions(
    request: Request,
    connector_type: str,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(ExternalConnectorVersionRegistry)
            .where(
                ExternalConnectorVersionRegistry.tenant_id == user.tenant_id,
                ExternalConnectorVersionRegistry.connector_type == connector_type,
            )
            .order_by(
                ExternalConnectorVersionRegistry.created_at.desc(),
                ExternalConnectorVersionRegistry.id.desc(),
            )
        )
    ).scalars().all()
    return ok(
        {
            "connector_type": connector_type,
            "versions": [
                {
                    "id": str(row.id),
                    "version": row.version,
                    "status": row.status,
                    "checksum": row.checksum,
                    "deprecation_date": row.deprecation_date.isoformat() if row.deprecation_date else None,
                }
                for row in rows
            ],
        },
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")
