from __future__ import annotations

import csv
import io
from datetime import datetime

from .base import BaseBankParser, BankTransaction


class AxisBankParser(BaseBankParser):
    """
    Parser for Axis Bank statement CSV format.
    Axis format: Tran Date,CHQNO,PARTICULARS,DR,CR,BAL
    """

    BANK_NAME = "Axis Bank"

    def parse_csv(self, content: str) -> list[BankTransaction]:
        transactions: list[BankTransaction] = []
        reader = csv.reader(io.StringIO(content))
        for row in reader:
            if len(row) < 4:
                continue
            if row[0].strip().lower() in ("tran date", "opening balance", ""):
                continue
            try:
                txn_date = datetime.strptime(row[0].strip(), "%d-%m-%Y").date()
                transactions.append(
                    BankTransaction(
                        transaction_date=txn_date,
                        value_date=None,
                        description=row[2].strip(),
                        reference=row[1].strip(),
                        debit=self._parse_decimal(row[3].strip() if len(row) > 3 else ""),
                        credit=self._parse_decimal(row[4].strip() if len(row) > 4 else ""),
                        balance=self._parse_decimal(row[5].strip() if len(row) > 5 else ""),
                        transaction_type=self._detect_transaction_type(row[2]),
                    )
                )
            except (ValueError, IndexError):
                continue
        return transactions
