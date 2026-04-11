from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.security import create_access_token, hash_password
from financeops.db.models.accounting_governance import AccountingPeriod, AccountingPeriodStatus
from financeops.db.models.users import IamUser, UserRole
from financeops.modules.org_setup.application.org_setup_service import OrgSetupService
from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.services.tenancy.module_enablement import set_module_enablement


@pytest.mark.asyncio
@pytest.mark.integration
async def test_control_plane_context_endpoint_returns_backend_modules_and_period(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    module = CpModuleRegistry(
        module_code="erp_sync",
        module_name="ERP Sync",
        engine_context="finance",
        is_financial_impacting=True,
        is_active=True,
    )
    async_session.add(module)
    await async_session.flush()
    await set_module_enablement(
        async_session,
        tenant_id=test_user.tenant_id,
        module_id=module.id,
        enabled=True,
        enablement_source="test",
        actor_user_id=test_user.id,
        correlation_id="ctx-phase4-4",
    )
    now = datetime.now(UTC)
    async_session.add(
        AccountingPeriod(
            tenant_id=test_user.tenant_id,
            org_entity_id=None,
            fiscal_year=now.year,
            period_number=now.month,
            period_start=date(now.year, now.month, 1),
            period_end=date(now.year, now.month, 28),
            status=AccountingPeriodStatus.OPEN,
        )
    )
    await async_session.flush()

    response = await async_client.get(
        "/api/v1/platform/control-plane/context",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert any(row["module_code"] == "erp_sync" for row in payload["enabled_modules"])
    assert any(tab["workspace_key"] == "erp" for tab in payload["workspace_tabs"])
    assert payload["current_period"]["source"] == "accounting_period"
    assert payload["current_period"]["period_label"] == f"{now.year:04d}-{now.month:02d}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_control_plane_context_endpoint_returns_current_entity_and_workspace(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
    ) -> None:
    module = CpModuleRegistry(
        module_code="custom_report_builder",
        module_name="Custom Reports",
        engine_context="finance",
        is_financial_impacting=True,
        is_active=True,
    )
    async_session.add(module)
    await async_session.flush()
    await set_module_enablement(
        async_session,
        tenant_id=test_user.tenant_id,
        module_id=module.id,
        enabled=True,
        enablement_source="test",
        actor_user_id=test_user.id,
        correlation_id="ctx-reports-workspace",
    )
    service = OrgSetupService(async_session)
    group = await service.submit_step1(
        test_user.tenant_id,
        {
            "group_name": "Acme Group",
            "country_of_incorp": "India",
            "country_code": "IN",
            "functional_currency": "INR",
            "reporting_currency": "INR",
        },
    )
    entity = (
        await service.submit_step2(
            test_user.tenant_id,
            group.id,
            [
                {
                    "legal_name": "Acme India Pvt Ltd",
                    "display_name": "Acme India",
                    "entity_type": "WHOLLY_OWNED_SUBSIDIARY",
                    "country_code": "IN",
                    "state_code": "KA",
                    "functional_currency": "INR",
                    "reporting_currency": "INR",
                    "fiscal_year_start": 4,
                    "applicable_gaap": "INDAS",
                }
            ],
        )
    )[0]
    await async_session.flush()

    response = await async_client.get(
        f"/api/v1/platform/control-plane/context?entity_id={entity.cp_entity_id}&workspace=reports",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["current_organisation"]["organisation_name"] == "Acme Group"
    assert payload["current_entity"]["entity_name"] == "Acme India Pvt Ltd"
    assert payload["current_module"]["module_key"] == "reports"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_control_plane_context_endpoint_marks_period_unavailable_without_accounting_period(
    async_client: AsyncClient,
    test_access_token: str,
) -> None:
    response = await async_client.get(
        "/api/v1/platform/control-plane/context",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["current_period"]["source"] == "unavailable"
    assert payload["current_period"]["period_label"] == "Unavailable"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_control_plane_context_endpoint_confirms_requested_module(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
    test_access_token: str,
) -> None:
    module = CpModuleRegistry(
        module_code="custom_report_builder",
        module_name="Custom Reports",
        engine_context="finance",
        is_financial_impacting=True,
        is_active=True,
    )
    async_session.add(module)
    await async_session.flush()
    await set_module_enablement(
        async_session,
        tenant_id=test_user.tenant_id,
        module_id=module.id,
        enabled=True,
        enablement_source="test",
        actor_user_id=test_user.id,
        correlation_id="ctx-module-confirm",
    )
    await async_session.flush()

    response = await async_client.get(
        "/api/v1/platform/control-plane/context?module=custom_report_builder",
        headers={"Authorization": f"Bearer {test_access_token}"},
    )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["current_module"]["module_code"] == "custom_report_builder"
    assert payload["current_module"]["source"] == "requested_module"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_manual_snapshot_endpoint_requires_finance_leader(
    async_client: AsyncClient,
    async_session: AsyncSession,
    test_user,
) -> None:
    finance_team_user = IamUser(
        tenant_id=test_user.tenant_id,
        email="snapshot-team@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Snapshot Finance Team",
        role=UserRole.finance_team,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(finance_team_user)
    await async_session.flush()
    token = create_access_token(
        finance_team_user.id,
        finance_team_user.tenant_id,
        finance_team_user.role.value,
    )

    response = await async_client.post(
        "/api/v1/platform/control-plane/snapshots/manual",
        headers={"Authorization": f"Bearer {token}"},
        json={"subject_type": "intent", "subject_id": str(uuid.uuid4())},
    )

    assert response.status_code == 403
    assert re.search("finance_approver role required", response.text)
