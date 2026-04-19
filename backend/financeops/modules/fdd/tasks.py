from __future__ import annotations

import uuid

from financeops.db.rls import clear_tenant_context, set_tenant_context
from financeops.db.session import AsyncSessionLocal
from financeops.modules.fdd.service import run_engagement
from financeops.tasks.async_runner import run_async
from financeops.tasks.celery_app import celery_app


@celery_app.task(name="advisory.fdd.run_engagement")
def run_fdd_engagement_task(tenant_id: str, engagement_id: str) -> dict:
    async def _run() -> dict:
        parsed_tenant_id = uuid.UUID(str(tenant_id))
        parsed_engagement_id = uuid.UUID(str(engagement_id))
        async with AsyncSessionLocal() as session:
            try:
                await set_tenant_context(session, str(parsed_tenant_id))
                engagement = await run_engagement(
                    session,
                    tenant_id=parsed_tenant_id,
                    engagement_id=parsed_engagement_id,
                )
                await session.commit()
                return {
                    "engagement_id": str(engagement.id),
                    "status": engagement.status,
                }
            finally:
                await clear_tenant_context(session)

    return run_async(_run())


__all__ = ["run_fdd_engagement_task"]
