from __future__ import annotations

import asyncio
import uuid

from financeops.db.session import tenant_session
from financeops.modules.search.service import reindex_tenant
from financeops.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="search.reindex")
def reindex_search_index(self, tenant_id: str) -> dict[str, int]:  # noqa: ANN001
    """
    Full search reindex for a tenant. Runs in Celery worker.
    """

    async def _run() -> dict[str, int]:
        tenant_uuid = uuid.UUID(str(tenant_id))
        async with tenant_session(tenant_uuid) as session:
            return await reindex_tenant(session, tenant_uuid)

    try:
        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)


__all__ = ["reindex_search_index"]
