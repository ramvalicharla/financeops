from __future__ import annotations

from uuid import UUID

import pytest

from financeops.core.exceptions import ValidationError
from financeops.services.accounting_common.journal_namespace import (
    build_journal_prefix,
    build_journal_reference,
)


def test_journal_namespace_prefixes_are_stable() -> None:
    assert build_journal_prefix("REV") == "REV-"
    assert build_journal_prefix("lease") == "LSE-"
    assert build_journal_prefix("prepaid") == "PPD-"
    assert build_journal_prefix("fixed_assets") == "FAR-"


def test_journal_reference_is_deterministic() -> None:
    run_id = UUID("00000000-0000-0000-0000-00000000a1b2")
    reference = build_journal_reference(engine_namespace="REV", run_id=run_id, sequence=12)

    assert reference == "REV-000000000000-000012"


def test_journal_namespace_rejects_invalid_prefix() -> None:
    with pytest.raises(ValidationError):
        build_journal_prefix("unsupported")
