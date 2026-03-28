from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from financeops.db.models.accounting_tax import GSTType, TDSSection, TaxOutcome
from financeops.modules.accounting_layer.engines.gst_engine import (
    _get_valid_state_code,
    _round4,
    determine_gst_lines,
    determine_gst_type,
)
from financeops.modules.accounting_layer.engines.tds_engine import (
    _get_applicable_tds_rule,
    determine_tds_line,
)

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


def _valid_gstin(prefix_state: str = "29") -> str:
    body = f"{prefix_state}AABCF1234A1Z"
    return f"{body}{_checksum_char(body)}"


class TestRound4:
    def test_rounds_to_4_places(self) -> None:
        assert _round4(Decimal("100.12345")) == Decimal("100.1235")

    def test_decimal_type(self) -> None:
        result = _round4(Decimal("1") / Decimal("3"))
        assert isinstance(result, Decimal)


class TestStateCodeValidation:
    def test_valid_gstin_state(self) -> None:
        assert _get_valid_state_code(_valid_gstin("29")) == "29"

    def test_invalid_gstin_returns_none(self) -> None:
        assert _get_valid_state_code("INVALID") is None

    def test_empty_returns_none(self) -> None:
        assert _get_valid_state_code("") is None


class TestDetermineGSTType:
    def test_same_state_intra(self) -> None:
        outcome, supplier, buyer = determine_gst_type(_valid_gstin("29"), _valid_gstin("29"))
        assert outcome == "SUCCESS_INTRA"
        assert supplier == "29"
        assert buyer == "29"

    def test_different_state_inter(self) -> None:
        outcome, supplier, buyer = determine_gst_type(_valid_gstin("29"), _valid_gstin("27"))
        assert outcome == "SUCCESS_INTER"
        assert supplier == "29"
        assert buyer == "27"

    def test_invalid_inputs_manual_flag(self) -> None:
        outcome, _, _ = determine_gst_type("BAD", _valid_gstin("27"))
        assert outcome == "MANUAL_FLAG"


