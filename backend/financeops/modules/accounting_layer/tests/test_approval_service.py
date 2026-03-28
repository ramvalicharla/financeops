from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from financeops.core.exceptions import AuthorizationError, ValidationError
from financeops.db.models.accounting_jv import JVStatus
from financeops.modules.accounting_layer.application.approval_service import (
    ROLE_APPROVAL_LEVEL,
    _THRESHOLD_L2,
    _THRESHOLD_L3,
    _enforce_approval_level,
    _enforce_maker_checker,
    required_approval_level,
)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _make_jv(
    *,
    status: str = JVStatus.UNDER_REVIEW,
    total_debit: Decimal = Decimal("100000"),
    created_by: uuid.UUID | None = None,
    version: int = 1,
    submitted_at: datetime | None = None,
    first_reviewed_at: datetime | None = None,
    decided_at: datetime | None = None,
) -> MagicMock:
    jv = MagicMock()
    jv.id = uuid.uuid4()
    jv.tenant_id = uuid.uuid4()
    jv.entity_id = uuid.uuid4()
    jv.status = status
    jv.version = version
    jv.total_debit = total_debit
    jv.created_by = created_by or uuid.uuid4()
    jv.submitted_at = submitted_at
    jv.first_reviewed_at = first_reviewed_at
    jv.decided_at = decided_at
    return jv


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def preparer_id() -> uuid.UUID:
    return uuid.uuid4()


class TestRequiredApprovalLevel:
    def test_below_l2_threshold_requires_level_1(self) -> None:
        assert required_approval_level(Decimal("499999.99")) == 1

    def test_at_l2_threshold_requires_level_2(self) -> None:
        assert required_approval_level(_THRESHOLD_L2) == 2

    def test_between_thresholds_requires_level_2(self) -> None:
        assert required_approval_level(Decimal("999999")) == 2

    def test_at_l3_threshold_requires_level_3(self) -> None:
        assert required_approval_level(_THRESHOLD_L3) == 3

    def test_above_l3_requires_level_3(self) -> None:
        assert required_approval_level(Decimal("10000000")) == 3

    def test_zero_amount_requires_level_1(self) -> None:
        assert required_approval_level(Decimal("0")) == 1

    def test_decimal_precision_boundary(self) -> None:
        assert required_approval_level(Decimal("500000.0000")) == 2


class TestMakerChecker:
    def test_preparer_cannot_approve_own_jv(self, preparer_id: uuid.UUID) -> None:
        jv = _make_jv(created_by=preparer_id)
        with pytest.raises(AuthorizationError, match="Maker-checker"):
            _enforce_maker_checker(jv, preparer_id, "ACCOUNTING_REVIEWER")

    def test_different_user_can_approve(self, preparer_id: uuid.UUID, user_id: uuid.UUID) -> None:
        jv = _make_jv(created_by=preparer_id)
        _enforce_maker_checker(jv, user_id, "ACCOUNTING_REVIEWER")

    def test_admin_cannot_self_approve(self, preparer_id: uuid.UUID) -> None:
        jv = _make_jv(created_by=preparer_id)
        with pytest.raises(AuthorizationError, match="Maker-checker"):
            _enforce_maker_checker(jv, preparer_id, "ACCOUNTING_ADMIN")


class TestEnforceApprovalLevel:
    def test_reviewer_approved_for_small_amount(self) -> None:
        jv = _make_jv(total_debit=Decimal("100000"))
        _enforce_approval_level(jv, "ACCOUNTING_REVIEWER")

    def test_reviewer_rejected_for_large_amount(self) -> None:
        jv = _make_jv(total_debit=Decimal("1000000"))
        with pytest.raises(AuthorizationError, match="level"):
            _enforce_approval_level(jv, "ACCOUNTING_REVIEWER")

    def test_sr_reviewer_approved_for_mid_amount(self) -> None:
        jv = _make_jv(total_debit=Decimal("1000000"))
        _enforce_approval_level(jv, "ACCOUNTING_SR_REVIEWER")

    def test_sr_reviewer_rejected_for_very_large_amount(self) -> None:
        jv = _make_jv(total_debit=Decimal("6000000"))
        with pytest.raises(AuthorizationError, match="level"):
            _enforce_approval_level(jv, "ACCOUNTING_SR_REVIEWER")

    def test_cfo_approver_can_approve_any_amount(self) -> None:
        jv = _make_jv(total_debit=Decimal("100000000"))
        _enforce_approval_level(jv, "ACCOUNTING_CFO_APPROVER")

    def test_admin_can_approve_any_amount(self) -> None:
        jv = _make_jv(total_debit=Decimal("100000000"))
        _enforce_approval_level(jv, "ACCOUNTING_ADMIN")

    def test_unknown_role_raises(self) -> None:
        jv = _make_jv(total_debit=Decimal("100000"))
        with pytest.raises(AuthorizationError, match="approval authority"):
            _enforce_approval_level(jv, "UNKNOWN_ROLE")

    def test_case_insensitive_role(self) -> None:
        jv = _make_jv(total_debit=Decimal("100000"))
        _enforce_approval_level(jv, "accounting_reviewer")

    def test_decimal_boundary_exact(self) -> None:
        jv = _make_jv(total_debit=_THRESHOLD_L2)
        with pytest.raises(AuthorizationError):
            _enforce_approval_level(jv, "ACCOUNTING_REVIEWER")
        _enforce_approval_level(jv, "ACCOUNTING_SR_REVIEWER")


class TestRoleApprovalLevelMap:
    def test_all_accounting_roles_mapped(self) -> None:
        expected = {
            "ACCOUNTING_REVIEWER",
            "ACCOUNTING_SR_REVIEWER",
            "ACCOUNTING_CFO_APPROVER",
            "ACCOUNTING_ADMIN",
        }
        assert expected.issubset(set(ROLE_APPROVAL_LEVEL.keys()))

    def test_preparer_not_in_approval_map(self) -> None:
        assert "ACCOUNTING_PREPARER" not in ROLE_APPROVAL_LEVEL

    def test_auditor_not_in_approval_map(self) -> None:
        assert "ACCOUNTING_AUDITOR" not in ROLE_APPROVAL_LEVEL

    def test_levels_are_1_2_or_3(self) -> None:
        for role, level in ROLE_APPROVAL_LEVEL.items():
            assert level in (1, 2, 3), f"{role} has invalid level {level}"


class TestDecimalPrecision:
    def test_threshold_comparisons_use_decimal(self) -> None:
        assert isinstance(_THRESHOLD_L2, Decimal)
        assert isinstance(_THRESHOLD_L3, Decimal)

    def test_boundary_arithmetic_exact(self) -> None:
        assert Decimal("0.1") + Decimal("0.2") == Decimal("0.3")

    def test_required_level_with_decimal_input(self) -> None:
        assert required_approval_level(Decimal("500000.0001")) == 2

    def test_threshold_l2_is_exact(self) -> None:
        assert _THRESHOLD_L2 == Decimal("500000")
        assert _THRESHOLD_L3 == Decimal("5000000")
