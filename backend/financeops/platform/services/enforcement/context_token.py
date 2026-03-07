from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from financeops.config import settings
from financeops.core.exceptions import AuthenticationError


@dataclass(frozen=True)
class ContextTokenPayload:
    tenant_id: str
    module_code: str
    decision: str
    policy_snapshot_version: int
    quota_check_id: str
    isolation_route_version: int
    issued_at: str
    expires_at: str
    correlation_id: str


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("utf-8"))


def _sign(payload_segment: str) -> str:
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload_segment.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def issue_context_token(claims: dict[str, Any]) -> str:
    payload_json = json.dumps(claims, separators=(",", ":"), sort_keys=True)
    payload_segment = _b64url_encode(payload_json.encode("utf-8"))
    signature = _sign(payload_segment)
    return f"{payload_segment}.{signature}"


def verify_context_token(token: str) -> dict[str, Any]:
    try:
        payload_segment, signature = token.split(".", 1)
    except ValueError as exc:
        raise AuthenticationError("Invalid control-plane token format") from exc

    expected = _sign(payload_segment)
    if not hmac.compare_digest(signature, expected):
        raise AuthenticationError("Invalid control-plane token signature")

    payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    expires_at = datetime.fromisoformat(str(payload["expires_at"]))
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise AuthenticationError("Control-plane token expired")
    return payload