class TestGSTEngine:
    @pytest.mark.asyncio
    async def test_determine_gst_lines_intra_splits_cgst_sgst(self) -> None:
        db = AsyncMock()
        rule = MagicMock()
        rule.id = uuid.uuid4()
        rule.gst_type = GSTType.CGST
        rule.gst_rate = Decimal("18")

        with (
            patch(
                "financeops.modules.accounting_layer.engines.gst_engine._get_applicable_gst_rule",
                new=AsyncMock(return_value=rule),
            ),
            patch(
                "financeops.modules.accounting_layer.engines.gst_engine._log_determination",
                new=AsyncMock(),
            ),
        ):
            result = await determine_gst_lines(
                db,
                tenant_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                jv_id=uuid.uuid4(),
                jv_version=1,
                account_code="5001",
                base_amount=Decimal("10000"),
                transaction_date=date(2026, 3, 28),
                supplier_gstin=_valid_gstin("29"),
                buyer_gstin=_valid_gstin("29"),
            )

        assert result.outcome == TaxOutcome.SUCCESS
        assert result.gst_sub_type == "INTRA"
        assert result.tax_amount == Decimal("1800.0000")
        assert len(result.tax_lines) == 2
        assert result.cgst_amount == Decimal("900.0000")
        assert result.sgst_amount == Decimal("900.0000")

    @pytest.mark.asyncio
    async def test_determine_gst_lines_inter_igst(self) -> None:
        db = AsyncMock()
        rule = MagicMock()
        rule.id = uuid.uuid4()
        rule.gst_type = GSTType.IGST
        rule.gst_rate = Decimal("12")

        with (
            patch(
                "financeops.modules.accounting_layer.engines.gst_engine._get_applicable_gst_rule",
                new=AsyncMock(return_value=rule),
            ),
            patch(
                "financeops.modules.accounting_layer.engines.gst_engine._log_determination",
                new=AsyncMock(),
            ),
        ):
            result = await determine_gst_lines(
                db,
                tenant_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                jv_id=uuid.uuid4(),
                jv_version=1,
                account_code="5001",
                base_amount=Decimal("50000"),
                transaction_date=date(2026, 3, 28),
                supplier_gstin=_valid_gstin("29"),
                buyer_gstin=_valid_gstin("27"),
            )

        assert result.outcome == TaxOutcome.SUCCESS
        assert result.gst_sub_type == "INTER"
        assert result.tax_amount == Decimal("6000.0000")
        assert len(result.tax_lines) == 1
        assert result.igst_amount == Decimal("6000.0000")

    @pytest.mark.asyncio
    async def test_determine_gst_lines_exempt_skipped(self) -> None:
        db = AsyncMock()
        rule = MagicMock()
        rule.id = uuid.uuid4()
        rule.gst_type = GSTType.EXEMPT
        rule.gst_rate = Decimal("0")

        with (
            patch(
                "financeops.modules.accounting_layer.engines.gst_engine._get_applicable_gst_rule",
                new=AsyncMock(return_value=rule),
            ),
            patch(
                "financeops.modules.accounting_layer.engines.gst_engine._log_determination",
                new=AsyncMock(),
            ),
        ):
            result = await determine_gst_lines(
                db,
                tenant_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                jv_id=uuid.uuid4(),
                jv_version=1,
                account_code="5001",
                base_amount=Decimal("50000"),
                transaction_date=date(2026, 3, 28),
                supplier_gstin=_valid_gstin("29"),
                buyer_gstin=_valid_gstin("29"),
            )

        assert result.outcome == TaxOutcome.SKIPPED
        assert result.tax_amount == Decimal("0")
        assert result.tax_lines == []

    @pytest.mark.asyncio
    async def test_determine_gst_lines_no_rule_manual_flag(self) -> None:
        db = AsyncMock()
        with (
            patch(
                "financeops.modules.accounting_layer.engines.gst_engine._get_applicable_gst_rule",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "financeops.modules.accounting_layer.engines.gst_engine._log_determination",
                new=AsyncMock(),
            ),
        ):
            result = await determine_gst_lines(
                db,
                tenant_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                jv_id=uuid.uuid4(),
                jv_version=1,
                account_code="5001",
                base_amount=Decimal("50000"),
                transaction_date=date(2026, 3, 28),
                supplier_gstin=_valid_gstin("29"),
                buyer_gstin=_valid_gstin("29"),
            )
        assert result.outcome == TaxOutcome.MANUAL_FLAG
        assert result.tax_lines == []

    @pytest.mark.asyncio
    async def test_determine_gst_lines_invalid_gstin_manual_flag(self) -> None:
        db = AsyncMock()
        with patch(
            "financeops.modules.accounting_layer.engines.gst_engine._log_determination",
            new=AsyncMock(),
        ):
            result = await determine_gst_lines(
                db,
                tenant_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                jv_id=uuid.uuid4(),
                jv_version=1,
                account_code="5001",
                base_amount=Decimal("50000"),
                transaction_date=date(2026, 3, 28),
                supplier_gstin="INVALID",
                buyer_gstin=_valid_gstin("29"),
            )
        assert result.outcome == TaxOutcome.MANUAL_FLAG
        assert result.tax_lines == []


