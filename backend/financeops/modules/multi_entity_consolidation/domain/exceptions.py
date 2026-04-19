from __future__ import annotations

import uuid


class ConsolidationError(Exception):
    """Base exception for multi-entity consolidation failures."""


class ConsolidationRunNotFoundError(ConsolidationError):
    def __init__(self, run_id: uuid.UUID) -> None:
        self.run_id = run_id
        super().__init__(f"Consolidation run not found: {run_id}")


class InvalidSourceRunError(ConsolidationError):
    def __init__(self, run_ref: str) -> None:
        self.run_ref = run_ref
        super().__init__(f"Source run not found or incomplete: {run_ref}")


class InvalidConsolidationInputError(ConsolidationError):
    """Raised when consolidation inputs fail validation."""


class MissingSourceEntityError(ConsolidationError):
    def __init__(self, missing_ids: list[uuid.UUID | str]) -> None:
        self.missing_ids = [str(value) for value in missing_ids]
        super().__init__(f"Missing source entities: {self.missing_ids}")


class MissingSourceBalanceError(ConsolidationError):
    def __init__(self, row_id: str) -> None:
        self.row_id = row_id
        super().__init__(f"Missing source balance for metric row {row_id}")
