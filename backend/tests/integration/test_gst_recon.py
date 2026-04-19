from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

pytestmark = pytest.mark.committed_session

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.db.models.gst import GstRateMaster, GstReconItem, GstReturn, GstReturnLineItem
from financeops.db.models.users import UserRole
from financeops.db.rls import set_tenant_context
from financeops.modules.gst_reconciliation.application.gst_service import (
    get_gst_rate_master,
    validate_gst_rate,
)
from financeops.modules.gst_reconciliation.application.gstn_import_service import parse_gstr1_json
from financeops.modules.gst_reconciliation.domain.exceptions import (
    GstRateMasterNotSeededError,
    InvalidGstinError,
)
from financeops.services.gst_service import import_gst_return_json, run_gst_reconciliation
from financeops.utils.gstin import validate_gstin


def _governed_context(intent_type: str) -> MutationContext:
    return MutationContext(
        intent_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        actor_user_id=None,
        actor_role=UserRole.finance_leader.value,
        intent_type=intent_type,
    )


async def _seed_rate_master(async_session: AsyncSession) -> None:
    await async_session.execute(delete(GstRateMaster))
    async_session.add_all(
        [
            GstRateMaster(rate=Decimal("0"), description="Zero"),
            GstRateMaster(rate=Decimal("1.5"), description="Diamonds"),
            GstRateMaster(rate=Decimal("3"), description="Gold"),
            GstRateMaster(rate=Decimal("5"), description="Five"),
            GstRateMaster(rate=Decimal("7.5"), description="Seven point five"),
            GstRateMaster(rate=Decimal("12"), description="Twelve"),
            GstRateMaster(rate=Decimal("18"), description="Eighteen"),
            GstRateMaster(rate=Decimal("28"), description="Twenty eight"),
        ]
    )
    await async_session.flush()


_BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_BASE36_MAP = {char: idx for idx, char in enumerate(_BASE36)}


