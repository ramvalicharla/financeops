from __future__ import annotations

import json

import pytest

from financeops.core.security import encrypt_field
from financeops.modules.erp_sync.infrastructure.secret_store import SecretStore


@pytest.mark.asyncio
async def test_secret_store_roundtrip_structured_payload() -> None:
    store = SecretStore()
    payload = {
        "client_id": "cid",
        "client_secret": "csecret",
        "access_token": "access",
        "refresh_token": "refresh",
        "token_expires_at": "2026-03-28T12:00:00+00:00",
        "realm_id": "realm-1",
    }
    secret_ref = encrypt_field(json.dumps(payload))

    resolved = await store.get_secret(secret_ref)

    assert resolved["client_id"] == "cid"
    assert resolved["client_secret"] == "csecret"
    assert resolved["access_token"] == "access"
    assert resolved["refresh_token"] == "refresh"
    assert resolved["token_expires_at"] == "2026-03-28T12:00:00+00:00"
    assert resolved["realm_id"] == "realm-1"


@pytest.mark.asyncio
async def test_secret_store_legacy_plain_secret_ref_maps_api_key() -> None:
    store = SecretStore()
    secret_ref = encrypt_field("legacy-api-key")

    resolved = await store.get_secret(secret_ref)

    assert resolved["api_key"] == "legacy-api-key"
    assert resolved["client_id"] is None


@pytest.mark.asyncio
async def test_secret_store_put_secret_merges_updates() -> None:
    store = SecretStore()

    first_ref = await store.put_secret(
        None,
        {"client_id": "cid", "client_secret": "csecret"},
    )
    second_ref = await store.put_secret(
        first_ref,
        {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
        },
    )

    resolved = await store.get_secret(second_ref)

    assert resolved["client_id"] == "cid"
    assert resolved["client_secret"] == "csecret"
    assert resolved["access_token"] == "new-access"
    assert resolved["refresh_token"] == "new-refresh"
