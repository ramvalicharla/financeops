from __future__ import annotations

import base64
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from financeops.modules.erp_sync.domain.enums import ConnectorType, DatasetType
from financeops.modules.erp_sync.infrastructure.connectors.base import (
    AbstractConnector,
    ConnectorCapabilityNotSupported,
    ExtractionError,
)
from financeops.modules.erp_sync.infrastructure.secret_store import SecretStore


class ConsentExpiredError(ExtractionError):
    error_code = "consent_expired"


def _to_decimal_if_numeric(value: Any) -> Any:
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if cleaned and all(ch.isdigit() or ch in {"-", "."} for ch in cleaned):
            try:
                return Decimal(cleaned)
            except (InvalidOperation, ValueError):
                return value
    return value


def _normalize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_payload(item) for item in value]
    return _to_decimal_if_numeric(value)


class AaFrameworkConnector(AbstractConnector):
    connector_type = ConnectorType.AA_FRAMEWORK
    connector_version = "4e.1.0"
    supports_resumable_extraction = False
    supported_datasets = {
        DatasetType.BANK_STATEMENT,
        DatasetType.BANK_TRANSACTION_REGISTER,
    }

    def __init__(self, *, secret_store: SecretStore | None = None) -> None:
        self._secret_store = secret_store or SecretStore()

    async def test_connection(self, credentials: dict[str, Any]) -> dict[str, Any]:
        resolved = await self._resolve_credentials(credentials=credentials)
        self._validate_consent_expiry(resolved)
        payload = await self._fetch_fi_payload(resolved, dataset_hint="connection_check")
        return {
            "ok": True,
            "connector_type": self.connector_type.value,
            "aa_handle": resolved["aa_handle"],
            "fip_id": resolved["fip_id"],
            "payload": payload,
        }

    async def extract(self, dataset_type: DatasetType, **kwargs: Any) -> dict[str, Any]:
        if dataset_type not in self.supported_datasets:
            raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)
        if not kwargs:
            raise ConnectorCapabilityNotSupported(self.connector_type, dataset_type)
        resolved = await self._resolve_credentials(
            credentials=kwargs.get("credentials"),
            secret_ref=kwargs.get("secret_ref"),
            extra=kwargs,
        )
        self._validate_consent_expiry(resolved)
        encrypted_payload = await self._fetch_fi_payload(resolved, dataset_hint=dataset_type.value)
        decrypted_payload = self._decrypt_fi_payload(encrypted_payload)
        normalized = _normalize_payload(decrypted_payload)
        records = self._extract_records(normalized)
        return {
            "dataset_type": dataset_type.value,
            "raw_data": normalized,
            "records": records,
            "line_count": len(records),
            "erp_reported_line_count": len(records),
            "is_resumable": False,
            "next_checkpoint": None,
            "consent_log": {
                "consent_reference": str(resolved["consent_artefact"]),
                "consent_action": "validated",
                "consent_payload_json": {
                    "aa_handle": resolved["aa_handle"],
                    "fip_id": resolved["fip_id"],
                    "dataset_type": dataset_type.value,
                },
            },
        }

    async def _resolve_credentials(
        self,
        *,
        credentials: dict[str, Any] | None = None,
        secret_ref: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved = dict(credentials or {})
        if not resolved and secret_ref:
            secret_payload = await self._secret_store.get_secret(secret_ref)
            if isinstance(secret_payload, dict):
                resolved.update(secret_payload)
        if extra:
            for key in (
                "aa_handle",
                "client_id",
                "client_secret",
                "fip_id",
                "consent_artefact",
                "consent_expires_at",
                "aa_base_url",
            ):
                if key in extra and extra[key] is not None:
                    resolved[key] = extra[key]
        resolved.setdefault("aa_base_url", "https://api.accountaggregator.example/fiu")
        for key in ("aa_handle", "client_id", "client_secret", "fip_id", "consent_artefact"):
            if not resolved.get(key):
                raise ExtractionError(f"AA Framework credential {key} is required")
        return resolved

    def _validate_consent_expiry(self, credentials: dict[str, Any]) -> None:
        raw_expiry = credentials.get("consent_expires_at")
        if not raw_expiry:
            return
        expiry_str = str(raw_expiry).replace("Z", "+00:00")
        try:
            expiry = datetime.fromisoformat(expiry_str)
        except ValueError as exc:
            raise ExtractionError("Invalid consent_expires_at format") from exc
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= datetime.now(timezone.utc):
            raise ConsentExpiredError("Consent artefact has expired; re-consent required")

    async def _fetch_fi_payload(self, credentials: dict[str, Any], *, dataset_hint: str) -> dict[str, Any]:
        url = f"{str(credentials['aa_base_url']).rstrip('/')}/fi/fetch"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        auth = (str(credentials["client_id"]), str(credentials["client_secret"]))
        body = {
            "aa_handle": credentials["aa_handle"],
            "fip_id": credentials["fip_id"],
            "consent_artefact": credentials["consent_artefact"],
            "dataset_hint": dataset_hint,
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, headers=headers, auth=auth, json=body)
        if response.status_code >= 400:
            raise ExtractionError(f"AA Framework fetch failed ({response.status_code})")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ExtractionError("AA Framework returned non-object payload")
        return payload

    def _decrypt_fi_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        encrypted_data = payload.get("encrypted_fi_data")
        if not encrypted_data:
            return payload
        if not isinstance(encrypted_data, str):
            raise ExtractionError("AA Framework encrypted_fi_data should be a base64 string")
        try:
            decoded = base64.b64decode(encrypted_data).decode("utf-8")
        except Exception as exc:  # pragma: no cover - defensive for malformed payloads.
            raise ExtractionError("Unable to decode encrypted FI data") from exc
        try:
            import json

            parsed = json.loads(decoded)
        except Exception as exc:  # pragma: no cover - defensive for malformed payloads.
            raise ExtractionError("Unable to parse decrypted FI data JSON") from exc
        if isinstance(parsed, dict):
            return parsed
        raise ExtractionError("AA Framework decrypted data was not a JSON object")

    @staticmethod
    def _extract_records(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        for key in ("transactions", "bank_transactions", "entries", "items", "records", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
            if isinstance(value, dict):
                nested = value.get("items") or value.get("records")
                if isinstance(nested, list):
                    return [row for row in nested if isinstance(row, dict)]
        return []
