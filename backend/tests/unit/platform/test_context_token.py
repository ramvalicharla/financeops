from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from financeops.core.exceptions import AuthenticationError
from financeops.platform.services.enforcement.context_token import (
    issue_context_token,
    verify_context_token,
)


def _claims(*, expires_in_seconds: int) -> dict[str, str | int]:
    now = datetime.now(UTC)
    return {
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "module_code": "revenue",
        "decision": "allow",
        "policy_snapshot_version": 1,
        "quota_check_id": "q-1",
        "isolation_route_version": 1,
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=expires_in_seconds)).isoformat(),
        "correlation_id": "corr-1",
    }


def test_context_token_roundtrip() -> None:
    token = issue_context_token(_claims(expires_in_seconds=120))
    payload = verify_context_token(token)
    assert payload["module_code"] == "revenue"
    assert payload["decision"] == "allow"


def test_context_token_rejects_tampering() -> None:
    token = issue_context_token(_claims(expires_in_seconds=120))
    payload, signature = token.split(".", 1)
    tampered = f"{payload}.{signature[:-1]}x"
    with pytest.raises(AuthenticationError):
        verify_context_token(tampered)


def test_context_token_rejects_expired() -> None:
    token = issue_context_token(_claims(expires_in_seconds=-1))
    with pytest.raises(AuthenticationError):
        verify_context_token(token)
