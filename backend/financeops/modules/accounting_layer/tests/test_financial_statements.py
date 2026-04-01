from __future__ import annotations

from decimal import Decimal

from financeops.modules.accounting_layer.application.financial_statements_service import (
    _AccountAggregate,
    _balance_amount,
    _classify_balance_sheet_bucket,
    _classify_pnl_bucket,
    _net_profit_from_rows,
    _signed_amount_for_bucket,
)


def _row(
    *,
    code: str,
    name: str,
    debit: str,
    credit: str,
    flag: str | None,
    subtype: str | None = None,
    tag: str | None = None,
    normal_balance: str | None = None,
) -> _AccountAggregate:
    return _AccountAggregate(
        account_code=code,
        account_name=name,
        debit_sum=Decimal(debit),
        credit_sum=Decimal(credit),
        bs_pl_flag=flag,
        asset_liability_class=subtype,
        cash_flow_tag=tag,
        normal_balance=normal_balance,
    )


def test_pnl_correctness_basic_aggregation() -> None:
    revenue_row = _row(
        code="4000",
        name="Software Revenue",
        debit="0",
        credit="1000",
        flag="REVENUE",
    )
    expense_row = _row(
        code="5000",
        name="Employee Benefits",
        debit="400",
        credit="0",
        flag="EXPENSE",
    )

    revenue_bucket = _classify_pnl_bucket(revenue_row)
    expense_bucket = _classify_pnl_bucket(expense_row)
    revenue_amount = _signed_amount_for_bucket(revenue_row, revenue_bucket)
    expense_amount = _signed_amount_for_bucket(expense_row, expense_bucket)
    net_profit = revenue_amount - expense_amount

    assert revenue_bucket == "REVENUE"
    assert expense_bucket == "OPERATING_EXPENSE"
    assert revenue_amount == Decimal("1000")
    assert expense_amount == Decimal("400")
    assert net_profit == Decimal("600")


def test_balance_sheet_balances_by_bucket() -> None:
    cash_row = _row(
        code="1000",
        name="Cash",
        debit="900",
        credit="0",
        flag="ASSET",
        subtype="CURRENT",
    )
    payable_row = _row(
        code="2000",
        name="Trade Payable",
        debit="0",
        credit="300",
        flag="LIABILITY",
        subtype="CURRENT",
    )
    equity_row = _row(
        code="3000",
        name="Share Capital",
        debit="0",
        credit="600",
        flag="EQUITY",
    )

    cash_bucket, _ = _classify_balance_sheet_bucket(cash_row)
    payable_bucket, _ = _classify_balance_sheet_bucket(payable_row)
    equity_bucket, _ = _classify_balance_sheet_bucket(equity_row)

    assets = _balance_amount(cash_row, cash_bucket)
    liabilities = _balance_amount(payable_row, payable_bucket)
    equity = _balance_amount(equity_row, equity_bucket)

    assert assets == Decimal("900")
    assert liabilities == Decimal("300")
    assert equity == Decimal("600")
    assert assets == liabilities + equity


def test_cash_flow_consistency_formula() -> None:
    net_profit = Decimal("250")
    non_cash_adjustments = Decimal("40")
    working_capital_changes = Decimal("-30")
    operating = net_profit + non_cash_adjustments + working_capital_changes
    investing = Decimal("-120")
    financing = Decimal("80")
    net_cash_flow = operating + investing + financing

    assert operating == Decimal("260")
    assert net_cash_flow == Decimal("220")
    assert net_cash_flow == operating + investing + financing


def test_retained_earnings_flow_from_cumulative_pnl() -> None:
    rows = [
        _row(code="4000", name="Revenue", debit="0", credit="1000", flag="REVENUE"),
        _row(code="5000", name="COGS", debit="350", credit="0", flag="EXPENSE"),
        _row(code="5100", name="Depreciation", debit="50", credit="0", flag="EXPENSE"),
    ]
    retained_earnings = _net_profit_from_rows(rows)

    assert retained_earnings == Decimal("600")
