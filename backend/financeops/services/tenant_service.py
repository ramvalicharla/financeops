from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.tenants import IamTenant, IamWorkspace, TenantStatus, TenantType, WorkspaceStatus
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

log = logging.getLogger(__name__)


async def create_tenant(
    session: AsyncSession,
    *,
    display_name: str,
    tenant_type: TenantType,
    country: str,
    timezone_str: str = "UTC",
    parent_tenant_id: uuid.UUID | None = None,
) -> IamTenant:
    """Create a new tenant with genesis chain hash."""
    tenant_id = uuid.uuid4()
    record_data = {
        "display_name": display_name,
        "tenant_type": tenant_type.value,
        "country": country,
        "timezone": timezone_str,
        "status": TenantStatus.active.value,
    }
    chain_hash = compute_chain_hash(record_data, GENESIS_HASH)

    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,  # self-referential: tenant's own ID
        display_name=display_name,
        tenant_type=tenant_type,
        country=country,
        timezone=timezone_str,
        status=TenantStatus.active,
        parent_tenant_id=parent_tenant_id,
        chain_hash=chain_hash,
        previous_hash=GENESIS_HASH,
    )
    session.add(tenant)
    await session.flush()
    log.info("Tenant created: id=%s name=%s", tenant.id, display_name)
    return tenant


async def get_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> IamTenant:
    """Return tenant by ID or raise NotFoundError."""
    result = await session.execute(
        select(IamTenant).where(IamTenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise NotFoundError(f"Tenant {tenant_id} not found")
    return tenant


async def create_default_workspace(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    name: str = "Default",
) -> IamWorkspace:
    """Create the default workspace for a new tenant."""
    workspace = IamWorkspace(
        tenant_id=tenant_id,
        name=name,
        status=WorkspaceStatus.active,
    )
    session.add(workspace)
    await session.flush()
    return workspace


async def list_workspaces(session: AsyncSession, tenant_id: uuid.UUID) -> list[IamWorkspace]:
    """List all workspaces for a tenant."""
    result = await session.execute(
        select(IamWorkspace).where(IamWorkspace.tenant_id == tenant_id)
    )
    return list(result.scalars().all())
