from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from financeops.db.rls import set_tenant_context
from financeops.modules.financial_risk_engine.application.materiality_service import (
    MaterialityService,
)
from financeops.modules.financial_risk_engine.application.run_service import RunService
from financeops.modules.financial_risk_engine.application.scoring_service import ScoringService
from financeops.modules.financial_risk_engine.application.validation_service import (
    ValidationService,
)
from financeops.modules.financial_risk_engine.infrastructure.repository import (
    FinancialRiskRepository,
)
from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.db.models.permissions import CpPermission
from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.services.isolation.routing_service import create_isolation_route
from financeops.platform.services.quotas.policy_service import assign_quota_to_tenant
from financeops.platform.services.rbac.permission_service import (
    create_permission,
    grant_role_permission,
)
from financeops.platform.services.rbac.role_service import assign_user_role, create_role
from financeops.platform.services.tenancy.module_enablement import set_module_enablement
from financeops.services.audit_writer import AuditEvent, AuditWriter
from tests.integration.entitlement_helpers import grant_boolean_entitlement
from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import seed_identity_user
from tests.integration.ratio_variance_phase1f4_helpers import (
    build_ratio_variance_service,
    seed_active_definition_set,
    seed_finalized_normalization_pair,
)
from tests.integration.temp_db_helpers import create_migrated_temp_database, drop_temp_database

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
)

FINANCIAL_RISK_TABLES: tuple[str, ...] = (
    "risk_definitions",
    "risk_definition_dependencies",
    "risk_weight_configurations",
    "risk_materiality_rules",
    "risk_runs",
    "risk_results",
    "risk_contributing_signals",
    "risk_rollforward_events",
    "risk_evidence_links",
)


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_database(raw_url: str, database: str) -> str:
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(scope="session")
async def financial_risk_phase1f5_db_url() -> AsyncGenerator[str, None]:
    target_url, temp_db, admin_url = await create_migrated_temp_database(
        prefix="financeops_risk",
        error_context="financial risk phase1f5 temp database",
    )

    try:
        yield target_url
    finally:
        await drop_temp_database(admin_url=admin_url, database_name=temp_db)


