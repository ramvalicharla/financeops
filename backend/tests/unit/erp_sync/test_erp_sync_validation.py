from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from financeops.modules.erp_sync.application.validation_service import (
    VALIDATION_CATEGORIES,
    ValidationService,
)
from financeops.modules.erp_sync.domain.enums import SyncRunStatus


def _base_payload() -> dict[str, object]:
    return {
        "dataset_token": "sha256:test",
        "currency": "INR",
        "entity_id": "entity_001",
        "from_date": date(2026, 1, 1),
        "to_date": date(2026, 1, 31),
        "total_debits": Decimal("100.00"),
        "total_credits": Decimal("100.00"),
    }


@pytest.mark.parametrize("category", VALIDATION_CATEGORIES)
def test_validation_all_20_categories_pass_with_explicit_override(category: str) -> None:
    service = ValidationService()
    result = service.validate(
        dataset_type="trial_balance",
        canonical_payload=_base_payload(),
        raw_payload={"payload_hash": "hash_1"},
        context={f"{category.lower()}_pass": True},
    )
    by_category = {entry["category"]: entry for entry in result["categories"]}
    assert by_category[category]["passed"] is True


@pytest.mark.parametrize("category", VALIDATION_CATEGORIES)
def test_validation_all_20_categories_fail_with_explicit_override(category: str) -> None:
    service = ValidationService()
    result = service.validate(
        dataset_type="trial_balance",
        canonical_payload=_base_payload(),
        raw_payload={"payload_hash": "hash_1"},
        context={f"{category.lower()}_pass": False},
    )
    by_category = {entry["category"]: entry for entry in result["categories"]}
    assert by_category[category]["passed"] is False
    assert result["run_status"] == SyncRunStatus.HALTED.value
    assert result["passed"] is False


def test_validation_success_when_defaults_satisfied() -> None:
    service = ValidationService()
    result = service.validate(
        dataset_type="trial_balance",
        canonical_payload=_base_payload(),
        raw_payload={"payload_hash": "hash_1"},
        context={
            "expected_raw_snapshot_hash": "hash_1",
            "entity_id": "entity_001",
        },
    )
    assert result["passed"] is True
    assert result["run_status"] == SyncRunStatus.COMPLETED.value
    assert len(result["categories"]) == 20
