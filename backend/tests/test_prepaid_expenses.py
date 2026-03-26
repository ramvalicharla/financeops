from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.core.security import create_access_token, hash_password
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.prepaid_expenses.application.amortisation_engine import calculate_slm_schedule
from financeops.modules.prepaid_expenses.application.prepaid_service import PrepaidService
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.db.models.organisations import CpOrganisation
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


async def _create_entity(async_session: AsyncSession, *, tenant_id: uuid.UUID, suffix: str) -> CpEntity:
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
        email=f"scoped-prepaid-{uuid.uuid4()}@example.com",
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


async def _create_schedule(
    service: PrepaidService,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    reference: str = "PP-001",
    total_amount: Decimal = Decimal("1200.0000"),
    coverage_start: date = date(2026, 1, 1),
    coverage_end: date = date(2026, 12, 31),
    status: str = "ACTIVE",
):
    return await service.create_schedule(
        tenant_id,
        entity_id,
        {
            "reference_number": reference,
            "description": "Annual subscription",
            "prepaid_type": "SUBSCRIPTION",
            "vendor_name": "SaaS Vendor",
            "invoice_number": "INV-001",
            "total_amount": total_amount,
            "coverage_start": coverage_start,
            "coverage_end": coverage_end,
            "amortisation_method": "SLM",
            "status": status,
        },
    )


