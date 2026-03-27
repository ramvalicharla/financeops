from __future__ import annotations

from io import BytesIO
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from openpyxl import Workbook
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.api.deps import get_async_session, get_current_user
from financeops.core.exceptions import NotFoundError
from financeops.db.models.users import IamUser
from financeops.platform.services.tenancy.entity_access import assert_entity_access, get_entities_for_user
from financeops.modules.scenario_modelling.models import (
    ScenarioDefinition,
    ScenarioLineItem,
    ScenarioResult,
    ScenarioSet,
)
from financeops.modules.scenario_modelling.service import (
    compute_all_scenarios,
    create_scenario_set,
    get_scenario_comparison,
    update_scenario_drivers,
)
from financeops.shared_kernel.pagination import Paginated

router = APIRouter(prefix="/scenarios", tags=["scenario-modelling"])


class CreateScenarioSetRequest(BaseModel):
    entity_id: uuid.UUID | None = None
    name: str
    base_period: str
    horizon_months: int = 12
    base_forecast_run_id: uuid.UUID | None = None


class UpdateScenarioRequest(BaseModel):
    driver_overrides: dict[str, str]
    scenario_label: str | None = None


async def _resolve_entity_for_user(
    session: AsyncSession,
    user: IamUser,
    entity_id: uuid.UUID | None,
) -> uuid.UUID:
    if entity_id is not None:
        await assert_entity_access(session, user.tenant_id, entity_id, user.id, user.role)
        return entity_id
    entities = await get_entities_for_user(
        session=session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        user_role=user.role,
    )
    if not entities:
        raise HTTPException(status_code=422, detail="entity_id is required because no entity is configured for this user")
    return entities[0].id


def _serialize_set(row: ScenarioSet) -> dict:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "entity_id": str(row.entity_id),
        "name": row.name,
        "base_period": row.base_period,
        "horizon_months": row.horizon_months,
        "base_forecast_run_id": str(row.base_forecast_run_id) if row.base_forecast_run_id else None,
        "created_by": str(row.created_by),
        "created_at": row.created_at.isoformat(),
    }


