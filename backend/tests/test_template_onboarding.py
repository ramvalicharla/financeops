from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.board_pack_generator import BoardPackGeneratorDefinition
from financeops.db.models.custom_report_builder import ReportDefinition
from financeops.db.models.scheduled_delivery import DeliverySchedule
from financeops.db.rls import set_tenant_context
from financeops.modules.template_onboarding.models import OnboardingState
from financeops.modules.template_onboarding.service import (
    TemplateAlreadyAppliedError,
    apply_template,
    complete_onboarding,
    get_or_create_onboarding_state,
    update_onboarding_step,
)
from financeops.modules.template_onboarding.templates import (
    TEMPLATE_REGISTRY,
    get_template,
)


@pytest.mark.asyncio
async def test_all_templates_present() -> None:
    """Registry exposes all seven onboarding templates."""
    assert len(TEMPLATE_REGISTRY) == 7
    assert {"saas", "manufacturing", "retail", "professional_services", "healthcare", "general", "it_services"}.issubset(
        TEMPLATE_REGISTRY.keys()
    )


@pytest.mark.asyncio
async def test_template_fields_complete() -> None:
    """Every template has required core fields and non-empty sections/reports."""
    for template in TEMPLATE_REGISTRY.values():
        assert template.id
        assert template.name
        assert template.industry
        assert template.description
        assert template.board_pack_sections
        assert template.report_definitions
        assert template.delivery_schedule


@pytest.mark.asyncio
async def test_get_template_valid() -> None:
    """get_template returns the SaaS template for valid identifier."""
    template = get_template("saas")
    assert template is not None
    assert template.id == "saas"


@pytest.mark.asyncio
async def test_get_template_invalid() -> None:
    """get_template returns None for unknown template identifiers."""
    assert get_template("unknown") is None


@pytest.mark.asyncio
async def test_get_or_create_new(async_session: AsyncSession, test_user) -> None:
    """Service creates onboarding state for a new tenant."""
    await set_tenant_context(async_session, test_user.tenant_id)
    state = await get_or_create_onboarding_state(async_session, test_user.tenant_id)
    assert state.tenant_id == test_user.tenant_id
    assert state.current_step == 1


@pytest.mark.asyncio
async def test_get_or_create_existing(async_session: AsyncSession, test_user) -> None:
    """Service returns existing onboarding state on repeated calls."""
    await set_tenant_context(async_session, test_user.tenant_id)
    first = await get_or_create_onboarding_state(async_session, test_user.tenant_id)
    second = await get_or_create_onboarding_state(async_session, test_user.tenant_id)
    assert first.id == second.id


@pytest.mark.asyncio
async def test_update_step(async_session: AsyncSession, test_user) -> None:
    """update_onboarding_step changes current step for the tenant state row."""
    await set_tenant_context(async_session, test_user.tenant_id)
    state = await update_onboarding_step(async_session, test_user.tenant_id, 2)
    assert state.current_step == 2


@pytest.mark.asyncio
async def test_update_industry(async_session: AsyncSession, test_user) -> None:
    """update_onboarding_step persists selected industry alongside step update."""
    await set_tenant_context(async_session, test_user.tenant_id)
    state = await update_onboarding_step(
        async_session,
        test_user.tenant_id,
        2,
        industry="saas",
    )
    assert state.industry == "saas"


@pytest.mark.asyncio
async def test_apply_saas_template(async_session: AsyncSession, test_user) -> None:
    """Applying SaaS template creates board-pack/report/delivery resources."""
    await set_tenant_context(async_session, test_user.tenant_id)
    result = await apply_template(
        async_session,
        test_user.tenant_id,
        "saas",
        test_user.id,
    )
    assert uuid.UUID(result["board_pack_definition_id"])
    assert result["report_definition_ids"]
    assert uuid.UUID(result["delivery_schedule_id"])


@pytest.mark.asyncio
async def test_apply_general_template(async_session: AsyncSession, test_user) -> None:
    """Applying General template creates expected resources."""
    await set_tenant_context(async_session, test_user.tenant_id)
    result = await apply_template(
        async_session,
        test_user.tenant_id,
        "general",
        test_user.id,
    )
    assert len(result["report_definition_ids"]) >= 1


@pytest.mark.asyncio
async def test_apply_it_services_template(async_session: AsyncSession, test_user) -> None:
    """Applying IT Services template creates expected resources."""
    await set_tenant_context(async_session, test_user.tenant_id)
    result = await apply_template(
        async_session,
        test_user.tenant_id,
        "it_services",
        test_user.id,
    )
    assert len(result["report_definition_ids"]) >= 1


