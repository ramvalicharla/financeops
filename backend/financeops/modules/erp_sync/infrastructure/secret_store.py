from __future__ import annotations

from typing import Any

from financeops.core.security import decrypt_field


class SecretStore:
    async def get_secret(self, secret_ref: str) -> dict[str, Any]:
        try:
            decrypted = decrypt_field(secret_ref)
        except Exception:
            decrypted = secret_ref
        return {"secret_ref": decrypted}