def _checksum_char(body: str) -> str:
    total = 0
    for idx, char in enumerate(body):
        value = _BASE36_MAP[char]
        factor = 1 if idx % 2 == 0 else 2
        product = value * factor
        total += (product // 36) + (product % 36)
    return _BASE36[(36 - (total % 36)) % 36]


def _valid_gstin(state_code: str = "29") -> str:
    body = f"{state_code}AABCF1234A1Z"
    gstin = f"{body}{_checksum_char(body)}"
    assert validate_gstin(gstin) is True
    return gstin


def _line_item(
    *,
    supplier_gstin: str | None = None,
    invoice_number: str = "INV-001",
    invoice_date: str | None = None,
    taxable_value: str = "1000.00",
    igst: str = "180.00",
    cgst: str = "0.00",
    sgst: str = "0.00",
    cess: str = "0.00",
    gst_rate: str = "18",
    payment_status: str | None = None,
    expense_category: str | None = None,
) -> dict:
    payload = {
        "supplier_gstin": supplier_gstin or _valid_gstin(),
        "invoice_number": invoice_number,
        "invoice_date": invoice_date or (date.today() - timedelta(days=30)).isoformat(),
        "taxable_value": taxable_value,
        "igst": igst,
        "cgst": cgst,
        "sgst": sgst,
        "cess": cess,
        "gst_rate": gst_rate,
    }
    if payment_status is not None:
        payload["payment_status"] = payment_status
    if expense_category is not None:
        payload["expense_category"] = expense_category
    return payload


async def _import_return(
    async_session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    created_by: uuid.UUID,
    return_type: str,
    line_items: list[dict],
) -> None:
    with governed_mutation_context(_governed_context("PREPARE_GST_RETURN")):
        await import_gst_return_json(
            async_session,
            tenant_id=tenant_id,
            period_year=2025,
            period_month=4,
            entity_name="GST Recon Entity",
            gstin="29ABCDE1234F1Z5",
            return_type=return_type,
            json_data={"line_items": line_items},
            created_by=created_by,
        )


async def _run_recon(async_session: AsyncSession, *, tenant_id: uuid.UUID, run_by: uuid.UUID) -> list[GstReconItem]:
    with governed_mutation_context(_governed_context("RUN_GST_RECONCILIATION")):
        return await run_gst_reconciliation(
            async_session,
            tenant_id=tenant_id,
            period_year=2025,
            period_month=4,
            entity_name="GST Recon Entity",
            return_type_a="GSTR1",
            return_type_b="GSTR2B",
            run_by=run_by,
        )


@pytest.mark.asyncio
async def test_gstr1_json_import_valid_returns_line_items(
    api_session_factory: async_sessionmaker[AsyncSession], test_tenant
) -> None:
    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        await _seed_rate_master(session)
        with governed_mutation_context(_governed_context("PREPARE_GST_RETURN")):
            gst_return = await import_gst_return_json(
                session,
                tenant_id=test_tenant.id,
                period_year=2025,
                period_month=4,
                entity_name="GST Recon Entity",
                gstin="29ABCDE1234F1Z5",
                return_type="GSTR1",
                json_data={"line_items": [_line_item()]},
                created_by=test_tenant.id,
            )
        gst_return_id = gst_return.id
        await session.commit()

    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        rows = (
            await session.execute(
                select(GstReturnLineItem).where(GstReturnLineItem.gst_return_id == gst_return_id)
            )
        ).scalars().all()
        gst_return = (
            await session.execute(select(GstReturn).where(GstReturn.id == gst_return_id))
        ).scalar_one()
    assert len(rows) == 1
    assert rows[0].invoice_number == "INV-001"
    assert gst_return.total_tax == Decimal("180.00")


@pytest.mark.asyncio
async def test_gstr2b_json_import_valid_returns_line_items(
    api_session_factory: async_sessionmaker[AsyncSession], test_tenant
) -> None:
    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        await _seed_rate_master(session)
        await _import_return(
            session,
            tenant_id=test_tenant.id,
            created_by=test_tenant.id,
            return_type="GSTR2B",
            line_items=[_line_item(invoice_number="2B-001", gst_rate="3")],
        )
        await session.commit()

    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        rows = (
            await session.execute(
                select(GstReturnLineItem).where(GstReturnLineItem.return_type == "GSTR2B")
            )
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].invoice_number == "2B-001"


@pytest.mark.asyncio
async def test_invalid_gstin_raises_invalid_gstin_error(
    api_session_factory: async_sessionmaker[AsyncSession], test_tenant
) -> None:
    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        await _seed_rate_master(session)
        await session.commit()

    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        with pytest.raises(InvalidGstinError):
            with governed_mutation_context(_governed_context("PREPARE_GST_RETURN")):
                await import_gst_return_json(
                    session,
                    tenant_id=test_tenant.id,
                    period_year=2025,
                    period_month=4,
                    entity_name="GST Recon Entity",
                    gstin="29ABCDE1234F1Z5",
                    return_type="GSTR1",
                    json_data={"line_items": [_line_item(supplier_gstin="00ABCDE1234F1Z5")]},
                    created_by=test_tenant.id,
                )


@pytest.mark.asyncio
async def test_invoice_exact_match_creates_matched_item(
    api_session_factory: async_sessionmaker[AsyncSession], test_tenant
) -> None:
    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        await _seed_rate_master(session)
        await _import_return(session, tenant_id=test_tenant.id, created_by=test_tenant.id, return_type="GSTR1", line_items=[_line_item()])
        await _import_return(session, tenant_id=test_tenant.id, created_by=test_tenant.id, return_type="GSTR2B", line_items=[_line_item()])
        await session.commit()

    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        items = await _run_recon(session, tenant_id=test_tenant.id, run_by=test_tenant.id)

    assert len(items) == 1
    assert items[0].match_type == "matched"


@pytest.mark.asyncio
async def test_itc_rule_36_invoice_not_in_2b_is_ineligible(
    api_session_factory: async_sessionmaker[AsyncSession], test_tenant
) -> None:
    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        await _seed_rate_master(session)
        await _import_return(session, tenant_id=test_tenant.id, created_by=test_tenant.id, return_type="GSTR1", line_items=[_line_item()])
        await _import_return(session, tenant_id=test_tenant.id, created_by=test_tenant.id, return_type="GSTR2B", line_items=[])
        await session.commit()

    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        items = await _run_recon(session, tenant_id=test_tenant.id, run_by=test_tenant.id)

    assert len(items) == 1
    assert items[0].itc_eligible is False
    assert items[0].itc_blocked_reason == "rule_36_missing_in_gstr2b"


@pytest.mark.asyncio
async def test_itc_rule_36_invoice_in_2b_is_eligible(
    api_session_factory: async_sessionmaker[AsyncSession], test_tenant
) -> None:
    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        await _seed_rate_master(session)
        await _import_return(session, tenant_id=test_tenant.id, created_by=test_tenant.id, return_type="GSTR1", line_items=[_line_item()])
        await _import_return(session, tenant_id=test_tenant.id, created_by=test_tenant.id, return_type="GSTR2B", line_items=[_line_item()])
        await session.commit()

    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        items = await _run_recon(session, tenant_id=test_tenant.id, run_by=test_tenant.id)

    assert items[0].itc_eligible is True
    assert items[0].itc_blocked_reason is None


@pytest.mark.asyncio
async def test_itc_rule_37_payment_overdue_180_days_reverses_itc(
    api_session_factory: async_sessionmaker[AsyncSession], test_tenant
) -> None:
    overdue_date = (date.today() - timedelta(days=181)).isoformat()
    line = _line_item(invoice_date=overdue_date, payment_status="PENDING")
    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        await _seed_rate_master(session)
        await _import_return(session, tenant_id=test_tenant.id, created_by=test_tenant.id, return_type="GSTR1", line_items=[line])
        await _import_return(session, tenant_id=test_tenant.id, created_by=test_tenant.id, return_type="GSTR2B", line_items=[line])
        await session.commit()

    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        items = await _run_recon(session, tenant_id=test_tenant.id, run_by=test_tenant.id)

    assert items[0].reverse_itc is True
    assert items[0].itc_eligible is False
    assert items[0].itc_blocked_reason == "rule_37_payment_overdue"


@pytest.mark.asyncio
async def test_itc_rule_38_motor_vehicle_blocked(
    api_session_factory: async_sessionmaker[AsyncSession], test_tenant
) -> None:
    line = _line_item(expense_category="motor_vehicle")
    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        await _seed_rate_master(session)
        await _import_return(session, tenant_id=test_tenant.id, created_by=test_tenant.id, return_type="GSTR1", line_items=[line])
        await _import_return(session, tenant_id=test_tenant.id, created_by=test_tenant.id, return_type="GSTR2B", line_items=[line])
        await session.commit()

    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        items = await _run_recon(session, tenant_id=test_tenant.id, run_by=test_tenant.id)

    assert items[0].itc_eligible is False
    assert items[0].itc_blocked_reason == "blocked_category:motor_vehicle"


@pytest.mark.asyncio
async def test_gst_rate_18_valid(api_session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with api_session_factory() as session:
        await _seed_rate_master(session)
        await session.commit()

    async with api_session_factory() as session:
        master = await get_gst_rate_master(session)
    assert validate_gst_rate(Decimal("18"), master) is True


@pytest.mark.asyncio
async def test_gst_rate_15_invalid_flagged(
    api_session_factory: async_sessionmaker[AsyncSession], test_tenant
) -> None:
    line = _line_item(invoice_number="INV-015", gst_rate="15")
    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        await _seed_rate_master(session)
        await _import_return(session, tenant_id=test_tenant.id, created_by=test_tenant.id, return_type="GSTR1", line_items=[line])
        await _import_return(session, tenant_id=test_tenant.id, created_by=test_tenant.id, return_type="GSTR2B", line_items=[line])
        await session.commit()

    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        items = await _run_recon(session, tenant_id=test_tenant.id, run_by=test_tenant.id)

    assert items[0].rate_mismatch is True


@pytest.mark.asyncio
async def test_gst_rate_3_valid(api_session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with api_session_factory() as session:
        await _seed_rate_master(session)
        await session.commit()

    async with api_session_factory() as session:
        master = await get_gst_rate_master(session)
    assert validate_gst_rate(Decimal("3"), master) is True


@pytest.mark.asyncio
async def test_gst_rate_master_empty_raises(api_session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with api_session_factory() as session:
        await session.execute(delete(GstRateMaster))
        await session.commit()

    async with api_session_factory() as session:
        with pytest.raises(GstRateMasterNotSeededError):
            await get_gst_rate_master(session)


@pytest.mark.asyncio
async def test_parse_gstr1_json_returns_decimals() -> None:
    rows = parse_gstr1_json({"line_items": [_line_item()]})
    assert rows[0].taxable_value == Decimal("1000.00")
    assert rows[0].igst_amount == Decimal("180.00")
