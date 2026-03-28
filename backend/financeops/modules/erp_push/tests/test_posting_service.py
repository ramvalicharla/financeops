from __future__ import annotations

import uuid
from decimal import Decimal

from financeops.db.models.erp_push import ErrorCategory, PushStatus
from financeops.modules.erp_push.application.posting_service import compute_idempotency_key
from financeops.modules.erp_push.domain.schemas import PushJournalLine, PushJournalPacket


def _make_packet(
    *,
    jv_id: uuid.UUID | None = None,
    jv_version: int = 1,
    connector_type: str = "zoho",
    amount: Decimal = Decimal("10000.00"),
) -> PushJournalPacket:
    current_jv_id = jv_id or uuid.uuid4()
    return PushJournalPacket(
        jv_id=current_jv_id,
        jv_number="JV-2026-03-0001",
        jv_version=jv_version,
        period_date="2026-03-01",
        description="Test JV",
        reference="REF-001",
        currency="INR",
        lines=[
            PushJournalLine(
                account_code="1001",
                external_account_id="EXT-1001",
                entry_type="DEBIT",
                amount=amount,
            ),
            PushJournalLine(
                account_code="2001",
                external_account_id="EXT-2001",
                entry_type="CREDIT",
                amount=amount,
            ),
        ],
        entity_id=uuid.uuid4(),
        connector_type=connector_type,
        idempotency_key="",
    )


class TestComputeIdempotencyKey:
    def test_deterministic(self) -> None:
        packet = _make_packet()
        assert compute_idempotency_key(packet) == compute_idempotency_key(packet)

    def test_changes_with_version(self) -> None:
        test_jv_id = uuid.uuid4()
        k1 = compute_idempotency_key(_make_packet(jv_id=test_jv_id, jv_version=1))
        k2 = compute_idempotency_key(_make_packet(jv_id=test_jv_id, jv_version=2))
        assert k1 != k2

    def test_changes_with_connector(self) -> None:
        test_jv_id = uuid.uuid4()
        k1 = compute_idempotency_key(_make_packet(jv_id=test_jv_id, connector_type="zoho"))
        k2 = compute_idempotency_key(_make_packet(jv_id=test_jv_id, connector_type="quickbooks"))
        assert k1 != k2

    def test_changes_with_decimal_amount(self) -> None:
        test_jv_id = uuid.uuid4()
        k1 = compute_idempotency_key(_make_packet(jv_id=test_jv_id, amount=Decimal("10000.00")))
        k2 = compute_idempotency_key(_make_packet(jv_id=test_jv_id, amount=Decimal("10000.01")))
        assert k1 != k2

    def test_sha256_length(self) -> None:
        assert len(compute_idempotency_key(_make_packet())) == 64


class TestPushStatusAndErrorConstants:
    def test_status_values(self) -> None:
        assert PushStatus.PUSH_IN_PROGRESS in PushStatus.ALL
        assert PushStatus.PUSHED in PushStatus.TERMINAL
        assert PushStatus.DEAD_LETTER in PushStatus.TERMINAL

    def test_error_categories(self) -> None:
        assert ErrorCategory.HARD == "HARD"
        assert ErrorCategory.SOFT == "SOFT"


class TestPacketDecimalSafety:
    def test_line_amounts_are_decimals(self) -> None:
        packet = _make_packet(amount=Decimal("99999.9999"))
        for line in packet.lines:
            assert isinstance(line.amount, Decimal)

    def test_no_float_leakage(self) -> None:
        packet = _make_packet(amount=Decimal("0.1") + Decimal("0.2"))
        for line in packet.lines:
            assert line.amount == Decimal("0.3")