@pytest.mark.asyncio
async def test_create_schedule(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP01")
    service = PrepaidService(async_session)
    row = await _create_schedule(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    assert row.reference_number == "PP-001"


@pytest.mark.asyncio
async def test_reference_unique_per_entity(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP02")
    service = PrepaidService(async_session)
    await _create_schedule(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    with pytest.raises(ValidationError):
        await _create_schedule(service, tenant_id=test_user.tenant_id, entity_id=entity.id)


@pytest.mark.asyncio
async def test_slm_schedule_sums_to_total() -> None:
    rows = calculate_slm_schedule(
        total_amount=Decimal("1200.0000"),
        coverage_start=date(2026, 1, 1),
        coverage_end=date(2026, 12, 31),
    )
    total = sum((row.amount for row in rows), start=Decimal("0"))
    assert total == Decimal("1200.0000")


@pytest.mark.asyncio
async def test_slm_last_period_absorbs_rounding() -> None:
    rows = calculate_slm_schedule(
        total_amount=Decimal("1000.0000"),
        coverage_start=date(2026, 1, 15),
        coverage_end=date(2026, 4, 14),
    )
    assert rows[-1].is_last_period is True
    total = sum((row.amount for row in rows), start=Decimal("0"))
    assert total == Decimal("1000.0000")


@pytest.mark.asyncio
async def test_slm_all_amounts_are_decimal() -> None:
    rows = calculate_slm_schedule(
        total_amount=Decimal("1000.0000"),
        coverage_start=date(2026, 1, 1),
        coverage_end=date(2026, 2, 28),
    )
    assert all(isinstance(row.amount, Decimal) for row in rows)


@pytest.mark.asyncio
async def test_run_period_creates_entries(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP03")
    service = PrepaidService(async_session)
    await _create_schedule(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    rows = await service.run_period(
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_run_period_idempotent(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP04")
    service = PrepaidService(async_session)
    schedule = await _create_schedule(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    first = await service.run_period(test_user.tenant_id, entity.id, date(2026, 1, 1), date(2026, 1, 31))
    second = await service.run_period(test_user.tenant_id, entity.id, date(2026, 1, 1), date(2026, 1, 31))
    entries = await service.get_entries(test_user.tenant_id, schedule.id, 0, 10)
    assert len(first) == 1
    assert len(second) == 1
    assert entries["total"] == 1


@pytest.mark.asyncio
async def test_run_period_updates_amortised_amount(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP05")
    service = PrepaidService(async_session)
    schedule = await _create_schedule(service, tenant_id=test_user.tenant_id, entity_id=entity.id)
    await service.run_period(test_user.tenant_id, entity.id, date(2026, 1, 1), date(2026, 1, 31))
    refreshed = await service.get_schedule(test_user.tenant_id, schedule.id)
    assert refreshed.amortised_amount > Decimal("0")


@pytest.mark.asyncio
async def test_run_period_sets_fully_amortised_status(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP06")
    service = PrepaidService(async_session)
    schedule = await _create_schedule(
        service,
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        reference="PP-006",
        total_amount=Decimal("100.0000"),
        coverage_start=date(2026, 1, 1),
        coverage_end=date(2026, 1, 31),
    )
    await service.run_period(test_user.tenant_id, entity.id, date(2026, 1, 1), date(2026, 1, 31))
    refreshed = await service.get_schedule(test_user.tenant_id, schedule.id)
    assert refreshed.status == "FULLY_AMORTISED"


@pytest.mark.asyncio
async def test_run_period_skips_cancelled_schedules(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP07")
    service = PrepaidService(async_session)
    await _create_schedule(
        service,
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        reference="PP-007",
        status="CANCELLED",
    )
    rows = await service.run_period(test_user.tenant_id, entity.id, date(2026, 1, 1), date(2026, 1, 31))
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_get_schedule_shows_past_and_future(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP08")
    service = PrepaidService(async_session)
    schedule = await _create_schedule(
        service,
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        reference="PP-008",
        coverage_start=date(2026, 1, 1),
        coverage_end=date(2026, 3, 31),
    )
    await service.run_period(test_user.tenant_id, entity.id, date(2026, 1, 1), date(2026, 1, 31))
    rows = await service.get_amortisation_schedule(test_user.tenant_id, schedule.id)
    assert any(item["is_actual"] for item in rows)
    assert any(not item["is_actual"] for item in rows)


@pytest.mark.asyncio
async def test_get_entries_pagination_respects_limit(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP09")
    service = PrepaidService(async_session)
    schedule = await _create_schedule(
        service,
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        reference="PP-009",
        coverage_start=date(2026, 1, 1),
        coverage_end=date(2026, 4, 30),
    )
    await service.run_period(test_user.tenant_id, entity.id, date(2026, 1, 1), date(2026, 1, 31))
    await service.run_period(test_user.tenant_id, entity.id, date(2026, 2, 1), date(2026, 2, 28))
    payload = await service.get_entries(test_user.tenant_id, schedule.id, skip=0, limit=1)
    assert len(payload["items"]) == 1
    assert payload["has_more"] is True


@pytest.mark.asyncio
async def test_get_schedules_filter_status(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP10")
    service = PrepaidService(async_session)
    await _create_schedule(service, tenant_id=test_user.tenant_id, entity_id=entity.id, reference="PP-010", status="ACTIVE")
    await _create_schedule(service, tenant_id=test_user.tenant_id, entity_id=entity.id, reference="PP-011", status="CANCELLED")
    payload = await service.get_schedules(test_user.tenant_id, entity.id, skip=0, limit=10, status="ACTIVE")
    assert all(item.status == "ACTIVE" for item in payload["items"])


@pytest.mark.asyncio
async def test_run_period_ignores_outside_coverage(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP11")
    service = PrepaidService(async_session)
    await _create_schedule(
        service,
        tenant_id=test_user.tenant_id,
        entity_id=entity.id,
        reference="PP-012",
        coverage_start=date(2026, 4, 1),
        coverage_end=date(2026, 4, 30),
    )
    rows = await service.run_period(test_user.tenant_id, entity.id, date(2026, 1, 1), date(2026, 1, 31))
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_schedule_update_non_financial_fields_allowed(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP12")
    service = PrepaidService(async_session)
    schedule = await _create_schedule(service, tenant_id=test_user.tenant_id, entity_id=entity.id, reference="PP-013")
    updated = await service.update_schedule(
        tenant_id=test_user.tenant_id,
        schedule_id=schedule.id,
        data={"description": "Updated description"},
    )
    assert updated.description == "Updated description"


@pytest.mark.asyncio
async def test_schedule_update_financial_fields_blocked_after_entries(async_session: AsyncSession, test_user: IamUser) -> None:
    entity = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP13")
    service = PrepaidService(async_session)
    schedule = await _create_schedule(service, tenant_id=test_user.tenant_id, entity_id=entity.id, reference="PP-014")
    await service.run_period(test_user.tenant_id, entity.id, date(2026, 1, 1), date(2026, 1, 31))
    with pytest.raises(ValidationError):
        await service.update_schedule(
            tenant_id=test_user.tenant_id,
            schedule_id=schedule.id,
            data={"total_amount": Decimal("999.0000")},
        )


@pytest.mark.asyncio
async def test_entity_isolation_prepaid(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_a = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP14")
    entity_b = await _create_entity(async_session, tenant_id=test_user.tenant_id, suffix="PP15")

    scoped_user = await _create_scoped_finance_team_user(
        async_client,
        async_session,
        test_user,
        entity_id=str(entity_b.id),
    )

    service = PrepaidService(async_session)
    schedule = await _create_schedule(service, tenant_id=test_user.tenant_id, entity_id=entity_a.id, reference="PP-015")

    denied = await async_client.get(
        f"/api/v1/prepaid/{schedule.id}",
        headers=_auth_headers(scoped_user),
    )
    assert denied.status_code == 403
