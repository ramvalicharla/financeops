from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.users import IamUser
from financeops.modules.statutory.models import StatutoryFiling, StatutoryRegisterEntry
from financeops.modules.statutory.service import add_register_entry, get_compliance_calendar, get_register, mark_as_filed


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_compliance_calendar_seeded(async_session: AsyncSession, test_user: IamUser) -> None:
    rows = await get_compliance_calendar(async_session, test_user.tenant_id, date.today().year)
    assert len(rows) >= 7


@pytest.mark.asyncio
async def test_overdue_filing_detected(async_session: AsyncSession, test_user: IamUser) -> None:
    filing = StatutoryFiling(
        tenant_id=test_user.tenant_id,
        form_number="X-1",
        form_description="Test",
        due_date=date.today() - timedelta(days=1),
        status="pending",
        penalty_amount=Decimal("0.00"),
    )
    async_session.add(filing)
    await async_session.flush()
    rows = await get_compliance_calendar(async_session, test_user.tenant_id, date.today().year)
    target = next(row for row in rows if row["form_number"] == "X-1")
    assert target["is_overdue"] is True


@pytest.mark.asyncio
async def test_filed_filing_not_overdue(async_session: AsyncSession, test_user: IamUser) -> None:
    filing = StatutoryFiling(
        tenant_id=test_user.tenant_id,
        form_number="X-2",
        form_description="Filed",
        due_date=date.today() - timedelta(days=1),
        filed_date=date.today(),
        status="filed",
        penalty_amount=Decimal("0.00"),
    )
    async_session.add(filing)
    await async_session.flush()
    rows = await get_compliance_calendar(async_session, test_user.tenant_id, date.today().year)
    target = next(row for row in rows if row["form_number"] == "X-2")
    assert target["is_overdue"] is False


@pytest.mark.asyncio
async def test_mark_as_filed_creates_new_record(async_session: AsyncSession, test_user: IamUser) -> None:
    filing = StatutoryFiling(
        tenant_id=test_user.tenant_id,
        form_number="X-3",
        form_description="To file",
        due_date=date.today() + timedelta(days=5),
        status="pending",
        penalty_amount=Decimal("0.00"),
    )
    async_session.add(filing)
    await async_session.flush()

    before = len((await async_session.execute(select(StatutoryFiling).where(StatutoryFiling.form_number == "X-3"))).scalars().all())
    await mark_as_filed(async_session, test_user.tenant_id, filing.id, date.today(), "REF-001")
    after = len((await async_session.execute(select(StatutoryFiling).where(StatutoryFiling.form_number == "X-3"))).scalars().all())
    assert after == before + 1


@pytest.mark.asyncio
async def test_statutory_filings_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    filing = StatutoryFiling(
        tenant_id=test_user.tenant_id,
        form_number="X-4",
        form_description="Append",
        due_date=date.today(),
        status="pending",
        penalty_amount=Decimal("0.00"),
    )
    async_session.add(filing)
    await async_session.flush()

    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("statutory_filings")))
    await async_session.execute(text(create_trigger_sql("statutory_filings")))
    await async_session.flush()

    with pytest.raises(Exception):
        await async_session.execute(text("UPDATE statutory_filings SET status='filed' WHERE id=:id"), {"id": filing.id})


@pytest.mark.asyncio
async def test_register_entry_created(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await add_register_entry(
        async_session,
        tenant_id=test_user.tenant_id,
        register_type="members",
        entry_date=date.today(),
        entry_description="Member entry",
        folio_number="F-1",
    )
    assert row.id is not None


@pytest.mark.asyncio
async def test_register_paginated(async_session: AsyncSession, test_user: IamUser) -> None:
    for idx in range(5):
        await add_register_entry(
            async_session,
            tenant_id=test_user.tenant_id,
            register_type="directors",
            entry_date=date.today(),
            entry_description=f"Entry {idx}",
            folio_number=f"F-{idx}",
        )
    payload = await get_register(async_session, test_user.tenant_id, "directors", limit=2, offset=0)
    assert payload["total"] >= 5
    assert len(payload["data"]) == 2


@pytest.mark.asyncio
async def test_days_until_due_correct(async_session: AsyncSession, test_user: IamUser) -> None:
    filing = StatutoryFiling(
        tenant_id=test_user.tenant_id,
        form_number="X-5",
        form_description="Future",
        due_date=date.today() + timedelta(days=10),
        status="pending",
        penalty_amount=Decimal("0.00"),
    )
    async_session.add(filing)
    await async_session.flush()
    rows = await get_compliance_calendar(async_session, test_user.tenant_id, date.today().year)
    target = next(row for row in rows if row["form_number"] == "X-5")
    assert target["days_until_due"] == 10


@pytest.mark.asyncio
async def test_statutory_rls(async_session: AsyncSession, test_user: IamUser) -> None:
    payload = await get_register(async_session, test_user.tenant_id, "members")
    assert all(row.tenant_id == test_user.tenant_id for row in payload["data"])


@pytest.mark.asyncio
async def test_api_calendar_endpoint(async_client, test_user: IamUser) -> None:
    response = await async_client.get(f"/api/v1/statutory/calendar?fiscal_year={date.today().year}", headers=_auth_headers(test_user))
    assert response.status_code == 200
    assert isinstance(response.json()["data"], list)


@pytest.mark.asyncio
async def test_api_mark_filed(async_client, async_session: AsyncSession, test_user: IamUser) -> None:
    filing = StatutoryFiling(
        tenant_id=test_user.tenant_id,
        form_number="X-6",
        form_description="Mark",
        due_date=date.today(),
        status="pending",
        penalty_amount=Decimal("0.00"),
    )
    async_session.add(filing)
    await async_session.flush()

    response = await async_client.post(
        f"/api/v1/statutory/filings/{filing.id}/file",
        headers=_auth_headers(test_user),
        json={"filed_date": date.today().isoformat(), "filing_reference": "REF-2"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "filed"


@pytest.mark.asyncio
async def test_api_register_entry(async_client, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/statutory/registers/members",
        headers=_auth_headers(test_user),
        json={
            "entry_date": date.today().isoformat(),
            "entry_description": "API register",
            "folio_number": "F-API",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["register_type"] == "members"
