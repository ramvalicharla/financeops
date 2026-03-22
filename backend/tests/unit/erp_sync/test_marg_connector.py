from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import (
    ConnectorCapabilityNotSupported,
    ExtractionError,
)
from financeops.modules.erp_sync.infrastructure.connectors.marg import MargConnector


@pytest.mark.asyncio
async def test_marg_v9_trial_balance_column_mapping() -> None:
    connector = MargConnector()
    csv_data = (
        "Account Name,Account Code,Opening Dr,Opening Cr,Closing Dr,Closing Cr\n"
        "Cash,1001,1,0,2,0\n"
    ).encode("utf-8")
    payload = await connector.extract(
        DatasetType.TRIAL_BALANCE,
        content=csv_data,
        filename="tb_v9.csv",
        marg_version="9.0",
    )
    assert payload["records"][0]["account_name"] == "Cash"
    assert payload["records"][0]["account_code"] == "1001"
    assert payload["records"][0]["opening_debit"] == Decimal("1")


@pytest.mark.asyncio
async def test_marg_v10_trial_balance_column_mapping() -> None:
    connector = MargConnector()
    csv_data = (
        "Ledger Name,Ledger Code,Op. Dr,Op. Cr,Cl. Dr,Cl. Cr\n"
        "Receivable,2001,10,0,8,0\n"
    ).encode("utf-8")
    payload = await connector.extract(
        DatasetType.TRIAL_BALANCE,
        content=csv_data,
        filename="tb_v10.csv",
        marg_version="10.0",
    )
    assert payload["records"][0]["account_name"] == "Receivable"
    assert payload["records"][0]["opening_debit"] == Decimal("10")


@pytest.mark.asyncio
async def test_marg_totals_row_detected_and_extracted() -> None:
    connector = MargConnector()
    csv_data = (
        "Account Name,Account Code,Opening Dr,Opening Cr,Closing Dr,Closing Cr\n"
        "Cash,1001,10,0,15,0\n"
        "Total,,10,0,15,0\n"
    ).encode("utf-8")
    payload = await connector.extract(
        DatasetType.TRIAL_BALANCE,
        content=csv_data,
        filename="tb_with_total.csv",
        marg_version="9.0",
    )
    assert payload["line_count"] == 1
    assert payload["erp_control_totals"]["Opening Dr"] == Decimal("10")


@pytest.mark.asyncio
async def test_marg_missing_required_column_raises() -> None:
    connector = MargConnector()
    csv_data = "Account Name,Opening Dr\nCash,10\n".encode("utf-8")
    with pytest.raises(ExtractionError, match="missing required columns"):
        await connector.extract(
            DatasetType.TRIAL_BALANCE,
            content=csv_data,
            filename="tb_missing.csv",
            marg_version="9.0",
        )


@pytest.mark.asyncio
async def test_marg_unsupported_dataset_raises_capability() -> None:
    connector = MargConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.PAYROLL_SUMMARY, content=b"a,b\n1,2\n", filename="x.csv")
