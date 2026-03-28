from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from financeops.core.exceptions import ValidationError
from financeops.db.models.accounting_jv import EntryType, JVStatus
from financeops.modules.accounting_layer.application.jv_service import (
    _compute_hash,
    _to_decimal,
    _validate_ready_to_submit,
)
from financeops.modules.accounting_layer.domain.state_machine import (
    MAX_RESUBMISSIONS,
    TransitionRequest,
    _valid_next_states,
    next_status_after_resubmit,
    validate_transition,
)


def _make_jv(
    *,
    status: str = JVStatus.DRAFT,
    version: int = 1,
    resubmission_count: int = 0,
    lines: list | None = None,
) -> MagicMock:
    jv = MagicMock()
    jv.id = uuid.uuid4()
    jv.tenant_id = uuid.uuid4()
    jv.entity_id = uuid.uuid4()
    jv.status = status
    jv.version = version
    jv.resubmission_count = resubmission_count
    jv.lines = lines or []
    return jv


def _make_line(
    *,
    entry_type: str = EntryType.DEBIT,
    amount: Decimal = Decimal("1000.00"),
    jv_version: int = 1,
) -> MagicMock:
    line = MagicMock()
    line.entry_type = entry_type
    line.amount = amount
    line.jv_version = jv_version
    return line


class TestToDecimal:
    def test_converts_string(self) -> None:
        assert _to_decimal("1000.50", "amount") == Decimal("1000.50")

    def test_converts_int(self) -> None:
        assert _to_decimal(1000, "amount") == Decimal("1000")

    def test_negative_raises(self) -> None:
        with pytest.raises(ValidationError, match="non-negative"):
            _to_decimal("-1", "amount")

    def test_invalid_string_raises(self) -> None:
        with pytest.raises(ValidationError):
            _to_decimal("not_a_number", "amount")

    def test_no_float_precision_loss(self) -> None:
        assert _to_decimal("0.1", "x") + _to_decimal("0.2", "x") == Decimal("0.3")


class TestComputeHash:
    def test_deterministic(self) -> None:
        assert _compute_hash("content", "prev") == _compute_hash("content", "prev")

    def test_different_content_different_hash(self) -> None:
        assert _compute_hash("content_a", "prev") != _compute_hash("content_b", "prev")

    def test_none_previous_hash_handled(self) -> None:
        digest = _compute_hash("content", None)
        assert isinstance(digest, str)
        assert len(digest) == 64


