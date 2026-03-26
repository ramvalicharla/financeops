from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.fixed_assets.application.depreciation_engine import (
    calculate_double_declining,
    calculate_it_act_wdv,
    calculate_slm,
    calculate_uop,
    calculate_wdv,
)
from financeops.modules.fixed_assets.application.fixed_asset_service import FixedAssetService
from financeops.modules.fixed_assets.application.impairment_engine import calculate_value_in_use
from financeops.modules.fixed_assets.models import FaDepreciationRun
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.db.models.organisations import CpOrganisation
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


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


async def _create_scoped_finance_team_user(
    async_client,
    async_session: AsyncSession,
    owner_user: IamUser,
    *,
    entity_id: str,
) -> IamUser:
    scoped_user = IamUser(
        tenant_id=owner_user.tenant_id,
        email=f"scoped-fa-{uuid.uuid4()}@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Scoped Finance Team",
        role=UserRole.finance_team,
        is_active=True,
    )
    async_session.add(scoped_user)
    await async_session.flush()

    assign_resp = await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(owner_user),
        json={
            "user_id": str(scoped_user.id),
            "entity_id": entity_id,
            "effective_from": datetime.utcnow().isoformat(),
            "effective_to": None,
        },
    )
    assert assign_resp.status_code == 200
    return scoped_user


