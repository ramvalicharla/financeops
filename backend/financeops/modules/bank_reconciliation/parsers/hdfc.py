from __future__ import annotations

import csv
import io
from datetime import datetime

from .base import BaseBankParser, BankTransaction


class HDFCBankParser(BaseBankParser):
    """
    Parser for HDFC Bank statement CSV format.
    HDFC CSV format: Date,Narration,Value Dt,Debit Amt,Credit Amt,
                     Chq/Ref Number,Closing Balance
    """

    BANK_NAME = "HDFC Bank"

    def parse_csv(self, content: str) -> list[BankTransaction]:
        transactions: list[BankTransaction] = []
        reader = csv.reader(io.StringIO(content))

        for row in reader:
            if len(row) < 6:
                continue
            if row[0].strip().lower() in ("date", "opening balance", "closing balance", ""):
                continue
            try:
                txn_date = datetime.strptime(row[0].strip(), "%d/%m/%y").date()
                transactions.append(
                    BankTransaction(
                        transaction_date=txn_date,
                        value_date=datetime.strptime(row[2].strip(), "%d/%m/%y").date() if row[2].strip() else None,
                        description=row[1].strip(),
                        reference=row[5].strip() if len(row) > 5 else "",
                        debit=self._parse_decimal(row[3].strip() if len(row) > 3 else ""),
                        credit=self._parse_decimal(row[4].strip() if len(row) > 4 else ""),
                        balance=self._parse_decimal(row[6].strip() if len(row) > 6 else ""),
                        transaction_type=self._detect_transaction_type(row[1]),
                    )
                )
            except (ValueError, IndexError):
                continue
        return transactions
