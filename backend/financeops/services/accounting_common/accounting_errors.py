from __future__ import annotations

from financeops.core.exceptions import ValidationError


class AccountingValidationError(ValidationError):
    def __init__(self, *, error_code: str, message: str | None = None) -> None:
        super().__init__(message or error_code)
        self.error_code = error_code

