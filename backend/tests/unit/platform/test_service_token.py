from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from financeops.core.exceptions import AuthenticationError
from financeops.platform.services.enforcement.service_token import (
    issue_service_token,
    verify_service_token,
)


def _claims(*, expires_in_seconds: int = 120) -> dict[str, str]:
    issued_at = datetime.now(UTC)
    return {
        "service_id": "worker.financeops",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "module_code": "revenue",
        "scope": "finance.execute",
        "nonce": "svc-123",
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(seconds=expires_in_seconds)).isoformat(),
    }


def test_issue_and_verify_service_token_round_trip() -> None:
    token = issue_service_token(_claims())
    payload = verify_service_token(token)
    assert payload["auth_mode"] == "service"
    assert payload["service_id"] == "worker.financeops"
    assert payload["scope"] == "finance.execute"


def test_verify_service_token_rejects_tampering() -> None:
    token = issue_service_token(_claims())
    payload_segment, signature = token.split(".", 1)
    tampered = f"{payload_segment}.{'A' * len(signature)}"
    with pytest.raises(AuthenticationError):
        verify_service_token(tampered)


def test_verify_service_token_rejects_expired_token() -> None:
    token = issue_service_token(_claims(expires_in_seconds=-1))
    with pytest.raises(AuthenticationError):
        verify_service_token(token)
