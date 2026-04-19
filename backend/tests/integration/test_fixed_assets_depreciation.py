from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal

import pytest

pytestmark = pytest.mark.committed_session

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.core.security import hash_password
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.coa.models import TenantCoaAccount
from financeops.modules.fixed_assets.application.depreciation_engine import (
    DepreciationMethod,
    IT_ACT_S32_THRESHOLD,
    get_depreciation,
)
from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService
from financeops.modules.fixed_assets.domain.exceptions import DepreciationCalculationError
from financeops.modules.fixed_assets.models import FaAsset, FaDepreciationRun
from financeops.modules.fixed_assets.tasks import _run_monthly_depreciation
from financeops.tasks.celery_app import celery_app
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.db.models.organisations import CpOrganisation
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _governed_context(intent_type: str) -> MutationContext:
    return MutationContext(
        intent_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        actor_user_id=None,
        actor_role=UserRole.finance_leader.value,
        intent_type=intent_type,
    )


async def _create_entity(
    async_session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    suffix: str,
) -> CpEntity:
    org = CpOrganisation(
        tenant_id=tenant_id,
        chain_hash=compute_chain_hash({"organisation_code": f"ORG_{suffix}"}, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        organisation_code=f"ORG_{suffix}",
        organisation_name=f"Org {suffix}",
        parent_organisation_id=None,
        supersedes_id=None,
        is_active=True,
    )
    async_session.add(org)
    await async_session.flush()

    entity = CpEntity(
        tenant_id=tenant_id,
        chain_hash=compute_chain_hash({"entity_code": f"ENT_{suffix}"}, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
        entity_code=f"ENT_{suffix}",
        entity_name=f"Entity {suffix}",
        organisation_id=org.id,
        group_id=None,
        base_currency="INR",
        country_code="IN",
        status="active",
    )
    async_session.add(entity)
    await async_session.flush()
    return entity


async def _create_second_active_user(async_session: AsyncSession, tenant_id: uuid.UUID) -> IamUser:
    user = IamUser(
        tenant_id=tenant_id,
        email=f"fa-approver-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="FA Approver",
        role=UserRole.finance_leader,
        is_active=True,
    )
    async_session.add(user)
    await async_session.flush()
    return user


async def _create_asset_class(
    async_session: AsyncSession,
    service: FixedAssetService,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> uuid.UUID:
    dep_expense = TenantCoaAccount(
        tenant_id=tenant_id,
        ledger_account_id=None,
        parent_subgroup_id=None,
        account_code=f"DEP-EXP-{uuid.uuid4().hex[:6].upper()}",
        display_name="Depreciation Expense",
        is_custom=True,
        is_active=True,
    )
    accum_dep = TenantCoaAccount(
        tenant_id=tenant_id,
        ledger_account_id=None,
        parent_subgroup_id=None,
        account_code=f"ACC-DEP-{uuid.uuid4().hex[:6].upper()}",
        display_name="Accumulated Depreciation",
        is_custom=True,
        is_active=True,
    )
    async_session.add(dep_expense)
    async_session.add(accum_dep)
    await async_session.flush()
    with governed_mutation_context(_governed_context("CREATE_FIXED_ASSET_CLASS")):
        row = await service.create_asset_class(
            tenant_id,
            entity_id,
            {
                "name": "Computers",
                "asset_type": "TANGIBLE",
                "default_method": "SLM",
                "default_useful_life_years": 3,
                "default_residual_pct": Decimal("0.0500"),
                "coa_dep_expense_account_id": dep_expense.id,
                "coa_accum_dep_account_id": accum_dep.id,
            },
        )
    return row.id


async def _create_asset(
    service: FixedAssetService,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    asset_class_id: uuid.UUID,
    asset_code: str,
    capitalisation_date: date,
    original_cost: Decimal,
    depreciation_method: str,
    status: str = "ACTIVE",
) -> uuid.UUID:
    with governed_mutation_context(_governed_context("CREATE_FIXED_ASSET")):
        row = await service.create_asset(
            tenant_id,
            entity_id,
            {
                "asset_class_id": asset_class_id,
                "asset_code": asset_code,
                "asset_name": f"Asset {asset_code}",
                "description": "Workstation",
                "purchase_date": capitalisation_date,
                "capitalisation_date": capitalisation_date,
                "original_cost": original_cost,
                "residual_value": Decimal("0.0000"),
                "useful_life_years": Decimal("1.0000"),
                "depreciation_method": depreciation_method,
                "status": status,
            },
        )
    return row.id


def _asset_for_calc(
    *,
    capitalisation_date: date | None,
    original_cost: Decimal,
    depreciation_method: str,
) -> FaAsset:
    return FaAsset(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        entity_id=uuid.uuid4(),
        asset_class_id=uuid.uuid4(),
        asset_code=f"FA-{uuid.uuid4().hex[:6]}",
        asset_name="Calc Asset",
        purchase_date=capitalisation_date,
        capitalisation_date=capitalisation_date,
        original_cost=original_cost,
        residual_value=Decimal("0.0000"),
        useful_life_years=Decimal("1.0000"),
        depreciation_method=depreciation_method,
        status="ACTIVE",
        is_active=True,
    )


@pytest.mark.asyncio
async def test_section_32_100_percent_in_acquisition_year_prorated() -> None:
    asset = _asset_for_calc(
        capitalisation_date=date(2026, 1, 1),
        original_cost=Decimal("12000.0000"),
        depreciation_method=DepreciationMethod.BLOCK_IT_ACT_S32,
    )
    depreciation = get_depreciation(
        asset=asset,
        opening_nbv=Decimal("12000.0000"),
        period_start=date(2025, 4, 1),
        period_end=date(2026, 3, 31),
        gaap="INDAS",
    )
    assert depreciation == Decimal("2958.9041")


@pytest.mark.asyncio
async def test_section_32_zero_in_subsequent_years() -> None:
    asset = _asset_for_calc(
        capitalisation_date=date(2026, 1, 1),
        original_cost=Decimal("12000.0000"),
        depreciation_method=DepreciationMethod.BLOCK_IT_ACT_S32,
    )
    depreciation = get_depreciation(
        asset=asset,
        opening_nbv=Decimal("12000.0000"),
        period_start=date(2026, 4, 1),
        period_end=date(2027, 3, 31),
        gaap="INDAS",
    )
    assert depreciation == Decimal("0.0000")


@pytest.mark.asyncio
async def test_section_32_partial_year_calculation_correct() -> None:
    asset = _asset_for_calc(
        capitalisation_date=date(2026, 2, 15),
        original_cost=Decimal("10000.0000"),
        depreciation_method=DepreciationMethod.BLOCK_IT_ACT_S32,
    )
    depreciation = get_depreciation(
        asset=asset,
        opening_nbv=Decimal("10000.0000"),
        period_start=date(2025, 4, 1),
        period_end=date(2026, 3, 31),
        gaap="INDAS",
    )
    assert depreciation == Decimal("1232.8767")


@pytest.mark.asyncio
async def test_section_32_threshold_asset_below_5000_auto_qualifies() -> None:
    asset = _asset_for_calc(
        capitalisation_date=date(2026, 3, 1),
        original_cost=IT_ACT_S32_THRESHOLD - Decimal("500.0000"),
        depreciation_method=DepreciationMethod.BLOCK_IT_ACT_S32,
    )
    depreciation = get_depreciation(
        asset=asset,
        opening_nbv=Decimal("4500.0000"),
        period_start=date(2025, 4, 1),
        period_end=date(2026, 3, 31),
        gaap="INDAS",
    )
    assert depreciation == Decimal("382.1918")


@pytest.mark.asyncio
async def test_get_depreciation_sl_unchanged_by_section_32_addition() -> None:
    asset = _asset_for_calc(
        capitalisation_date=date(2026, 1, 1),
        original_cost=Decimal("1200.0000"),
        depreciation_method=DepreciationMethod.SLM,
    )
    depreciation = get_depreciation(
        asset=asset,
        opening_nbv=Decimal("1200.0000"),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        gaap="INDAS",
    )
    assert depreciation == Decimal("1200.0000")


@pytest.mark.asyncio
async def test_missing_acquisition_date_raises_calculation_error() -> None:
    asset = _asset_for_calc(
        capitalisation_date=None,
        original_cost=Decimal("12000.0000"),
        depreciation_method=DepreciationMethod.BLOCK_IT_ACT_S32,
    )
    with pytest.raises(DepreciationCalculationError):
        get_depreciation(
            asset=asset,
            opening_nbv=Decimal("12000.0000"),
            period_start=date(2025, 4, 1),
            period_end=date(2026, 3, 31),
            gaap="INDAS",
        )


@pytest.mark.asyncio
async def test_monthly_task_posts_journal_entry_for_each_active_asset(
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    await _create_second_active_user(async_session, test_user.tenant_id)
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FADEP01")
    service = FixedAssetService(async_session)
    asset_class_id = await _create_asset_class(
        async_session,
        service,
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
    )
    await _create_asset(
        service,
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        asset_class_id=asset_class_id,
        asset_code="FA-301",
        capitalisation_date=date(2026, 4, 1),
        original_cost=Decimal("1200.0000"),
        depreciation_method="SLM",
    )
    await _create_asset(
        service,
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        asset_class_id=asset_class_id,
        asset_code="FA-302",
        capitalisation_date=date(2026, 4, 1),
        original_cost=Decimal("1200.0000"),
        depreciation_method="SLM",
    )
    await _create_asset(
        service,
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        asset_class_id=asset_class_id,
        asset_code="FA-303",
        capitalisation_date=date(2026, 4, 1),
        original_cost=Decimal("1200.0000"),
        depreciation_method="SLM",
        status="DISPOSED",
    )
    await async_session.commit()

    posted: list[str] = []

    async def _fake_poster(
        session,
        *,
        tenant_id,
        asset,
        asset_class,
        depreciation_amount,
        journal_reference,
        journal_date,
    ) -> str:
        del session, tenant_id, asset_class, depreciation_amount, journal_date
        posted.append(asset.asset_code)
        return journal_reference

    @asynccontextmanager
    async def _session_factory():
        yield async_session

    result = await _run_monthly_depreciation(
        tenant_id=str(test_user.tenant_id),
        period="2026-04",
        journal_poster=_fake_poster,
        session_factory=_session_factory,
    )

    count = int(
        (
            await async_session.execute(
                select(func.count()).select_from(FaDepreciationRun).where(FaDepreciationRun.tenant_id == test_user.tenant_id)
            )
        ).scalar_one()
    )
    assert result["created_runs"] == 2
    assert result["posted_journals"] == 2
    assert count == 2
    assert sorted(posted) == ["FA-301", "FA-302"]


def test_monthly_task_registered_in_celery() -> None:
    assert "financeops.modules.fixed_assets.tasks" in celery_app.conf.imports
    assert (
        celery_app.conf.beat_schedule["fa-monthly-depreciation"]["task"]
        == "financeops.modules.fixed_assets.tasks.run_monthly_depreciation_task"
    )
