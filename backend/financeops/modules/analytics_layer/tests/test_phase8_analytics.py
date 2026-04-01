from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from financeops.modules.analytics_layer.application import drilldown_service, kpi_service, ratio_service, variance_service
from financeops.modules.analytics_layer.application.common import ResolvedScope, variance_payload


def _scope() -> ResolvedScope:
    return ResolvedScope(
        entity_ids=[uuid.uuid4()],
        as_of_date=date(2026, 3, 31),
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        scope_dimension={"org_entity_id": str(uuid.uuid4())},
    )


@pytest.mark.asyncio
async def test_kpi_accuracy_vs_financial_statements(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    scope = _scope()
    pnl = SimpleNamespace(
        from_date=scope.from_date,
        to_date=scope.to_date,
        revenue=Decimal("1000"),
        gross_profit=Decimal("700"),
        operating_profit=Decimal("500"),
        net_profit=Decimal("400"),
        breakdown=[
            SimpleNamespace(account_code="DEP", account_name="Depreciation", amount=Decimal("50")),
            SimpleNamespace(account_code="INT", account_name="Interest", amount=Decimal("100")),
        ],
    )
    bs = SimpleNamespace(
        as_of_date=scope.as_of_date,
        assets=[
            SimpleNamespace(account_code="INV", account_name="Inventory", amount=Decimal("100"), sub_type="CURRENT"),
            SimpleNamespace(account_code="AR", account_name="Receivables", amount=Decimal("300"), sub_type="CURRENT"),
        ],
        liabilities=[
            SimpleNamespace(account_code="AP", account_name="Payables", amount=Decimal("200"), sub_type="CURRENT"),
        ],
        equity=[],
        totals=SimpleNamespace(liabilities=Decimal("500"), equity=Decimal("250")),
    )
    cf = SimpleNamespace(net_cash_flow=Decimal("120"))

    monkeypatch.setattr(kpi_service, "resolve_scope", AsyncMock(return_value=scope))
    monkeypatch.setattr(
        kpi_service,
        "compute_statement_bundle",
        AsyncMock(return_value={"tb": object(), "pnl": pnl, "bs": bs, "cf": cf}),
    )
    monkeypatch.setattr(
        kpi_service,
        "create_snapshot",
        AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4(), snapshot_type="PNL", as_of_date=scope.as_of_date, period_from=scope.from_date, period_to=scope.to_date)),
    )
    monkeypatch.setattr(kpi_service, "create_metric_rows", AsyncMock(return_value=None))

    result = await kpi_service.compute_kpis(
        session,
        tenant_id=uuid.uuid4(),
        org_entity_id=scope.entity_ids[0],
        org_group_id=None,
        as_of_date=scope.as_of_date,
        from_date=scope.from_date,
        to_date=scope.to_date,
    )
    metrics = {row.metric_name: row.metric_value for row in result.rows}
    assert metrics["revenue"] == Decimal("1000")
    assert metrics["gross_profit"] == Decimal("700")
    assert metrics["ebitda"] == Decimal("550")
    assert metrics["net_profit"] == Decimal("400")
    assert metrics["current_ratio"] == Decimal("2.000000")
    assert metrics["quick_ratio"] == Decimal("1.500000")


@pytest.mark.asyncio
async def test_variance_correctness(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    scope = _scope()
    prev_scope = ResolvedScope(
        entity_ids=scope.entity_ids,
        as_of_date=date(2026, 2, 28),
        from_date=date(2026, 2, 1),
        to_date=date(2026, 2, 28),
        scope_dimension=scope.scope_dimension,
    )

    monkeypatch.setattr(
        variance_service,
        "resolve_scope",
        AsyncMock(side_effect=[scope, prev_scope]),
    )
    monkeypatch.setattr(
        variance_service,
        "calculate_kpi_metrics",
        AsyncMock(side_effect=[({"revenue": Decimal("120"), "net_profit": Decimal("20")}, []), ({"revenue": Decimal("100"), "net_profit": Decimal("10")}, [])]),
    )
    monkeypatch.setattr(
        variance_service,
        "_pnl_account_map",
        AsyncMock(
            side_effect=[
                {"4000": ("Revenue", Decimal("120"))},
                {"4000": ("Revenue", Decimal("100"))},
            ]
        ),
    )
    monkeypatch.setattr(
        variance_service,
        "create_snapshot",
        AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4(), snapshot_type="PNL", as_of_date=scope.to_date, period_from=scope.from_date, period_to=scope.to_date)),
    )

    result = await variance_service.compute_variance(
        session,
        tenant_id=uuid.uuid4(),
        org_entity_id=scope.entity_ids[0],
        org_group_id=None,
        from_date=scope.from_date,
        to_date=scope.to_date,
    )
    rows = {row.metric_name: row for row in result.metric_variances}
    assert rows["revenue"].variance_value == Decimal("20")
    assert rows["revenue"].variance_percent == Decimal("20.000000")
    assert rows["net_profit"].variance_value == Decimal("10")
    assert len(result.account_variances) == 1


