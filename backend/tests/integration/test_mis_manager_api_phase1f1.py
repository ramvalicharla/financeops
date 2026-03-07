from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.mis_phase1f1_helpers import (
    build_ingest_service,
    csv_b64,
    ensure_tenant_context,
    hash64,
    seed_control_plane_for_mis,
    seed_identity_user,
)


async def _seed_snapshot_direct(
    *,
    async_session: AsyncSession,
    tenant_id: uuid.UUID,
    code_seed: str,
    validated: bool,
) -> dict:
    await ensure_tenant_context(async_session, tenant_id)
    service = build_ingest_service(async_session)
    payload = csv_b64("Metric,Period_2026_01\nRevenue Net,1000\nMarketing Expense,200\n")
    committed = await service.commit_template_version(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        template_code=f"mis_api_{code_seed}",
        template_name="API Template",
        template_type="pnl_monthly",
        created_by=tenant_id,
        structure_hash=hash64(f"{code_seed}:structure"),
        header_hash=hash64(f"{code_seed}:header"),
        row_signature_hash=hash64(f"{code_seed}:row"),
        column_signature_hash=hash64(f"{code_seed}:col"),
        detection_summary_json={"seed": code_seed},
        drift_reason=None,
        activate=True,
        effective_from=None,
    )
    uploaded = await service.upload_snapshot(
        tenant_id=tenant_id,
        organisation_id=tenant_id,
        template_id=uuid.UUID(committed["template_id"]),
        template_version_id=uuid.UUID(committed["template_version_id"]),
        reporting_period=date(2026, 1, 31),
        upload_artifact_id=uuid.uuid4(),
        file_name="snapshot.csv",
        file_content_base64=payload,
        sheet_name="csv",
        currency_code="USD",
        created_by=tenant_id,
    )
    if not validated:
        return {"snapshot_id": uploaded["snapshot_id"]}
    validated_row = await service.validate_snapshot(
        tenant_id=tenant_id,
        snapshot_id=uuid.UUID(uploaded["snapshot_id"]),
        created_by=tenant_id,
    )
    return {"snapshot_id": validated_row["snapshot_id"]}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_detect_endpoint_requires_context_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/mis/templates/detect",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "",
        },
        json={
            "organisation_id": str(uuid.uuid4()),
            "template_code": "context_required",
            "template_name": "Context Required",
            "template_type": "pnl_monthly",
            "file_name": "template.csv",
            "file_content_base64": csv_b64("Metric,Period_2026_01\nRevenue Net,1000\n"),
            "sheet_name": "csv",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_detect_endpoint_rejects_invalid_context_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/mis/templates/detect",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "invalid.token",
        },
        json={
            "organisation_id": str(uuid.uuid4()),
            "template_code": "invalid_context",
            "template_name": "Invalid Context",
            "template_type": "pnl_monthly",
            "file_name": "template.csv",
            "file_content_base64": csv_b64("Metric,Period_2026_01\nRevenue Net,1000\n"),
            "sheet_name": "csv",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.integration
async def test_detect_endpoint_requires_module_enablement(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_mis(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=False,
        grant_permissions=True,
    )
    response = await async_client.post(
        "/api/v1/mis/templates/detect",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "template_code": "module_disabled",
            "template_name": "Module Disabled",
            "template_type": "pnl_monthly",
            "file_name": "template.csv",
            "file_content_base64": csv_b64("Metric,Period_2026_01\nRevenue Net,1000\n"),
            "sheet_name": "csv",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_upload_endpoint_requires_rbac_permission(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_mis(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=False,
    )
    response = await async_client.post(
        "/api/v1/mis/snapshots/upload",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "template_id": str(uuid.uuid4()),
            "template_version_id": str(uuid.uuid4()),
            "reporting_period": "2026-01-31",
            "upload_artifact_id": str(uuid.uuid4()),
            "file_name": "snapshot.csv",
            "file_content_base64": csv_b64("Metric,Period_2026_01\nRevenue Net,1000\n"),
            "sheet_name": "csv",
            "currency_code": "USD",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_detect_endpoint_denies_when_quota_exceeded(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_mis(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
        quota_max=0,
    )
    response = await async_client.post(
        "/api/v1/mis/templates/detect",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "template_code": "quota_denied",
            "template_name": "Quota Denied",
            "template_type": "pnl_monthly",
            "file_name": "template.csv",
            "file_content_base64": csv_b64("Metric,Period_2026_01\nRevenue Net,1000\n"),
            "sheet_name": "csv",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_detect_endpoint_denies_when_routing_resolution_fails(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_mis(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
        with_route=False,
    )
    response = await async_client.post(
        "/api/v1/mis/templates/detect",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "template_code": "route_denied",
            "template_name": "Route Denied",
            "template_type": "pnl_monthly",
            "file_name": "template.csv",
            "file_content_base64": csv_b64("Metric,Period_2026_01\nRevenue Net,1000\n"),
            "sheet_name": "csv",
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_finalize_endpoint_denies_wrong_tenant_access(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    tenant_b_id = uuid.uuid4()
    tenant_b_user_id = uuid.uuid4()
    tenant_b_user = await seed_identity_user(
        async_session,
        tenant_id=tenant_b_id,
        user_id=tenant_b_user_id,
        email="tenantb@example.com",
    )
    await seed_control_plane_for_mis(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    await seed_control_plane_for_mis(
        async_session,
        tenant_id=tenant_b_user.tenant_id,
        user_id=tenant_b_user.id,
        enable_module=True,
        grant_permissions=True,
    )

    tenant_b_data = await _seed_snapshot_direct(
        async_session=async_session,
        tenant_id=tenant_b_user.tenant_id,
        code_seed="tenant_b",
        validated=True,
    )
    response = await async_client.post(
        f"/api/v1/mis/snapshots/{tenant_b_data['snapshot_id']}/finalize",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_normalized_lines_endpoint_returns_only_tenant_scoped_data(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    tenant_b_id = uuid.uuid4()
    tenant_b_user_id = uuid.uuid4()
    tenant_b_user = await seed_identity_user(
        async_session,
        tenant_id=tenant_b_id,
        user_id=tenant_b_user_id,
        email="tenantb_scope@example.com",
    )
    await seed_control_plane_for_mis(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    await seed_control_plane_for_mis(
        async_session,
        tenant_id=tenant_b_user.tenant_id,
        user_id=tenant_b_user.id,
        enable_module=True,
        grant_permissions=True,
    )

    tenant_b_data = await _seed_snapshot_direct(
        async_session=async_session,
        tenant_id=tenant_b_user.tenant_id,
        code_seed="tenant_b",
        validated=False,
    )

    other = await async_client.get(
        f"/api/v1/mis/snapshots/{tenant_b_data['snapshot_id']}/normalized-lines",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert other.status_code == 200
    assert other.json() == []
