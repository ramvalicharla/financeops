from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from financeops.db.models.accounting_jv import EntryType, JVStatus
from financeops.modules.accounting_layer.application import revaluation_service
from financeops.modules.accounting_layer.application.journal_service import _append_gl_entries
from financeops.services.consolidation import group_consolidation_service
from financeops.services.consolidation.translation_service import translate_group_financials


class _FakeAsyncSession:
    async def flush(self) -> None:
        return None


class _CollectorSession(_FakeAsyncSession):
    def __init__(self) -> None:
        self.rows: list[Any] = []

    def add(self, row: Any) -> None:
        self.rows.append(row)


@pytest.mark.asyncio
async def test_gl_entries_stored_in_functional_currency_only() -> None:
    tenant_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    db = _CollectorSession()
    jv = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        chain_hash="0" * 64,
        version=1,
        jv_number="JV-TEST-001",
        description="FX Journal",
        currency="INR",
        lines=[
            SimpleNamespace(
                jv_version=1,
                line_number=1,
                entry_type=EntryType.DEBIT,
                amount=Decimal("100.00"),  # transaction amount (USD)
                base_amount=Decimal("8300.00"),  # functional amount (INR)
                account_code="1100",
                account_name="Trade Receivable",
                functional_currency="INR",
            ),
            SimpleNamespace(
                jv_version=1,
                line_number=2,
                entry_type=EntryType.CREDIT,
                amount=Decimal("100.00"),
                base_amount=Decimal("8300.00"),
                account_code="4000",
                account_name="Revenue",
                functional_currency="INR",
            ),
        ],
    )
    entity = SimpleNamespace(id=entity_id, entity_name="Entity A", base_currency="INR")

    await _append_gl_entries(
        db,
        jv=jv,
        entity=entity,
        created_by=uuid.uuid4(),
        journal_date=date(2026, 4, 1),
    )

    assert len(db.rows) == 2
    assert all(row.currency == "INR" for row in db.rows)
    assert db.rows[0].debit_amount == Decimal("8300.00")
    assert db.rows[0].credit_amount == Decimal("0")
    assert db.rows[1].debit_amount == Decimal("0")
    assert db.rows[1].credit_amount == Decimal("8300.00")


