from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from financeops.db.models.accounting_jv import JVStatus
from financeops.modules.accounting_layer.application.push_gate import (
    GateFailure,
    gate_account_mappings_complete,
    gate_entity_config_complete,
    gate_jv_approved,
    gate_no_stale_mappings,
    gate_period_open,
    run_all_push_gates,
)


def _make_jv(
    *,
    status: str = JVStatus.APPROVED,
    fiscal_year: int = 2026,
    fiscal_period: int = 3,
    entity_id: uuid.UUID | None = None,
    lines: list | None = None,
) -> MagicMock:
    jv = MagicMock()
    jv.id = uuid.uuid4()
    jv.tenant_id = uuid.uuid4()
    jv.entity_id = entity_id or uuid.uuid4()
    jv.status = status
    jv.fiscal_year = fiscal_year
    jv.fiscal_period = fiscal_period
    jv.version = 1
    jv.lines = lines or []
    return jv


def _make_ref(
    *,
    internal_account_code: str = "1001",
    is_stale: bool = False,
    is_active: bool = True,
) -> MagicMock:
    ref = MagicMock()
    ref.internal_account_code = internal_account_code
    ref.is_stale = is_stale
    ref.is_active = is_active
    return ref


def _make_connection(*, connection_status: str = "active") -> MagicMock:
    connection = MagicMock()
    connection.connection_status = connection_status
    connection.tenant_id = uuid.uuid4()
    connection.id = uuid.uuid4()
    connection.secret_ref = None
    connection.pinned_connector_version = None
    connection.connector_type = "zoho"
    return connection


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


class TestGateJVApproved:
    @pytest.mark.asyncio
    async def test_approved_passes(self) -> None:
        await gate_jv_approved(_make_jv(status=JVStatus.APPROVED))

    @pytest.mark.asyncio
    async def test_draft_fails(self) -> None:
        with pytest.raises(GateFailure) as exc:
            await gate_jv_approved(_make_jv(status=JVStatus.DRAFT))
        assert exc.value.gate == "JV_STATUS"

    @pytest.mark.asyncio
    async def test_submitted_fails(self) -> None:
        with pytest.raises(GateFailure) as exc:
            await gate_jv_approved(_make_jv(status=JVStatus.SUBMITTED))
        assert exc.value.gate == "JV_STATUS"


class TestGatePeriodOpen:
    @pytest.mark.asyncio
    async def test_unlocked_period_passes(self, tenant_id: uuid.UUID) -> None:
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        await gate_period_open(
            db,
            tenant_id=tenant_id,
            entity_id=uuid.uuid4(),
            fiscal_year=2026,
            fiscal_period=3,
        )

    @pytest.mark.asyncio
    async def test_locked_period_fails(self, tenant_id: uuid.UUID) -> None:
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = MagicMock()
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(GateFailure) as exc:
            await gate_period_open(
                db,
                tenant_id=tenant_id,
                entity_id=uuid.uuid4(),
                fiscal_year=2026,
                fiscal_period=3,
            )
        assert exc.value.gate == "PERIOD_LOCKED"


class TestGateAccountMappingsComplete:
    @pytest.mark.asyncio
    async def test_all_mapped_passes(self, tenant_id: uuid.UUID) -> None:
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [
            _make_ref(internal_account_code="1001"),
            _make_ref(internal_account_code="2001"),
        ]
        db.execute = AsyncMock(return_value=result)

        await gate_account_mappings_complete(
            db,
            tenant_id=tenant_id,
            connector_type="ZOHO",
            account_codes=["1001", "2001"],
        )

    @pytest.mark.asyncio
    async def test_unmapped_code_fails(self, tenant_id: uuid.UUID) -> None:
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [_make_ref(internal_account_code="1001")]
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(GateFailure) as exc:
            await gate_account_mappings_complete(
                db,
                tenant_id=tenant_id,
                connector_type="ZOHO",
                account_codes=["1001", "2001"],
            )
        assert exc.value.gate == "ACCOUNT_MAPPING"
        assert "2001" in exc.value.reason

    @pytest.mark.asyncio
    async def test_empty_account_codes_fails(self, tenant_id: uuid.UUID) -> None:
        db = AsyncMock()
        with pytest.raises(GateFailure) as exc:
            await gate_account_mappings_complete(
                db,
                tenant_id=tenant_id,
                connector_type="ZOHO",
                account_codes=[],
            )
        assert exc.value.gate == "ACCOUNT_MAPPING"


