from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.working_capital import WorkingCapitalSnapshot
from financeops.modules.working_capital.models import APLineItem, ARLineItem, WCSnapshot
from financeops.services.audit_writer import AuditWriter
from financeops.services.reconciliation_service import (
    create_gl_entry,
    create_tb_row,
    list_gl_entries,
    run_ageing_gl_reconciliation,
    run_gl_tb_reconciliation,
    run_inventory_gl_reconciliation,
)


@pytest.mark.asyncio
async def test_create_gl_entry(async_session: AsyncSession, test_tenant):
    entry = await create_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=3,
        entity_name="Entity A",
        account_code="1000",
        account_name="Cash",
        debit_amount=Decimal("1000.00"),
        credit_amount=Decimal("0.00"),
        uploaded_by=test_tenant.id,
    )
    assert entry.account_code == "1000"
    assert entry.debit_amount == Decimal("1000.00")
    assert len(entry.chain_hash) == 64


@pytest.mark.asyncio
async def test_create_tb_row(async_session: AsyncSession, test_tenant):
    row = await create_tb_row(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025,
        period_month=3,
        entity_name="Entity A",
        account_code="1000",
        account_name="Cash",
        opening_balance=Decimal("0"),
        period_debit=Decimal("1000"),
        period_credit=Decimal("0"),
        closing_balance=Decimal("1000"),
        uploaded_by=test_tenant.id,
    )
    assert row.closing_balance == Decimal("1000")
    assert len(row.chain_hash) == 64


@pytest.mark.asyncio
async def test_reconciliation_no_break(async_session: AsyncSession, test_tenant):
    """GL total matches TB closing balance — no recon items created."""
    entity = "Recon_NB"
    period_year, period_month = 2025, 4
    await create_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        account_code="2000",
        account_name="AR",
        debit_amount=Decimal("500"),
        credit_amount=Decimal("0"),
        uploaded_by=test_tenant.id,
    )
    await create_tb_row(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        account_code="2000",
        account_name="AR",
        opening_balance=Decimal("0"),
        period_debit=Decimal("500"),
        period_credit=Decimal("0"),
        closing_balance=Decimal("500"),  # GL net = 500, TB = 500 → no break
        uploaded_by=test_tenant.id,
    )
    items = await run_gl_tb_reconciliation(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        run_by=test_tenant.id,
    )
    assert items == []


@pytest.mark.asyncio
async def test_reconciliation_finds_break(async_session: AsyncSession, test_tenant):
    """GL total differs from TB closing balance — one recon item created."""
    entity = "Recon_Break"
    period_year, period_month = 2025, 5
    await create_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        account_code="3000",
        account_name="Revenue",
        debit_amount=Decimal("0"),
        credit_amount=Decimal("1000"),
        uploaded_by=test_tenant.id,
    )
    await create_tb_row(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        account_code="3000",
        account_name="Revenue",
        opening_balance=Decimal("0"),
        period_debit=Decimal("0"),
        period_credit=Decimal("1200"),
        closing_balance=Decimal("1200"),  # TB has extra 200 → break
        uploaded_by=test_tenant.id,
    )
    items = await run_gl_tb_reconciliation(
        async_session,
        tenant_id=test_tenant.id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity,
        run_by=test_tenant.id,
    )
    assert len(items) == 1
    assert items[0].account_code == "3000"
    # GL net = 0 - 1000 = -1000; TB = 1200; diff = 1200 - (-1000) = 2200
    assert items[0].difference == Decimal("2200")
    assert items[0].status == "open"
    assert len(items[0].chain_hash) == 64


@pytest.mark.asyncio
async def test_gl_entry_chain_hash_sequence(async_session: AsyncSession, test_tenant):
    """GL entries form a valid hash chain."""
    e1 = await create_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025, period_month=6,
        entity_name="Chain", account_code="4000", account_name="Expenses",
        debit_amount=Decimal("100"), credit_amount=Decimal("0"),
        uploaded_by=test_tenant.id,
    )
    e2 = await create_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2025, period_month=6,
        entity_name="Chain", account_code="4001", account_name="Rent",
        debit_amount=Decimal("200"), credit_amount=Decimal("0"),
        uploaded_by=test_tenant.id,
    )
    assert e2.previous_hash == e1.chain_hash


@pytest.mark.asyncio
async def test_list_gl_entries_filter(async_session: AsyncSession, test_tenant):
    entity = "Filter_GL"
    await create_gl_entry(
        async_session, tenant_id=test_tenant.id,
        period_year=2025, period_month=1, entity_name=entity,
        account_code="5000", account_name="COGS",
        debit_amount=Decimal("300"), credit_amount=Decimal("0"),
        uploaded_by=test_tenant.id,
    )
    result = await list_gl_entries(
        async_session,
        test_tenant.id,
        period_year=2025,
        period_month=1,
        entity_name=entity,
    )
    assert len(result) >= 1
    assert all(e.entity_name == entity for e in result)


