from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from financeops.modules.erp_push.domain.schemas import PushJournalLine, PushJournalPacket
from financeops.modules.erp_push.infrastructure.clients.qbo import (
    QBO_AUTH_INVALID_TOKEN,
    QBO_NOT_FOUND,
    QBO_RATE_LIMIT,
    _build_qbo_journal_payload,
    push_journal_to_qbo,
)
from financeops.modules.erp_push.infrastructure.clients.tally import (
    TALLY_NETWORK,
    TALLY_REJECTED,
    _build_tally_voucher_xml,
    _parse_tally_response,
    push_journal_to_tally,
)
from financeops.modules.erp_push.infrastructure.clients.zoho import (
    ZOHO_AUTH_INVALID_TOKEN,
    ZOHO_NETWORK,
    ZOHO_PAYLOAD_INVALID,
    ZOHO_RATE_LIMIT,
    _build_zoho_journal_payload,
    _decimal_to_str,
    push_journal_to_zoho,
)
from financeops.modules.erp_sync.infrastructure.connectors.http_backoff import RateLimitError


def _make_packet(connector_type: str = "zoho") -> PushJournalPacket:
    return PushJournalPacket(
        jv_id=uuid.uuid4(),
        jv_number="JV-2026-03-0001",
        jv_version=1,
        period_date="2026-03-01",
        description="Test JV",
        reference="REF-001",
        currency="INR",
        lines=[
            PushJournalLine(
                account_code="1001",
                external_account_id="EXT-1001",
                entry_type="DEBIT",
                amount=Decimal("50000.00"),
            ),
            PushJournalLine(
                account_code="2001",
                external_account_id="EXT-2001",
                entry_type="CREDIT",
                amount=Decimal("50000.00"),
            ),
        ],
        entity_id=uuid.uuid4(),
        connector_type=connector_type,
        idempotency_key="k" * 64,
    )


class TestDecimalToString:
    def test_decimal_to_str(self) -> None:
        assert _decimal_to_str(Decimal("50000.00")) == "50000.00"

    def test_no_float_rounding(self) -> None:
        text = _decimal_to_str(Decimal("0.1") + Decimal("0.2"))
        assert text.startswith("0.30")


class TestZohoClient:
    def test_payload_uses_external_account_id_and_string_amounts(self) -> None:
        payload = _build_zoho_journal_payload(_make_packet("zoho"), "org")
        for item in payload["line_items"]:
            assert item["account_id"].startswith("EXT-")
            assert isinstance(item["amount"], str)

    @pytest.mark.asyncio
    async def test_simulation_mode(self) -> None:
        result = await push_journal_to_zoho(
            _make_packet("zoho"),
            access_token="token",
            organization_id="org",
            simulation=True,
        )
        assert result.success is True
        assert result.external_journal_id is not None

    @pytest.mark.asyncio
    async def test_401_is_hard(self) -> None:
        with patch(
            "financeops.modules.erp_push.infrastructure.clients.zoho.with_backoff",
            new_callable=AsyncMock,
            return_value=MagicMock(status_code=401, text=""),
        ):
            result = await push_journal_to_zoho(
                _make_packet("zoho"),
                access_token="token",
                organization_id="org",
            )
        assert result.error_code == ZOHO_AUTH_INVALID_TOKEN
        assert result.error_category == "HARD"

    @pytest.mark.asyncio
    async def test_400_is_hard(self) -> None:
        with patch(
            "financeops.modules.erp_push.infrastructure.clients.zoho.with_backoff",
            new_callable=AsyncMock,
            return_value=MagicMock(status_code=400, text="bad"),
        ):
            result = await push_journal_to_zoho(
                _make_packet("zoho"),
                access_token="token",
                organization_id="org",
            )
        assert result.error_code == ZOHO_PAYLOAD_INVALID

    @pytest.mark.asyncio
    async def test_rate_limit_soft(self) -> None:
        with patch(
            "financeops.modules.erp_push.infrastructure.clients.zoho.with_backoff",
            new_callable=AsyncMock,
            side_effect=RateLimitError(429, 3),
        ):
            result = await push_journal_to_zoho(
                _make_packet("zoho"),
                access_token="token",
                organization_id="org",
            )
        assert result.error_code == ZOHO_RATE_LIMIT

    @pytest.mark.asyncio
    async def test_network_soft(self) -> None:
        with patch(
            "financeops.modules.erp_push.infrastructure.clients.zoho.with_backoff",
            new_callable=AsyncMock,
            side_effect=httpx.NetworkError("boom"),
        ):
            result = await push_journal_to_zoho(
                _make_packet("zoho"),
                access_token="token",
                organization_id="org",
            )
        assert result.error_code == ZOHO_NETWORK


