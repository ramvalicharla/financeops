from __future__ import annotations


class BankReconError(Exception):
    pass


class InsufficientDataError(BankReconError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class StatementAlreadyProcessedError(BankReconError):
    def __init__(self, statement_id) -> None:
        super().__init__(f"Already processed: {statement_id}")
