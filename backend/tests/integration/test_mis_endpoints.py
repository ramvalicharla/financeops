from __future__ import annotations

import base64
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.services.isolation.routing_service import (
    create_isolation_route,
)
from financeops.platform.services.quotas.policy_service import assign_quota_to_tenant
from financeops.platform.services.rbac.permission_service import (
    create_permission,
    grant_role_permission,
)
from financeops.platform.services.rbac.role_service import assign_user_role, create_role
from financeops.platform.services.tenancy.module_enablement import set_module_enablement
from financeops.services.audit_writer import AuditEvent, AuditWriter
from tests.integration.entitlement_helpers import grant_boolean_entitlement


async def _seed_control_plane_for_mis(
    api_db_session: AsyncSession, *, tenant_id, user_id
) -> None:
    await AuditWriter.insert_financial_record(
        api_db_session,
        model_class=CpTenant,
        tenant_id=tenant_id,
        record_data={"tenant_code": f"TEN-{str(tenant_id)[:8]}", "status": "active"},
        values={
            "id": tenant_id,
            "tenant_code": f"TEN-{str(tenant_id)[:8]}",
            "display_name": "Test Tenant",
            "country_code": "US",
            "region": "us-east-1",
            "billing_tier": "pro",
            "status": "active",
            "correlation_id": "mis-test",
            "deactivated_at": None,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action="platform.test.seed",
            resource_type="cp_tenant",
            resource_id=str(tenant_id),
        ),
    )

    module = (
        await api_db_session.execute(
            select(CpModuleRegistry).where(CpModuleRegistry.module_code == "mis_manager")
        )
    ).scalar_one_or_none()
    if module is None:
        module = CpModuleRegistry(
            module_code="mis_manager",
            module_name="MIS Manager",
            engine_context="finance",
            is_financial_impacting=True,
            is_active=True,
        )
        await AuditWriter.insert_record(
            api_db_session,
            record=module,
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="platform.test.module.seed",
                resource_type="cp_module_registry",
                resource_id=str(module.id),
            ),
        )

    now = datetime.now(UTC)
    await set_module_enablement(
        api_db_session,
        tenant_id=tenant_id,
        module_id=module.id,
        enabled=True,
        enablement_source="test",
        actor_user_id=user_id,
        correlation_id="mis-test",
        effective_from=now,
        effective_to=None,
    )
    await grant_boolean_entitlement(
        api_db_session,
        tenant_id=tenant_id,
        feature_name="mis_manager",
        actor_user_id=user_id,
    )
    await assign_quota_to_tenant(
        api_db_session,
        tenant_id=tenant_id,
        quota_type="api_requests",
        window_type="sliding",
        window_seconds=60,
        max_value=1000,
        enforcement_mode="reject",
        effective_from=now,
        effective_to=None,
        actor_user_id=user_id,
        correlation_id="mis-test",
    )
    await create_isolation_route(
        api_db_session,
        tenant_id=tenant_id,
        isolation_tier="tier1",
        db_cluster="shared-primary",
        schema_name="public",
        worker_pool="shared-workers",
        region="us-east-1",
        migration_state="active",
        route_version=1,
        effective_from=now,
        effective_to=None,
        actor_user_id=user_id,
        correlation_id="mis-test",
    )

    role = await create_role(
        api_db_session,
        tenant_id=tenant_id,
        role_code=f"MIS_ROLE_{str(uuid4())[:8]}",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=user_id,
        correlation_id="mis-test",
    )

    permissions = [
        ("mis_template", "mis_template_create"),
        ("mis_template", "mis_snapshot_view"),
        ("mis_template_version", "mis_template_review"),
        ("mis_snapshot", "mis_snapshot_upload"),
        ("mis_snapshot", "mis_snapshot_finalize"),
        ("mis_snapshot", "mis_snapshot_view"),
        ("mis_ingestion_exception", "mis_snapshot_view"),
        ("mis_drift_event", "mis_template_review"),
        ("mis_normalized_line", "mis_snapshot_view"),
    ]

    for resource_type, action in permissions:
        permission = await create_permission(
            api_db_session,
            actor_tenant_id=tenant_id,
            actor_user_id=user_id,
            permission_code=f"{resource_type}.{action}.{str(uuid4())[:8]}",
            resource_type=resource_type,
            action=action,
            description="mis endpoint test permission",
        )
        await grant_role_permission(
            api_db_session,
            tenant_id=tenant_id,
            role_id=role.id,
            permission_id=permission.id,
            effect="allow",
            actor_user_id=user_id,
            correlation_id="mis-test",
        )

    await assign_user_role(
        api_db_session,
        tenant_id=tenant_id,
        user_id=user_id,
        role_id=role.id,
        context_type="tenant",
        context_id=tenant_id,
        effective_from=now,
        effective_to=None,
        assigned_by=user_id,
        actor_user_id=user_id,
        correlation_id="mis-test",
    )
    await api_db_session.flush()


