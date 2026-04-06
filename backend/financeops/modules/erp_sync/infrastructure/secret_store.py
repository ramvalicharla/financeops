from __future__ import annotations

import json
import logging
from typing import Any

from financeops.core.security import decrypt_field, encrypt_field

logger = logging.getLogger(__name__)

CANONICAL_CREDENTIAL_KEYS: tuple[str, ...] = (
    "client_id",
    "client_secret",
    "access_token",
    "refresh_token",
    "token_expires_at",
    "realm_id",
    "organization_id",
    "use_sandbox",
    "api_key",
)


def _empty_payload() -> dict[str, Any]:
    return {key: None for key in CANONICAL_CREDENTIAL_KEYS}


class SecretStore:
    async def get_secret(self, secret_ref: str) -> dict[str, Any]:
        text_ref = str(secret_ref or "").strip()
        if not text_ref:
            return _empty_payload()

        try:
            decrypted = decrypt_field(text_ref)
        except Exception:
            logger.warning("secret_ref_decrypt_failed_fallback_plain")
            decrypted = text_ref

        try:
            payload = json.loads(decrypted)
        except (json.JSONDecodeError, TypeError):
            return {**_empty_payload(), "api_key": decrypted}

        if not isinstance(payload, dict):
            return _empty_payload()
        return {**_empty_payload(), **payload}

    async def put_secret(
        self,
        existing_ref: str | None,
        updates: dict[str, Any],
    ) -> str:
        current_payload = (
            await self.get_secret(str(existing_ref))
            if str(existing_ref or "").strip()
            else _empty_payload()
        )
        merged = {**current_payload, **(updates or {})}
        return encrypt_field(json.dumps(merged))


secret_store = SecretStore()
