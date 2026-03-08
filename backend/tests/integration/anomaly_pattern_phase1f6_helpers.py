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
from financeops.modules.anomaly_pattern_engine.application.correlation_service import (
    CorrelationService,
)
from financeops.modules.anomaly_pattern_engine.application.materiality_service import (
    MaterialityService,
)
from financeops.modules.anomaly_pattern_engine.application.persistence_service import (
    PersistenceService,
)
from financeops.modules.anomaly_pattern_engine.application.run_service import RunService
from financeops.modules.anomaly_pattern_engine.application.scoring_service import ScoringService
from financeops.modules.anomaly_pattern_engine.application.statistical_service import (
    StatisticalService,
)
from financeops.modules.anomaly_pattern_engine.application.validation_service import (
    ValidationService,
)
from financeops.modules.anomaly_pattern_engine.infrastructure.repository import (
    AnomalyPatternRepository,
)
from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.db.models.permissions import CpPermission
from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.services.isolation.routing_service import create_isolation_route
from financeops.platform.services.quotas.policy_service import assign_quota_to_tenant
from financeops.platform.services.rbac.permission_service import create_permission, grant_role_permission
from financeops.platform.services.rbac.role_service import assign_user_role, create_role
from financeops.platform.services.tenancy.module_enablement import set_module_enablement
from financeops.services.audit_writer import AuditEvent, AuditWriter
from tests.integration.financial_risk_phase1f5_helpers import (
    build_financial_risk_service,
    seed_active_risk_configuration,
    seed_identity_user,
    seed_upstream_ratio_run,
)

DEFAULT_TEST_DATABASE_URL = "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"

