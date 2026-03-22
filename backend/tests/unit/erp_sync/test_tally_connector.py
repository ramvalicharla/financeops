from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import (
    ConnectorCapabilityNotSupported,
)
from financeops.modules.erp_sync.infrastructure.connectors.tally import (
    TallyConnector,
    _decode_xml,
)


SAMPLE_TALLY_XML = """\
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <COMPANYNAME>Demo Co</COMPANYNAME>
  </HEADER>
  <BODY>
    <DATA>
      <ROW>
        <ACCOUNT_CODE>1001</ACCOUNT_CODE>
        <ACCOUNT_NAME>Cash</ACCOUNT_NAME>
        <OPENING_DEBIT>1,234.50</OPENING_DEBIT>
        <OPENING_CREDIT>-250.00</OPENING_CREDIT>
      </ROW>
      <ROW>
        <ACCOUNT_CODE>2001</ACCOUNT_CODE>
        <ACCOUNT_NAME>Payable</ACCOUNT_NAME>
        <OPENING_DEBIT>0</OPENING_DEBIT>
        <OPENING_CREDIT>984.50</OPENING_CREDIT>
      </ROW>
      <TOTAL_DEBIT>1,234.50</TOTAL_DEBIT>
      <TOTAL_CREDIT>1,234.50</TOTAL_CREDIT>
    </DATA>
  </BODY>
</ENVELOPE>
"""


@pytest.mark.asyncio
async def test_tally_test_connection_success() -> None:
    connector = TallyConnector()

    async def fake_post_xml(credentials: dict[str, object], request_xml: str) -> str:
        assert credentials["tally_host"] == "localhost"
        assert "<ID>List of Companies</ID>" in request_xml
        return SAMPLE_TALLY_XML

    connector._post_xml = fake_post_xml  # type: ignore[method-assign]
    result = await connector.test_connection(
        {"tally_host": "localhost", "tally_port": 9000, "tally_company_name": "Demo Co"}
    )
    assert result["ok"] is True
    assert result["connector_type"] == "tally"


@pytest.mark.asyncio
async def test_tally_test_connection_company_mismatch() -> None:
    connector = TallyConnector()

    async def fake_post_xml(credentials: dict[str, object], request_xml: str) -> str:
        return SAMPLE_TALLY_XML

    connector._post_xml = fake_post_xml  # type: ignore[method-assign]
    result = await connector.test_connection(
        {"tally_host": "localhost", "tally_port": 9000, "tally_company_name": "Wrong Co"}
    )
    assert result["ok"] is False
    assert "mismatch" in str(result["message"]).lower()


@pytest.mark.asyncio
async def test_tally_extract_trial_balance_parses_decimal_values() -> None:
    connector = TallyConnector()

    async def fake_post_xml(credentials: dict[str, object], request_xml: str) -> str:
        assert "<ID>Trial Balance</ID>" in request_xml
        return SAMPLE_TALLY_XML

    connector._post_xml = fake_post_xml  # type: ignore[method-assign]
    payload = await connector.extract(
        DatasetType.TRIAL_BALANCE,
        credentials={"tally_host": "localhost", "tally_port": 9000, "tally_company_name": "Demo Co"},
    )
    assert payload["dataset_type"] == "trial_balance"
    assert payload["line_count"] == 2
    assert isinstance(payload["records"][0]["OPENING_DEBIT"], Decimal)
    assert payload["records"][0]["OPENING_DEBIT"] == Decimal("1234.50")
    assert payload["records"][0]["OPENING_CREDIT"] == Decimal("-250.00")
    assert payload["erp_control_totals"]["total_debit"] == Decimal("1234.50")


@pytest.mark.asyncio
async def test_tally_unsupported_dataset_raises_capability_error() -> None:
    connector = TallyConnector()
    with pytest.raises(ConnectorCapabilityNotSupported):
        await connector.extract(DatasetType.PAYROLL_SUMMARY, credentials={"tally_company_name": "Demo Co"})


def test_tally_decoder_handles_cp1252() -> None:
    text = "Caf\xe9".encode("cp1252")
    assert _decode_xml(text) == "Café"