class TestTDSEngine:
    @pytest.mark.asyncio
    async def test_determine_tds_line_success_with_surcharge_cess(self) -> None:
        db = AsyncMock()
        rule = MagicMock()
        rule.id = uuid.uuid4()
        rule.tds_rate = Decimal("10")
        rule.surcharge_rate = Decimal("10")
        rule.cess_rate = Decimal("4")

        with (
            patch(
                "financeops.modules.accounting_layer.engines.tds_engine._get_applicable_tds_rule",
                new=AsyncMock(return_value=rule),
            ),
            patch(
                "financeops.modules.accounting_layer.engines.tds_engine._log_tds_determination",
                new=AsyncMock(),
            ),
        ):
            result = await determine_tds_line(
                db,
                tenant_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                jv_id=uuid.uuid4(),
                jv_version=1,
                vendor_id=uuid.uuid4(),
                tds_section=TDSSection.S194J,
                base_amount=Decimal("100000"),
                transaction_date=date(2026, 3, 28),
            )

        assert result.outcome == TaxOutcome.SUCCESS
        assert result.tds_amount == Decimal("11440.0000")
        assert len(result.tax_lines) == 1

    @pytest.mark.asyncio
    async def test_determine_tds_line_no_rule_manual_flag(self) -> None:
        db = AsyncMock()
        with (
            patch(
                "financeops.modules.accounting_layer.engines.tds_engine._get_applicable_tds_rule",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "financeops.modules.accounting_layer.engines.tds_engine._log_tds_determination",
                new=AsyncMock(),
            ),
        ):
            result = await determine_tds_line(
                db,
                tenant_id=uuid.uuid4(),
                entity_id=uuid.uuid4(),
                jv_id=uuid.uuid4(),
                jv_version=1,
                vendor_id=uuid.uuid4(),
                tds_section=TDSSection.S194C,
                base_amount=Decimal("100000"),
                transaction_date=date(2026, 3, 28),
            )
        assert result.outcome == TaxOutcome.MANUAL_FLAG
        assert result.tax_lines == []

    @pytest.mark.asyncio
    async def test_vendor_specific_tds_rule_overrides_entity_rule(self) -> None:
        vendor_rule = MagicMock()
        entity_rule = MagicMock()
        db = AsyncMock()
        first = MagicMock()
        first.scalar_one_or_none.return_value = vendor_rule
        second = MagicMock()
        second.scalar_one_or_none.return_value = entity_rule
        db.execute = AsyncMock(side_effect=[first, second])

        result = await _get_applicable_tds_rule(
            db,
            tenant_id=uuid.uuid4(),
            entity_id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            tds_section=TDSSection.S194C,
            transaction_date=date(2026, 3, 28),
        )
        assert result is vendor_rule

    @pytest.mark.asyncio
    async def test_entity_level_tds_rule_used_when_vendor_rule_missing(self) -> None:
        vendor_none = MagicMock()
        vendor_none.scalar_one_or_none.return_value = None
        entity_match = MagicMock()
        expected_rule = MagicMock()
        entity_match.scalar_one_or_none.return_value = expected_rule
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=[vendor_none, entity_match])

        result = await _get_applicable_tds_rule(
            db,
            tenant_id=uuid.uuid4(),
            entity_id=uuid.uuid4(),
            vendor_id=uuid.uuid4(),
            tds_section=TDSSection.S194C,
            transaction_date=date(2026, 3, 28),
        )
        assert result is expected_rule


class TestTaxConstants:
    def test_gst_types_complete(self) -> None:
        assert len(GSTType.ALL) == 5
        assert GSTType.CGST in GSTType.ALL
        assert GSTType.SGST in GSTType.ALL
        assert GSTType.IGST in GSTType.ALL
        assert GSTType.EXEMPT in GSTType.ALL
        assert GSTType.NIL in GSTType.ALL

    def test_tds_sections_complete(self) -> None:
        assert len(TDSSection.ALL) == 3
        assert TDSSection.S194C in TDSSection.ALL
        assert TDSSection.S194J in TDSSection.ALL
        assert TDSSection.S194I in TDSSection.ALL

    def test_tax_outcomes_complete(self) -> None:
        assert TaxOutcome.SUCCESS in TaxOutcome.ALL
        assert TaxOutcome.MANUAL_FLAG in TaxOutcome.ALL
        assert TaxOutcome.SKIPPED in TaxOutcome.ALL
        assert TaxOutcome.ERROR in TaxOutcome.ALL
