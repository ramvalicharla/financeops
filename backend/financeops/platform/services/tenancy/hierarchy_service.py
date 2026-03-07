from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.db.models.groups import CpGroup
from financeops.platform.db.models.organisations import CpOrganisation
from financeops.platform.db.models.user_membership import (
    CpUserEntityAssignment,
    CpUserOrganisationAssignment,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _now() -> datetime:
    return datetime.now(UTC)


async def create_organisation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    code: str,
    name: str,
    parent_organisation_id: uuid.UUID | None,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpOrganisation:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpOrganisation,
        tenant_id=tenant_id,
        record_data={"organisation_code": code, "organisation_name": name},
        values={
            "organisation_code": code,
            "organisation_name": name,
            "parent_organisation_id": parent_organisation_id,
            "supersedes_id": None,
            "is_active": True,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.hierarchy.organisation.created",
            resource_type="cp_organisation",
            new_value={"organisation_code": code},
        ),
    )


async def create_group(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    code: str,
    name: str,
    organisation_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpGroup:
    org_exists = await session.execute(
        select(CpOrganisation.id).where(
            CpOrganisation.tenant_id == tenant_id,
            CpOrganisation.id == organisation_id,
        )
    )
    if org_exists.scalar_one_or_none() is None:
        raise NotFoundError("Organisation not found")
    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpGroup,
        tenant_id=tenant_id,
        record_data={"group_code": code, "group_name": name, "organisation_id": str(organisation_id)},
        values={
            "group_code": code,
            "group_name": name,
            "organisation_id": organisation_id,
            "is_active": True,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.hierarchy.group.created",
            resource_type="cp_group",
            new_value={"group_code": code},
        ),
    )


async def create_entity(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_code: str,
    entity_name: str,
    organisation_id: uuid.UUID,
    group_id: uuid.UUID | None,
    base_currency: str,
    country_code: str,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpEntity:
    org_exists = await session.execute(
        select(CpOrganisation.id).where(
            CpOrganisation.tenant_id == tenant_id,
            CpOrganisation.id == organisation_id,
        )
    )
    if org_exists.scalar_one_or_none() is None:
        raise NotFoundError("Organisation not found")

    if group_id is not None:
        group_row = await session.execute(
            select(CpGroup.organisation_id).where(
                CpGroup.tenant_id == tenant_id,
                CpGroup.id == group_id,
            )
        )
        parent_org = group_row.scalar_one_or_none()
        if parent_org is None:
            raise NotFoundError("Group not found")
        if parent_org != organisation_id:
            raise ValidationError("Group must belong to the same organisation")

    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpEntity,
        tenant_id=tenant_id,
        record_data={"entity_code": entity_code, "entity_name": entity_name},
        values={
            "entity_code": entity_code,
            "entity_name": entity_name,
            "organisation_id": organisation_id,
            "group_id": group_id,
            "base_currency": base_currency.upper(),
            "country_code": country_code.upper(),
            "status": "active",
            "deactivated_at": None,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.hierarchy.entity.created",
            resource_type="cp_entity",
            new_value={"entity_code": entity_code},
        ),
    )


async def _ensure_no_overlap_org(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    organisation_id: uuid.UUID,
    effective_from: datetime,
    effective_to: datetime | None,
) -> None:
    result = await session.execute(
        select(CpUserOrganisationAssignment).where(
            CpUserOrganisationAssignment.tenant_id == tenant_id,
            CpUserOrganisationAssignment.user_id == user_id,
            CpUserOrganisationAssignment.organisation_id == organisation_id,
            CpUserOrganisationAssignment.is_active.is_(True),
        )
    )
    for row in result.scalars().all():
        row_end = row.effective_to or datetime.max.replace(tzinfo=UTC)
        incoming_end = effective_to or datetime.max.replace(tzinfo=UTC)
        if effective_from < row_end and row.effective_from < incoming_end:
            raise ValidationError("Overlapping organisation assignment window")


async def assign_user_to_organisation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    organisation_id: uuid.UUID,
    effective_from: datetime,
    effective_to: datetime | None,
    is_primary: bool,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpUserOrganisationAssignment:
    await _ensure_no_overlap_org(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        organisation_id=organisation_id,
        effective_from=effective_from,
        effective_to=effective_to,
    )
    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpUserOrganisationAssignment,
        tenant_id=tenant_id,
        record_data={
            "user_id": str(user_id),
            "organisation_id": str(organisation_id),
            "effective_from": effective_from.isoformat(),
        },
        values={
            "user_id": user_id,
            "organisation_id": organisation_id,
            "is_primary": is_primary,
            "is_active": True,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.membership.user_organisation.assigned",
            resource_type="cp_user_organisation_assignment",
            new_value={"user_id": str(user_id), "organisation_id": str(organisation_id)},
        ),
    )


async def assign_user_to_entity(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_id: uuid.UUID,
    effective_from: datetime,
    effective_to: datetime | None,
    actor_user_id: uuid.UUID,
    correlation_id: str,
) -> CpUserEntityAssignment:
    result = await session.execute(
        select(CpUserEntityAssignment).where(
            CpUserEntityAssignment.tenant_id == tenant_id,
            CpUserEntityAssignment.user_id == user_id,
            CpUserEntityAssignment.entity_id == entity_id,
            CpUserEntityAssignment.is_active.is_(True),
        )
    )
    for row in result.scalars().all():
        row_end = row.effective_to or datetime.max.replace(tzinfo=UTC)
        incoming_end = effective_to or datetime.max.replace(tzinfo=UTC)
        if effective_from < row_end and row.effective_from < incoming_end:
            raise ValidationError("Overlapping entity assignment window")

    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpUserEntityAssignment,
        tenant_id=tenant_id,
        record_data={
            "user_id": str(user_id),
            "entity_id": str(entity_id),
            "effective_from": effective_from.isoformat(),
        },
        values={
            "user_id": user_id,
            "entity_id": entity_id,
            "is_active": True,
            "effective_from": effective_from,
            "effective_to": effective_to,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.membership.user_entity.assigned",
            resource_type="cp_user_entity_assignment",
            new_value={"user_id": str(user_id), "entity_id": str(entity_id)},
        ),
    )
