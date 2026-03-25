from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


@dataclass
class BankTransaction:
    transaction_date: date
    value_date: Optional[date]
    description: str
    reference: str
    debit: Optional[Decimal]
    credit: Optional[Decimal]
    balance: Optional[Decimal]
    transaction_type: str  # NEFT|RTGS|IMPS|UPI|CHQ|ATM|POS|OTHER

    @property
    def amount(self) -> Decimal:
        if self.credit:
            return self.credit
        return -(self.debit or Decimal("0"))


class BaseBankParser:
    BANK_NAME: str = ""

    def parse_csv(self, content: str) -> list[BankTransaction]:
        raise NotImplementedError

    def parse_excel(self, content: bytes) -> list[BankTransaction]:
        raise NotImplementedError

    def _parse_decimal(self, value: str) -> Optional[Decimal]:
        if not value or value.strip() in ("", "-", "0.00", "0"):
            return None
        clean = value.replace(",", "").strip()
        try:
            return Decimal(clean).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        except Exception:
            return None

    def _detect_transaction_type(self, description: str) -> str:
        desc = description.upper()
        if "NEFT" in desc:
            return "NEFT"
        if "RTGS" in desc:
            return "RTGS"
        if "IMPS" in desc:
            return "IMPS"
        if "UPI" in desc:
            return "UPI"
        if "ATM" in desc:
            return "ATM"
        if "POS" in desc:
            return "POS"
        if "CHQ" in desc or "CHEQUE" in desc:
            return "CHQ"
        return "OTHER"
