from __future__ import annotations

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.db.models.board_pack_narrative_engine import (
    BoardPackDefinition,
    BoardPackInclusionRule,
    BoardPackSectionDefinition,
    NarrativeTemplate,
)
from financeops.db.rls import set_tenant_context
from tests.integration.board_pack_phase1f7_helpers import (
    build_board_pack_service,
    ensure_tenant_context,
    seed_active_board_pack_configuration,
    seed_control_plane_for_board_pack,
    seed_identity_user,
    seed_upstream_for_board_pack,
)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_endpoint_requires_context_token(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.post(
        "/api/v1/board-pack/runs",
        headers={
            "Authorization": f"Bearer {test_access_token}",
            "X-Control-Plane-Token": "",
        },
        json={
            "organisation_id": str(uuid.uuid4()),
            "reporting_period": "2026-01-31",
            "source_metric_run_ids": [str(uuid.uuid4())],
            "source_risk_run_ids": [str(uuid.uuid4())],
            "source_anomaly_run_ids": [str(uuid.uuid4())],
        },
    )
    assert response.status_code in {400, 403}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_endpoint_requires_module_enablement(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_board_pack(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=False,
        grant_permissions=True,
    )
    response = await async_client.post(
        "/api/v1/board-pack/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "reporting_period": "2026-01-31",
            "source_metric_run_ids": [str(uuid.uuid4())],
            "source_risk_run_ids": [str(uuid.uuid4())],
            "source_anomaly_run_ids": [str(uuid.uuid4())],
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_endpoint_requires_rbac_permission(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_board_pack(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=False,
    )
    response = await async_client.post(
        "/api/v1/board-pack/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "reporting_period": "2026-01-31",
            "source_metric_run_ids": [str(uuid.uuid4())],
            "source_risk_run_ids": [str(uuid.uuid4())],
            "source_anomaly_run_ids": [str(uuid.uuid4())],
        },
    )
    assert response.status_code in {400, 403}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_execute_endpoint_denies_wrong_tenant_access(
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
        email="boardpack_b@example.com",
    )
    await seed_control_plane_for_board_pack(
        async_session,
        tenant_id=tenant_b,
        user_id=user_b,
        enable_module=True,
        grant_permissions=True,
    )
    await ensure_tenant_context(async_session, tenant_b)
    upstream = await seed_upstream_for_board_pack(
        async_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=user_b,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_board_pack_configuration(
        async_session,
        tenant_id=tenant_b,
        organisation_id=tenant_b,
        created_by=user_b,
        effective_from=date(2026, 1, 1),
    )
    service = build_board_pack_service(async_session)
    with governed_mutation_context(
        MutationContext(
            intent_id=uuid.uuid4(),
            job_id=uuid.uuid4(),
            actor_user_id=user_b,
            actor_role="finance_leader",
            intent_type="TEST_BOARD_PACK_RUN",
        )
    ):
        created = await service.create_run(
            tenant_id=tenant_b,
            organisation_id=tenant_b,
            reporting_period=date(2026, 1, 31),
            source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
            source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
            source_anomaly_run_ids=[uuid.UUID(upstream["anomaly_run_id"])],
            created_by=user_b,
        )

    await seed_control_plane_for_board_pack(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    response = await async_client.post(
        f"/api/v1/board-pack/runs/{created['run_id']}/execute",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code in (400, 403, 404)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_definition_section_template_rule_endpoints_allow_path(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_board_pack(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )

    definition = await async_client.post(
        "/api/v1/board-pack/definitions",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "board_pack_code": f"monthly_board_pack_{uuid.uuid4().hex[:6]}",
            "board_pack_name": "Monthly Board Pack",
            "audience_scope": "board",
            "section_order_json": {},
            "inclusion_config_json": {},
            "effective_from": "2026-01-01",
            "status": "candidate",
        },
    )
    assert definition.status_code == 201
    definition_payload = definition.json()["data"]
    definition_id = definition_payload["id"]
    assert definition_payload["intent_id"]
    assert definition_payload["job_id"]
    await set_tenant_context(async_session, test_user.tenant_id)
    definition_row = await async_session.get(BoardPackDefinition, uuid.UUID(definition_id))
    assert definition_row is not None
    assert definition_row.created_by_intent_id is not None
    assert definition_row.recorded_by_job_id is not None

    section = await async_client.post(
        "/api/v1/board-pack/sections",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "section_code": f"exec_{uuid.uuid4().hex[:6]}",
            "section_name": "Executive Summary",
            "section_type": "executive_summary",
            "section_order_default": 1,
            "effective_from": "2026-01-01",
            "status": "candidate",
        },
    )
    assert section.status_code == 201
    section_id = section.json()["data"]["id"]
    section_row = await async_session.get(BoardPackSectionDefinition, uuid.UUID(section_id))
    assert section_row is not None
    assert section_row.created_by_intent_id is not None
    assert section_row.recorded_by_job_id is not None

    template = await async_client.post(
        "/api/v1/board-pack/narrative-templates",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "template_code": f"exec_tpl_{uuid.uuid4().hex[:6]}",
            "template_name": "Exec Template",
            "template_type": "executive_summary_template",
            "template_text": "{section_title}: {section_summary_text}",
            "effective_from": "2026-01-01",
            "status": "candidate",
        },
    )
    assert template.status_code == 201
    template_id = template.json()["data"]["id"]
    template_row = await async_session.get(NarrativeTemplate, uuid.UUID(template_id))
    assert template_row is not None
    assert template_row.created_by_intent_id is not None
    assert template_row.recorded_by_job_id is not None

    rule = await async_client.post(
        "/api/v1/board-pack/inclusion-rules",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "rule_code": f"rule_{uuid.uuid4().hex[:6]}",
            "rule_name": "Top Limit",
            "rule_type": "top_severity_issues",
            "inclusion_logic_json": {"top_limit": 5},
            "effective_from": "2026-01-01",
            "status": "candidate",
        },
    )
    assert rule.status_code == 201
    rule_id = rule.json()["data"]["id"]
    rule_row = await async_session.get(BoardPackInclusionRule, uuid.UUID(rule_id))
    assert rule_row is not None
    assert rule_row.created_by_intent_id is not None
    assert rule_row.recorded_by_job_id is not None

    assert (
        await async_client.get(
            "/api/v1/board-pack/definitions",
            headers={"Authorization": f"Bearer {test_access_token}"},
        )
    ).status_code == 200
    assert (
        await async_client.get(
            f"/api/v1/board-pack/definitions/{definition_id}/versions",
            headers={"Authorization": f"Bearer {test_access_token}"},
        )
    ).status_code == 200
    assert (
        await async_client.get(
            "/api/v1/board-pack/sections",
            headers={"Authorization": f"Bearer {test_access_token}"},
        )
    ).status_code == 200
    assert (
        await async_client.get(
            f"/api/v1/board-pack/sections/{section_id}/versions",
            headers={"Authorization": f"Bearer {test_access_token}"},
        )
    ).status_code == 200
    assert (
        await async_client.get(
            "/api/v1/board-pack/narrative-templates",
            headers={"Authorization": f"Bearer {test_access_token}"},
        )
    ).status_code == 200
    assert (
        await async_client.get(
            f"/api/v1/board-pack/narrative-templates/{template_id}/versions",
            headers={"Authorization": f"Bearer {test_access_token}"},
        )
    ).status_code == 200
    assert (
        await async_client.get(
            "/api/v1/board-pack/inclusion-rules",
            headers={"Authorization": f"Bearer {test_access_token}"},
        )
    ).status_code == 200
    assert (
        await async_client.get(
            f"/api/v1/board-pack/inclusion-rules/{rule_id}/versions",
            headers={"Authorization": f"Bearer {test_access_token}"},
        )
    ).status_code == 200


@pytest.mark.asyncio
@pytest.mark.integration
async def test_board_pack_run_and_result_endpoints_allow_path(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    await seed_control_plane_for_board_pack(
        async_session,
        tenant_id=test_user.tenant_id,
        user_id=test_user.id,
        enable_module=True,
        grant_permissions=True,
    )
    upstream = await seed_upstream_for_board_pack(
        async_session,
        tenant_id=test_user.tenant_id,
        organisation_id=test_user.tenant_id,
        created_by=test_user.id,
        reporting_period=date(2026, 1, 31),
    )
    await seed_active_board_pack_configuration(
        async_session,
        tenant_id=test_user.tenant_id,
        organisation_id=test_user.tenant_id,
        created_by=test_user.id,
        effective_from=date(2026, 1, 1),
    )

    create = await async_client.post(
        "/api/v1/board-pack/runs",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={
            "organisation_id": str(test_user.tenant_id),
            "reporting_period": "2026-01-31",
            "source_metric_run_ids": [upstream["metric_run_id"]],
            "source_risk_run_ids": [upstream["risk_run_id"]],
            "source_anomaly_run_ids": [upstream["anomaly_run_id"]],
        },
    )
    assert create.status_code == 201
    run_id = create.json()["data"]["run_id"]

    execute = await async_client.post(
        f"/api/v1/board-pack/runs/{run_id}/execute",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert execute.status_code == 200
    payload = execute.json()["data"]
    assert payload["section_count"] >= 1
    executed_run_id = payload["run_id"]

    get_run = await async_client.get(
        f"/api/v1/board-pack/runs/{executed_run_id}",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert get_run.status_code == 200
    assert get_run.json()["data"]["status"] == "completed"

    summary = await async_client.get(
        f"/api/v1/board-pack/runs/{executed_run_id}/summary",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert summary.status_code == 200

    sections = await async_client.get(
        f"/api/v1/board-pack/runs/{executed_run_id}/sections",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert sections.status_code == 200
    assert len(sections.json()) >= 1

    narratives = await async_client.get(
        f"/api/v1/board-pack/runs/{executed_run_id}/narratives",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert narratives.status_code == 200

    evidence = await async_client.get(
        f"/api/v1/board-pack/runs/{executed_run_id}/evidence",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert evidence.status_code == 200

