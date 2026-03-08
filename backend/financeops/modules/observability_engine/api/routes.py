from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.db.models.users import IamUser
from financeops.modules.observability_engine.api.schemas import (
    DiffRequest,
    DiffResponse,
    GraphResponse,
    ReplayValidateResponse,
)
from financeops.modules.observability_engine.application.diff_service import DiffService
from financeops.modules.observability_engine.application.graph_service import GraphService
from financeops.modules.observability_engine.application.replay_service import ReplayService
from financeops.modules.observability_engine.application.run_service import RunService
from financeops.modules.observability_engine.application.validation_service import ValidationService
from financeops.modules.observability_engine.infrastructure.repository import (
    ObservabilityRepository,
)
from financeops.modules.observability_engine.policies.control_plane_policy import (
    observability_control_plane_dependency,
)

router = APIRouter()


def _build_service(session: AsyncSession) -> RunService:
    repository = ObservabilityRepository(session)
    return RunService(
        repository=repository,
        validation_service=ValidationService(),
        diff_service=DiffService(),
        replay_service=ReplayService(),
        graph_service=GraphService(repository),
    )


@router.get(
    "/runs",
    dependencies=[
        Depends(
            observability_control_plane_dependency(
                action="observability_view", resource_type="observability_run_registry"
            )
        )
    ],
)
async def list_runs(
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    service = _build_service(session)
    return await service.list_registry_runs(tenant_id=user.tenant_id)


@router.get(
    "/runs/{id}",
    dependencies=[
        Depends(
            observability_control_plane_dependency(
                action="observability_view", resource_type="observability_run_registry"
            )
        )
    ],
)
async def get_run(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    service = _build_service(session)
    row = await service.get_registry_run(tenant_id=user.tenant_id, registry_or_run_id=id)
    if row is None:
        try:
            row = await service.discover_and_sync_run(
                tenant_id=user.tenant_id,
                run_id=id,
                created_by=user.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        await session.commit()
    return row


@router.get(
    "/runs/{id}/dependencies",
    dependencies=[
        Depends(
            observability_control_plane_dependency(
                action="observability_graph_view", resource_type="lineage_graph_snapshot"
            )
        )
    ],
)
async def get_run_dependencies(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    snapshot = await ObservabilityRepository(session).resolve_run_snapshot(
        tenant_id=user.tenant_id, run_id=id
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="run is not discoverable for tenant")
    return {
        "run_id": str(snapshot["run_id"]),
        "module_code": str(snapshot["module_code"]),
        "run_token": str(snapshot["run_token"]),
        "dependencies": list(snapshot.get("dependencies", [])),
    }


@router.post(
    "/diff",
    response_model=DiffResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            observability_control_plane_dependency(
                action="observability_diff", resource_type="run_token_diff_result"
            )
        )
    ],
)
async def create_diff(
    body: DiffRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> DiffResponse:
    service = _build_service(session)
    try:
        payload = await service.run_diff(
            tenant_id=user.tenant_id,
            base_run_id=body.base_run_id,
            compare_run_id=body.compare_run_id,
            created_by=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return DiffResponse(
        diff_id=uuid.UUID(str(payload["diff_id"])),
        base_run_id=uuid.UUID(str(payload["base_run_id"])),
        compare_run_id=uuid.UUID(str(payload["compare_run_id"])),
        drift_flag=bool(payload["drift_flag"]),
        summary=dict(payload["summary"]),
        idempotent=bool(payload.get("idempotent", False)),
    )


@router.get(
    "/diff/{id}",
    dependencies=[
        Depends(
            observability_control_plane_dependency(
                action="observability_diff", resource_type="run_token_diff_result"
            )
        )
    ],
)
async def get_diff(
    id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    payload = await _build_service(session).get_diff(tenant_id=user.tenant_id, diff_id=id)
    if payload is None:
        raise HTTPException(status_code=404, detail="diff not found")
    return payload


@router.post(
    "/replay-validate/{run_id}",
    response_model=ReplayValidateResponse,
    dependencies=[
        Depends(
            observability_control_plane_dependency(
                action="observability_replay_validate", resource_type="observability_run"
            )
        )
    ],
)
async def replay_validate(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> ReplayValidateResponse:
    service = _build_service(session)
    try:
        payload = await service.replay_validate(
            tenant_id=user.tenant_id,
            run_id=run_id,
            created_by=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await session.commit()
    return ReplayValidateResponse(
        run_id=uuid.UUID(str(payload["run_id"])),
        module_code=str(payload["module_code"]),
        stored_run_token=str(payload["stored_run_token"]),
        recomputed_run_token=str(payload["recomputed_run_token"]),
        matches=bool(payload["matches"]),
    )


@router.get(
    "/graph/{run_id}",
    response_model=GraphResponse,
    dependencies=[
        Depends(
            observability_control_plane_dependency(
                action="observability_graph_view", resource_type="lineage_graph_snapshot"
            )
        )
    ],
)
async def get_graph(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> GraphResponse:
    service = _build_service(session)
    row = await service.latest_graph(tenant_id=user.tenant_id, root_run_id=run_id)
    if row is None:
        try:
            row = await service.build_graph_snapshot(
                tenant_id=user.tenant_id,
                root_run_id=run_id,
                created_by=user.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        await session.commit()
    return GraphResponse(
        graph_snapshot_id=uuid.UUID(str(row["graph_snapshot_id"])),
        root_run_id=uuid.UUID(str(row["root_run_id"])),
        deterministic_hash=str(row["deterministic_hash"]),
        graph=dict(row["graph"]),
    )


@router.get(
    "/events/{run_id}",
    dependencies=[
        Depends(
            observability_control_plane_dependency(
                action="observability_view", resource_type="governance_event"
            )
        )
    ],
)
async def list_events(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> list[dict]:
    return await _build_service(session).list_events(tenant_id=user.tenant_id, run_id=run_id)


@router.get(
    "/performance/{run_id}",
    dependencies=[
        Depends(
            observability_control_plane_dependency(
                action="observability_view", resource_type="run_performance_metric"
            )
        )
    ],
)
async def get_performance(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    row = await _build_service(session).latest_performance(tenant_id=user.tenant_id, run_id=run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="performance metrics not found")
    return row