ANOMALY_TABLES: tuple[str, ...] = (
    "anomaly_definitions",
    "anomaly_pattern_rules",
    "anomaly_persistence_rules",
    "anomaly_correlation_rules",
    "anomaly_statistical_rules",
    "anomaly_runs",
    "anomaly_results",
    "anomaly_contributing_signals",
    "anomaly_rollforward_events",
    "anomaly_evidence_links",
)


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_database(raw_url: str, database: str) -> str:
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(scope="session")
async def anomaly_phase1f6_db_url() -> AsyncGenerator[str, None]:
    base_url = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    admin_db = os.getenv("TEST_DATABASE_ADMIN_DB", "postgres")
    suffix = uuid.uuid4().hex[:10]
    temp_db = f"financeops_anomaly_{suffix}"
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
    env.setdefault("SECRET_KEY", "test-secret-key")
    env.setdefault("JWT_SECRET", "test-jwt-secret")
    env.setdefault("FIELD_ENCRYPTION_KEY", "test-field-encryption-key")
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
            "alembic upgrade head failed for anomaly phase1f6 temp database\n"
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
async def anomaly_phase1f6_engine(anomaly_phase1f6_db_url: str):
    engine = create_async_engine(anomaly_phase1f6_db_url, echo=False, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def anomaly_phase1f6_session(anomaly_phase1f6_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(anomaly_phase1f6_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()


def build_anomaly_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=AnomalyPatternRepository(session),
        validation_service=ValidationService(),
        statistical_service=StatisticalService(),
        scoring_service=ScoringService(),
        materiality_service=MaterialityService(),
        persistence_service=PersistenceService(),
        correlation_service=CorrelationService(),
    )


async def ensure_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await set_tenant_context(session, tenant_id)


async def seed_control_plane_for_anomaly(
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
            "correlation_id": "anomaly-phase1f6",
            "deactivated_at": None,
        },
        audit=AuditEvent(tenant_id=tenant_id, user_id=user_id, action="platform.test.seed", resource_type="cp_tenant", resource_id=str(tenant_id)),
    )
    module = (await session.execute(select(CpModuleRegistry).where(CpModuleRegistry.module_code == "anomaly_pattern_engine"))).scalar_one_or_none()
    if module is None:
        module = CpModuleRegistry(module_code="anomaly_pattern_engine", module_name="Anomaly Pattern Engine", engine_context="finance", is_financial_impacting=True, is_active=True)
        await AuditWriter.insert_record(session, record=module, audit=AuditEvent(tenant_id=tenant_id, user_id=user_id, action="platform.test.module.seed", resource_type="cp_module_registry", resource_id=str(module.id)))
    now = datetime.now(UTC)
    if enable_module:
        await set_module_enablement(session, tenant_id=tenant_id, module_id=module.id, enabled=True, enablement_source="test", actor_user_id=user_id, correlation_id="anomaly-phase1f6", effective_from=now, effective_to=None)
    await assign_quota_to_tenant(session, tenant_id=tenant_id, quota_type="api_requests", window_type="sliding", window_seconds=60, max_value=1000, enforcement_mode="reject", effective_from=now, effective_to=None, actor_user_id=user_id, correlation_id="anomaly-phase1f6")
    await create_isolation_route(session, tenant_id=tenant_id, isolation_tier="tier1", db_cluster="shared-primary", schema_name="public", worker_pool="shared-workers", region="us-east-1", migration_state="active", route_version=1, effective_from=now, effective_to=None, actor_user_id=user_id, correlation_id="anomaly-phase1f6")
    if not grant_permissions:
        await session.flush()
        return
    role = await create_role(session, tenant_id=tenant_id, role_code=f"ANOMALY_ROLE_{uuid.uuid4().hex[:8]}", role_scope="tenant", inherits_role_id=None, is_active=True, actor_user_id=user_id, correlation_id="anomaly-phase1f6")
    perms = [
        ("anomaly_run", "anomaly_engine_run"),
        ("anomaly_run", "anomaly_engine_view"),
        ("anomaly_definition", "anomaly_definition_manage"),
        ("anomaly_definition", "anomaly_engine_view"),
        ("anomaly_pattern_rule", "anomaly_pattern_rule_manage"),
        ("anomaly_pattern_rule", "anomaly_engine_view"),
        ("anomaly_persistence_rule", "anomaly_persistence_rule_manage"),
        ("anomaly_persistence_rule", "anomaly_engine_view"),
        ("anomaly_correlation_rule", "anomaly_correlation_rule_manage"),
        ("anomaly_correlation_rule", "anomaly_engine_view"),
        ("anomaly_statistical_rule", "anomaly_statistical_rule_manage"),
        ("anomaly_statistical_rule", "anomaly_engine_view"),
        ("anomaly_result", "anomaly_engine_view"),
        ("anomaly_contributing_signal", "anomaly_engine_view"),
        ("anomaly_rollforward_event", "anomaly_engine_view"),
        ("anomaly_evidence_link", "anomaly_engine_evidence_view"),
    ]
    for resource_type, action in perms:
        permission = (await session.execute(select(CpPermission).where(CpPermission.resource_type == resource_type, CpPermission.action == action))).scalars().first()
        if permission is None:
            permission = await create_permission(session, actor_tenant_id=tenant_id, actor_user_id=user_id, permission_code=f"{resource_type}.{action}.global", resource_type=resource_type, action=action, description="anomaly phase1f6 integration permission")
        await grant_role_permission(session, tenant_id=tenant_id, role_id=role.id, permission_id=permission.id, effect="allow", actor_user_id=user_id, correlation_id="anomaly-phase1f6")
    await assign_user_role(session, tenant_id=tenant_id, user_id=user_id, role_id=role.id, context_type="tenant", context_id=tenant_id, effective_from=now, effective_to=None, assigned_by=user_id, actor_user_id=user_id, correlation_id="anomaly-phase1f6")
    await session.flush()


async def seed_upstream_for_anomaly(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    created_by: uuid.UUID,
    reporting_period: date,
) -> dict[str, str]:
    ratio = await seed_upstream_ratio_run(
        session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=created_by,
        reporting_period=reporting_period,
    )
    await seed_active_risk_configuration(
        session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=created_by,
        effective_from=date(reporting_period.year, reporting_period.month, 1),
    )
    risk_service = build_financial_risk_service(session)
    risk_created = await risk_service.create_run(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        reporting_period=reporting_period,
        source_metric_run_ids=[uuid.UUID(ratio["ratio_run_id"])],
        source_variance_run_ids=[uuid.UUID(ratio["ratio_run_id"])],
        source_trend_run_ids=[uuid.UUID(ratio["ratio_run_id"])],
        source_reconciliation_session_ids=[],
        created_by=created_by,
    )
    risk_executed = await risk_service.execute_run(
        tenant_id=tenant_id, run_id=uuid.UUID(risk_created["run_id"]), actor_user_id=created_by
    )
    return {"metric_run_id": ratio["ratio_run_id"], "risk_run_id": risk_executed["run_id"]}


async def seed_active_anomaly_configuration(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    created_by: uuid.UUID,
    effective_from: date,
) -> dict[str, str]:
    repository = AnomalyPatternRepository(session)
    definition = await repository.create_anomaly_definition(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        anomaly_code=f"ANOM_PAYROLL_{uuid.uuid4().hex[:6]}",
        anomaly_name="Payroll Spike Pattern",
        anomaly_domain="payroll",
        signal_selector_json={
            "metric_codes": ["revenue", "payroll_cost"],
            "variance_codes": ["payroll_cost"],
            "trend_codes": ["payroll_growth_pct"],
            "risk_codes": [],
            "board_critical": False,
        },
        definition_json={"detector": "zscore"},
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        effective_to=None,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    pattern_rule = await repository.create_pattern_rule(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        rule_code=f"APR_{uuid.uuid4().hex[:6]}",
        rule_name="Default Pattern Rule",
        pattern_signature_json={
            "signals": ["payroll_spike", "margin_drop"],
            "window": 3,
        },
        classification_behavior_json={"default_classification": "point_anomaly"},
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    persistence_rule = await repository.create_persistence_rule(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        rule_code=f"APS_{uuid.uuid4().hex[:6]}",
        rule_name="Default Persistence Rule",
        rolling_window=3,
        recurrence_threshold=2,
        escalation_logic_json={"escalate_on_consecutive": 2},
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    correlation_rule = await repository.create_correlation_rule(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        rule_code=f"ACR_{uuid.uuid4().hex[:6]}",
        rule_name="Default Correlation Rule",
        correlation_window=3,
        min_signal_count=2,
        correlation_logic_json={"mode": "windowed_signal_count"},
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    statistical_rule = await repository.create_statistical_rule(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        rule_code=f"ASR_{uuid.uuid4().hex[:6]}",
        rule_name="Default Statistical Rule",
        rolling_window=3,
        baseline_type="rolling_mean",
        z_threshold=Decimal("1.500000"),
        regime_shift_threshold_pct=Decimal("0.150000"),
        seasonal_period=12,
        seasonal_adjustment_flag=False,
        benchmark_group_id=None,
        configuration_json={
            "moderate_z": "1.5",
            "high_z": "2.0",
            "extreme_z": "3.0",
            "material_score": "0.5",
        },
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    await session.flush()
    return {
        "anomaly_definition_id": str(definition.id),
        "pattern_rule_id": str(pattern_rule.id),
        "persistence_rule_id": str(persistence_rule.id),
        "correlation_rule_id": str(correlation_rule.id),
        "statistical_rule_id": str(statistical_rule.id),
    }
