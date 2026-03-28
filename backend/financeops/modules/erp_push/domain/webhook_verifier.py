from __future__ import annotations

import base64
import hashlib
import hmac


def verify_zoho_webhook_signature(
    *,
    raw_body: bytes,
    received_token: str,
    webhook_secret: str,
) -> bool:
    if not received_token or not webhook_secret:
        return False
    expected = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected.lower(), received_token.lower())


def verify_qbo_webhook_signature(
    *,
    raw_body: bytes,
    received_hash: str,
    verifier_token: str,
) -> bool:
    if not received_hash or not verifier_token:
        return False
    expected_bytes = hmac.new(
        verifier_token.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).digest()
    expected_hash = base64.b64encode(expected_bytes).decode("utf-8")
    return hmac.compare_digest(expected_hash, received_hash)


def verify_tally_webhook(*, raw_body: bytes, headers: dict[str, str]) -> bool:
    _ = (raw_body, headers)
    return True