@pytest.mark.asyncio
async def test_ratio_correctness(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    scope = _scope()

    pnl_current = SimpleNamespace(revenue=Decimal("1000"), net_profit=Decimal("200"), cost_of_sales=Decimal("300"))
    bs_current = SimpleNamespace(
        assets=[
            SimpleNamespace(account_code="INV", account_name="Inventory", amount=Decimal("100")),
            SimpleNamespace(account_code="AR", account_name="Receivables", amount=Decimal("150")),
        ],
        liabilities=[SimpleNamespace(account_code="AP", account_name="Payables", amount=Decimal("90"))],
        totals=SimpleNamespace(assets=Decimal("1000"), equity=Decimal("500")),
    )
    bs_open = SimpleNamespace(
        assets=[SimpleNamespace(account_code="INV", account_name="Inventory", amount=Decimal("80"))],
        liabilities=[SimpleNamespace(account_code="AP", account_name="Payables", amount=Decimal("70"))],
        totals=SimpleNamespace(assets=Decimal("900"), equity=Decimal("450")),
    )

    monkeypatch.setattr(ratio_service, "resolve_scope", AsyncMock(return_value=scope))
    monkeypatch.setattr(
        ratio_service,
        "compute_statement_bundle",
        AsyncMock(side_effect=[{"pnl": pnl_current, "bs": bs_current}, {"pnl": pnl_current, "bs": bs_open}]),
    )
    monkeypatch.setattr(
        ratio_service,
        "create_snapshot",
        AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4(), snapshot_type="BS", as_of_date=scope.as_of_date, period_from=scope.from_date, period_to=scope.to_date)),
    )
    monkeypatch.setattr(ratio_service, "create_metric_rows", AsyncMock(return_value=None))

    result = await ratio_service.compute_ratios(
        session,
        tenant_id=uuid.uuid4(),
        org_entity_id=scope.entity_ids[0],
        org_group_id=None,
        as_of_date=scope.as_of_date,
        from_date=scope.from_date,
        to_date=scope.to_date,
    )
    rows = {row.metric_name: row.metric_value for row in result.rows}
    assert rows["roe"] > Decimal("0")
    assert rows["roa"] > Decimal("0")
    assert rows["asset_turnover"] > Decimal("0")


