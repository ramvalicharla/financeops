from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from financeops.modules.accounting_layer.domain.schemas import JournalCreate, JournalLineCreate


class TestJournalLineCreate:
    def test_requires_account_reference(self) -> None:
        with pytest.raises(PydanticValidationError):
            JournalLineCreate(debit=Decimal("100.00"), credit=Decimal("0.00"))

    def test_rejects_both_debit_credit(self) -> None:
        with pytest.raises(PydanticValidationError):
            JournalLineCreate(
                account_code="1000",
                debit=Decimal("100.00"),
                credit=Decimal("100.00"),
            )

    def test_rejects_negative_amount(self) -> None:
        with pytest.raises(PydanticValidationError):
            JournalLineCreate(
                account_code="1000",
                debit=Decimal("-1"),
                credit=Decimal("0"),
            )

    def test_accepts_tenant_coa_account_id_only(self) -> None:
        line = JournalLineCreate(
            tenant_coa_account_id=uuid.uuid4(),
            debit=Decimal("250.00"),
            credit=Decimal("0.00"),
            memo="Opening balance",
        )
        assert line.debit == Decimal("250.00")
        assert line.credit == Decimal("0.00")


class TestJournalCreate:
    def test_requires_balanced_lines(self) -> None:
        with pytest.raises(PydanticValidationError):
            JournalCreate(
                org_entity_id=uuid.uuid4(),
                journal_date=date(2026, 4, 1),
                reference="JV-REF-1",
                narration="Mismatch example",
                lines=[
                    JournalLineCreate(account_code="1000", debit=Decimal("100.00"), credit=Decimal("0.00")),
                    JournalLineCreate(account_code="2000", debit=Decimal("0.00"), credit=Decimal("90.00")),
                ],
            )

    def test_accepts_balanced_journal(self) -> None:
        journal = JournalCreate(
            org_entity_id=uuid.uuid4(),
            journal_date=date(2026, 4, 1),
            reference="JV-REF-2",
            narration="Balanced example",
            lines=[
                JournalLineCreate(account_code="1000", debit=Decimal("500.00"), credit=Decimal("0.00")),
                JournalLineCreate(account_code="2000", debit=Decimal("0.00"), credit=Decimal("500.00")),
            ],
        )
        assert sum(line.debit for line in journal.lines) == Decimal("500.00")
        assert sum(line.credit for line in journal.lines) == Decimal("500.00")
