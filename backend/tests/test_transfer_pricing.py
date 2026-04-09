from __future__ import annotations

from decimal import Decimal
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.core.security import create_access_token
from financeops.db.append_only import append_only_function_sql, create_trigger_sql, drop_trigger_sql
from financeops.db.models.users import IamUser
from financeops.modules.transfer_pricing.models import ICTransaction, TransferPricingDoc
from financeops.modules.transfer_pricing.service import (
    add_transaction as _add_transaction,
    check_3ceb_applicability,
    compute_arm_length_adjustment,
    generate_form_3ceb as _generate_form_3ceb,
)


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


def _governed_context(intent_type: str) -> MutationContext:
    return MutationContext(
        intent_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        actor_user_id=None,
        actor_role="finance_leader",
        intent_type=intent_type,
    )


async def add_transaction(*args, **kwargs):
    with governed_mutation_context(_governed_context("ADD_TRANSFER_PRICING_TRANSACTION")):
        return await _add_transaction(*args, **kwargs)


async def generate_form_3ceb(*args, **kwargs):
    with governed_mutation_context(_governed_context("GENERATE_TRANSFER_PRICING_DOC")):
        return await _generate_form_3ceb(*args, **kwargs)


@pytest.mark.asyncio
async def test_3ceb_required_when_international_exists(async_session: AsyncSession, test_user: IamUser) -> None:
    await add_transaction(
        async_session,
        tenant_id=test_user.tenant_id,
        fiscal_year=2026,
        transaction_type="services",
        related_party_name="Related Co",
        related_party_country="USA",
        transaction_amount=Decimal("1000.00"),
        currency="INR",
        pricing_method="TNMM",
        is_international=True,
    )
    payload = await check_3ceb_applicability(async_session, test_user.tenant_id, 2026)
    assert payload["is_required"] is True


@pytest.mark.asyncio
async def test_3ceb_not_required_when_no_transactions(async_session: AsyncSession, test_user: IamUser) -> None:
    payload = await check_3ceb_applicability(async_session, test_user.tenant_id, 2026)
    assert payload["is_required"] is False


@pytest.mark.asyncio
async def test_ic_transaction_append_only(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await add_transaction(
        async_session,
        tenant_id=test_user.tenant_id,
        fiscal_year=2026,
        transaction_type="services",
        related_party_name="R1",
        related_party_country="USA",
        transaction_amount=Decimal("500.00"),
        currency="INR",
        pricing_method="TNMM",
        is_international=True,
    )
    await async_session.execute(text(append_only_function_sql()))
    await async_session.execute(text(drop_trigger_sql("ic_transactions")))
    await async_session.execute(text(create_trigger_sql("ic_transactions")))
    await async_session.flush()

    with pytest.raises(Exception):
        await async_session.execute(text("UPDATE ic_transactions SET transaction_type='goods' WHERE id=:id"), {"id": row.id})


@pytest.mark.asyncio
async def test_transaction_amount_inr_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await add_transaction(
        async_session,
        tenant_id=test_user.tenant_id,
        fiscal_year=2026,
        transaction_type="services",
        related_party_name="R2",
        related_party_country="USA",
        transaction_amount=Decimal("500.00"),
        currency="INR",
        pricing_method="TNMM",
        is_international=True,
    )
    assert isinstance(row.transaction_amount_inr, Decimal)


@pytest.mark.asyncio
async def test_arm_length_adjustment_computed_correctly() -> None:
    adjustment = await compute_arm_length_adjustment(
        transaction_amount=Decimal("100.00"),
        arm_length_price=Decimal("100.00"),
        actual_price=Decimal("80.00"),
    )
    assert adjustment == Decimal("20.00")


@pytest.mark.asyncio
async def test_generate_3ceb_creates_doc(async_session: AsyncSession, test_user: IamUser) -> None:
    await add_transaction(
        async_session,
        tenant_id=test_user.tenant_id,
        fiscal_year=2026,
        transaction_type="services",
        related_party_name="R3",
        related_party_country="USA",
        transaction_amount=Decimal("100.00"),
        currency="INR",
        pricing_method="TNMM",
        is_international=True,
    )
    doc = await generate_form_3ceb(async_session, test_user.tenant_id, 2026, test_user.id)
    assert doc.document_type == "form_3ceb"


@pytest.mark.asyncio
async def test_doc_version_increments(async_session: AsyncSession, test_user: IamUser) -> None:
    first = await generate_form_3ceb(async_session, test_user.tenant_id, 2026, test_user.id)
    second = await generate_form_3ceb(async_session, test_user.tenant_id, 2026, test_user.id)
    assert second.version == first.version + 1


@pytest.mark.asyncio
async def test_all_amounts_decimal(async_session: AsyncSession, test_user: IamUser) -> None:
    row = await add_transaction(
        async_session,
        tenant_id=test_user.tenant_id,
        fiscal_year=2026,
        transaction_type="goods",
        related_party_name="R4",
        related_party_country="IND",
        transaction_amount=Decimal("100.00"),
        currency="INR",
        pricing_method="CUP",
        is_international=False,
    )
    assert isinstance(row.adjustment_required, Decimal)


@pytest.mark.asyncio
async def test_tp_rls(async_session: AsyncSession, test_user: IamUser) -> None:
    other = ICTransaction(
        tenant_id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        fiscal_year=2026,
        transaction_type="services",
        related_party_name="Other",
        related_party_country="USA",
        transaction_amount=Decimal("10.00"),
        currency="INR",
        transaction_amount_inr=Decimal("10.00"),
        pricing_method="TNMM",
        adjustment_required=Decimal("0.00"),
        is_international=True,
    )
    async_session.add(other)
    await async_session.flush()

    rows = (
        await async_session.execute(
            select(ICTransaction).where(ICTransaction.tenant_id == test_user.tenant_id)
        )
    ).scalars().all()
    assert all(row.tenant_id == test_user.tenant_id for row in rows)


@pytest.mark.asyncio
async def test_api_add_transaction(async_client, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/transfer-pricing/transactions",
        headers=_auth_headers(test_user),
        json={
            "fiscal_year": 2026,
            "transaction_type": "services",
            "related_party_name": "API Co",
            "related_party_country": "USA",
            "transaction_amount": "100.00",
            "currency": "INR",
            "pricing_method": "TNMM",
            "is_international": True,
        },
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_generate_3ceb(async_client, test_user: IamUser) -> None:
    response = await async_client.post(
        "/api/v1/transfer-pricing/generate-3ceb",
        headers=_auth_headers(test_user),
        json={"fiscal_year": 2026},
    )
    assert response.status_code == 200
    assert response.json()["data"]["document_type"] == "form_3ceb"


@pytest.mark.asyncio
async def test_applicability_endpoint(async_client, test_user: IamUser) -> None:
    response = await async_client.get("/api/v1/transfer-pricing/applicability?fiscal_year=2026", headers=_auth_headers(test_user))
    assert response.status_code == 200
    assert "is_required" in response.json()["data"]