@pytest.mark.asyncio
async def test_create_gl_entry_uses_audit_writer(
    async_session: AsyncSession, test_tenant
):
    with patch(
        "financeops.services.reconciliation_service.AuditWriter.insert_financial_record",
        wraps=AuditWriter.insert_financial_record,
    ) as spy:
        await create_gl_entry(
            async_session,
            tenant_id=test_tenant.id,
            period_year=2025,
            period_month=10,
            entity_name="Audit Entity",
            account_code="9000",
            account_name="Audit",
            debit_amount=Decimal("1"),
            credit_amount=Decimal("0"),
            uploaded_by=test_tenant.id,
        )
    assert spy.await_count == 1


@pytest.mark.asyncio
async def test_create_tb_row_uses_audit_writer(
    async_session: AsyncSession, test_tenant
):
    with patch(
        "financeops.services.reconciliation_service.AuditWriter.insert_financial_record",
        wraps=AuditWriter.insert_financial_record,
    ) as spy:
        await create_tb_row(
            async_session,
            tenant_id=test_tenant.id,
            period_year=2025,
            period_month=10,
            entity_name="Audit Entity",
            account_code="9000",
            account_name="Audit",
            opening_balance=Decimal("0"),
            period_debit=Decimal("1"),
            period_credit=Decimal("0"),
            closing_balance=Decimal("1"),
            uploaded_by=test_tenant.id,
        )
    assert spy.await_count == 1


@pytest.mark.asyncio
async def test_ar_ageing_bucket_classification_and_variance(
    async_session: AsyncSession, test_tenant
):
    snapshot = WCSnapshot(
        tenant_id=test_tenant.id,
        period="2026-03",
        entity_id=None,
        snapshot_date=date(2026, 3, 31),
        ar_total=Decimal("1600.00"),
        ar_current=Decimal("0"),
        ar_30=Decimal("0"),
        ar_60=Decimal("0"),
        ar_90=Decimal("0"),
        dso_days=Decimal("0"),
        ap_total=Decimal("0"),
        ap_current=Decimal("0"),
        ap_30=Decimal("0"),
        ap_60=Decimal("0"),
        ap_90=Decimal("0"),
        dpo_days=Decimal("0"),
        inventory_days=Decimal("0"),
        ccc_days=Decimal("0"),
        net_working_capital=Decimal("0"),
        current_ratio=Decimal("1.0000"),
        quick_ratio=Decimal("1.0000"),
    )
    async_session.add(snapshot)
    await async_session.flush()
    async_session.add_all(
        [
            ARLineItem(
                snapshot_id=snapshot.id,
                tenant_id=test_tenant.id,
                customer_name="Customer A",
                invoice_number="AR-001",
                invoice_date=date(2026, 2, 1),
                due_date=date(2026, 3, 10),
                days_overdue=45,
                amount=Decimal("1000.00"),
                currency="USD",
                amount_base_currency=Decimal("1000.00"),
                aging_bucket="days_30",
            ),
            ARLineItem(
                snapshot_id=snapshot.id,
                tenant_id=test_tenant.id,
                customer_name="Customer B",
                invoice_number="AR-002",
                invoice_date=date(2026, 1, 15),
                due_date=date(2026, 2, 14),
                days_overdue=95,
                amount=Decimal("600.00"),
                currency="USD",
                amount_base_currency=Decimal("600.00"),
                aging_bucket="over_90",
            ),
        ]
    )
    await create_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2026,
        period_month=3,
        entity_name="HQ",
        account_code="1101",
        account_name="AR 31-60",
        debit_amount=Decimal("800.00"),
        credit_amount=Decimal("0"),
        uploaded_by=test_tenant.id,
        currency="USD",
    )

    result = await run_ageing_gl_reconciliation(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2026,
        period_month=3,
        ageing_type="ar",
        entity_name="HQ",
        gl_account_mapping={
            "0-30": [],
            "31-60": ["1101"],
            "61-90": [],
            "90+": ["1199"],
        },
        run_by=test_tenant.id,
    )

    bucket_map = {row["bucket"]: row for row in result["bucket_results"]}
    assert bucket_map["31-60"]["ar_total"] == "1000.00"
    assert bucket_map["31-60"]["gl_balance"] == "800.00"
    assert bucket_map["31-60"]["variance"] == "200.00"
    assert bucket_map["31-60"]["within_tolerance"] is False
    assert bucket_map["90+"]["variance"] == "600.00"
    assert bucket_map["90+"]["within_tolerance"] is True
    assert len(result["items"]) == 1
    assert all(item.recon_type == "ar_ageing_gl" for item in result["items"])


