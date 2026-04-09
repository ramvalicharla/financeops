from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from financeops.db.rls import set_tenant_context
from financeops.modules.ratio_variance_engine.application.materiality_service import (
    MaterialityService,
)
from financeops.modules.ratio_variance_engine.application.metric_definition_service import (
    MetricDefinitionService,
)
from financeops.modules.ratio_variance_engine.application.run_service import RunService
from financeops.modules.ratio_variance_engine.application.trend_service import TrendService
from financeops.modules.ratio_variance_engine.application.validation_service import (
    ValidationService,
)
from financeops.modules.ratio_variance_engine.application.variance_service import (
    VarianceService,
)
from financeops.modules.ratio_variance_engine.infrastructure.repository import (
    RatioVarianceRepository,
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
from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import (
    seed_finalized_normalization_pair,
    seed_identity_user,
)

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
)

RATIO_TABLES: tuple[str, ...] = (
    "metric_definitions",
    "metric_definition_components",
    "variance_definitions",
    "trend_definitions",
    "materiality_rules",
    "metric_runs",
    "metric_results",
    "variance_results",
    "trend_results",
    "metric_evidence_links",
)


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_database(raw_url: str, database: str) -> str:
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(scope="session")
async def ratio_phase1f4_db_url() -> AsyncGenerator[str, None]:
    base_url = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    admin_db = os.getenv("TEST_DATABASE_ADMIN_DB", "postgres")
    suffix = uuid.uuid4().hex[:10]
    temp_db = f"financeops_ratio_{suffix}"
    if not re.fullmatch(r"[a-z0-9_]+", temp_db):
        raise RuntimeError(f"Invalid temp database name: {temp_db}")

    admin_url = _with_database(base_url, admin_db)
    target_url = _with_database(base_url, temp_db)
    conn = await asyncpg.connect(_to_asyncpg_dsn(admin_url))
    try:
        await conn.execute(f'CREATE DATABASE "{temp_db}"')
    finally:
        await conn.close()

    env = os.environ.copy()
    env["DATABASE_URL"] = target_url
    env["MIGRATION_DATABASE_URL"] = target_url
    env.setdefault("SECRET_KEY", "test-secret-key")
    env.setdefault("JWT_SECRET", "test-jwt-secret-32-characters-long-000")
    env.setdefault("FIELD_ENCRYPTION_KEY", "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=")
    env.setdefault("REDIS_URL", "redis://localhost:6380/0")
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=str(_backend_dir()),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if migration.returncode != 0:
        raise RuntimeError(
            "alembic upgrade head failed for ratio phase1f4 temp database\n"
            f"stdout:\n{migration.stdout}\n"
            f"stderr:\n{migration.stderr}"
        )

    try:
        yield target_url
    finally:
        cleanup_conn = await asyncpg.connect(_to_asyncpg_dsn(admin_url))
        try:
            await cleanup_conn.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = $1
                  AND pid <> pg_backend_pid()
                """,
                temp_db,
            )
            await cleanup_conn.execute(f'DROP DATABASE IF EXISTS "{temp_db}"')
        finally:
            await cleanup_conn.close()


@pytest_asyncio.fixture(scope="session")
async def ratio_phase1f4_engine(ratio_phase1f4_db_url: str):
    engine = create_async_engine(ratio_phase1f4_db_url, echo=False, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def ratio_phase1f4_session(
    ratio_phase1f4_engine,
) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(ratio_phase1f4_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()


def build_ratio_variance_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=RatioVarianceRepository(session),
        metric_definition_service=MetricDefinitionService(),
        variance_service=VarianceService(),
        trend_service=TrendService(),
        materiality_service=MaterialityService(),
        validation_service=ValidationService(),
    )


async def ensure_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await set_tenant_context(session, tenant_id)


async def seed_control_plane_for_ratio_variance(
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
            "correlation_id": "ratio-phase1f4",
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
        select(CpModuleRegistry).where(CpModuleRegistry.module_code == "ratio_variance_engine")
    )
    module = module_result.scalar_one_or_none()
    if module is None:
        module = CpModuleRegistry(
            module_code="ratio_variance_engine",
            module_name="Ratio Variance Engine",
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
            correlation_id="ratio-phase1f4",
            effective_from=now,
            effective_to=None,
        )
        await grant_boolean_entitlement(
            session,
            tenant_id=tenant_id,
            feature_name="ratio_variance_engine",
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
        correlation_id="ratio-phase1f4",
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
        correlation_id="ratio-phase1f4",
    )
    if not grant_permissions:
        await session.flush()
        return
    role = await create_role(
        session,
        tenant_id=tenant_id,
        role_code=f"RATIO_ROLE_{uuid.uuid4().hex[:8]}",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=user_id,
        correlation_id="ratio-phase1f4",
    )
    permissions = [
        ("metric_run", "ratio_variance_run"),
        ("metric_run", "ratio_variance_view"),
        ("metric_definition", "metric_definition_manage"),
        ("variance_definition", "variance_definition_manage"),
        ("trend_definition", "trend_definition_manage"),
        ("materiality_rule", "materiality_rule_manage"),
        ("metric_evidence_link", "ratio_variance_evidence_view"),
        ("metric_definition", "ratio_variance_view"),
        ("variance_definition", "ratio_variance_view"),
        ("trend_definition", "ratio_variance_view"),
        ("materiality_rule", "ratio_variance_view"),
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
                description="ratio phase1f4 integration permission",
            )
        await grant_role_permission(
            session,
            tenant_id=tenant_id,
            role_id=role.id,
            permission_id=permission.id,
            effect="allow",
            actor_user_id=user_id,
            correlation_id="ratio-phase1f4",
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
        correlation_id="ratio-phase1f4",
    )
    await session.flush()


async def seed_active_definition_set(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    created_by: uuid.UUID,
    effective_from: date,
) -> dict[str, str]:
    repo = RatioVarianceRepository(session)
    metric = await repo.create_metric_definition(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        definition_code=f"REV_{uuid.uuid4().hex[:6]}",
        definition_name="Revenue",
        metric_code="revenue",
        formula_type="sum",
        formula_json={},
        unit_type="amount",
        directionality="higher_is_better",
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        components=[
            {
                "component_code": "c1",
                "source_type": "payroll_metric",
                "source_key": "gross_pay",
                "operator": "add",
                "weight": "1",
                "ordinal_position": 1,
                "metadata_json": {},
            }
        ],
        created_by=created_by,
    )
    variance = await repo.create_variance_definition(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        definition_code=f"VAR_{uuid.uuid4().hex[:6]}",
        definition_name="Revenue MoM",
        metric_code="revenue",
        comparison_type="mom_abs_pct",
        configuration_json={},
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    trend = await repo.create_trend_definition(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        definition_code=f"TRD_{uuid.uuid4().hex[:6]}",
        definition_name="Revenue rolling3",
        metric_code="revenue",
        trend_type="rolling_average",
        window_size=3,
        configuration_json={},
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    materiality = await repo.create_materiality_rule(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        definition_code=f"MAT_{uuid.uuid4().hex[:6]}",
        definition_name="Default",
        rule_json={"absolute_threshold": "1", "percentage_threshold": "0.1", "basis_points_threshold": "5"},
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    await session.flush()
    return {
        "metric_id": str(metric.id),
        "variance_id": str(variance.id),
        "trend_id": str(trend.id),
        "materiality_id": str(materiality.id),
    }

