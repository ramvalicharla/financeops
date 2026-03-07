from __future__ import annotations

import pytest

from financeops.core.exceptions import ValidationError
from financeops.schemas.prepaid import PrepaidInput
from financeops.services.prepaid.pattern_resolver import normalize_pattern


def _base_payload() -> dict:
    return {
        "prepaid_code": "PPD-PAT-001",
        "description": "Pattern test",
        "prepaid_currency": "USD",
        "reporting_currency": "USD",
        "term_start_date": "2026-01-01",
        "term_end_date": "2026-03-31",
        "base_amount_contract_currency": "300.000000",
        "period_frequency": "monthly",
        "rate_mode": "month_end_locked",
        "source_expense_reference": "SRC-PPD-PAT-001",
        "source_reference_id": "00000000-0000-0000-0000-00000000c001",
        "adjustments": [],
    }


def test_straight_line_generates_monthly_grid() -> None:
    payload = {
        **_base_payload(),
        "pattern_type": "straight_line",
    }
    normalized = normalize_pattern(PrepaidInput.model_validate(payload))

    assert [item.period_seq for item in normalized.periods] == [1, 2, 3]
    assert normalized.periods[0].period_start_date.isoformat() == "2026-01-01"
    assert normalized.periods[-1].period_end_date.isoformat() == "2026-03-31"


def test_weighted_period_rejects_mixed_fields() -> None:
    payload = {
        **_base_payload(),
        "pattern_type": "weighted_period",
        "periods": [
            {
                "period_seq": 1,
                "period_start_date": "2026-01-01",
                "period_end_date": "2026-01-31",
                "recognition_date": "2026-01-31",
                "weight": "1.0",
                "percentage": "0.5",
            },
            {
                "period_seq": 2,
                "period_start_date": "2026-02-01",
                "period_end_date": "2026-03-31",
                "recognition_date": "2026-03-31",
                "weight": "1.0",
            },
        ],
    }
    with pytest.raises(ValidationError):
        normalize_pattern(PrepaidInput.model_validate(payload))


def test_explicit_percentages_must_sum_exactly() -> None:
    invalid_payload = {
        **_base_payload(),
        "pattern_type": "explicit_percentages",
        "periods": [
            {
                "period_seq": 1,
                "period_start_date": "2026-01-01",
                "period_end_date": "2026-01-31",
                "recognition_date": "2026-01-31",
                "percentage": "0.600000",
            },
            {
                "period_seq": 2,
                "period_start_date": "2026-02-01",
                "period_end_date": "2026-03-31",
                "recognition_date": "2026-03-31",
                "percentage": "0.300000",
            },
        ],
    }
    with pytest.raises(ValidationError):
        normalize_pattern(PrepaidInput.model_validate(invalid_payload))

    valid_payload = {
        **_base_payload(),
        "pattern_type": "explicit_percentages",
        "periods": [
            {
                "period_seq": 1,
                "period_start_date": "2026-01-01",
                "period_end_date": "2026-01-31",
                "recognition_date": "2026-01-31",
                "percentage": "0.600000",
            },
            {
                "period_seq": 2,
                "period_start_date": "2026-02-01",
                "period_end_date": "2026-03-31",
                "recognition_date": "2026-03-31",
                "percentage": "0.400000",
            },
        ],
    }
    normalized = normalize_pattern(PrepaidInput.model_validate(valid_payload))
    assert len(normalized.periods) == 2


def test_explicit_amounts_must_sum_to_base_amount() -> None:
    payload = {
        **_base_payload(),
        "pattern_type": "explicit_amounts",
        "periods": [
            {
                "period_seq": 1,
                "period_start_date": "2026-01-01",
                "period_end_date": "2026-01-31",
                "recognition_date": "2026-01-31",
                "amount": "100.000000",
            },
            {
                "period_seq": 2,
                "period_start_date": "2026-02-01",
                "period_end_date": "2026-03-31",
                "recognition_date": "2026-03-31",
                "amount": "150.000000",
            },
        ],
    }
    with pytest.raises(ValidationError):
        normalize_pattern(PrepaidInput.model_validate(payload))
