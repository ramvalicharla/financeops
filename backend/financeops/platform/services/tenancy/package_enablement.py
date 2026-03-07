from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.packages import CpPackage
from financeops.platform.db.models.tenant_packages import CpTenantPackageAssignment
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _now() -> datetime:
    return datetime.now(UTC)


async def create_package(
    session: AsyncSession,
    *,
    package_code: str,
    package_name: str,
    version: str,
    actor_tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    description: str | None,
) -> CpPackage:
    return await AuditWriter.insert_record(
        session,
        record=CpPackage(
            package_code=package_code,
            package_name=package_name,
            version=version,
            is_active=True,
            description=description,
        ),
        audit=AuditEvent(
            tenant_id=actor_tenant_id,
            user_id=actor_user_id,
            action="platform.package.created",
            resource_type="cp_package",
            new_value={"package_code": package_code, "version": version},
        ),
    )


async def assign_package_to_tenant(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    package_id: uuid.UUID,
    assignment_status: str,
    actor_user_id: uuid.UUID,
    correlation_id: str,
    effective_from: datetime | None = None,
    effective_to: datetime | None = None,
) -> CpTenantPackageAssignment:
    now = effective_from or _now()
    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpTenantPackageAssignment,
        tenant_id=tenant_id,
        record_data={
            "package_id": str(package_id),
            "assignment_status": assignment_status,
            "effective_from": now.isoformat(),
        },
        values={
            "package_id": package_id,
            "assignment_status": assignment_status,
            "effective_from": now,
            "effective_to": effective_to,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.package.assigned",
            resource_type="cp_tenant_package_assignment",
            new_value={"package_id": str(package_id), "assignment_status": assignment_status},
        ),
    )


async def get_active_package_assignment(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    as_of: datetime,
) -> CpTenantPackageAssignment | None:
    result = await session.execute(
        select(CpTenantPackageAssignment)
        .where(
            CpTenantPackageAssignment.tenant_id == tenant_id,
            CpTenantPackageAssignment.effective_from <= as_of,
            (CpTenantPackageAssignment.effective_to.is_(None) | (CpTenantPackageAssignment.effective_to > as_of)),
        )
        .order_by(CpTenantPackageAssignment.effective_from.desc())
    )
    return result.scalars().first()