@pytest.mark.asyncio
async def test_apply_invalid_template(async_session: AsyncSession, test_user) -> None:
    """Applying unknown template raises ValueError."""
    await set_tenant_context(async_session, test_user.tenant_id)
    with pytest.raises(ValueError):
        await apply_template(async_session, test_user.tenant_id, "not_real", test_user.id)


@pytest.mark.asyncio
async def test_apply_duplicate_template(async_session: AsyncSession, test_user) -> None:
    """Applying template twice for same tenant raises conflict error."""
    await set_tenant_context(async_session, test_user.tenant_id)
    await apply_template(async_session, test_user.tenant_id, "saas", test_user.id)
    with pytest.raises(TemplateAlreadyAppliedError):
        await apply_template(async_session, test_user.tenant_id, "saas", test_user.id)


@pytest.mark.asyncio
async def test_get_state_creates_if_missing(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    """GET state creates missing onboarding_state row for authenticated tenant."""
    response = await async_client.get(
        "/api/v1/onboarding/state",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["current_step"] == 1


@pytest.mark.asyncio
async def test_get_state_returns_existing(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    """GET state returns previously created state for tenant."""
    await set_tenant_context(async_session, test_user.tenant_id)
    state = await get_or_create_onboarding_state(async_session, test_user.tenant_id)
    state.current_step = 4
    await async_session.flush()

    response = await async_client.get(
        "/api/v1/onboarding/state",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["current_step"] == 4


@pytest.mark.asyncio
async def test_patch_state_updates_step(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    """PATCH state updates current_step for authenticated tenant."""
    response = await async_client.patch(
        "/api/v1/onboarding/state",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"current_step": 2},
    )
    assert response.status_code == 200
    assert response.json()["data"]["current_step"] == 2


@pytest.mark.asyncio
async def test_patch_state_updates_industry(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    """PATCH state updates industry field."""
    response = await async_client.patch(
        "/api/v1/onboarding/state",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"industry": "saas"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["industry"] == "saas"


@pytest.mark.asyncio
async def test_list_templates_public(async_client: AsyncClient) -> None:
    """Public templates endpoint returns seven template summaries."""
    response = await async_client.get("/api/v1/onboarding/templates")
    assert response.status_code == 200
    assert len(response.json()["data"]) == 7


@pytest.mark.asyncio
async def test_get_template_detail(async_client: AsyncClient) -> None:
    """Template detail endpoint returns full template payload."""
    response = await async_client.get("/api/v1/onboarding/templates/saas")
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["id"] == "saas"
    assert payload["board_pack_sections"]
    assert payload["report_definitions"]


@pytest.mark.asyncio
async def test_get_template_detail_404(async_client: AsyncClient) -> None:
    """Unknown template detail request returns 404."""
    response = await async_client.get("/api/v1/onboarding/templates/unknown")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_apply_endpoint(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_access_token: str,
    test_user,
) -> None:
    """Apply endpoint creates linked resources and returns their IDs."""
    response = await async_client.post(
        "/api/v1/onboarding/apply",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"template_id": "saas"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert uuid.UUID(payload["board_pack_definition_id"])
    assert payload["report_definition_ids"]
    assert uuid.UUID(payload["delivery_schedule_id"])

    await set_tenant_context(async_session, test_user.tenant_id)
    board_row = (
        await async_session.execute(
            select(BoardPackGeneratorDefinition).where(
                BoardPackGeneratorDefinition.id == uuid.UUID(payload["board_pack_definition_id"])
            )
        )
    ).scalar_one_or_none()
    report_row = (
        await async_session.execute(
            select(ReportDefinition).where(ReportDefinition.id == uuid.UUID(payload["report_definition_ids"][0]))
        )
    ).scalar_one_or_none()
    schedule_row = (
        await async_session.execute(
            select(DeliverySchedule).where(DeliverySchedule.id == uuid.UUID(payload["delivery_schedule_id"]))
        )
    ).scalar_one_or_none()
    assert board_row is not None
    assert report_row is not None
    assert schedule_row is not None


@pytest.mark.asyncio
async def test_complete_onboarding(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    """Complete endpoint marks onboarding as completed at step five."""
    response = await async_client.post(
        "/api/v1/onboarding/complete",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )
    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["completed"] is True
    assert payload["current_step"] == 5


@pytest.mark.asyncio
async def test_apply_endpoint_conflict(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    """Second apply call returns 409 when template already applied for tenant."""
    first = await async_client.post(
        "/api/v1/onboarding/apply",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"template_id": "general"},
    )
    assert first.status_code == 200

    second = await async_client.post(
        "/api/v1/onboarding/apply",
        headers={"Authorization": f"Bearer {test_access_token}"},
        json={"template_id": "general"},
    )
    assert second.status_code == 409
