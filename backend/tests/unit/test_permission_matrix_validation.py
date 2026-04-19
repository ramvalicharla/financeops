from __future__ import annotations

import pytest

from financeops import main
from financeops.platform.services.rbac.permission_matrix import (
    PERMISSIONS,
    validate_permission_matrix,
)


def test_permission_matrix_validates_at_startup() -> None:
    main._validate_permission_matrix_configuration()


def test_duplicate_permission_key_raises_at_startup() -> None:
    entry = PERMISSIONS["budget.approve"]
    with pytest.raises(ValueError, match="Duplicate permission key: budget.approve"):
        validate_permission_matrix(
            [
                ("budget.approve", entry),
                ("budget.approve", entry),
            ]
        )