def _csv_b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


@pytest.mark.asyncio
async def test_detect_commit_and_list_templates(
    async_client: AsyncClient,
    api_db_session: AsyncSession,
    api_test_user,
    api_test_access_token: str,
):
    await _seed_control_plane_for_mis(
        api_db_session,
        tenant_id=api_test_user.tenant_id,
        user_id=api_test_user.id,
    )

    csv_payload = _csv_b64(
        "Metric,Period_2026_01\nRevenue Net,1000\nMarketing Expense,200\n"
    )

    detect = await async_client.post(
        "/api/v1/mis/templates/detect",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json={
            "organisation_id": str(api_test_user.tenant_id),
            "template_code": "pnl_monthly_test",
            "template_name": "Monthly PnL",
            "template_type": "pnl_monthly",
            "file_name": "mis_template.csv",
            "file_content_base64": csv_payload,
        },
    )
    assert detect.status_code == 200
    detection_payload = detect.json()["data"]
    assert detection_payload["signature"]["structure_hash"]

    commit = await async_client.post(
        "/api/v1/mis/templates/commit-version",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json={
            "organisation_id": str(api_test_user.tenant_id),
            "template_code": "pnl_monthly_test",
            "template_name": "Monthly PnL",
            "template_type": "pnl_monthly",
            "structure_hash": detection_payload["signature"]["structure_hash"],
            "header_hash": detection_payload["signature"]["header_hash"],
            "row_signature_hash": detection_payload["signature"]["row_signature_hash"],
            "column_signature_hash": detection_payload["signature"][
                "column_signature_hash"
            ],
            "detection_summary_json": detection_payload["detection_summary_json"],
            "activate": True,
        },
    )
    assert commit.status_code == 201

    list_resp = await async_client.get(
        "/api/v1/mis/templates",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
    )
    assert list_resp.status_code == 200
    rows = list_resp.json()["data"]
    assert any(row["template_code"] == "pnl_monthly_test" for row in rows)


@pytest.mark.asyncio
async def test_snapshot_upload_idempotent_on_duplicate(
    async_client: AsyncClient,
    api_db_session: AsyncSession,
    api_test_user,
    api_test_access_token: str,
):
    await _seed_control_plane_for_mis(
        api_db_session,
        tenant_id=api_test_user.tenant_id,
        user_id=api_test_user.id,
    )

    csv_payload = _csv_b64(
        "Metric,Period_2026_01\nRevenue Net,1000\nMarketing Expense,200\n"
    )

    detect = await async_client.post(
        "/api/v1/mis/templates/detect",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json={
            "organisation_id": str(api_test_user.tenant_id),
            "template_code": "snapshot_template",
            "template_name": "Snapshot Template",
            "template_type": "pnl_monthly",
            "file_name": "template.csv",
            "file_content_base64": csv_payload,
        },
    )
    detection_payload = detect.json()["data"]
    commit = await async_client.post(
        "/api/v1/mis/templates/commit-version",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json={
            "organisation_id": str(api_test_user.tenant_id),
            "template_code": "snapshot_template",
            "template_name": "Snapshot Template",
            "template_type": "pnl_monthly",
            "structure_hash": detection_payload["signature"]["structure_hash"],
            "header_hash": detection_payload["signature"]["header_hash"],
            "row_signature_hash": detection_payload["signature"]["row_signature_hash"],
            "column_signature_hash": detection_payload["signature"][
                "column_signature_hash"
            ],
            "detection_summary_json": detection_payload["detection_summary_json"],
            "activate": True,
        },
    )
    commit_payload = commit.json()["data"]
    upload_body = {
        "organisation_id": str(api_test_user.tenant_id),
        "template_id": commit_payload["template_id"],
        "template_version_id": commit_payload["template_version_id"],
        "reporting_period": "2026-01-31",
        "upload_artifact_id": str(uuid4()),
        "file_name": "snapshot.csv",
        "file_content_base64": csv_payload,
        "currency_code": "USD",
    }

    first = await async_client.post(
        "/api/v1/mis/snapshots/upload",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json=upload_body,
    )
    assert first.status_code == 201
    first_payload = first.json()["data"]
    assert first_payload["idempotent"] is False

    second = await async_client.post(
        "/api/v1/mis/snapshots/upload",
        headers={"Authorization": f"Bearer {api_test_access_token}"},
        json=upload_body,
    )
    assert second.status_code == 201
    second_payload = second.json()["data"]
    assert second_payload["idempotent"] is True
    assert second_payload["snapshot_id"] == first_payload["snapshot_id"]
    assert second_payload["snapshot_token"] == first_payload["snapshot_token"]


