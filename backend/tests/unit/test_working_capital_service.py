from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.db.models.users import UserRole
from financeops.services.working_capital_service import (
    create_snapshot,
    get_latest_snapshot,
    list_snapshots,
)


def _governed_context(intent_type: str) -> MutationContext:
    return MutationContext(
        intent_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        actor_user_id=None,
        actor_role=UserRole.finance_leader.value,
        intent_type=intent_type,
    )


@pytest.mark.asyncio
async def test_create_snapshot_basic(async_session: AsyncSession, test_tenant):
    with governed_mutation_context(_governed_context("CREATE_WORKING_CAPITAL_SNAPSHOT")):
        snap = await create_snapshot(
            async_session,
            tenant_id=test_tenant.id,
            period_year=2025,
            period_month=3,
            entity_name="WC_Entity",
            created_by=test_tenant.id,
            cash_and_equivalents=Decimal("10000"),
            accounts_receivable=Decimal("5000"),
            accounts_payable=Decimal("3000"),
        )
    assert snap.entity_name == "WC_Entity"
    assert snap.total_current_assets == Decimal("15000")
    assert snap.total_current_liabilities == Decimal("3000")
    assert snap.working_capital == Decimal("12000")
    assert len(snap.chain_hash) == 64


@pytest.mark.asyncio
async def test_create_snapshot_ratios(async_session: AsyncSession, test_tenant):
    with governed_mutation_context(_governed_context("CREATE_WORKING_CAPITAL_SNAPSHOT")):
        snap = await create_snapshot(
            async_session,
            tenant_id=test_tenant.id,
            period_year=2025,
            period_month=4,
            entity_name="Ratios_Entity",
            created_by=test_tenant.id,
            cash_and_equivalents=Decimal("2000"),
            accounts_receivable=Decimal("3000"),
            inventory=Decimal("1000"),
            accounts_payable=Decimal("2000"),
        )
    assert snap.current_ratio == Decimal("3.0000")
    assert snap.quick_ratio == Decimal("2.5000")
    assert snap.cash_ratio == Decimal("1.0000")


@pytest.mark.asyncio
async def test_create_snapshot_zero_liabilities(async_session: AsyncSession, test_tenant):
    with governed_mutation_context(_governed_context("CREATE_WORKING_CAPITAL_SNAPSHOT")):
        snap = await create_snapshot(
            async_session,
            tenant_id=test_tenant.id,
            period_year=2025,
            period_month=5,
            entity_name="ZeroLiab_Entity",
            created_by=test_tenant.id,
            cash_and_equivalents=Decimal("5000"),
        )
    assert snap.current_ratio == Decimal("0")
    assert snap.quick_ratio == Decimal("0")
    assert snap.cash_ratio == Decimal("0")


@pytest.mark.asyncio
async def test_get_latest_snapshot_returns_most_recent(
    async_session: AsyncSession, test_tenant
):
    entity = "Latest_Entity"
    with governed_mutation_context(_governed_context("CREATE_WORKING_CAPITAL_SNAPSHOT")):
        await create_snapshot(
            async_session,
            tenant_id=test_tenant.id,
            period_year=2025,
            period_month=1,
            entity_name=entity,
            created_by=test_tenant.id,
            cash_and_equivalents=Decimal("1000"),
        )
    with governed_mutation_context(_governed_context("CREATE_WORKING_CAPITAL_SNAPSHOT")):
        await create_snapshot(
            async_session,
            tenant_id=test_tenant.id,
            period_year=2025,
            period_month=3,
            entity_name=entity,
            created_by=test_tenant.id,
            cash_and_equivalents=Decimal("9999"),
        )
    latest = await get_latest_snapshot(async_session, test_tenant.id, entity)
    assert latest is not None
    assert latest.period_month == 3
    assert latest.cash_and_equivalents == Decimal("9999")


@pytest.mark.asyncio
async def test_list_snapshots_filter(async_session: AsyncSession, test_tenant):
    entity = "Filter_WC"
    with governed_mutation_context(_governed_context("CREATE_WORKING_CAPITAL_SNAPSHOT")):
        await create_snapshot(
            async_session,
            tenant_id=test_tenant.id,
            period_year=2025,
            period_month=6,
            entity_name=entity,
            created_by=test_tenant.id,
            cash_and_equivalents=Decimal("500"),
        )
    result = await list_snapshots(
        async_session, test_tenant.id, entity_name=entity
    )
    assert len(result) >= 1
    assert all(s.entity_name == entity for s in result)


@pytest.mark.asyncio
async def test_create_snapshot_requires_governed_context(async_session: AsyncSession, test_tenant):
    with pytest.raises(ValidationError):
        await create_snapshot(
            async_session,
            tenant_id=test_tenant.id,
            period_year=2025,
            period_month=7,
            entity_name="Blocked_WC",
            created_by=test_tenant.id,
            cash_and_equivalents=Decimal("100"),
        )