class TestStateMachine:
    def _req(self, from_status: str, to_status: str, **kwargs: object) -> TransitionRequest:
        return TransitionRequest(
            from_status=from_status,
            to_status=to_status,
            triggered_by_role=str(kwargs.get("role", "Preparer")),
            is_admin=bool(kwargs.get("is_admin", False)),
            comment=kwargs.get("comment") if isinstance(kwargs.get("comment"), str) else None,
            resubmission_count=int(kwargs.get("resubmission_count", 0)),
        )

    def test_forward_path(self) -> None:
        validate_transition(self._req(JVStatus.DRAFT, JVStatus.SUBMITTED))
        validate_transition(self._req(JVStatus.SUBMITTED, JVStatus.PENDING_REVIEW))
        validate_transition(self._req(JVStatus.PENDING_REVIEW, JVStatus.UNDER_REVIEW))
        validate_transition(self._req(JVStatus.UNDER_REVIEW, JVStatus.APPROVED))

    def test_push_path(self) -> None:
        validate_transition(self._req(JVStatus.APPROVED, JVStatus.PUSH_IN_PROGRESS))
        validate_transition(self._req(JVStatus.PUSH_IN_PROGRESS, JVStatus.PUSH_FAILED))
        validate_transition(self._req(JVStatus.PUSH_FAILED, JVStatus.PUSH_IN_PROGRESS))
        validate_transition(self._req(JVStatus.PUSH_IN_PROGRESS, JVStatus.PUSHED))

    def test_rejection_requires_comment(self) -> None:
        with pytest.raises(ValidationError, match="comment"):
            validate_transition(self._req(JVStatus.PENDING_REVIEW, JVStatus.REJECTED))

    def test_rejection_with_comment(self) -> None:
        validate_transition(
            self._req(
                JVStatus.UNDER_REVIEW,
                JVStatus.REJECTED,
                comment="Account mismatch",
            )
        )

    def test_resubmission_limit(self) -> None:
        with pytest.raises(ValidationError, match="max resubmissions"):
            validate_transition(
                self._req(
                    JVStatus.REJECTED,
                    JVStatus.RESUBMITTED,
                    resubmission_count=MAX_RESUBMISSIONS,
                )
            )

    def test_void_requires_admin_and_comment(self) -> None:
        with pytest.raises(ValidationError, match="Admin"):
            validate_transition(
                self._req(JVStatus.DRAFT, JVStatus.VOIDED, comment="Fix", is_admin=False)
            )

        with pytest.raises(ValidationError, match="void reason"):
            validate_transition(self._req(JVStatus.DRAFT, JVStatus.VOIDED, is_admin=True))

        validate_transition(
            self._req(JVStatus.DRAFT, JVStatus.VOIDED, comment="Fix", is_admin=True)
        )

    def test_terminal_states_blocked(self) -> None:
        with pytest.raises(ValidationError, match="terminal"):
            validate_transition(self._req(JVStatus.PUSHED, JVStatus.VOIDED, is_admin=True, comment="X"))
        with pytest.raises(ValidationError, match="terminal"):
            validate_transition(self._req(JVStatus.VOIDED, JVStatus.DRAFT))

    def test_invalid_transition_rejected(self) -> None:
        with pytest.raises(ValidationError, match="not allowed"):
            validate_transition(self._req(JVStatus.DRAFT, JVStatus.PUSHED))


class TestResubmitNextState:
    def test_below_limit_returns_resubmitted(self) -> None:
        for count in range(MAX_RESUBMISSIONS):
            assert next_status_after_resubmit(count) == JVStatus.RESUBMITTED

    def test_at_or_above_limit_returns_escalated(self) -> None:
        assert next_status_after_resubmit(MAX_RESUBMISSIONS) == JVStatus.ESCALATED
        assert next_status_after_resubmit(MAX_RESUBMISSIONS + 1) == JVStatus.ESCALATED


class TestValidateReadyToSubmit:
    def test_no_lines_raises(self) -> None:
        with pytest.raises(ValidationError, match="at least one line"):
            _validate_ready_to_submit(_make_jv(lines=[]))

    def test_single_line_raises(self) -> None:
        line = _make_line(entry_type=EntryType.DEBIT, amount=Decimal("100"))
        with pytest.raises(ValidationError, match="at least 2 lines"):
            _validate_ready_to_submit(_make_jv(lines=[line]))

    def test_unbalanced_raises(self) -> None:
        debit = _make_line(entry_type=EntryType.DEBIT, amount=Decimal("1000"))
        credit = _make_line(entry_type=EntryType.CREDIT, amount=Decimal("900"))
        with pytest.raises(ValidationError, match="not balanced"):
            _validate_ready_to_submit(_make_jv(lines=[debit, credit]))

    def test_balanced_passes(self) -> None:
        debit = _make_line(entry_type=EntryType.DEBIT, amount=Decimal("1000"))
        credit = _make_line(entry_type=EntryType.CREDIT, amount=Decimal("1000"))
        _validate_ready_to_submit(_make_jv(lines=[debit, credit]))


class TestStatusConstants:
    def test_all_contains_12_states(self) -> None:
        assert len(JVStatus.ALL) == 12

    def test_terminal_subset(self) -> None:
        assert JVStatus.TERMINAL_STATES.issubset(JVStatus.IMMUTABLE_STATES)

    def test_valid_next_states_helper(self) -> None:
        next_states = _valid_next_states(JVStatus.DRAFT)
        assert JVStatus.SUBMITTED in next_states
        assert JVStatus.VOIDED in next_states
        assert _valid_next_states(JVStatus.PUSHED) == []
