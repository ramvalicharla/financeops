from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from financeops.core.exceptions import ValidationError
from financeops.db.models.erp_push import ErrorCategory, PushStatus
from financeops.modules.erp_push.application.posting_service import (
    _dispatch_to_connector,
    compute_idempotency_key,
)
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


def _scalar_result(value):
    return SimpleNamespace(scalar_one_or_none=lambda: value)


class TestConnectorCredentialReadiness:
    @pytest.mark.asyncio
    async def test_zoho_dispatch_requires_persisted_organization_id(self) -> None:
        tenant_id = uuid.uuid4()
        connection_id = uuid.uuid4()
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=_scalar_result(
                SimpleNamespace(
                    id=connection_id,
                    organisation_id=tenant_id,
                    secret_ref="enc-secret",
                )
            )
        )

        with (
            patch(
                "financeops.modules.erp_push.application.posting_service.secret_store.get_secret",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "financeops.modules.erp_push.application.posting_service.get_decrypted_access_token",
                new_callable=AsyncMock,
                return_value="access-token",
            ),
        ):
            with pytest.raises(
                ValidationError,
                match="Zoho organization_id missing from persisted connection credentials",
            ):
                await _dispatch_to_connector(
                    db,
                    packet=_make_packet(connector_type="zoho"),
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    connector_type="zoho",
                    simulation=False,
                )

    @pytest.mark.asyncio
    async def test_qbo_dispatch_requires_persisted_realm_id(self) -> None:
        tenant_id = uuid.uuid4()
        connection_id = uuid.uuid4()
        db = AsyncMock()
        db.execute = AsyncMock(
            return_value=_scalar_result(
                SimpleNamespace(
                    id=connection_id,
                    organisation_id=tenant_id,
                    secret_ref="enc-secret",
                )
            )
        )

        with (
            patch(
                "financeops.modules.erp_push.application.posting_service.secret_store.get_secret",
                new_callable=AsyncMock,
                return_value={},
            ),
            patch(
                "financeops.modules.erp_push.application.posting_service.get_decrypted_access_token",
                new_callable=AsyncMock,
                return_value="access-token",
            ),
        ):
            with pytest.raises(
                ValidationError,
                match="QuickBooks realm_id missing from persisted connection credentials",
            ):
                await _dispatch_to_connector(
                    db,
                    packet=_make_packet(connector_type="quickbooks"),
                    tenant_id=tenant_id,
                    connection_id=connection_id,
                    connector_type="quickbooks",
                    simulation=False,
                )