@pytest.mark.asyncio
async def test_revaluation_posts_fx_gain_to_pnl_account(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()
    db = _FakeAsyncSession()

    captured_lines: list[dict[str, Any]] = []

    async def _fake_get_entity_for_tenant(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(id=entity_id, base_currency="INR")

    async def _fake_load_exposures(*args: Any, **kwargs: Any) -> Any:
        return [
            revaluation_service._Exposure(
                account_code="1100",
                account_name="Trade Receivable",
                transaction_currency="USD",
                functional_currency="INR",
                foreign_balance=Decimal("100"),
                historical_base_balance=Decimal("8000"),
            )
        ]

    async def _fake_get_latest_rate(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(rate=Decimal("82"))

    async def _fake_create_jv(*args: Any, **kwargs: Any) -> Any:
        nonlocal captured_lines
        captured_lines = kwargs["lines"]
        return SimpleNamespace(id=uuid.uuid4(), status=JVStatus.DRAFT)

    async def _fake_noop(*args: Any, **kwargs: Any) -> Any:
        return None

    async def _fake_audit_insert(*args: Any, **kwargs: Any) -> Any:
        model_class = kwargs.get("model_class")
        if getattr(model_class, "__name__", "") == "AccountingFxRevaluationRun":
            return SimpleNamespace(id=run_id)
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(revaluation_service, "_get_entity_for_tenant", _fake_get_entity_for_tenant)
    monkeypatch.setattr(revaluation_service, "_load_monetary_exposures", _fake_load_exposures)
    monkeypatch.setattr(revaluation_service, "get_required_latest_fx_rate", _fake_get_latest_rate)
    monkeypatch.setattr(revaluation_service, "create_jv", _fake_create_jv)
    monkeypatch.setattr(revaluation_service, "approve_journal", _fake_noop)
    monkeypatch.setattr(revaluation_service, "post_journal", _fake_noop)
    monkeypatch.setattr(
        revaluation_service.AuditWriter,
        "insert_financial_record",
        staticmethod(_fake_audit_insert),
    )

    result = await revaluation_service.run_fx_revaluation(
        db,
        tenant_id=tenant_id,
        entity_id=entity_id,
        as_of_date=date(2026, 4, 1),
        initiated_by=user_id,
    )

    assert result["status"] == "COMPLETED"
    # (82 - 80) * 100
    assert result["total_fx_difference"] == "200.0000"

    assert len(captured_lines) == 2
    receivable_line = next(line for line in captured_lines if line["account_code"] == "1100")
    fx_gain_loss_line = next(
        line for line in captured_lines if line["account_code"] == "FX_GAIN_LOSS"
    )

    assert receivable_line["entry_type"] == EntryType.DEBIT
    assert receivable_line["amount"] == Decimal("200.0000")
    # Gain goes to P&L as credit in this scenario.
    assert fx_gain_loss_line["entry_type"] == EntryType.CREDIT
    assert fx_gain_loss_line["amount"] == Decimal("200.0000")


@pytest.mark.asyncio
async def test_translation_reports_cta_separate_from_pnl(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    group_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    cp_entity_id = uuid.uuid4()
    db = _FakeAsyncSession()

    async def _fake_load_group_entities(*args: Any, **kwargs: Any) -> Any:
        group = SimpleNamespace(group_name="Group A")
        entities = [
            SimpleNamespace(
                id=entity_id,
                cp_entity_id=cp_entity_id,
                legal_name="Entity A",
                functional_currency="USD",
            )
        ]
        return group, entities

    async def _fake_get_bs(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(
            totals=SimpleNamespace(
                assets=Decimal("1000"),
                liabilities=Decimal("600"),
                equity=Decimal("400"),
            ),
            retained_earnings=Decimal("100"),
        )

    async def _fake_get_pnl(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(net_profit=Decimal("100"))

    async def _fake_get_rate(*args: Any, **kwargs: Any) -> Any:
        rate_type = kwargs["rate_type"]
        return SimpleNamespace(rate=Decimal("80" if rate_type == "CLOSING" else "75"))

    monkeypatch.setattr(
        "financeops.services.consolidation.translation_service._load_group_entities",
        _fake_load_group_entities,
    )
    monkeypatch.setattr(
        "financeops.services.consolidation.translation_service.get_balance_sheet",
        _fake_get_bs,
    )
    monkeypatch.setattr(
        "financeops.services.consolidation.translation_service.get_profit_and_loss",
        _fake_get_pnl,
    )
    monkeypatch.setattr(
        "financeops.services.consolidation.translation_service.get_required_latest_fx_rate",
        _fake_get_rate,
    )

    result = await translate_group_financials(
        db,
        tenant_id=tenant_id,
        org_group_id=group_id,
        presentation_currency="INR",
        as_of_date=date(2026, 4, 1),
        initiated_by=None,
    )

    assert result["cta_account_code"] == "CTA_FCTR"
    assert "total_cta" in result["totals"]
    assert result["entity_results"][0]["translated_net_profit"] == "7500.0000"
    # CTA is reported separately, not merged into translated net profit.
    assert result["entity_results"][0]["cta_amount"] != result["entity_results"][0]["translated_net_profit"]


@pytest.mark.asyncio
async def test_consolidation_translates_before_elimination(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    group_id = uuid.uuid4()
    org_entity_id = uuid.uuid4()
    cp_entity_id = uuid.uuid4()
    as_of_date = date(2026, 4, 1)

    captured_balance: dict[str, Decimal] = {}

    async def _fake_load_scope(*args: Any, **kwargs: Any) -> Any:
        group = SimpleNamespace(group_name="Group A", reporting_currency="INR")
        entities = [
            group_consolidation_service._EntityRow(
                org_entity_id=org_entity_id,
                cp_entity_id=cp_entity_id,
                legal_name="Entity A",
                reporting_currency="USD",
            )
        ]
        return group, entities, {}, {org_entity_id: Decimal("1")}

    async def _fake_fetch_gl(*args: Any, **kwargs: Any) -> Any:
        return [
            group_consolidation_service._GlAggregateRow(
                cp_entity_id=cp_entity_id,
                account_code="1000",
                account_name="Cash",
                debit_sum=Decimal("100"),
                credit_sum=Decimal("0"),
                bs_pl_flag="ASSET",
                asset_liability_class="CURRENT_ASSET",
            )
        ]

    async def _fake_rate(*args: Any, **kwargs: Any) -> Any:
        return SimpleNamespace(rate=Decimal("80"))

    def _fake_eliminations(*, account_map: Any, account_entity_exposure: Any) -> Any:
        captured_balance["debit_sum"] = account_map["1000"].debit_sum
        captured_balance["credit_sum"] = account_map["1000"].credit_sum
        captured_balance["balance"] = account_map["1000"].balance
        return [], []

    def _fake_statements(*, account_map: Any) -> Any:
        return {
            "trial_balance": {
                "rows": [],
                "total_debit": "0.000000",
                "total_credit": "0.000000",
                "is_balanced": True,
            },
            "pnl": {},
            "balance_sheet": {
                "assets": [],
                "liabilities": [],
                "equity": [],
                "totals": {
                    "assets": "0.000000",
                    "liabilities": "0.000000",
                    "equity": "0.000000",
                    "liabilities_and_equity": "0.000000",
                },
                "is_balanced": True,
            },
        }

    monkeypatch.setattr(group_consolidation_service, "_load_group_scope", _fake_load_scope)
    monkeypatch.setattr(group_consolidation_service, "_fetch_gl_aggregates", _fake_fetch_gl)
    monkeypatch.setattr(group_consolidation_service, "get_required_latest_fx_rate", _fake_rate)
    monkeypatch.setattr(group_consolidation_service, "_build_eliminations", _fake_eliminations)
    monkeypatch.setattr(group_consolidation_service, "_build_statement_payload", _fake_statements)

    await group_consolidation_service._compute_group_consolidation(
        SimpleNamespace(),
        tenant_id=tenant_id,
        org_group_id=group_id,
        as_of_date=as_of_date,
        from_date=None,
        to_date=None,
        presentation_currency="INR",
    )

    # 100 USD translated with 80 closing rate before elimination stage.
    assert captured_balance["debit_sum"] == Decimal("8000.000000")
    assert captured_balance["credit_sum"] == Decimal("0.000000")
    assert captured_balance["balance"] == Decimal("8000.000000")


@pytest.mark.asyncio
async def test_translation_cta_continuity_across_period_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant_id = uuid.uuid4()
    group_id = uuid.uuid4()
    entity_id = uuid.uuid4()
    cp_entity_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db = _FakeAsyncSession()

    cta_values: list[Decimal] = []
    run_count = 0

    async def _fake_load_group_entities(*args: Any, **kwargs: Any) -> Any:
        group = SimpleNamespace(group_name="Group A")
        entities = [
            SimpleNamespace(
                id=entity_id,
                cp_entity_id=cp_entity_id,
                legal_name="Entity A",
                functional_currency="USD",
            )
        ]
        return group, entities

    async def _fake_get_bs(*args: Any, **kwargs: Any) -> Any:
        as_of = kwargs["as_of_date"]
        if as_of == date(2026, 3, 31):
            return SimpleNamespace(
                totals=SimpleNamespace(
                    assets=Decimal("1000"),
                    liabilities=Decimal("600"),
                    equity=Decimal("400"),
                ),
                retained_earnings=Decimal("100"),
            )
        return SimpleNamespace(
            totals=SimpleNamespace(
                assets=Decimal("1200"),
                liabilities=Decimal("700"),
                equity=Decimal("500"),
            ),
            retained_earnings=Decimal("140"),
        )

    async def _fake_get_pnl(*args: Any, **kwargs: Any) -> Any:
        as_of = kwargs["to_date"]
        return SimpleNamespace(net_profit=Decimal("100" if as_of == date(2026, 3, 31) else "140"))

    async def _fake_get_rate(*args: Any, **kwargs: Any) -> Any:
        as_of = kwargs["as_of_date"]
        rate_type = kwargs["rate_type"]
        if as_of == date(2026, 3, 31):
            return SimpleNamespace(rate=Decimal("80" if rate_type == "CLOSING" else "75"))
        return SimpleNamespace(rate=Decimal("82" if rate_type == "CLOSING" else "78"))

    async def _fake_audit_insert(*args: Any, **kwargs: Any) -> Any:
        nonlocal run_count
        model_name = getattr(kwargs.get("model_class"), "__name__", "")
        if model_name == "ConsolidationTranslationRun":
            run_count += 1
            return SimpleNamespace(id=uuid.uuid4())
        if model_name == "ConsolidationTranslationEntityResult":
            cta_values.append(Decimal(str(kwargs["values"]["cta_amount"])))
            return SimpleNamespace(id=uuid.uuid4())
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(
        "financeops.services.consolidation.translation_service._load_group_entities",
        _fake_load_group_entities,
    )
    monkeypatch.setattr(
        "financeops.services.consolidation.translation_service.get_balance_sheet",
        _fake_get_bs,
    )
    monkeypatch.setattr(
        "financeops.services.consolidation.translation_service.get_profit_and_loss",
        _fake_get_pnl,
    )
    monkeypatch.setattr(
        "financeops.services.consolidation.translation_service.get_required_latest_fx_rate",
        _fake_get_rate,
    )
    monkeypatch.setattr(
        "financeops.services.consolidation.translation_service.AuditWriter.insert_financial_record",
        staticmethod(_fake_audit_insert),
    )

    first = await translate_group_financials(
        db,
        tenant_id=tenant_id,
        org_group_id=group_id,
        presentation_currency="INR",
        as_of_date=date(2026, 3, 31),
        initiated_by=user_id,
    )
    second = await translate_group_financials(
        db,
        tenant_id=tenant_id,
        org_group_id=group_id,
        presentation_currency="INR",
        as_of_date=date(2026, 4, 30),
        initiated_by=user_id,
    )

    assert run_count == 2
    assert len(cta_values) == 2
    assert Decimal(first["totals"]["total_cta"]) == cta_values[0]
    assert Decimal(second["totals"]["total_cta"]) == cta_values[1]
    # Continuity check: second period CTA remains an equity reserve measure,
    # not auto-reset to zero by the engine.
    assert cta_values[1] != Decimal("0.0000")
