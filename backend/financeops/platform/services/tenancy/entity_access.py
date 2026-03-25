from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.users import UserRole
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.db.models.user_membership import CpUserEntityAssignment

_ALL_ENTITY_ROLES = {
    UserRole.finance_leader,
    UserRole.platform_owner,
    UserRole.platform_admin,
    UserRole.super_admin,
}


def _normalize_role(user_role: UserRole | str) -> UserRole | None:
    if isinstance(user_role, UserRole):
        return user_role
    try:
        return UserRole(str(user_role))
    except ValueError:
        return None


async def get_entities_for_user(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    user_role: UserRole | str,
) -> list[CpEntity]:
    normalized_role = _normalize_role(user_role)
    if normalized_role in _ALL_ENTITY_ROLES:
        result = await session.execute(
            select(CpEntity)
            .where(CpEntity.tenant_id == tenant_id)
            .where(CpEntity.status == "active")
            .order_by(CpEntity.entity_name)
        )
        return list(result.scalars().all())

    result = await session.execute(
        select(CpEntity)
        .join(CpUserEntityAssignment, CpUserEntityAssignment.entity_id == CpEntity.id)
        .where(CpEntity.tenant_id == tenant_id)
        .where(CpEntity.status == "active")
        .where(CpUserEntityAssignment.user_id == user_id)
        .where(CpUserEntityAssignment.is_active.is_(True))
        .order_by(CpEntity.entity_name)
    )
    return list(result.scalars().all())


async def get_entity_for_user(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    user_id: uuid.UUID,
    user_role: UserRole | str,
) -> CpEntity:
    entity = await session.get(CpEntity, entity_id)
    if entity is None or entity.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Entity not found")

    normalized_role = _normalize_role(user_role)
    if normalized_role in _ALL_ENTITY_ROLES:
        return entity

    assignment = (
        await session.execute(
            select(CpUserEntityAssignment)
            .where(CpUserEntityAssignment.user_id == user_id)
            .where(CpUserEntityAssignment.entity_id == entity_id)
            .where(CpUserEntityAssignment.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=403, detail="Access to this entity is not permitted")
    return entity


async def assert_entity_access(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    user_id: uuid.UUID,
    user_role: UserRole | str,
) -> None:
    if entity_id is None:
        return
    await get_entity_for_user(
        session=session,
        tenant_id=tenant_id,
        entity_id=entity_id,
        user_id=user_id,
        user_role=user_role,
    )


__all__ = ["get_entities_for_user", "get_entity_for_user", "assert_entity_access"]

