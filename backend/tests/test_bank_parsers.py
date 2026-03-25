from __future__ import annotations

from decimal import Decimal

import pytest

from financeops.modules.bank_reconciliation.parsers.axis import AxisBankParser
from financeops.modules.bank_reconciliation.parsers.factory import (
    detect_bank_from_content,
)
from financeops.modules.bank_reconciliation.parsers.hdfc import HDFCBankParser
from financeops.modules.bank_reconciliation.parsers.icici import ICICIBankParser
from financeops.modules.bank_reconciliation.parsers.sbi import SBIBankParser


def test_hdfc_csv_parsing() -> None:
    sample = (
        "Date,Narration,Value Dt,Debit Amt,Credit Amt,Chq/Ref Number,Closing Balance\n"
        "01/04/24,UPI/123456/Payment,01/04/24,1000.00,,REF001,99000.00\n"
        "02/04/24,NEFT/ABC Corp,02/04/24,,50000.00,REF002,149000.00\n"
    )
    txns = HDFCBankParser().parse_csv(sample)
    assert len(txns) == 2
    assert isinstance(txns[0].debit, Decimal)
    assert isinstance(txns[1].credit, Decimal)
    assert txns[0].transaction_type == "UPI"
    assert txns[1].transaction_type == "NEFT"


def test_icici_csv_parsing() -> None:
    sample = (
        "Transaction Date,Value Date,Description,Ref No./Cheque No.,Debit,Credit,Balance\n"
        "03/04/2024,03/04/2024,RTGS/XYZ,REF100,100.00,,900.00\n"
    )
    txns = ICICIBankParser().parse_csv(sample)
    assert len(txns) == 1
    assert txns[0].transaction_date.day == 3
    assert txns[0].transaction_date.month == 4
    assert txns[0].transaction_date.year == 2024


def test_sbi_csv_parsing() -> None:
    sample = "Txn Date,Value Date,Description,Ref No/Cheque No,Debit,Credit,Balance\n04 Apr 2024,,IMPS/ABC,REF1,10.00,,100.00\n"
    txns = SBIBankParser().parse_csv(sample)
    assert len(txns) == 1
    assert txns[0].transaction_date.month == 4


def test_axis_csv_parsing() -> None:
    sample = "Tran Date,CHQNO,PARTICULARS,DR,CR,BAL\n05-04-2024,REF1,NEFT/ABC,10.00,,90.00\n"
    txns = AxisBankParser().parse_csv(sample)
    assert len(txns) == 1
    assert txns[0].transaction_date.day == 5


def test_bank_auto_detection_hdfc() -> None:
    assert detect_bank_from_content("HDFC Bank statement header") == "hdfc"


def test_bank_auto_detection_icici() -> None:
    assert detect_bank_from_content("ICICI Bank statement header") == "icici"


def test_bank_auto_detection_unknown_raises() -> None:
    with pytest.raises(ValueError):
        detect_bank_from_content("Unknown bank content")


def test_all_amounts_decimal_not_float() -> None:
    sample = (
        "Date,Narration,Value Dt,Debit Amt,Credit Amt,Chq/Ref Number,Closing Balance\n"
        "01/04/24,UPI/1,01/04/24,100.00,,R1,900.00\n"
    )
    txn = HDFCBankParser().parse_csv(sample)[0]
    assert isinstance(txn.debit, Decimal)
    assert txn.credit is None


def test_upi_transaction_type_detected() -> None:
    sample = (
        "Date,Narration,Value Dt,Debit Amt,Credit Amt,Chq/Ref Number,Closing Balance\n"
        "01/04/24,UPI/ABC,01/04/24,10.00,,R1,90.00\n"
    )
    assert HDFCBankParser().parse_csv(sample)[0].transaction_type == "UPI"


def test_neft_transaction_type_detected() -> None:
    sample = (
        "Date,Narration,Value Dt,Debit Amt,Credit Amt,Chq/Ref Number,Closing Balance\n"
        "01/04/24,NEFT/ABC,01/04/24,10.00,,R1,90.00\n"
    )
    assert HDFCBankParser().parse_csv(sample)[0].transaction_type == "NEFT"


def test_rtgs_transaction_type_detected() -> None:
    sample = (
        "Date,Narration,Value Dt,Debit Amt,Credit Amt,Chq/Ref Number,Closing Balance\n"
        "01/04/24,RTGS/ABC,01/04/24,10.00,,R1,90.00\n"
    )
    assert HDFCBankParser().parse_csv(sample)[0].transaction_type == "RTGS"


def test_empty_csv_returns_empty_list() -> None:
    assert HDFCBankParser().parse_csv("") == []


def test_malformed_row_skipped_gracefully() -> None:
    sample = "Date,Narration,Value Dt,Debit Amt,Credit Amt,Chq/Ref Number,Closing Balance\nnot-a-date,data\n"
    assert HDFCBankParser().parse_csv(sample) == []
