from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.normalization_phase1f3_helpers import (
    build_normalization_service,
    csv_b64,
    ensure_tenant_context,
    seed_control_plane_for_normalization,
    seed_identity_user,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_detect_endpoint_requires_context_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/normalization/sources/detect",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "",
        },
        json={
            "source_code": "payroll_api_detect",
            "file_name": "payroll.csv",
            "file_content_base64": csv_b64(
                "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,1000,USD\n"
            ),
            "source_family_hint": "payroll",
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
    await seed_control_plane_for_normalization(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=False,
        grant_permissions=True,
    )
    response = await async_client.post(
        "/api/v1/normalization/sources/detect",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "source_code": "payroll_api_detect_mod_disabled",
            "file_name": "payroll.csv",
            "file_content_base64": csv_b64(
                "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,1000,USD\n"
            ),
            "source_family_hint": "payroll",
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
    await seed_control_plane_for_normalization(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=False,
    )
    response = await async_client.post(
        "/api/v1/normalization/runs/upload",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "source_id": str(uuid.uuid4()),
            "source_version_id": str(uuid.uuid4()),
            "run_type": "payroll_normalization",
            "reporting_period": "2026-01-31",
            "source_artifact_id": str(uuid.uuid4()),
            "file_name": "payroll.csv",
            "file_content_base64": csv_b64(
                "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,1000,USD\n"
            ),
            "sheet_name": "csv",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_finalize_endpoint_denies_wrong_tenant_access(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    tenant_b = uuid.uuid4()
    user_b = uuid.uuid4()
    await seed_identity_user(
        async_session,
        tenant_id=tenant_b,
        user_id=user_b,
        email="norm_b@example.com",
    )
    await seed_control_plane_for_normalization(
        async_session,
        tenant_id=tenant_b,
        user_id=user_b,
        enable_module=True,
        grant_permissions=True,
    )
    await ensure_tenant_context(async_session, tenant_b)
    service_b = build_normalization_service(async_session)
    committed = await service_b.commit_source_version(
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        source_family="payroll",
        source_code=f"tenant_b_{uuid.uuid4().hex[:8]}",
        source_name="Tenant B Source",
        structure_hash="a" * 64,
        header_hash="b" * 64,
        row_signature_hash="c" * 64,
        source_detection_summary_json={
            "headers": ["Employee ID", "Employee Name", "Gross Pay", "Currency"]
        },
        activate=True,
        created_by=user_b,
    )
    uploaded = await service_b.upload_run(
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        source_id=uuid.UUID(committed["source_id"]),
        source_version_id=uuid.UUID(committed["source_version_id"]),
        run_type="payroll_normalization",
        reporting_period=date(2026, 1, 31),
        source_artifact_id=uuid.uuid4(),
        file_name="payroll.csv",
        file_content_base64=csv_b64(
            "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,1000,USD\n"
        ),
        sheet_name="csv",
        created_by=user_b,
    )
    validated = await service_b.validate_run(
        tenant_id=tenant_b,
        run_id=uuid.UUID(uploaded["run_id"]),
        created_by=user_b,
    )

    await seed_control_plane_for_normalization(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    response = await async_client.post(
        f"/api/v1/normalization/runs/{validated['run_id']}/finalize",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code in (403, 404)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_normalized_lines_endpoint_returns_only_tenant_scoped_data(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    tenant_b = uuid.uuid4()
    user_b = uuid.uuid4()
    await seed_identity_user(
        async_session,
        tenant_id=tenant_b,
        user_id=user_b,
        email="norm_lines_b@example.com",
    )
    await seed_control_plane_for_normalization(
        async_session,
        tenant_id=tenant_b,
        user_id=user_b,
        enable_module=True,
        grant_permissions=True,
    )
    await ensure_tenant_context(async_session, tenant_b)
    service_b = build_normalization_service(async_session)
    committed = await service_b.commit_source_version(
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        source_family="payroll",
        source_code=f"tenant_b_lines_{uuid.uuid4().hex[:8]}",
        source_name="Tenant B Lines Source",
        structure_hash="d" * 64,
        header_hash="e" * 64,
        row_signature_hash="f" * 64,
        source_detection_summary_json={
            "headers": ["Employee ID", "Employee Name", "Gross Pay", "Currency"]
        },
        activate=True,
        created_by=user_b,
    )
    uploaded = await service_b.upload_run(
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        source_id=uuid.UUID(committed["source_id"]),
        source_version_id=uuid.UUID(committed["source_version_id"]),
        run_type="payroll_normalization",
        reporting_period=date(2026, 1, 31),
        source_artifact_id=uuid.uuid4(),
        file_name="payroll.csv",
        file_content_base64=csv_b64(
            "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,1000,USD\n"
        ),
        sheet_name="csv",
        created_by=user_b,
    )
    await seed_control_plane_for_normalization(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    response = await async_client.get(
        f"/api/v1/normalization/runs/{uploaded['run_id']}/payroll-lines",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert response.json()["data"] == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_normalization_upload_allow_path(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_normalization(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    commit = await async_client.post(
        "/api/v1/normalization/sources/commit-version",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "source_family": "payroll",
            "source_code": f"allow_{uuid.uuid4().hex[:8]}",
            "source_name": "Allow Source",
            "structure_hash": "a" * 64,
            "header_hash": "b" * 64,
            "row_signature_hash": "c" * 64,
            "source_detection_summary_json": {
                "headers": ["Employee ID", "Employee Name", "Gross Pay", "Currency"]
            },
            "activate": True,
        },
    )
    assert commit.status_code == 201
    payload = commit.json()["data"]
    upload = await async_client.post(
        "/api/v1/normalization/runs/upload",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "source_id": payload["source_id"],
            "source_version_id": payload["source_version_id"],
            "run_type": "payroll_normalization",
            "reporting_period": "2026-01-31",
            "source_artifact_id": str(uuid.uuid4()),
            "file_name": "payroll.csv",
            "file_content_base64": csv_b64(
                "Employee ID,Employee Name,Gross Pay,Currency\nE001,Alice,1000,USD\n"
            ),
            "sheet_name": "csv",
        },
    )
    assert upload.status_code == 201
    upload_payload = upload.json()["data"]
    assert upload_payload["payroll_line_count"] >= 1

    validate = await async_client.post(
        f"/api/v1/normalization/runs/{upload_payload['run_id']}/validate",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert validate.status_code == 200
    validate_payload = validate.json()["data"]
    assert validate_payload["run_status"] in ("validated", "failed")

    if validate_payload["run_status"] == "validated":
        finalize = await async_client.post(
            f"/api/v1/normalization/runs/{validate_payload['run_id']}/finalize",
            headers={"Authorization": f"Bearer {test_access_token}"},
        )
        assert finalize.status_code == 200
    assert finalize.json()["data"]["run_status"] == "finalized"

    summary = await async_client.get(
        f"/api/v1/normalization/runs/{upload_payload['run_id']}/summary",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert summary.status_code == 200
    assert summary.json()["data"]["payroll_line_count"] >= 1