def _serialize_definition(row: ScenarioDefinition) -> dict:
    return {
        "id": str(row.id),
        "scenario_set_id": str(row.scenario_set_id),
        "tenant_id": str(row.tenant_id),
        "entity_id": str(row.entity_id),
        "scenario_name": row.scenario_name,
        "scenario_label": row.scenario_label,
        "is_base_case": row.is_base_case,
        "driver_overrides": dict(row.driver_overrides or {}),
        "colour_hex": row.colour_hex,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_set(
    body: CreateScenarioSetRequest,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_for_user(session, user, body.entity_id)
    scenario_set = await create_scenario_set(
        session,
        tenant_id=user.tenant_id,
        name=body.name,
        base_period=body.base_period,
        horizon_months=body.horizon_months,
        created_by=user.id,
        base_forecast_run_id=body.base_forecast_run_id,
        entity_id=resolved_entity_id,
    )
    definitions = (
        await session.execute(
            select(ScenarioDefinition).where(
                ScenarioDefinition.tenant_id == user.tenant_id,
                ScenarioDefinition.entity_id == resolved_entity_id,
                ScenarioDefinition.scenario_set_id == scenario_set.id,
            )
        )
    ).scalars().all()
    return {
        "scenario_set": _serialize_set(scenario_set),
        "scenario_definitions": [_serialize_definition(row) for row in definitions],
    }


@router.get("")
async def list_sets(
    entity_id: uuid.UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int | None = Query(default=None, ge=0),
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Paginated[dict]:
    resolved_entity_id = await _resolve_entity_for_user(session, user, entity_id)
    effective_skip = offset if offset is not None else skip
    stmt = select(ScenarioSet).where(
        ScenarioSet.tenant_id == user.tenant_id,
        ScenarioSet.entity_id == resolved_entity_id,
    )
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(ScenarioSet.created_at.desc(), ScenarioSet.id.desc())
            .limit(limit)
            .offset(effective_skip)
        )
    ).scalars().all()
    return Paginated[dict](
        items=[_serialize_set(row) for row in rows],
        total=int(total),
        limit=limit,
        skip=effective_skip,
        has_more=(effective_skip + len(rows)) < int(total),
    )


@router.get("/{set_id}")
async def get_set(
    set_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    try:
        resolved_entity_id = await _resolve_entity_for_user(session, user, entity_id)
    except HTTPException as exc:
        if exc.status_code == 422:
            raise HTTPException(status_code=404, detail="Scenario set not found") from exc
        raise
    scenario_set = (
        await session.execute(
            select(ScenarioSet).where(
                ScenarioSet.id == set_id,
                ScenarioSet.tenant_id == user.tenant_id,
                ScenarioSet.entity_id == resolved_entity_id,
            )
        )
    ).scalar_one_or_none()
    if scenario_set is None:
        raise HTTPException(status_code=404, detail="Scenario set not found")
    definitions = (
        await session.execute(
            select(ScenarioDefinition).where(
                ScenarioDefinition.tenant_id == user.tenant_id,
                ScenarioDefinition.entity_id == resolved_entity_id,
                ScenarioDefinition.scenario_set_id == set_id,
            )
        )
    ).scalars().all()
    latest_results: list[dict] = []
    for definition in definitions:
        result = (
            await session.execute(
                select(ScenarioResult)
                .where(
                    ScenarioResult.tenant_id == user.tenant_id,
                    ScenarioResult.entity_id == resolved_entity_id,
                    ScenarioResult.scenario_definition_id == definition.id,
                )
                .order_by(ScenarioResult.computed_at.desc(), ScenarioResult.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if result is None:
            continue
        latest_results.append(
            {
                "id": str(result.id),
                "scenario_definition_id": str(result.scenario_definition_id),
                "computed_at": result.computed_at.isoformat(),
            }
        )
    return {
        "scenario_set": _serialize_set(scenario_set),
        "scenario_definitions": [_serialize_definition(row) for row in definitions],
        "latest_results": latest_results,
    }


@router.patch("/{set_id}/scenarios/{definition_id}")
async def patch_definition(
    set_id: uuid.UUID,
    definition_id: uuid.UUID,
    body: UpdateScenarioRequest,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_for_user(session, user, entity_id)
    definition = (
        await session.execute(
            select(ScenarioDefinition).where(
                ScenarioDefinition.id == definition_id,
                ScenarioDefinition.scenario_set_id == set_id,
                ScenarioDefinition.tenant_id == user.tenant_id,
                ScenarioDefinition.entity_id == resolved_entity_id,
            )
        )
    ).scalar_one_or_none()
    if definition is None:
        raise HTTPException(status_code=404, detail="Scenario definition not found")

    try:
        updated = await update_scenario_drivers(
            session,
            tenant_id=user.tenant_id,
            scenario_definition_id=definition_id,
            driver_overrides=body.driver_overrides,
            entity_id=resolved_entity_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if body.scenario_label:
        updated.scenario_label = body.scenario_label
        await session.flush()
    return _serialize_definition(updated)


@router.post("/{set_id}/compute")
async def compute_set(
    set_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_for_user(session, user, entity_id)
    try:
        results = await compute_all_scenarios(
            session,
            tenant_id=user.tenant_id,
            scenario_set_id=set_id,
            entity_id=resolved_entity_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
    payload: list[dict] = []
    for row in results:
        count = (
            await session.execute(
                select(func.count()).select_from(ScenarioLineItem).where(
                    ScenarioLineItem.scenario_result_id == row.id,
                    ScenarioLineItem.tenant_id == user.tenant_id,
                    ScenarioLineItem.entity_id == resolved_entity_id,
                )
            )
        ).scalar_one()
        payload.append(
            {
                "id": str(row.id),
                "scenario_definition_id": str(row.scenario_definition_id),
                "line_items_count": int(count),
                "computed_at": row.computed_at.isoformat(),
            }
        )
    return {"results": payload}


@router.get("/{set_id}/comparison")
async def comparison(
    set_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> dict:
    resolved_entity_id = await _resolve_entity_for_user(session, user, entity_id)
    try:
        payload = await get_scenario_comparison(
            session,
            tenant_id=user.tenant_id,
            scenario_set_id=set_id,
            entity_id=resolved_entity_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc

    return {
        "scenario_set_name": payload["scenario_set_name"],
        "base_period": payload["base_period"],
        "scenarios": [
            {
                "scenario_name": row["scenario_name"],
                "scenario_label": row["scenario_label"],
                "colour_hex": row["colour_hex"],
                "is_base_case": row["is_base_case"],
                "summary": {
                    "revenue_total": format(row["summary"]["revenue_total"], "f"),
                    "ebitda_total": format(row["summary"]["ebitda_total"], "f"),
                    "ebitda_margin_pct": format(row["summary"]["ebitda_margin_pct"], "f"),
                    "net_profit_total": format(row["summary"]["net_profit_total"], "f"),
                },
                "monthly": [
                    {
                        "period": item["period"],
                        "revenue": format(item["revenue"], "f"),
                        "ebitda": format(item["ebitda"], "f"),
                    }
                    for item in row["monthly"]
                ],
            }
            for row in payload["scenarios"]
        ],
        "waterfall": {
            "base_ebitda": format(payload["waterfall"]["base_ebitda"], "f"),
            "drivers": [
                {
                    "driver_name": item["driver_name"],
                    "impact": format(item["impact"], "f"),
                }
                for item in payload["waterfall"]["drivers"]
            ],
            "optimistic_ebitda": format(payload["waterfall"]["optimistic_ebitda"], "f"),
            "pessimistic_ebitda": format(payload["waterfall"]["pessimistic_ebitda"], "f"),
        },
    }


@router.get("/{set_id}/export")
async def export_set(
    set_id: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    session: AsyncSession = Depends(get_async_session),
    user: IamUser = Depends(get_current_user),
) -> Response:
    payload = await comparison(set_id=set_id, entity_id=entity_id, session=session, user=user)

    workbook = Workbook()
    # default sheet reused for first scenario
    for index, scenario in enumerate(payload["scenarios"]):
        if index == 0:
            sheet = workbook.active
            sheet.title = scenario["scenario_label"][:31] or "Scenario 1"
        else:
            sheet = workbook.create_sheet(title=(scenario["scenario_label"][:31] or f"Scenario {index+1}"))
        sheet.append(["Period", "Revenue", "EBITDA"])
        for row in scenario["monthly"]:
            sheet.append([row["period"], row["revenue"], row["ebitda"]])

    buffer = BytesIO()
    workbook.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="scenarios_{set_id}.xlsx"'},
    )