@pytest.mark.asyncio
async def test_ap_ageing_tolerance_can_allow_mismatch(
    async_session: AsyncSession, test_tenant
):
    snapshot = WCSnapshot(
        tenant_id=test_tenant.id,
        period="2026-04",
        entity_id=None,
        snapshot_date=date(2026, 4, 30),
        ar_total=Decimal("0"),
        ar_current=Decimal("0"),
        ar_30=Decimal("0"),
        ar_60=Decimal("0"),
        ar_90=Decimal("0"),
        dso_days=Decimal("0"),
        ap_total=Decimal("450.00"),
        ap_current=Decimal("0"),
        ap_30=Decimal("0"),
        ap_60=Decimal("0"),
        ap_90=Decimal("0"),
        dpo_days=Decimal("0"),
        inventory_days=Decimal("0"),
        ccc_days=Decimal("0"),
        net_working_capital=Decimal("0"),
        current_ratio=Decimal("1.0000"),
        quick_ratio=Decimal("1.0000"),
    )
    async_session.add(snapshot)
    await async_session.flush()
    async_session.add(
        APLineItem(
            snapshot_id=snapshot.id,
            tenant_id=test_tenant.id,
            vendor_name="Vendor A",
            invoice_number="AP-001",
            invoice_date=date(2026, 3, 1),
            due_date=date(2026, 3, 31),
            days_overdue=70,
            amount=Decimal("450.00"),
            currency="USD",
            amount_base_currency=Decimal("450.00"),
            aging_bucket="days_60",
            early_payment_discount_available=False,
        )
    )
    await create_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2026,
        period_month=4,
        entity_name="HQ",
        account_code="2100",
        account_name="AP 61-90",
        debit_amount=Decimal("0"),
        credit_amount=Decimal("50.00"),
        uploaded_by=test_tenant.id,
        currency="USD",
    )

    result = await run_ageing_gl_reconciliation(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2026,
        period_month=4,
        ageing_type="ap",
        entity_name="HQ",
        gl_account_mapping={
            "0-30": [],
            "31-60": [],
            "61-90": ["2100"],
            "90+": [],
        },
        tolerance_by_bucket={"61-90": "500"},
        run_by=test_tenant.id,
    )

    bucket_map = {row["bucket"]: row for row in result["bucket_results"]}
    assert bucket_map["61-90"]["variance"] == "500.00"
    assert bucket_map["61-90"]["within_tolerance"] is True
    assert result["items"] == []


@pytest.mark.asyncio
async def test_inventory_vs_gl_creates_recon_item_on_mismatch(
    async_session: AsyncSession, test_tenant
):
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=WorkingCapitalSnapshot,
        tenant_id=test_tenant.id,
        record_data={
            "period_year": 2026,
            "period_month": 5,
            "entity_name": "HQ",
            "inventory": "500000.00",
        },
        values={
            "period_year": 2026,
            "period_month": 5,
            "entity_name": "HQ",
            "currency": "USD",
            "cash_and_equivalents": Decimal("0"),
            "accounts_receivable": Decimal("0"),
            "inventory": Decimal("500000.00"),
            "prepaid_expenses": Decimal("0"),
            "other_current_assets": Decimal("0"),
            "total_current_assets": Decimal("500000.00"),
            "accounts_payable": Decimal("0"),
            "accrued_liabilities": Decimal("0"),
            "short_term_debt": Decimal("0"),
            "other_current_liabilities": Decimal("0"),
            "total_current_liabilities": Decimal("0"),
            "working_capital": Decimal("500000.00"),
            "current_ratio": Decimal("1.0000"),
            "quick_ratio": Decimal("1.0000"),
            "cash_ratio": Decimal("0.0000"),
            "created_by": test_tenant.id,
            "notes": "inventory test",
        },
    )
    await create_gl_entry(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2026,
        period_month=5,
        entity_name="HQ",
        account_code="1300",
        account_name="Inventory",
        debit_amount=Decimal("480000.00"),
        credit_amount=Decimal("0"),
        uploaded_by=test_tenant.id,
        currency="USD",
    )

    result = await run_inventory_gl_reconciliation(
        async_session,
        tenant_id=test_tenant.id,
        period_year=2026,
        period_month=5,
        entity_name="HQ",
        gl_account_codes=["1300"],
        run_by=test_tenant.id,
    )

    assert result["result"]["inventory_value"] == "500000.00"
    assert result["result"]["gl_balance"] == "480000.00"
    assert result["result"]["variance"] == "20000.00"
    assert result["result"]["status"] == "MISMATCH"
    assert result["item"] is not None
    assert result["item"].recon_type == "inventory_gl"


@pytest.mark.asyncio
async def test_inventory_vs_gl_requires_explicit_mapping(
    async_session: AsyncSession, test_tenant
):
    with pytest.raises(ValueError, match="Explicit GL account mapping is required"):
        await run_inventory_gl_reconciliation(
            async_session,
            tenant_id=test_tenant.id,
            period_year=2026,
            period_month=6,
            entity_name="HQ",
            gl_account_codes=[],
            run_by=test_tenant.id,
        )
