from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.audit import AuditTrail
from financeops.db.models.consolidation import ConsolidationLineItem
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash
from tests.utils.consolidation_seed import seed_consolidation_drill_dataset


async def _create_other_tenant_user_token(async_session: AsyncSession) -> str:
    tenant_id = uuid.uuid4()
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name="Other Tenant",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(
            {
                "display_name": "Other Tenant",
                "tenant_type": TenantType.direct.value,
                "country": "US",
                "timezone": "UTC",
            },
            GENESIS_HASH,
        ),
        previous_hash=GENESIS_HASH,
    )
    async_session.add(tenant)
    await async_session.flush()
    user = IamUser(
        tenant_id=tenant.id,
        email="otheruser@example.com",
        hashed_password=hash_password("OtherPass123!"),
        full_name="Other User",
        role=UserRole.finance_team,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(user)
    await async_session.flush()
    return create_access_token(user.id, tenant.id, user.role.value)


@pytest.mark.asyncio
async def test_drilldown_endpoints_are_deterministic_and_read_only(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant,
    test_user,
    test_access_token: str,
) -> None:
    seeded = await seed_consolidation_drill_dataset(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        correlation_id="corr-drill-endpoints",
    )
    run_id = seeded["run_id"]

    before_audit = int(
        await async_session.scalar(
            select(func.count()).select_from(AuditTrail).where(AuditTrail.tenant_id == test_tenant.id)
        )
        or 0
    )
    before_line_items = int(
        await async_session.scalar(
            select(func.count())
            .select_from(ConsolidationLineItem)
            .where(
                ConsolidationLineItem.tenant_id == test_tenant.id,
                ConsolidationLineItem.run_id == run_id,
            )
        )
        or 0
    )

    account_resp = await async_client.get(
        f"/api/v1/consolidation/run/{run_id}/accounts/4000",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert account_resp.status_code == 200
    account_payload = account_resp.json()
    assert account_payload["account_code"] == "4000"
    assert account_payload["child_entity_ids"] == sorted(account_payload["child_entity_ids"])

    entity_id = account_payload["child_entity_ids"][0]
    entity_resp = await async_client.get(
        f"/api/v1/consolidation/run/{run_id}/entities/{entity_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert entity_resp.status_code == 200
    entity_payload = entity_resp.json()
    assert entity_payload["child_line_item_ids"] == sorted(entity_payload["child_line_item_ids"])

    line_item_id = entity_payload["child_line_item_ids"][0]
    line_resp = await async_client.get(
        f"/api/v1/consolidation/run/{run_id}/line-items/{line_item_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert line_resp.status_code == 200
    line_payload = line_resp.json()
    assert line_payload["child_snapshot_line_id"]

    snapshot_resp = await async_client.get(
        f"/api/v1/consolidation/run/{run_id}/snapshot-lines/{line_payload['child_snapshot_line_id']}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert snapshot_resp.status_code == 200
    snapshot_payload = snapshot_resp.json()
    assert snapshot_payload["snapshot_line"]["snapshot_line_id"] == line_payload["child_snapshot_line_id"]

    after_audit = int(
        await async_session.scalar(
            select(func.count()).select_from(AuditTrail).where(AuditTrail.tenant_id == test_tenant.id)
        )
        or 0
    )
    after_line_items = int(
        await async_session.scalar(
            select(func.count())
            .select_from(ConsolidationLineItem)
            .where(
                ConsolidationLineItem.tenant_id == test_tenant.id,
                ConsolidationLineItem.run_id == run_id,
            )
        )
        or 0
    )
    assert after_audit == before_audit
    assert after_line_items == before_line_items


@pytest.mark.asyncio
async def test_drilldown_endpoints_enforce_tenant_isolation(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_tenant,
    test_user,
    test_access_token: str,
) -> None:
    seeded = await seed_consolidation_drill_dataset(
        async_session,
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        correlation_id="corr-drill-rls",
    )
    other_token = await _create_other_tenant_user_token(async_session)
    run_id = seeded["run_id"]

    own_response = await async_client.get(
        f"/api/v1/consolidation/run/{run_id}/accounts/4000",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert own_response.status_code == 200

    cross_tenant_response = await async_client.get(
        f"/api/v1/consolidation/run/{run_id}/accounts/4000",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert cross_tenant_response.status_code == 404