class TestGateNoStaleMappings:
    @pytest.mark.asyncio
    async def test_no_stale_passes(self, tenant_id: uuid.UUID) -> None:
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=result)

        await gate_no_stale_mappings(
            db,
            tenant_id=tenant_id,
            connector_type="ZOHO",
            account_codes=["1001"],
        )

    @pytest.mark.asyncio
    async def test_stale_mapping_fails(self, tenant_id: uuid.UUID) -> None:
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [
            _make_ref(internal_account_code="1001", is_stale=True)
        ]
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(GateFailure) as exc:
            await gate_no_stale_mappings(
                db,
                tenant_id=tenant_id,
                connector_type="ZOHO",
                account_codes=["1001"],
            )
        assert exc.value.gate == "STALE_MAPPING"
        assert "1001" in exc.value.reason


class TestGateEntityConfigComplete:
    @pytest.mark.asyncio
    async def test_active_connection_passes(self, tenant_id: uuid.UUID) -> None:
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = _make_connection(connection_status="active")
        db.execute = AsyncMock(return_value=result)

        await gate_entity_config_complete(
            db,
            tenant_id=tenant_id,
            entity_id=uuid.uuid4(),
            connector_type="ZOHO",
        )

    @pytest.mark.asyncio
    async def test_no_connection_fails(self, tenant_id: uuid.UUID) -> None:
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result)

        with pytest.raises(GateFailure) as exc:
            await gate_entity_config_complete(
                db,
                tenant_id=tenant_id,
                entity_id=uuid.uuid4(),
                connector_type="ZOHO",
            )
        assert exc.value.gate == "ENTITY_CONFIG"


class TestRunAllPushGates:
    @pytest.mark.asyncio
    async def test_all_gates_pass(self, tenant_id: uuid.UUID) -> None:
        line = MagicMock()
        line.jv_version = 1
        line.account_code = "1001"

        jv = _make_jv(status=JVStatus.APPROVED, lines=[line], entity_id=uuid.uuid4())
        jv.tenant_id = tenant_id

        period_result = MagicMock()
        period_result.scalar_one_or_none.return_value = None

        mapping_result = MagicMock()
        mapping_result.scalars.return_value.all.return_value = [
            _make_ref(internal_account_code="1001")
        ]

        stale_result = MagicMock()
        stale_result.scalars.return_value.all.return_value = []

        connection_result = MagicMock()
        connection_result.scalar_one_or_none.return_value = _make_connection(connection_status="active")

        calls = 0

        async def mock_execute(_stmt: object) -> MagicMock:
            nonlocal calls
            calls += 1
            if calls == 1:
                return period_result
            if calls == 2:
                return mapping_result
            if calls == 3:
                return stale_result
            return connection_result

        db = AsyncMock()
        db.execute = mock_execute

        await run_all_push_gates(db, jv=jv, connector_type="ZOHO", tenant_id=tenant_id)

    @pytest.mark.asyncio
    async def test_first_failing_gate_raises(self, tenant_id: uuid.UUID) -> None:
        jv = _make_jv(status=JVStatus.DRAFT)
        jv.tenant_id = tenant_id

        with pytest.raises(GateFailure) as exc:
            await run_all_push_gates(
                AsyncMock(),
                jv=jv,
                connector_type="ZOHO",
                tenant_id=tenant_id,
            )
        assert exc.value.gate == "JV_STATUS"

    @pytest.mark.asyncio
    async def test_gate_failure_carries_reason(self, tenant_id: uuid.UUID) -> None:
        jv = _make_jv(status=JVStatus.REJECTED)
        jv.tenant_id = tenant_id

        with pytest.raises(GateFailure) as exc:
            await run_all_push_gates(
                AsyncMock(),
                jv=jv,
                connector_type="QBO",
                tenant_id=tenant_id,
            )
        assert exc.value.gate == "JV_STATUS"
        assert "REJECTED" in exc.value.reason
