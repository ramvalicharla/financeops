from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.tenants import IamTenant


class OrgGateService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_setup_complete(self, tenant_id: uuid.UUID) -> bool:
        row = (
            await self._session.execute(
                select(IamTenant.org_setup_complete).where(IamTenant.id == tenant_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Tenant not found")
        return bool(row)

    async def get_current_step(self, tenant_id: uuid.UUID) -> int:
        row = (
            await self._session.execute(
                select(IamTenant.org_setup_step).where(IamTenant.id == tenant_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Tenant not found")
        return int(row)


__all__ = ["OrgGateService"]