@pytest.mark.asyncio
async def test_drilldown_consistency(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    entity_id = uuid.uuid4()
    scope = ResolvedScope(
        entity_ids=[entity_id],
        as_of_date=date(2026, 3, 31),
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        scope_dimension={"org_entity_id": str(entity_id)},
    )
    monkeypatch.setattr(drilldown_service, "resolve_scope", AsyncMock(return_value=scope))
    monkeypatch.setattr(
        drilldown_service,
        "get_profit_and_loss",
        AsyncMock(
            return_value=SimpleNamespace(
                breakdown=[SimpleNamespace(account_code="4000", account_name="Revenue", amount=Decimal("100"))]
            )
        ),
    )
    monkeypatch.setattr(
        drilldown_service,
        "get_balance_sheet",
        AsyncMock(return_value=SimpleNamespace(assets=[], liabilities=[], equity=[])),
    )

    gl_row = SimpleNamespace(
        id=uuid.uuid4(),
        account_code="4000",
        account_name="Revenue",
        debit_amount=Decimal("0"),
        credit_amount=Decimal("100"),
        source_ref="JV-2026-03-0001",
        created_at=datetime.now(tz=timezone.utc),
    )
    jv_row = SimpleNamespace(
        id=uuid.uuid4(),
        jv_number="JV-2026-03-0001",
        period_date=date(2026, 3, 20),
        status="PUSHED",
        external_reference_id=None,
        reference="REF",
    )

    class _Scalars:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return _Scalars(self._rows)

    session.execute = AsyncMock(side_effect=[_Result([gl_row]), _Result([jv_row])])

    result = await drilldown_service.get_metric_drilldown(
        session,
        tenant_id=uuid.uuid4(),
        metric_name="revenue",
        org_entity_id=entity_id,
        org_group_id=None,
        from_date=scope.from_date,
        to_date=scope.to_date,
        as_of_date=scope.as_of_date,
    )
    assert len(result.accounts) == 1
    assert result.accounts[0].account_code == "4000"
    assert len(result.gl_entries) == 1
    assert len(result.journals) == 1


@pytest.mark.asyncio
async def test_snapshot_reproducibility(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    scope = _scope()
    pnl = SimpleNamespace(
        from_date=scope.from_date,
        to_date=scope.to_date,
        revenue=Decimal("100"),
        gross_profit=Decimal("70"),
        operating_profit=Decimal("40"),
        net_profit=Decimal("30"),
        breakdown=[],
    )
    bs = SimpleNamespace(
        as_of_date=scope.as_of_date,
        assets=[],
        liabilities=[],
        equity=[],
        totals=SimpleNamespace(liabilities=Decimal("1"), equity=Decimal("1")),
    )
    cf = SimpleNamespace(net_cash_flow=Decimal("0"))

    monkeypatch.setattr(kpi_service, "resolve_scope", AsyncMock(return_value=scope))
    monkeypatch.setattr(
        kpi_service,
        "compute_statement_bundle",
        AsyncMock(return_value={"tb": object(), "pnl": pnl, "bs": bs, "cf": cf}),
    )
    monkeypatch.setattr(
        kpi_service,
        "create_snapshot",
        AsyncMock(side_effect=[
            SimpleNamespace(id=uuid.uuid4(), snapshot_type="PNL", as_of_date=scope.as_of_date, period_from=scope.from_date, period_to=scope.to_date),
            SimpleNamespace(id=uuid.uuid4(), snapshot_type="PNL", as_of_date=scope.as_of_date, period_from=scope.from_date, period_to=scope.to_date),
        ]),
    )
    monkeypatch.setattr(kpi_service, "create_metric_rows", AsyncMock(return_value=None))

    first = await kpi_service.compute_kpis(
        session,
        tenant_id=uuid.uuid4(),
        org_entity_id=scope.entity_ids[0],
        org_group_id=None,
        as_of_date=scope.as_of_date,
        from_date=scope.from_date,
        to_date=scope.to_date,
    )
    second = await kpi_service.compute_kpis(
        session,
        tenant_id=uuid.uuid4(),
        org_entity_id=scope.entity_ids[0],
        org_group_id=None,
        as_of_date=scope.as_of_date,
        from_date=scope.from_date,
        to_date=scope.to_date,
    )
    first_rows = {row.metric_name: row.metric_value for row in first.rows}
    second_rows = {row.metric_name: row.metric_value for row in second.rows}
    assert first_rows == second_rows


@pytest.mark.asyncio
async def test_cfo_validation_1_kpi_net_profit_reconciles_to_pnl(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    scope = _scope()
    pnl = SimpleNamespace(
        from_date=scope.from_date,
        to_date=scope.to_date,
        revenue=Decimal("1200"),
        gross_profit=Decimal("800"),
        operating_profit=Decimal("500"),
        net_profit=Decimal("325.50"),
        breakdown=[],
    )
    bs = SimpleNamespace(
        as_of_date=scope.as_of_date,
        assets=[],
        liabilities=[],
        equity=[],
        totals=SimpleNamespace(liabilities=Decimal("100"), equity=Decimal("250")),
    )
    cf = SimpleNamespace(net_cash_flow=Decimal("44"))

    monkeypatch.setattr(kpi_service, "resolve_scope", AsyncMock(return_value=scope))
    monkeypatch.setattr(
        kpi_service,
        "compute_statement_bundle",
        AsyncMock(return_value={"tb": object(), "pnl": pnl, "bs": bs, "cf": cf}),
    )
    create_snapshot_mock = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(),
            snapshot_type="PNL",
            as_of_date=scope.as_of_date,
            period_from=scope.from_date,
            period_to=scope.to_date,
        )
    )
    monkeypatch.setattr(kpi_service, "create_snapshot", create_snapshot_mock)
    monkeypatch.setattr(kpi_service, "create_metric_rows", AsyncMock(return_value=None))

    result = await kpi_service.compute_kpis(
        session,
        tenant_id=uuid.uuid4(),
        org_entity_id=scope.entity_ids[0],
        org_group_id=None,
        as_of_date=scope.as_of_date,
        from_date=scope.from_date,
        to_date=scope.to_date,
    )
    metrics = {row.metric_name: row.metric_value for row in result.rows}
    assert metrics["net_profit"] == pnl.net_profit

    snapshot_payload = create_snapshot_mock.await_args.kwargs["data_json"]["metrics"]
    assert Decimal(snapshot_payload["net_profit"]) == pnl.net_profit


def test_cfo_validation_2_variance_math_and_previous_zero_handling() -> None:
    variance_value, variance_percent = variance_payload(Decimal("120"), Decimal("100"))
    assert variance_value == Decimal("20")
    assert variance_percent == Decimal("20.000000")

    zero_prev_value, zero_prev_percent = variance_payload(Decimal("50"), Decimal("0"))
    assert zero_prev_value == Decimal("50")
    assert zero_prev_percent is None


@pytest.mark.asyncio
async def test_cfo_validation_3_drilldown_lineage_is_traceable(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    entity_id = uuid.uuid4()
    scope = ResolvedScope(
        entity_ids=[entity_id],
        as_of_date=date(2026, 3, 31),
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        scope_dimension={"org_entity_id": str(entity_id)},
    )
    monkeypatch.setattr(drilldown_service, "resolve_scope", AsyncMock(return_value=scope))
    monkeypatch.setattr(
        drilldown_service,
        "get_profit_and_loss",
        AsyncMock(
            return_value=SimpleNamespace(
                breakdown=[SimpleNamespace(account_code="4100", account_name="Services Revenue", amount=Decimal("175"))]
            )
        ),
    )
    monkeypatch.setattr(
        drilldown_service,
        "get_balance_sheet",
        AsyncMock(return_value=SimpleNamespace(assets=[], liabilities=[], equity=[])),
    )

    source_ref = "JV-2026-03-0099"
    gl_row = SimpleNamespace(
        id=uuid.uuid4(),
        account_code="4100",
        account_name="Services Revenue",
        debit_amount=Decimal("0"),
        credit_amount=Decimal("175"),
        source_ref=source_ref,
        created_at=datetime.now(tz=timezone.utc),
    )
    jv_row = SimpleNamespace(
        id=uuid.uuid4(),
        jv_number=source_ref,
        period_date=date(2026, 3, 20),
        status="POSTED",
        external_reference_id=None,
        reference="source",
    )

    class _Scalars:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return _Scalars(self._rows)

    session.execute = AsyncMock(side_effect=[_Result([gl_row]), _Result([jv_row])])

    result = await drilldown_service.get_metric_drilldown(
        session,
        tenant_id=uuid.uuid4(),
        metric_name="revenue",
        org_entity_id=entity_id,
        org_group_id=None,
        from_date=scope.from_date,
        to_date=scope.to_date,
        as_of_date=scope.as_of_date,
    )

    assert result.accounts[0].account_code == "4100"
    assert result.gl_entries[0].source_ref == source_ref
    assert result.journals[0].journal_number == source_ref


@pytest.mark.asyncio
async def test_cfo_validation_4_snapshot_is_recomputable(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    scope = _scope()

    pnl = SimpleNamespace(
        from_date=scope.from_date,
        to_date=scope.to_date,
        revenue=Decimal("500"),
        gross_profit=Decimal("300"),
        operating_profit=Decimal("150"),
        net_profit=Decimal("125"),
        breakdown=[],
    )
    bs = SimpleNamespace(
        as_of_date=scope.as_of_date,
        assets=[],
        liabilities=[],
        equity=[],
        totals=SimpleNamespace(liabilities=Decimal("20"), equity=Decimal("40")),
    )
    cf = SimpleNamespace(net_cash_flow=Decimal("9"))
    create_snapshot_mock = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid.uuid4(),
            snapshot_type="PNL",
            as_of_date=scope.as_of_date,
            period_from=scope.from_date,
            period_to=scope.to_date,
        )
    )

    monkeypatch.setattr(kpi_service, "resolve_scope", AsyncMock(return_value=scope))
    monkeypatch.setattr(
        kpi_service,
        "compute_statement_bundle",
        AsyncMock(return_value={"tb": object(), "pnl": pnl, "bs": bs, "cf": cf}),
    )
    monkeypatch.setattr(kpi_service, "create_snapshot", create_snapshot_mock)
    monkeypatch.setattr(kpi_service, "create_metric_rows", AsyncMock(return_value=None))

    result = await kpi_service.compute_kpis(
        session,
        tenant_id=uuid.uuid4(),
        org_entity_id=scope.entity_ids[0],
        org_group_id=None,
        as_of_date=scope.as_of_date,
        from_date=scope.from_date,
        to_date=scope.to_date,
    )
    metric_map = {row.metric_name: row.metric_value for row in result.rows}
    snapshot_metrics = create_snapshot_mock.await_args.kwargs["data_json"]["metrics"]
    assert Decimal(snapshot_metrics["revenue"]) == metric_map["revenue"]
    assert Decimal(snapshot_metrics["net_profit"]) == metric_map["net_profit"]


@pytest.mark.asyncio
async def test_cfo_validation_5_multi_entity_consistency(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_tenant_id = uuid.uuid4()
    entity_a = uuid.uuid4()
    entity_b = uuid.uuid4()
    shared_scope = ResolvedScope(
        entity_ids=[entity_a, entity_b],
        as_of_date=date(2026, 3, 31),
        from_date=date(2026, 3, 1),
        to_date=date(2026, 3, 31),
        scope_dimension={"org_group_id": str(uuid.uuid4())},
    )

    pnl_a = SimpleNamespace(
        from_date=shared_scope.from_date,
        to_date=shared_scope.to_date,
        revenue=Decimal("100"),
        gross_profit=Decimal("60"),
        operating_profit=Decimal("40"),
        net_profit=Decimal("30"),
        breakdown=[],
    )
    pnl_b = SimpleNamespace(
        from_date=shared_scope.from_date,
        to_date=shared_scope.to_date,
        revenue=Decimal("220"),
        gross_profit=Decimal("130"),
        operating_profit=Decimal("95"),
        net_profit=Decimal("80"),
        breakdown=[],
    )

    bs_a = SimpleNamespace(
        as_of_date=shared_scope.as_of_date,
        assets=[],
        liabilities=[],
        equity=[],
        totals=SimpleNamespace(liabilities=Decimal("20"), equity=Decimal("25")),
    )
    bs_b = SimpleNamespace(
        as_of_date=shared_scope.as_of_date,
        assets=[],
        liabilities=[],
        equity=[],
        totals=SimpleNamespace(liabilities=Decimal("30"), equity=Decimal("55")),
    )

    cf_a = SimpleNamespace(net_cash_flow=Decimal("4"))
    cf_b = SimpleNamespace(net_cash_flow=Decimal("7"))

    async def _bundle(
        _db,
        *,
        tenant_id: uuid.UUID,
        entity_id: uuid.UUID,
        from_date: date,
        to_date: date,
        as_of_date: date,
    ) -> dict[str, object]:
        assert tenant_id == expected_tenant_id
        assert from_date == shared_scope.from_date
        assert to_date == shared_scope.to_date
        assert as_of_date == shared_scope.as_of_date
        if entity_id == entity_a:
            return {"tb": object(), "pnl": pnl_a, "bs": bs_a, "cf": cf_a}
        if entity_id == entity_b:
            return {"tb": object(), "pnl": pnl_b, "bs": bs_b, "cf": cf_b}
        raise AssertionError("Unexpected entity")

    monkeypatch.setattr(kpi_service, "compute_statement_bundle", _bundle)

    metrics, lineage = await kpi_service.calculate_kpi_metrics(
        AsyncMock(),
        tenant_id=expected_tenant_id,
        scope=shared_scope,
    )

    assert metrics["revenue"] == pnl_a.revenue + pnl_b.revenue
    assert metrics["net_profit"] == pnl_a.net_profit + pnl_b.net_profit
    assert len(lineage) == 2