async def _create_asset_class(
    service: FixedAssetService,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> uuid.UUID:
    row = await service.create_asset_class(
        tenant_id,
        entity_id,
        {
            "name": "Computers",
            "asset_type": "TANGIBLE",
            "default_method": "SLM",
            "default_useful_life_years": 3,
            "default_residual_pct": Decimal("0.0500"),
        },
    )
    return row.id


async def _create_asset(
    service: FixedAssetService,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    asset_class_id: uuid.UUID,
    asset_code: str = "FA-001",
    status: str = "ACTIVE",
) -> uuid.UUID:
    row = await service.create_asset(
        tenant_id,
        entity_id,
        {
            "asset_class_id": asset_class_id,
            "asset_code": asset_code,
            "asset_name": "Engineering Laptop",
            "description": "Workstation",
            "purchase_date": date(2026, 1, 1),
            "capitalisation_date": date(2026, 1, 1),
            "original_cost": Decimal("1200.0000"),
            "residual_value": Decimal("0.0000"),
            "useful_life_years": Decimal("1.0000"),
            "depreciation_method": "SLM",
            "status": status,
        },
    )
    return row.id


@pytest.mark.asyncio
async def test_create_asset_class(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA01")
    service = FixedAssetService(async_session)
    row = await service.create_asset_class(
        test_user.tenant_id,
        entity.id,
        {
            "name": "Servers",
            "asset_type": "TANGIBLE",
            "default_method": "SLM",
            "default_useful_life_years": 5,
        },
    )
    assert row.name == "Servers"


@pytest.mark.asyncio
async def test_create_asset(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA02")
    service = FixedAssetService(async_session)
    class_id = await _create_asset_class(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    asset_id = await _create_asset(
        service,
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        asset_class_id=class_id,
    )
    row = await service.get_asset(test_user.tenant_id, asset_id)
    assert row.asset_code == "FA-001"


@pytest.mark.asyncio
async def test_asset_code_unique_per_entity(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA03")
    service = FixedAssetService(async_session)
    class_id = await _create_asset_class(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    await _create_asset(service, tenant_id=test_user.tenant_id, entity_id=entity.id, asset_class_id=class_id)
    with pytest.raises(Exception):
        await _create_asset(service, tenant_id=test_user.tenant_id, entity_id=entity.id, asset_class_id=class_id)


@pytest.mark.asyncio
async def test_slm_calculation_correct() -> None:
    dep = calculate_slm(
        original_cost=Decimal("1200.0000"),
        residual_value=Decimal("0.0000"),
        useful_life_years=Decimal("1.0000"),
        period_days=365,
    )
    assert dep == Decimal("1200.0000")


@pytest.mark.asyncio
async def test_wdv_calculation_correct() -> None:
    dep = calculate_wdv(
        opening_nbv=Decimal("1000.0000"),
        rate=Decimal("0.1000"),
        period_days=365,
    )
    assert dep == Decimal("100.0000")


@pytest.mark.asyncio
async def test_double_declining_does_not_go_below_residual() -> None:
    dep = calculate_double_declining(
        opening_nbv=Decimal("100.0000"),
        useful_life_years=Decimal("2.0000"),
        residual_value=Decimal("80.0000"),
        period_days=365,
    )
    assert dep == Decimal("20.0000")


@pytest.mark.asyncio
async def test_it_act_half_year_convention() -> None:
    dep = calculate_it_act_wdv(
        opening_block_value=Decimal("1000.0000"),
        additions=Decimal("0.0000"),
        disposals=Decimal("0.0000"),
        rate=Decimal("0.1500"),
        half_year_additions=Decimal("200.0000"),
    )
    assert dep == Decimal("165.0000")


@pytest.mark.asyncio
async def test_uop_calculation_correct() -> None:
    dep = calculate_uop(
        original_cost=Decimal("1000.0000"),
        residual_value=Decimal("0.0000"),
        total_units=Decimal("1000"),
        units_this_period=Decimal("50"),
    )
    assert dep == Decimal("50.0000")


@pytest.mark.asyncio
async def test_all_depreciation_results_are_decimal() -> None:
    values = [
        calculate_slm(Decimal("100"), Decimal("0"), Decimal("1"), 365),
        calculate_wdv(Decimal("100"), Decimal("0.1"), 365),
        calculate_double_declining(Decimal("100"), Decimal("2"), Decimal("0"), 365),
        calculate_uop(Decimal("100"), Decimal("0"), Decimal("10"), Decimal("1")),
        calculate_it_act_wdv(Decimal("100"), Decimal("0"), Decimal("0"), Decimal("0.1")),
    ]
    assert all(isinstance(value, Decimal) for value in values)


@pytest.mark.asyncio
async def test_depreciation_run_creates_record(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA04")
    service = FixedAssetService(async_session)
    class_id = await _create_asset_class(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    await _create_asset(service, tenant_id=test_user.tenant_id, entity_id=entity.id, asset_class_id=class_id)

    rows = await service.run_depreciation(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        gaap="INDAS",
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_depreciation_run_idempotent(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA05")
    service = FixedAssetService(async_session)
    class_id = await _create_asset_class(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    await _create_asset(service, tenant_id=test_user.tenant_id, entity_id=entity.id, asset_class_id=class_id)

    await service.run_depreciation(test_user.tenant_id, entity.id, date(2026, 1, 1), date(2026, 12, 31), "INDAS")
    await service.run_depreciation(test_user.tenant_id, entity.id, date(2026, 1, 1), date(2026, 12, 31), "INDAS")
    count = int(
        (
            await async_session.execute(
                select(func.count()).select_from(FaDepreciationRun).where(FaDepreciationRun.tenant_id == test_user.tenant_id)
            )
        ).scalar_one()
    )
    assert count == 1


@pytest.mark.asyncio
async def test_depreciation_run_skips_disposed_assets(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA06")
    service = FixedAssetService(async_session)
    class_id = await _create_asset_class(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    await _create_asset(
        service,
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        asset_class_id=class_id,
        status="DISPOSED",
    )

    rows = await service.run_depreciation(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
    )
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_period_run_covers_all_active_assets(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA07")
    service = FixedAssetService(async_session)
    class_id = await _create_asset_class(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    await _create_asset(service, tenant_id=test_user.tenant_id, entity_id=entity.id, asset_class_id=class_id, asset_code="FA-101")
    await _create_asset(service, tenant_id=test_user.tenant_id, entity_id=entity.id, asset_class_id=class_id, asset_code="FA-102")
    await _create_asset(
        service,
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        asset_class_id=class_id,
        asset_code="FA-103",
        status="DISPOSED",
    )

    rows = await service.run_depreciation(test_user.tenant_id, entity.id, date(2026, 1, 1), date(2026, 12, 31), "INDAS")
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_proportional_revaluation(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA08")
    service = FixedAssetService(async_session)
    class_id = await _create_asset_class(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    asset_id = await _create_asset(service, tenant_id=test_user.tenant_id, entity_id=entity.id, asset_class_id=class_id)

    row = await service.post_revaluation(
        tenant_id=test_user.tenant_id,
        asset_id=asset_id,
        fair_value=Decimal("1500.0000"),
        method="PROPORTIONAL",
        revaluation_date=date(2026, 12, 31),
    )
    assert row.revaluation_surplus == Decimal("300.0000")


@pytest.mark.asyncio
async def test_elimination_revaluation(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA09")
    service = FixedAssetService(async_session)
    class_id = await _create_asset_class(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    asset_id = await _create_asset(service, tenant_id=test_user.tenant_id, entity_id=entity.id, asset_class_id=class_id)

    row = await service.post_revaluation(
        tenant_id=test_user.tenant_id,
        asset_id=asset_id,
        fair_value=Decimal("900.0000"),
        method="ELIMINATION",
        revaluation_date=date(2026, 12, 31),
    )
    assert row.method == "ELIMINATION"


@pytest.mark.asyncio
async def test_impairment_loss_calculated_correctly(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA10")
    service = FixedAssetService(async_session)
    class_id = await _create_asset_class(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    asset_id = await _create_asset(service, tenant_id=test_user.tenant_id, entity_id=entity.id, asset_class_id=class_id)

    row = await service.post_impairment(
        tenant_id=test_user.tenant_id,
        asset_id=asset_id,
        value_in_use=Decimal("600.0000"),
        fvlcts=Decimal("550.0000"),
        discount_rate=Decimal("0.1000"),
        impairment_date=date(2026, 12, 31),
    )
    assert row.impairment_loss == Decimal("600.0000")


@pytest.mark.asyncio
async def test_impairment_zero_if_recoverable_exceeds_nbv(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA11")
    service = FixedAssetService(async_session)
    class_id = await _create_asset_class(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    asset_id = await _create_asset(service, tenant_id=test_user.tenant_id, entity_id=entity.id, asset_class_id=class_id)

    row = await service.post_impairment(
        tenant_id=test_user.tenant_id,
        asset_id=asset_id,
        value_in_use=Decimal("2000.0000"),
        fvlcts=Decimal("1900.0000"),
        discount_rate=Decimal("0.1000"),
        impairment_date=date(2026, 12, 31),
    )
    assert row.impairment_loss == Decimal("0")


@pytest.mark.asyncio
async def test_value_in_use_discounted_cash_flow() -> None:
    value = calculate_value_in_use(
        [Decimal("100.00"), Decimal("120.00"), Decimal("140.00")],
        discount_rate=Decimal("0.1000"),
    )
    assert value > Decimal("0")


@pytest.mark.asyncio
async def test_fixed_asset_register_returns_all_assets(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA12")
    service = FixedAssetService(async_session)
    class_id = await _create_asset_class(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    await _create_asset(service, tenant_id=test_user.tenant_id, entity_id=entity.id, asset_class_id=class_id, asset_code="FA-201")
    await _create_asset(service, tenant_id=test_user.tenant_id, entity_id=entity.id, asset_class_id=class_id, asset_code="FA-202")

    rows = await service.get_fixed_asset_register(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        as_of_date=date(2026, 12, 31),
    )
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_fixed_asset_register_nbv_correct(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA13")
    service = FixedAssetService(async_session)
    class_id = await _create_asset_class(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    await _create_asset(service, tenant_id=test_user.tenant_id, entity_id=entity.id, asset_class_id=class_id)
    await service.run_depreciation(test_user.tenant_id, entity.id, date(2026, 1, 1), date(2026, 12, 31), "INDAS")

    rows = await service.get_fixed_asset_register(test_user.tenant_id, entity.id, date(2026, 12, 31), "INDAS")
    assert rows[0]["nbv"] == Decimal("0.0000")


@pytest.mark.asyncio
async def test_entity_isolation_fixed_assets(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA14")
    entity_b = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="FA15")

    assign_org_resp = await async_client.post(
        "/api/v1/platform/org/assignments/entity",
        headers=_auth_headers(test_user),
        json={
            "user_id": str(test_user.id),
            "entity_id": str(entity_a.id),
            "effective_from": datetime.utcnow().isoformat(),
            "effective_to": None,
        },
    )
    assert assign_org_resp.status_code in {200, 409}

    scoped_user = await _create_scoped_finance_team_user(
        async_client,
        async_session,
        test_user,
        entity_id=str(entity_b.id),
    )

    service = FixedAssetService(async_session)
    class_id = await _create_asset_class(service, tenant_id=test_user.tenant_id, entity_id=entity_a.id)
    asset_id = await _create_asset(
        service,
        tenant_id=test_user.tenant_id,
        entity_id=entity_a.id,
        asset_class_id=class_id,
        asset_code="FA-ISO",
    )

    denied = await async_client.get(
        f"/api/v1/fixed-assets/{asset_id}",
        headers=_auth_headers(scoped_user),
    )
    assert denied.status_code == 403
