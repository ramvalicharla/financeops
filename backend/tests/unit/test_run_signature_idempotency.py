from __future__ import annotations

from financeops.services.accounting_common.run_signature import build_request_signature


def test_build_request_signature_is_order_insensitive_for_lists_and_dicts() -> None:
    payload_a = {
        "period": {"year": 2026, "month": 3},
        "entities": [{"entity_id": "b"}, {"entity_id": "a"}],
    }
    payload_b = {
        "entities": [{"entity_id": "a"}, {"entity_id": "b"}],
        "period": {"month": 3, "year": 2026},
    }

    assert build_request_signature(payload_a) == build_request_signature(payload_b)


def test_build_request_signature_changes_when_payload_changes() -> None:
    payload_a = {"engine": "revenue", "version": 1}
    payload_b = {"engine": "revenue", "version": 2}

    assert build_request_signature(payload_a) != build_request_signature(payload_b)
