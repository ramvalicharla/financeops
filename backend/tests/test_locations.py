from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token
from financeops.db.models.users import IamUser
from financeops.platform.db.models.entities import CpEntity
from financeops.utils.gstin import INDIA_STATE_CODES, extract_state_code, validate_gstin, validate_pan, validate_tan

_BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_BASE36_MAP = {char: idx for idx, char in enumerate(_BASE36)}


def _auth_headers(user: IamUser) -> dict[str, str]:
    token = create_access_token(user.id, user.tenant_id, user.role.value)
    return {"Authorization": f"Bearer {token}"}


def _data(response):
    payload = response.json()
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _checksum_char(body: str) -> str:
    total = 0
    for idx, char in enumerate(body):
        value = _BASE36_MAP[char]
        factor = 1 if idx % 2 == 0 else 2
        product = value * factor
        total += (product // 36) + (product % 36)
    return _BASE36[(36 - (total % 36)) % 36]


def _build_gstin(state_code: str, pan: str = "AABCF1234A", entity_code: str = "1") -> str:
    body = f"{state_code}{pan}{entity_code}Z"
    return f"{body}{_checksum_char(body)}"


async def _default_entity_id(async_session: AsyncSession, tenant_id: uuid.UUID) -> str:
    entity_id = (
        await async_session.execute(
            select(CpEntity.id)
            .where(CpEntity.tenant_id == tenant_id)
            .order_by(CpEntity.created_at.asc())
            .limit(1)
        )
    ).scalar_one()
    return str(entity_id)


async def _create_org_entity(async_client, user: IamUser) -> str:
    step1 = await async_client.post(
        "/api/v1/org-setup/step1",
        headers=_auth_headers(user),
        json={
            "group_name": f"Group {uuid.uuid4()}",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
        },
    )
    assert step1.status_code == 200
    group_id = _data(step1)["group"]["id"]

    step2 = await async_client.post(
        "/api/v1/org-setup/step2",
        headers=_auth_headers(user),
        json={
            "group_id": group_id,
            "entities": [
                {
                    "legal_name": f"Entity {uuid.uuid4()}",
                    "display_name": "Entity",
                    "entity_type": "WHOLLY_OWNED_SUBSIDIARY",
                    "country_code": "IN",
                    "functional_currency": "INR",
                    "reporting_currency": "INR",
                    "fiscal_year_start": 4,
                    "applicable_gaap": "INDAS",
                }
            ],
        },
    )
    assert step2.status_code == 200
    return str(_data(step2)["entities"][0]["id"])


@pytest.mark.asyncio
async def test_validate_gstin_valid() -> None:
    assert validate_gstin(_build_gstin("36")) is True


@pytest.mark.asyncio
async def test_validate_gstin_invalid_length() -> None:
    assert validate_gstin("36AABCF1234A1Z") is False


@pytest.mark.asyncio
async def test_validate_gstin_invalid_state_code() -> None:
    assert validate_gstin(_build_gstin("99")) is False


@pytest.mark.asyncio
async def test_extract_state_code_telangana() -> None:
    assert extract_state_code(_build_gstin("36")) == "36"


@pytest.mark.asyncio
async def test_validate_pan_valid() -> None:
    assert validate_pan("AABCF1234A") is True


@pytest.mark.asyncio
async def test_validate_pan_invalid() -> None:
    assert validate_pan("AABCF123") is False


@pytest.mark.asyncio
async def test_validate_tan_valid() -> None:
    assert validate_tan("ABCD12345E") is True


@pytest.mark.asyncio
async def test_all_36_state_codes_present() -> None:
    assert len(INDIA_STATE_CODES) >= 36


@pytest.mark.asyncio
async def test_create_location(async_client, async_session: AsyncSession, test_user: IamUser) -> None:
    entity_id = await _default_entity_id(async_session, test_user.tenant_id)
    response = await async_client.post(
        "/api/v1/locations",
        headers=_auth_headers(test_user),
        json={
            "entity_id": entity_id,
            "location_name": "Hyderabad HQ",
            "location_code": "HYD-HQ",
            "city": "Hyderabad",
            "state": "Telangana",
        },
    )
    assert response.status_code == 200
    assert _data(response)["location_code"] == "HYD-HQ"


@pytest.mark.asyncio
async def test_create_location_extracts_state_code(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_id = await _default_entity_id(async_session, test_user.tenant_id)
    gstin = _build_gstin("36")
    response = await async_client.post(
        "/api/v1/locations",
        headers=_auth_headers(test_user),
        json={
            "entity_id": entity_id,
            "location_name": "Telangana Branch",
            "location_code": "TS-01",
            "gstin": gstin,
        },
    )
    assert response.status_code == 200
    assert _data(response)["state_code"] == "36"


@pytest.mark.asyncio
async def test_create_location_validates_gstin(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_id = await _default_entity_id(async_session, test_user.tenant_id)
    response = await async_client.post(
        "/api/v1/locations",
        headers=_auth_headers(test_user),
        json={
            "entity_id": entity_id,
            "location_name": "Invalid GST",
            "location_code": "GST-ERR",
            "gstin": "36AABCF1234A1Z0",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_location_code_unique_per_entity(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_id = await _default_entity_id(async_session, test_user.tenant_id)
    payload = {
        "entity_id": entity_id,
        "location_name": "Mumbai Office",
        "location_code": "MUM-01",
    }
    first = await async_client.post("/api/v1/locations", headers=_auth_headers(test_user), json=payload)
    assert first.status_code == 200
    second = await async_client.post("/api/v1/locations", headers=_auth_headers(test_user), json=payload)
    assert second.status_code == 422


@pytest.mark.asyncio
async def test_set_primary_unsets_others(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_id = await _default_entity_id(async_session, test_user.tenant_id)
    a = await async_client.post(
        "/api/v1/locations",
        headers=_auth_headers(test_user),
        json={
            "entity_id": entity_id,
            "location_name": "Location A",
            "location_code": "LOC-A",
            "is_primary": True,
        },
    )
    assert a.status_code == 200
    b = await async_client.post(
        "/api/v1/locations",
        headers=_auth_headers(test_user),
        json={
            "entity_id": entity_id,
            "location_name": "Location B",
            "location_code": "LOC-B",
        },
    )
    assert b.status_code == 200

    set_primary = await async_client.post(
        f"/api/v1/locations/{_data(b)['id']}/set-primary",
        headers=_auth_headers(test_user),
    )
    assert set_primary.status_code == 200
    assert _data(set_primary)["is_primary"] is True

    fetch_a = await async_client.get(
        f"/api/v1/locations/{_data(a)['id']}",
        headers=_auth_headers(test_user),
    )
    assert fetch_a.status_code == 200
    assert _data(fetch_a)["is_primary"] is False


@pytest.mark.asyncio
async def test_get_locations_paginated(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_id = await _default_entity_id(async_session, test_user.tenant_id)
    for index in range(3):
        created = await async_client.post(
            "/api/v1/locations",
            headers=_auth_headers(test_user),
            json={
                "entity_id": entity_id,
                "location_name": f"Location {index}",
                "location_code": f"LOC-PG-{uuid.uuid4().hex[:8]}",
            },
        )
        assert created.status_code == 200

    listed = await async_client.get(
        f"/api/v1/locations?entity_id={entity_id}&skip=0&limit=2",
        headers=_auth_headers(test_user),
    )
    assert listed.status_code == 200
    payload = _data(listed)
    assert len(payload["items"]) == 2
    assert payload["has_more"] is True


@pytest.mark.asyncio
async def test_create_cost_centre(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_id = await _default_entity_id(async_session, test_user.tenant_id)
    response = await async_client.post(
        "/api/v1/locations/cost-centres",
        headers=_auth_headers(test_user),
        json={
            "entity_id": entity_id,
            "cost_centre_code": "FIN-01",
            "cost_centre_name": "Finance",
        },
    )
    assert response.status_code == 200
    assert _data(response)["cost_centre_code"] == "FIN-01"


@pytest.mark.asyncio
async def test_cost_centre_tree_structure(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_id = await _default_entity_id(async_session, test_user.tenant_id)
    parent = await async_client.post(
        "/api/v1/locations/cost-centres",
        headers=_auth_headers(test_user),
        json={
            "entity_id": entity_id,
            "cost_centre_code": "CC-PARENT",
            "cost_centre_name": "Parent",
        },
    )
    assert parent.status_code == 200
    child = await async_client.post(
        "/api/v1/locations/cost-centres",
        headers=_auth_headers(test_user),
        json={
            "entity_id": entity_id,
            "parent_id": _data(parent)["id"],
            "cost_centre_code": "CC-CHILD",
            "cost_centre_name": "Child",
        },
    )
    assert child.status_code == 200
    grandchild = await async_client.post(
        "/api/v1/locations/cost-centres",
        headers=_auth_headers(test_user),
        json={
            "entity_id": entity_id,
            "parent_id": _data(child)["id"],
            "cost_centre_code": "CC-GRAND",
            "cost_centre_name": "Grandchild",
        },
    )
    assert grandchild.status_code == 200

    tree = await async_client.get(
        f"/api/v1/locations/cost-centres/tree?entity_id={entity_id}",
        headers=_auth_headers(test_user),
    )
    assert tree.status_code == 200
    payload = _data(tree)
    assert len(payload) == 1
    assert payload[0]["cost_centre_code"] == "CC-PARENT"
    assert payload[0]["children"][0]["cost_centre_code"] == "CC-CHILD"
    assert payload[0]["children"][0]["children"][0]["cost_centre_code"] == "CC-GRAND"


@pytest.mark.asyncio
async def test_cost_centre_code_unique_per_entity(
    async_client,
    async_session: AsyncSession,
    test_user: IamUser,
) -> None:
    entity_id = await _default_entity_id(async_session, test_user.tenant_id)
    payload = {
        "entity_id": entity_id,
        "cost_centre_code": "CC-UNI",
        "cost_centre_name": "Unique",
    }
    first = await async_client.post(
        "/api/v1/locations/cost-centres",
        headers=_auth_headers(test_user),
        json=payload,
    )
    assert first.status_code == 200
    second = await async_client.post(
        "/api/v1/locations/cost-centres",
        headers=_auth_headers(test_user),
        json=payload,
    )
    assert second.status_code == 422


@pytest.mark.asyncio
async def test_update_entity_saves_gstin(async_client, test_user: IamUser) -> None:
    org_entity_id = await _create_org_entity(async_client, test_user)
    gstin = _build_gstin("29")
    response = await async_client.patch(
        f"/api/v1/org-setup/entities/{org_entity_id}",
        headers=_auth_headers(test_user),
        json={"gstin": gstin},
    )
    assert response.status_code == 200
    assert _data(response)["gstin"] == gstin


@pytest.mark.asyncio
async def test_update_entity_auto_extracts_state_code(async_client, test_user: IamUser) -> None:
    org_entity_id = await _create_org_entity(async_client, test_user)
    gstin = _build_gstin("36")
    response = await async_client.patch(
        f"/api/v1/org-setup/entities/{org_entity_id}",
        headers=_auth_headers(test_user),
        json={"gstin": gstin},
    )
    assert response.status_code == 200
    assert _data(response)["state_code"] == "36"


@pytest.mark.asyncio
async def test_update_entity_validates_gstin_format(async_client, test_user: IamUser) -> None:
    org_entity_id = await _create_org_entity(async_client, test_user)
    response = await async_client.patch(
        f"/api/v1/org-setup/entities/{org_entity_id}",
        headers=_auth_headers(test_user),
        json={"gstin": "BAD-GSTIN"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_tenant_saves_pan(async_client, test_user: IamUser) -> None:
    updated = await async_client.patch(
        "/api/v1/tenants/me",
        headers=_auth_headers(test_user),
        json={"pan": "AABCF1234A"},
    )
    assert updated.status_code == 200

    me = await async_client.get("/api/v1/tenants/me", headers=_auth_headers(test_user))
    assert me.status_code == 200
    assert _data(me)["pan"] == "AABCF1234A"
