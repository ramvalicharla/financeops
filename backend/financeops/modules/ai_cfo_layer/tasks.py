from __future__ import annotations

import time
import uuid
from datetime import date
from typing import Any

from financeops.modules.ai_cfo_layer.application.narrative_service import generate_narrative
from financeops.observability.business_metrics import ai_narrative_duration_ms
from financeops.db.session import AsyncSessionLocal
from financeops.tasks.async_runner import run_async
from financeops.tasks.celery_app import celery_app


@celery_app.task(name="ai_cfo.generate_narrative_async")
def generate_narrative_async_task(
    *,
    tenant_id: str,
    actor_user_id: str,
    org_entity_id: str | None,
    org_group_id: str | None,
    from_date: str,
    to_date: str,
    comparison: str,
) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        started = time.perf_counter()
        async with AsyncSessionLocal() as session:
            try:
                payload = await generate_narrative(
                    session,
                    tenant_id=uuid.UUID(tenant_id),
                    actor_user_id=uuid.UUID(actor_user_id),
                    org_entity_id=uuid.UUID(org_entity_id) if org_entity_id else None,
                    org_group_id=uuid.UUID(org_group_id) if org_group_id else None,
                    from_date=date.fromisoformat(from_date),
                    to_date=date.fromisoformat(to_date),
                    comparison=comparison,
                )
                await session.commit()
                ai_narrative_duration_ms.labels(status="success").observe(
                    (time.perf_counter() - started) * 1000
                )
                return payload.model_dump(mode="json")
            except Exception:
                await session.rollback()
                ai_narrative_duration_ms.labels(status="failed").observe(
                    (time.perf_counter() - started) * 1000
                )
                raise

    return run_async(_run())
