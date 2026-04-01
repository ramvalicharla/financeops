from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.exceptions import AuthorizationError
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.erp_integration.application.service import ErpIntegrationService
from financeops.modules.erp_integration.schemas import (
    CoaImportRequest,
    CoaMapRequest,
    ConnectorCreateRequest,
    ConnectorResponse,
    ConnectorStatusUpdateRequest,
    JournalExportRequest,
    JournalImportRequest,
    MasterRowsRequest,
    MasterSyncRequest,
    SyncJobResponse,
    SyncRunRequest,
)
from financeops.db.models.erp_integration import ErpMasterEntityType
from financeops.shared_kernel.response import ok


router = APIRouter(prefix="/erp", tags=["ERP Integration"])

_ERP_ALLOWED_ROLES = {
    UserRole.super_admin,
    UserRole.platform_owner,
    UserRole.platform_admin,
    UserRole.finance_leader,
    UserRole.finance_team,
}


def _assert_erp_access(user: IamUser) -> None:
    if user.role not in _ERP_ALLOWED_ROLES:
        raise AuthorizationError("ERP integration access requires finance/admin role.")


def _connector_payload(row: Any) -> ConnectorResponse:
    return ConnectorResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        org_entity_id=row.org_entity_id,
        erp_type=row.erp_type,
        auth_type=row.auth_type,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        last_sync_at=row.last_sync_at,
        created_at=row.created_at,
    )


def _job_payload(row: Any) -> SyncJobResponse:
    return SyncJobResponse(
        id=row.id,
        tenant_id=row.tenant_id,
        org_entity_id=row.org_entity_id,
        erp_connector_id=row.erp_connector_id,
        sync_type=row.sync_type,
        module=row.module,
        status=row.status,
        started_at=row.started_at,
        completed_at=row.completed_at,
        error_message=row.error_message,
        retry_count=row.retry_count,
        result_summary=row.result_summary,
        created_at=row.created_at,
    )


@router.post("/connectors")
async def create_connector(
    request: Request,
    body: ConnectorCreateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    row = await service.create_connector(
        tenant_id=user.tenant_id,
        user_id=user.id,
        body=body,
    )
    await session.commit()
    return ok(
        _connector_payload(row).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/connectors")
async def list_connectors(
    request: Request,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    rows = await service.list_connectors(tenant_id=user.tenant_id)
    return ok(
        [_connector_payload(row).model_dump(mode="json") for row in rows],
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/connectors/{connector_id}")
async def get_connector(
    request: Request,
    connector_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    row = await service.get_connector(tenant_id=user.tenant_id, connector_id=connector_id)
    return ok(
        _connector_payload(row).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.patch("/connectors/{connector_id}/status")
async def update_connector_status(
    request: Request,
    connector_id: uuid.UUID,
    body: ConnectorStatusUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    row = await service.update_connector_status(
        tenant_id=user.tenant_id,
        connector_id=connector_id,
        status=body.status,
    )
    await session.commit()
    return ok(
        _connector_payload(row).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/connectors/{connector_id}/test")
async def test_connector(
    request: Request,
    connector_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    result = await service.test_connector(tenant_id=user.tenant_id, connector_id=connector_id)
    return ok(
        {"connector_id": str(connector_id), "ok": True, "result": result},
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/sync/run")
async def run_sync(
    request: Request,
    body: SyncRunRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    job = await service.run_sync_job(tenant_id=user.tenant_id, actor=user, body=body)
    await session.commit()
    return ok(
        _job_payload(job).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/sync/jobs")
async def list_sync_jobs(
    request: Request,
    erp_connector_id: uuid.UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    rows = await service.list_jobs(
        tenant_id=user.tenant_id,
        erp_connector_id=erp_connector_id,
    )
    return ok(
        [_job_payload(row).model_dump(mode="json") for row in rows],
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.get("/sync/jobs/{job_id}")
async def get_sync_job(
    request: Request,
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    row = await service.get_job(tenant_id=user.tenant_id, job_id=job_id)
    return ok(
        _job_payload(row).model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    ).model_dump(mode="json")


@router.post("/sync/coa/import")
async def import_coa(
    request: Request,
    body: CoaImportRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    payload = await service.import_coa(tenant_id=user.tenant_id, connector_id=body.erp_connector_id)
    await session.commit()
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/sync/coa/map")
async def map_coa(
    request: Request,
    body: CoaMapRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    payload = await service.map_coa(tenant_id=user.tenant_id, body=body)
    await session.commit()
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/sync/journals/import")
async def import_journals(
    request: Request,
    body: JournalImportRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    payload = await service.import_journals(tenant_id=user.tenant_id, actor=user, body=body)
    await session.commit()
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/sync/journals/export")
async def export_journals(
    request: Request,
    body: JournalExportRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    payload = await service.export_journals(tenant_id=user.tenant_id, actor=user, body=body)
    await session.commit()
    return ok(payload, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/sync/vendors")
async def sync_vendors(
    request: Request,
    body: MasterRowsRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    result = await service.sync_master_data(
        tenant_id=user.tenant_id,
        actor=user,
        body=MasterSyncRequest(
            erp_connector_id=body.erp_connector_id,
            rows=body.rows,
            entity_type=ErpMasterEntityType.VENDOR,
        ),
    )
    await session.commit()
    return ok(result, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")


@router.post("/sync/customers")
async def sync_customers(
    request: Request,
    body: MasterRowsRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict[str, Any]:
    _assert_erp_access(user)
    service = ErpIntegrationService(session)
    result = await service.sync_master_data(
        tenant_id=user.tenant_id,
        actor=user,
        body=MasterSyncRequest(
            erp_connector_id=body.erp_connector_id,
            rows=body.rows,
            entity_type=ErpMasterEntityType.CUSTOMER,
        ),
    )
    await session.commit()
    return ok(result, request_id=getattr(request.state, "request_id", None)).model_dump(mode="json")
