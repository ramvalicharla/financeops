from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from financeops.modules.erp_sync.domain.enums import DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import (
    ConnectorCapabilityNotSupported,
    ExtractionError,
)
from financeops.modules.erp_sync.infrastructure.connectors.tally import (
    TallyConnector,
    _decode_xml,
    get_indian_fiscal_year,
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


def test_tally_trial_balance_xml_request_format() -> None:
    connector = TallyConnector()
    xml = connector._build_trial_balance_request(date(2026, 4, 1), date(2026, 4, 30))
    assert "<REPORTNAME>Trial Balance</REPORTNAME>" in xml
    assert "<SVFROMDATE>20260401</SVFROMDATE>" in xml
    assert "<SVTODATE>20260430</SVTODATE>" in xml


def test_tally_trial_balance_response_parsing() -> None:
    connector = TallyConnector()
    xml = """
    <ENVELOPE>
      <BODY>
        <LEDGER NAME="Cash"><CLOSINGBALANCE>1234.56</CLOSINGBALANCE></LEDGER>
        <LEDGER NAME="Payable"><CLOSINGBALANCE>-100.00</CLOSINGBALANCE></LEDGER>
      </BODY>
    </ENVELOPE>
    """
    rows = connector._parse_trial_balance_response(xml)
    assert len(rows) == 2
    assert rows[0].account_name == "Cash"
    assert rows[0].amount == Decimal("1234.56")
    assert rows[1].is_debit is False


def test_tally_decimal_amounts_not_float() -> None:
    connector = TallyConnector()
    xml = """
    <ENVELOPE>
      <BODY>
        <LEDGER NAME="Cash"><CLOSINGBALANCE>10.10</CLOSINGBALANCE></LEDGER>
      </BODY>
    </ENVELOPE>
    """
    rows = connector._parse_trial_balance_response(xml)
    assert isinstance(rows[0].amount, Decimal)


def test_tally_indian_fiscal_year_computation() -> None:
    fy_start, fy_end = get_indian_fiscal_year(date(2026, 5, 1))
    assert fy_start == date(2026, 4, 1)
    assert fy_end == date(2027, 3, 31)
    fy_start_prev, fy_end_prev = get_indian_fiscal_year(date(2026, 2, 1))
    assert fy_start_prev == date(2025, 4, 1)
    assert fy_end_prev == date(2026, 3, 31)


@pytest.mark.asyncio
async def test_tally_connection_test_success() -> None:
    connector = TallyConnector()

    async def fake_post_xml(credentials: dict[str, object], request_xml: str) -> str:
        return SAMPLE_TALLY_XML

    connector._post_xml = fake_post_xml  # type: ignore[method-assign]
    result = await connector.test_connection(
        {"tally_host": "localhost", "tally_port": 9000, "tally_company_name": "Demo Co"}
    )
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_tally_connection_test_failure_handling() -> None:
    connector = TallyConnector()

    async def fake_post_xml(credentials: dict[str, object], request_xml: str) -> str:
        raise ExtractionError("gateway down")

    connector._post_xml = fake_post_xml  # type: ignore[method-assign]
    with pytest.raises(ExtractionError):
        await connector.extract(
            DatasetType.TRIAL_BALANCE,
            credentials={"tally_host": "localhost", "tally_port": 9000, "tally_company_name": "Demo Co"},
        )


def test_tally_xml_parse_error_handling() -> None:
    connector = TallyConnector()
    with pytest.raises(ExtractionError):
        connector._parse_trial_balance_response("<ENVELOPE><BODY><LEDGER></BODY></ENVELOPE>")