@pytest_asyncio.fixture(scope="session")
async def financial_risk_phase1f5_engine(financial_risk_phase1f5_db_url: str):
    engine = create_async_engine(financial_risk_phase1f5_db_url, echo=False, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def financial_risk_phase1f5_session(
    financial_risk_phase1f5_engine,
) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(financial_risk_phase1f5_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()


def build_financial_risk_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=FinancialRiskRepository(session),
        validation_service=ValidationService(),
        scoring_service=ScoringService(),
        materiality_service=MaterialityService(),
    )


async def ensure_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await set_tenant_context(session, tenant_id)


async def seed_control_plane_for_financial_risk(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    enable_module: bool = True,
    grant_permissions: bool = True,
) -> None:
    await AuditWriter.insert_financial_record(
        session,
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
            "correlation_id": "risk-phase1f5",
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
    module_result = await session.execute(
        select(CpModuleRegistry).where(CpModuleRegistry.module_code == "financial_risk_engine")
    )
    module = module_result.scalar_one_or_none()
    if module is None:
        module = CpModuleRegistry(
            module_code="financial_risk_engine",
            module_name="Financial Risk Engine",
            engine_context="finance",
            is_financial_impacting=True,
            is_active=True,
        )
        await AuditWriter.insert_record(
            session,
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
    if enable_module:
        await set_module_enablement(
            session,
            tenant_id=tenant_id,
            module_id=module.id,
            enabled=True,
            enablement_source="test",
            actor_user_id=user_id,
            correlation_id="risk-phase1f5",
            effective_from=now,
            effective_to=None,
        )
        await grant_boolean_entitlement(
            session,
            tenant_id=tenant_id,
            feature_name="financial_risk_engine",
            actor_user_id=user_id,
        )
    await assign_quota_to_tenant(
        session,
        tenant_id=tenant_id,
        quota_type="api_requests",
        window_type="sliding",
        window_seconds=60,
        max_value=1000,
        enforcement_mode="reject",
        effective_from=now,
        effective_to=None,
        actor_user_id=user_id,
        correlation_id="risk-phase1f5",
    )
    await create_isolation_route(
        session,
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
        correlation_id="risk-phase1f5",
    )
    if not grant_permissions:
        await session.flush()
        return

    role = await create_role(
        session,
        tenant_id=tenant_id,
        role_code=f"RISK_ROLE_{uuid.uuid4().hex[:8]}",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=user_id,
        correlation_id="risk-phase1f5",
    )
    permissions = [
        ("risk_run", "financial_risk_run"),
        ("risk_run", "financial_risk_view"),
        ("risk_definition", "risk_definition_manage"),
        ("risk_weight_configuration", "risk_weight_manage"),
        ("risk_materiality_rule", "risk_materiality_manage"),
        ("risk_evidence_link", "financial_risk_evidence_view"),
        ("risk_definition", "financial_risk_view"),
        ("risk_weight_configuration", "financial_risk_view"),
        ("risk_materiality_rule", "financial_risk_view"),
        ("risk_result", "financial_risk_view"),
        ("risk_contributing_signal", "financial_risk_view"),
        ("risk_rollforward_event", "financial_risk_view"),
    ]
    for resource_type, action in permissions:
        permission_result = await session.execute(
            select(CpPermission).where(
                CpPermission.resource_type == resource_type,
                CpPermission.action == action,
            )
        )
        permission = permission_result.scalars().first()
        if permission is None:
            permission = await create_permission(
                session,
                actor_tenant_id=tenant_id,
                actor_user_id=user_id,
                permission_code=f"{resource_type}.{action}.global",
                resource_type=resource_type,
                action=action,
                description="financial risk phase1f5 integration permission",
            )
        await grant_role_permission(
            session,
            tenant_id=tenant_id,
            role_id=role.id,
            permission_id=permission.id,
            effect="allow",
            actor_user_id=user_id,
            correlation_id="risk-phase1f5",
        )
    await assign_user_role(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        role_id=role.id,
        context_type="tenant",
        context_id=tenant_id,
        effective_from=now,
        effective_to=None,
        assigned_by=user_id,
        actor_user_id=user_id,
        correlation_id="risk-phase1f5",
    )
    await session.flush()


async def seed_upstream_ratio_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    created_by: uuid.UUID,
    reporting_period: date,
) -> dict[str, str]:
    pair = await seed_finalized_normalization_pair(
        session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=created_by,
        reporting_period=reporting_period,
    )
    await seed_active_definition_set(
        session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=created_by,
        effective_from=date(reporting_period.year, reporting_period.month, 1),
    )
    ratio_service = build_ratio_variance_service(session)
    created = await ratio_service.create_run(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        reporting_period=reporting_period,
        scope_json={"entity": "LE1"},
        mis_snapshot_id=None,
        payroll_run_id=uuid.UUID(pair["payroll_run_id"]),
        gl_run_id=uuid.UUID(pair["gl_run_id"]),
        reconciliation_session_id=None,
        payroll_gl_reconciliation_run_id=None,
        created_by=created_by,
    )
    executed = await ratio_service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=created_by,
    )
    return {
        "ratio_run_id": executed["run_id"],
        "ratio_run_token": executed["run_token"],
        "payroll_run_id": pair["payroll_run_id"],
        "gl_run_id": pair["gl_run_id"],
    }


async def seed_active_risk_configuration(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    created_by: uuid.UUID,
    effective_from: date,
) -> dict[str, str]:
    repository = FinancialRiskRepository(session)
    first = await repository.create_risk_definition(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        risk_code=f"RISK_PAYROLL_{uuid.uuid4().hex[:6]}",
        risk_name="Payroll Cost Risk",
        risk_domain="payroll",
        signal_selector_json={
            "metric_codes": ["revenue"],
            "variance_codes": ["revenue"],
            "trend_codes": ["revenue"],
            "include_reconciliation": False,
        },
        definition_json={"kind": "base"},
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        effective_to=None,
        supersedes_id=None,
        status="active",
        dependencies=[],
        created_by=created_by,
    )
    second = await repository.create_risk_definition(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        risk_code=f"RISK_LIQ_{uuid.uuid4().hex[:6]}",
        risk_name="Liquidity Risk",
        risk_domain="liquidity",
        signal_selector_json={
            "metric_codes": ["revenue"],
            "variance_codes": ["revenue"],
            "trend_codes": [],
            "include_reconciliation": True,
        },
        definition_json={"kind": "dependent"},
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        effective_to=None,
        supersedes_id=None,
        status="active",
        dependencies=[
            {
                "dependency_type": "risk_result",
                "depends_on_risk_definition_id": first.id,
                "signal_reference_code": None,
                "propagation_factor": Decimal("0.6"),
                "amplification_rule_json": {},
                "attenuation_rule_json": {},
                "cap_limit": Decimal("0.8"),
            }
        ],
        created_by=created_by,
    )
    weight = await repository.create_weight_configuration(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        weight_code=f"WG_{uuid.uuid4().hex[:6]}",
        risk_code="*",
        scope_type="global",
        scope_value=None,
        weight_value=Decimal("1"),
        board_critical_override=False,
        configuration_json={},
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    materiality = await repository.create_materiality_rule(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        rule_code=f"MAT_{uuid.uuid4().hex[:6]}",
        rule_name="Default Materiality",
        threshold_json={"materiality_threshold": "0.20"},
        severity_mapping_json={
            "critical": "0.85",
            "high": "0.65",
            "medium": "0.40",
            "low": "0.20",
        },
        propagation_behavior_json={},
        escalation_rule_json={},
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    await session.flush()
    return {
        "risk_definition_id": str(first.id),
        "dependent_risk_definition_id": str(second.id),
        "weight_id": str(weight.id),
        "materiality_rule_id": str(materiality.id),
    }

