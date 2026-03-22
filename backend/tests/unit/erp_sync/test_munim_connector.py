from __future__ import annotations

import json
from decimal import Decimal

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import (
    ConnectorCapabilityNotSupported,
    ExtractionError,
)
from financeops.modules.erp_sync.infrastructure.connectors.munim import MunimConnector


@pytest.mark.asyncio
async def test_munim_variant_csv_mapping() -> None:
    connector = MunimConnector()
    csv_data = (
        "Ledger Name,Ledger Code,Dr Amount,Cr Amount\n"
        "Cash,1001,1200.50,0\n"
    ).encode("utf-8")
    payload = await connector.extract(
        DatasetType.TRIAL_BALANCE,
        app_variant="MUNIM",
        content=csv_data,
        filename="munim_tb.csv",
    )
    assert payload["records"][0]["account_name"] == "Cash"
    assert payload["records"][0]["account_code"] == "1001"
    assert payload["records"][0]["closing_debit"] == Decimal("1200.50")


@pytest.mark.asyncio
async def test_vyapar_variant_json_mapping() -> None:
    connector = MunimConnector()
    raw = [
        {
            "Sales No": "INV-1",
            "Sales Date": "2026-01-01",
            "Party": "ABC Traders",
            "Grand Total": "2500.75",
        }
    ]
    payload = await connector.extract(
        DatasetType.INVOICE_REGISTER,
        app_variant="VYAPAR",
        content=json.dumps(raw).encode("utf-8"),
        filename="vyapar_invoice.json",
    )
    assert payload["records"][0]["invoice_number"] == "INV-1"
    assert payload["records"][0]["invoice_amount"] == Decimal("2500.75")


@pytest.mark.asyncio
async def test_munim_missing_required_columns_raises() -> None:
    connector = MunimConnector()
    csv_data = "Ledger Name,Dr Amount\nCash,10\n".encode("utf-8")
    with pytest.raises(ExtractionError, match="missing required columns"):
        await connector.extract(
            DatasetType.TRIAL_BALANCE,
            app_variant="MUNIM",
            content=csv_data,
            filename="missing.csv",
        )


@pytest.mark.asyncio
async def test_munim_unsupported_dataset_raises_capability() -> None:
    connector = MunimConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.PAYROLL_SUMMARY, content=b"a,b\n1,2\n", filename="x.csv")
