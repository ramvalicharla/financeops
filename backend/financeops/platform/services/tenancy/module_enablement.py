from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.db.models.tenant_module_enablement import CpTenantModuleEnablement
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _now() -> datetime:
    return datetime.now(UTC)


async def create_module_registry_item(
    session: AsyncSession,
    *,
    module_code: str,
    module_name: str,
    engine_context: str,
    is_financial_impacting: bool,
    actor_tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> CpModuleRegistry:
    return await AuditWriter.insert_record(
        session,
        record=CpModuleRegistry(
            module_code=module_code,
            module_name=module_name,
            engine_context=engine_context,
            is_financial_impacting=is_financial_impacting,
            is_active=True,
        ),
        audit=AuditEvent(
            tenant_id=actor_tenant_id,
            user_id=actor_user_id,
            action="platform.module_registry.created",
            resource_type="cp_module_registry",
            new_value={"module_code": module_code, "engine_context": engine_context},
        ),
    )


async def set_module_enablement(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    module_id: uuid.UUID,
    enabled: bool,
    enablement_source: str,
    actor_user_id: uuid.UUID,
    correlation_id: str,
    effective_from: datetime | None = None,
    effective_to: datetime | None = None,
) -> CpTenantModuleEnablement:
    now = effective_from or _now()
    return await AuditWriter.insert_financial_record(
        session,
        model_class=CpTenantModuleEnablement,
        tenant_id=tenant_id,
        record_data={
            "module_id": str(module_id),
            "enabled": enabled,
            "effective_from": now.isoformat(),
        },
        values={
            "module_id": module_id,
            "enabled": enabled,
            "enablement_source": enablement_source,
            "effective_from": now,
            "effective_to": effective_to,
            "correlation_id": correlation_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.module_enablement.set",
            resource_type="cp_tenant_module_enablement",
            new_value={"module_id": str(module_id), "enabled": enabled},
        ),
    )


async def resolve_module_enablement(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    module_code: str,
    as_of: datetime,
) -> tuple[uuid.UUID, bool]:
    mod_result = await session.execute(
        select(CpModuleRegistry).where(CpModuleRegistry.module_code == module_code)
    )
    module = mod_result.scalar_one_or_none()
    if module is None:
        raise NotFoundError("Module registry entry not found")

    result = await session.execute(
        select(CpTenantModuleEnablement)
        .where(
            CpTenantModuleEnablement.tenant_id == tenant_id,
            CpTenantModuleEnablement.module_id == module.id,
            CpTenantModuleEnablement.effective_from <= as_of,
            (CpTenantModuleEnablement.effective_to.is_(None) | (CpTenantModuleEnablement.effective_to > as_of)),
        )
        .order_by(CpTenantModuleEnablement.effective_from.desc())
    )
    row = result.scalars().first()
    return module.id, bool(row.enabled) if row is not None else False
