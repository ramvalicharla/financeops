from __future__ import annotations

from financeops.core.exceptions import ValidationError


class OrgSetupError(ValidationError):
    """Base validation error for org setup workflows."""


class CircularOwnershipError(OrgSetupError):
    """Raised when an ownership edge would create a cycle."""

    def __init__(self, message: str = "Ownership relationship would create a circular ownership chain") -> None:
        super().__init__(message)


__all__ = ["OrgSetupError", "CircularOwnershipError"]
