from __future__ import annotations

import csv
import io
from datetime import datetime

from .base import BaseBankParser, BankTransaction


class SBIBankParser(BaseBankParser):
    """
    Parser for SBI Bank statement CSV format.
    SBI format: Txn Date,Value Date,Description,Ref No/Cheque No,
                Debit,Credit,Balance
    """

    BANK_NAME = "State Bank of India"

    def parse_csv(self, content: str) -> list[BankTransaction]:
        transactions: list[BankTransaction] = []
        reader = csv.reader(io.StringIO(content))
        for row in reader:
            if len(row) < 5:
                continue
            if row[0].strip().lower() in ("txn date", ""):
                continue
            try:
                txn_date = datetime.strptime(row[0].strip(), "%d %b %Y").date()
                transactions.append(
                    BankTransaction(
                        transaction_date=txn_date,
                        value_date=None,
                        description=row[2].strip(),
                        reference=row[3].strip(),
                        debit=self._parse_decimal(row[4].strip()),
                        credit=self._parse_decimal(row[5].strip() if len(row) > 5 else ""),
                        balance=self._parse_decimal(row[6].strip() if len(row) > 6 else ""),
                        transaction_type=self._detect_transaction_type(row[2]),
                    )
                )
            except (ValueError, IndexError):
                continue
        return transactions
