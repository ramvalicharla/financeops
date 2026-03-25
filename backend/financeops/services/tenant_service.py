from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.tenants import (
    IamTenant,
    IamWorkspace,
    TenantStatus,
    TenantType,
    WorkspaceStatus,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter

log = logging.getLogger(__name__)


def generate_tenant_slug(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]", "-", str(name).lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return (slug or "tenant")[:100]


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
    tenant_slug = generate_tenant_slug(display_name)
    tenant = await AuditWriter.insert_financial_record(
        session,
        model_class=IamTenant,
        tenant_id=tenant_id,
        record_data={
            "display_name": display_name,
            "slug": tenant_slug,
            "tenant_type": tenant_type.value,
            "country": country,
            "timezone": timezone_str,
            "status": TenantStatus.active.value,
        },
        values={
            "id": tenant_id,
            "display_name": display_name,
            "slug": tenant_slug,
            "tenant_type": tenant_type,
            "country": country,
            "timezone": timezone_str,
            "status": TenantStatus.active,
            "parent_tenant_id": parent_tenant_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            action="tenant.created",
            resource_type="tenant",
            resource_name=display_name,
            new_value={"tenant_type": tenant_type.value, "country": country},
        ),
    )
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


async def update_tenant_settings(
    session: AsyncSession,
    *,
    tenant: IamTenant,
    actor_user_id: uuid.UUID,
    display_name: str | None = None,
    timezone_str: str | None = None,
) -> IamTenant:
    """Update mutable tenant settings and persist via audited flush path."""
    old_state = {
        "display_name": tenant.display_name,
        "timezone": tenant.timezone,
    }
    changed = False

    if display_name is not None and display_name != tenant.display_name:
        tenant.display_name = display_name
        changed = True
    if timezone_str is not None and timezone_str != tenant.timezone:
        tenant.timezone = timezone_str
        changed = True
    if not changed:
        return tenant

    await AuditWriter.flush_with_audit(
        session,
        audit=AuditEvent(
            tenant_id=tenant.id,
            user_id=actor_user_id,
            action="tenant.updated",
            resource_type="tenant",
            resource_id=str(tenant.id),
            resource_name=tenant.display_name,
            old_value=old_state,
            new_value={
                "display_name": tenant.display_name,
                "timezone": tenant.timezone,
            },
        ),
    )
    return tenant


async def create_default_workspace(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    name: str = "Default",
) -> IamWorkspace:
    """Create the default workspace for a new tenant."""
    workspace = await AuditWriter.insert_record(
        session,
        record=IamWorkspace(
            tenant_id=tenant_id,
            name=name,
            status=WorkspaceStatus.active,
        ),
        audit=AuditEvent(
            tenant_id=tenant_id,
            action="workspace.created",
            resource_type="workspace",
            resource_name=name,
            new_value={"status": WorkspaceStatus.active.value},
        ),
    )
    return workspace


async def list_workspaces(
    session: AsyncSession, tenant_id: uuid.UUID
) -> list[IamWorkspace]:
    """List all workspaces for a tenant."""
    result = await session.execute(
        select(IamWorkspace).where(IamWorkspace.tenant_id == tenant_id)
    )
    return list(result.scalars().all())

