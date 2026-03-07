from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.db.models.user_membership import CpUserEntityAssignment
from financeops.platform.services.tenancy.hierarchy_service import (
    assign_user_to_entity,
    create_entity,
    create_group,
    create_organisation,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


async def ensure_cp_tenant(async_session: AsyncSession, *, tenant_id, actor_user_id) -> None:
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=CpTenant,
        tenant_id=tenant_id,
        record_data={"tenant_code": f"TEN-{str(tenant_id)[:8]}", "status": "active"},
        values={
            "id": tenant_id,
            "tenant_code": f"TEN-{str(tenant_id)[:8]}",
            "display_name": "Tenant",
            "country_code": "US",
            "region": "us-east-1",
            "billing_tier": "pro",
            "status": "active",
            "correlation_id": "corr-hierarchy",
            "deactivated_at": None,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=actor_user_id,
            action="platform.test.seed",
            resource_type="cp_tenant",
            resource_id=str(tenant_id),
        ),
    )


@pytest.mark.asyncio
async def test_membership_tables_are_identity_only(async_session: AsyncSession, test_user) -> None:
    await ensure_cp_tenant(
        async_session,
        tenant_id=test_user.tenant_id,
        actor_user_id=test_user.id,
    )
    org = await create_organisation(
        async_session,
        tenant_id=test_user.tenant_id,
        code="ORG1",
        name="Org 1",
        parent_organisation_id=None,
        actor_user_id=test_user.id,
        correlation_id="corr-hierarchy",
    )
    grp = await create_group(
        async_session,
        tenant_id=test_user.tenant_id,
        code="GRP1",
        name="Group 1",
        organisation_id=org.id,
        actor_user_id=test_user.id,
        correlation_id="corr-hierarchy",
    )
    ent = await create_entity(
        async_session,
        tenant_id=test_user.tenant_id,
        entity_code="ENT1",
        entity_name="Entity 1",
        organisation_id=org.id,
        group_id=grp.id,
        base_currency="USD",
        country_code="US",
        actor_user_id=test_user.id,
        correlation_id="corr-hierarchy",
    )
    assignment = await assign_user_to_entity(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        entity_id=ent.id,
        effective_from=datetime.now(UTC),
        effective_to=None,
        actor_user_id=test_user.id,
        correlation_id="corr-hierarchy",
    )
    assert assignment.entity_id == ent.id
    assert not hasattr(CpUserEntityAssignment, "role_code")
