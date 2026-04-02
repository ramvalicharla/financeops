from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.analytics_layer import AnalyticsAlert
from financeops.modules.analytics_layer.schemas import AlertCreateRequest, AlertEvaluationRow, AlertRow


def _is_triggered(*, value: Decimal, threshold: Decimal, condition: str) -> bool:
    if condition == "GT":
        return value > threshold
    if condition == "LT":
        return value < threshold
    if condition == "ABS_GT":
        return abs(value) > threshold
    return False


async def create_alert(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    body: AlertCreateRequest,
) -> AlertRow:
    row = AnalyticsAlert(
        tenant_id=tenant_id,
        metric_name=body.metric_name,
        threshold=body.threshold,
        condition=body.condition,
        description=body.description,
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(row)
    await db.flush()
    return AlertRow(
        id=row.id,
        metric_name=row.metric_name,
        threshold=row.threshold,
        condition=row.condition,
        description=row.description,
        created_at=row.created_at,
    )


async def list_alerts(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[AlertRow]:
    rows = (
        await db.execute(
            select(AnalyticsAlert)
            .where(AnalyticsAlert.tenant_id == tenant_id)
            .order_by(AnalyticsAlert.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return [
        AlertRow(
            id=row.id,
            metric_name=row.metric_name,
            threshold=row.threshold,
            condition=row.condition,
            description=row.description,
            created_at=row.created_at,
        )
        for row in rows
    ]


async def evaluate_alerts(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    metrics: dict[str, Decimal],
) -> list[AlertEvaluationRow]:
    rows = (
        await db.execute(
            select(AnalyticsAlert).where(AnalyticsAlert.tenant_id == tenant_id)
        )
    ).scalars().all()
    payload: list[AlertEvaluationRow] = []
    for row in rows:
        value = metrics.get(row.metric_name)
        if value is None:
            continue
        payload.append(
            AlertEvaluationRow(
                metric_name=row.metric_name,
                metric_value=value,
                threshold=row.threshold,
                condition=row.condition,
                triggered=_is_triggered(value=value, threshold=row.threshold, condition=row.condition),
                description=row.description,
            )
        )
    return payload
