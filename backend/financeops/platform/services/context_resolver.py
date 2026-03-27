from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.locations.models import CpLocation
from financeops.platform.db.models.entities import CpEntity


async def resolve_entity_id(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    session: AsyncSession,
) -> uuid.UUID:
    if entity_id is not None:
        match = (
            await session.execute(
                select(CpEntity.id).where(
                    CpEntity.id == entity_id,
                    CpEntity.tenant_id == tenant_id,
                    CpEntity.status == "active",
                )
            )
        ).scalar_one_or_none()
        if match is None:
            raise HTTPException(status_code=404, detail="Entity not found")
        return match

    count = int(
        (
            await session.execute(
                select(func.count()).select_from(CpEntity).where(
                    CpEntity.tenant_id == tenant_id,
                    CpEntity.status == "active",
                )
            )
        ).scalar_one()
    )
    if count == 1:
        row = (
            await session.execute(
                select(CpEntity.id).where(
                    CpEntity.tenant_id == tenant_id,
                    CpEntity.status == "active",
                )
            )
        ).scalar_one()
        return row
    if count > 1:
        raise HTTPException(
            status_code=422,
            detail="entity_id is required for multi-entity tenants",
        )
    raise HTTPException(status_code=422, detail="No active entity found for tenant")


async def resolve_location_id(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    location_id: uuid.UUID | None,
    session: AsyncSession,
) -> uuid.UUID | None:
    if location_id is not None:
        match = (
            await session.execute(
                select(CpLocation.id).where(
                    CpLocation.id == location_id,
                    CpLocation.tenant_id == tenant_id,
                    CpLocation.entity_id == entity_id,
                    CpLocation.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if match is None:
            raise HTTPException(status_code=404, detail="Location not found")
        return match

    count = int(
        (
            await session.execute(
                select(func.count()).select_from(CpLocation).where(
                    CpLocation.tenant_id == tenant_id,
                    CpLocation.entity_id == entity_id,
                    CpLocation.is_active.is_(True),
                )
            )
        ).scalar_one()
    )
    if count == 1:
        row = (
            await session.execute(
                select(CpLocation.id).where(
                    CpLocation.tenant_id == tenant_id,
                    CpLocation.entity_id == entity_id,
                    CpLocation.is_active.is_(True),
                )
            )
        ).scalar_one()
        return row
    return None


__all__ = ["resolve_entity_id", "resolve_location_id"]
