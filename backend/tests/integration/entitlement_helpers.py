from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.payment.application.entitlement_service import EntitlementService


async def grant_boolean_entitlement(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    feature_name: str,
    actor_user_id: uuid.UUID,
) -> None:
    await EntitlementService(session).create_tenant_override_entitlement(
        tenant_id=tenant_id,
        feature_name=feature_name,
        access_type="boolean",
        effective_limit=1,
        metadata={"source": "test"},
        actor_user_id=actor_user_id,
    )
    await session.flush()