class TestQboClient:
    def test_payload_uses_external_account_id_and_string_amounts(self) -> None:
        payload = _build_qbo_journal_payload(_make_packet("quickbooks"))
        for item in payload["Line"]:
            assert isinstance(item["Amount"], str)
            assert item["JournalEntryLineDetail"]["AccountRef"]["value"].startswith("EXT-")

    @pytest.mark.asyncio
    async def test_simulation_mode(self) -> None:
        result = await push_journal_to_qbo(
            _make_packet("quickbooks"),
            access_token="token",
            realm_id="realm",
            simulation=True,
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_401_is_hard(self) -> None:
        with patch(
            "financeops.modules.erp_push.infrastructure.clients.qbo.with_backoff",
            new_callable=AsyncMock,
            return_value=MagicMock(status_code=401, text=""),
        ):
            result = await push_journal_to_qbo(
                _make_packet("quickbooks"),
                access_token="token",
                realm_id="realm",
            )
        assert result.error_code == QBO_AUTH_INVALID_TOKEN

    @pytest.mark.asyncio
    async def test_404_is_hard(self) -> None:
        with patch(
            "financeops.modules.erp_push.infrastructure.clients.qbo.with_backoff",
            new_callable=AsyncMock,
            return_value=MagicMock(status_code=404, text="missing"),
        ):
            result = await push_journal_to_qbo(
                _make_packet("quickbooks"),
                access_token="token",
                realm_id="realm",
            )
        assert result.error_code == QBO_NOT_FOUND

    @pytest.mark.asyncio
    async def test_rate_limit_soft(self) -> None:
        with patch(
            "financeops.modules.erp_push.infrastructure.clients.qbo.with_backoff",
            new_callable=AsyncMock,
            side_effect=RateLimitError(429, 3),
        ):
            result = await push_journal_to_qbo(
                _make_packet("quickbooks"),
                access_token="token",
                realm_id="realm",
            )
        assert result.error_code == QBO_RATE_LIMIT


class TestTallyClient:
    def test_xml_builder_returns_parseable_xml(self) -> None:
        xml = _build_tally_voucher_xml(_make_packet("tally"))
        parsed = _parse_tally_response(xml)
        assert isinstance(parsed, dict)

    def test_parse_error_xml(self) -> None:
        result = _parse_tally_response("<ENVELOPE><LINEERROR>bad</LINEERROR></ENVELOPE>")
        assert result["success"] is False

    def test_parse_invalid_xml(self) -> None:
        result = _parse_tally_response("not xml")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_simulation_mode(self) -> None:
        result = await push_journal_to_tally(_make_packet("tally"), simulation=True)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_network_soft(self) -> None:
        with patch(
            "financeops.modules.erp_push.infrastructure.clients.tally.httpx.AsyncClient"
        ) as mock_client:
            client_obj = MagicMock()
            client_obj.post = AsyncMock(side_effect=httpx.NetworkError("down"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=client_obj)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await push_journal_to_tally(_make_packet("tally"), simulation=False)
        assert result.error_code == TALLY_NETWORK

    @pytest.mark.asyncio
    async def test_rejected_hard(self) -> None:
        response_xml = """<ENVELOPE><BODY><IMPORTDATA><IMPORTRESULT><LINEERROR>bad</LINEERROR><CREATED>0</CREATED></IMPORTRESULT></IMPORTDATA></BODY></ENVELOPE>"""
        with patch(
            "financeops.modules.erp_push.infrastructure.clients.tally.httpx.AsyncClient"
        ) as mock_client:
            response = MagicMock(status_code=200, text=response_xml)
            client_obj = MagicMock()
            client_obj.post = AsyncMock(return_value=response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=client_obj)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await push_journal_to_tally(_make_packet("tally"), simulation=False)
        assert result.error_code == TALLY_REJECTED
