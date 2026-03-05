from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import TenantContextError

log = logging.getLogger(__name__)


async def set_tenant_context(session: AsyncSession, tenant_id: UUID | str) -> None:
    """Set PostgreSQL session variable used by RLS policies."""
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    log.debug("RLS context set for tenant %s", str(tenant_id)[:8])


async def clear_tenant_context(session: AsyncSession) -> None:
    """Clear the RLS context variable."""
    await session.execute(
        text("SELECT set_config('app.current_tenant_id', '', true)")
    )


async def get_current_tenant_from_db(session: AsyncSession) -> str:
    """Read back the currently-set tenant context variable from PostgreSQL."""
    result = await session.execute(
        text("SELECT current_setting('app.current_tenant_id', true)")
    )
    value = result.scalar()
    return str(value) if value else ""


async def verify_rls_active(session: AsyncSession, table_name: str) -> bool:
    """
    Confirm RLS is enabled on the given table.
    Queries pg_class to check relrowsecurity flag.
    """
    result = await session.execute(
        text(
            """
            SELECT relrowsecurity
            FROM pg_class
            WHERE relname = :table_name
            """
        ),
        {"table_name": table_name},
    )
    row = result.fetchone()
    if row is None:
        log.warning("Table %s not found in pg_class", table_name)
        return False
    enabled = bool(row[0])
    if not enabled:
        log.error("RLS NOT ACTIVE on table %s — security violation risk!", table_name)
    return enabled


async def assert_tenant_context(session: AsyncSession) -> str:
    """
    Assert that a tenant context is set; raise TenantContextError if not.
    Returns the current tenant_id string.
    """
    tenant_id = await get_current_tenant_from_db(session)
    if not tenant_id:
        raise TenantContextError("No tenant context set — RLS context missing")
    return tenant_id
