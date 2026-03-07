from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from financeops.core.exceptions import ValidationError
from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import LINEAGE_INCOMPLETE


@dataclass(frozen=True)
class LineageValidationResult:
    is_complete: bool
    error_code: str = LINEAGE_INCOMPLETE
    details: dict[str, Any] | None = None

    def as_metadata(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "lineage_is_complete": self.is_complete,
            "details": self.details or {},
        }


def ensure_model_columns(model_class: type[Any], required_columns: tuple[str, ...]) -> None:
    missing = [column for column in required_columns if not hasattr(model_class, column)]
    if missing:
        raise ValidationError(
            f"Model {model_class.__name__} missing required columns: {', '.join(missing)}"
        )


def ensure_lineage_complete(result: LineageValidationResult) -> None:
    if result.is_complete:
        return
    raise AccountingValidationError(error_code=result.error_code)
