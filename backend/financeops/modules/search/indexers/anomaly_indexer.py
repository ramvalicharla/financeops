from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.anomaly_pattern_engine import AnomalyResult
from financeops.modules.search.service import upsert_index_entry


async def index_anomaly(session: AsyncSession, anomaly: AnomalyResult) -> None:
    await upsert_index_entry(
        session,
        tenant_id=anomaly.tenant_id,
        entity_type="anomaly",
        entity_id=anomaly.id,
        title=f"{anomaly.anomaly_name} - {anomaly.severity}",
        subtitle=anomaly.anomaly_domain,
        body=anomaly.status_note,
        url=f"/anomalies/{anomaly.id}",
        metadata={
            "severity": anomaly.severity,
            "status": anomaly.alert_status,
            "anomaly_code": anomaly.anomaly_code,
        },
    )


async def reindex_all_anomalies(session: AsyncSession, tenant_id: uuid.UUID) -> int:
    rows = (
        await session.execute(
            select(AnomalyResult).where(AnomalyResult.tenant_id == tenant_id)
        )
    ).scalars().all()
    for row in rows:
        await index_anomaly(session, row)
    return len(rows)


__all__ = ["index_anomaly", "reindex_all_anomalies"]

