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
from financeops.modules.board_pack_narrative_engine.application.inclusion_service import (
    InclusionService,
)
from financeops.modules.board_pack_narrative_engine.application.narrative_service import (
    NarrativeService,
)
from financeops.modules.board_pack_narrative_engine.application.run_service import RunService
from financeops.modules.board_pack_narrative_engine.application.section_service import (
    SectionService,
)
from financeops.modules.board_pack_narrative_engine.application.validation_service import (
    ValidationService,
)
from financeops.modules.board_pack_narrative_engine.infrastructure.repository import (
    BoardPackNarrativeRepository,
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
from tests.integration.anomaly_pattern_phase1f6_helpers import (
    build_anomaly_service,
    seed_active_anomaly_configuration,
    seed_upstream_for_anomaly,
)
from tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers import seed_identity_user

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
)

BOARD_PACK_TABLES: tuple[str, ...] = (
    "board_pack_definitions",
    "board_pack_section_definitions",
    "narrative_templates",
    "board_pack_inclusion_rules",
    "board_pack_runs",
    "board_pack_results",
    "board_pack_section_results",
    "board_pack_narrative_blocks",
    "board_pack_evidence_links",
)


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_database(raw_url: str, database: str) -> str:
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(scope="session")
async def board_pack_phase1f7_db_url() -> AsyncGenerator[str, None]:
    base_url = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    admin_db = os.getenv("TEST_DATABASE_ADMIN_DB", "postgres")
    suffix = uuid.uuid4().hex[:10]
    temp_db = f"financeops_boardpack_{suffix}"
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
            "alembic upgrade head failed for board pack phase1f7 temp database\n"
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
async def board_pack_phase1f7_engine(board_pack_phase1f7_db_url: str):
    engine = create_async_engine(board_pack_phase1f7_db_url, echo=False, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def board_pack_phase1f7_session(
    board_pack_phase1f7_engine,
) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(board_pack_phase1f7_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()


def build_board_pack_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=BoardPackNarrativeRepository(session),
        validation_service=ValidationService(),
        inclusion_service=InclusionService(),
        section_service=SectionService(),
        narrative_service=NarrativeService(),
    )


async def ensure_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await set_tenant_context(session, tenant_id)


async def seed_control_plane_for_board_pack(
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
            "correlation_id": "board-pack-phase1f7",
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
        await session.execute(
            select(CpModuleRegistry).where(
                CpModuleRegistry.module_code == "board_pack_narrative_engine"
            )
        )
    ).scalar_one_or_none()
    if module is None:
        module = CpModuleRegistry(
            module_code="board_pack_narrative_engine",
            module_name="Board Pack Narrative Engine",
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
            correlation_id="board-pack-phase1f7",
            effective_from=now,
            effective_to=None,
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
        correlation_id="board-pack-phase1f7",
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
        correlation_id="board-pack-phase1f7",
    )

    if not grant_permissions:
        await session.flush()
        return

    role = await create_role(
        session,
        tenant_id=tenant_id,
        role_code=f"BOARD_PACK_ROLE_{uuid.uuid4().hex[:8]}",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=user_id,
        correlation_id="board-pack-phase1f7",
    )
    permissions = [
        ("board_pack_run", "board_pack_run"),
        ("board_pack_run", "board_pack_view"),
        ("board_pack_definition", "board_pack_definition_manage"),
        ("board_pack_definition", "board_pack_view"),
        ("board_pack_section_definition", "board_pack_section_manage"),
        ("board_pack_section_definition", "board_pack_view"),
        ("narrative_template", "board_pack_template_manage"),
        ("narrative_template", "board_pack_view"),
        ("board_pack_inclusion_rule", "board_pack_inclusion_rule_manage"),
        ("board_pack_inclusion_rule", "board_pack_view"),
        ("board_pack_result", "board_pack_view"),
        ("board_pack_section_result", "board_pack_view"),
        ("board_pack_narrative_block", "board_pack_view"),
        ("board_pack_evidence_link", "board_pack_evidence_view"),
    ]
    for resource_type, action in permissions:
        permission = (
            await session.execute(
                select(CpPermission).where(
                    CpPermission.resource_type == resource_type,
                    CpPermission.action == action,
                )
            )
        ).scalars().first()
        if permission is None:
            permission = await create_permission(
                session,
                actor_tenant_id=tenant_id,
                actor_user_id=user_id,
                permission_code=f"{resource_type}.{action}.global",
                resource_type=resource_type,
                action=action,
                description="board pack phase1f7 integration permission",
            )
        await grant_role_permission(
            session,
            tenant_id=tenant_id,
            role_id=role.id,
            permission_id=permission.id,
            effect="allow",
            actor_user_id=user_id,
            correlation_id="board-pack-phase1f7",
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
        correlation_id="board-pack-phase1f7",
    )
    await session.flush()


async def seed_upstream_for_board_pack(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    created_by: uuid.UUID,
    reporting_period: date,
) -> dict[str, str]:
    upstream = await seed_upstream_for_anomaly(
        session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=created_by,
        reporting_period=reporting_period,
    )
    await seed_active_anomaly_configuration(
        session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=created_by,
        effective_from=date(reporting_period.year, reporting_period.month, 1),
    )
    anomaly_service = build_anomaly_service(session)
    created = await anomaly_service.create_run(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        reporting_period=reporting_period,
        source_metric_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_variance_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_trend_run_ids=[uuid.UUID(upstream["metric_run_id"])],
        source_risk_run_ids=[uuid.UUID(upstream["risk_run_id"])],
        source_reconciliation_session_ids=[],
        created_by=created_by,
    )
    executed = await anomaly_service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(created["run_id"]),
        actor_user_id=created_by,
    )
    return {
        "metric_run_id": upstream["metric_run_id"],
        "risk_run_id": upstream["risk_run_id"],
        "anomaly_run_id": executed["run_id"],
    }


async def seed_active_board_pack_configuration(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    created_by: uuid.UUID,
    effective_from: date,
) -> dict[str, str]:
    repository = BoardPackNarrativeRepository(session)
    definition = await repository.create_board_pack_definition(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        board_pack_code=f"monthly_board_pack_{uuid.uuid4().hex[:6]}",
        board_pack_name="Monthly Board Pack",
        audience_scope="board",
        section_order_json={
            "executive_summary": 1,
            "financial_performance": 2,
            "key_risks": 3,
            "anomaly_watchlist": 4,
        },
        inclusion_config_json={"top_limit": 5},
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        effective_to=None,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    sections = []
    for order, section in enumerate(
        (
            ("executive_summary", "Executive Summary", "executive_summary"),
            ("financial_performance", "Financial Performance", "financial_performance"),
            ("key_risks", "Key Risks", "key_risks"),
            ("anomaly_watchlist", "Anomaly Watchlist", "anomaly_watchlist"),
        ),
        start=1,
    ):
        section_row = await repository.create_section_definition(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            section_code=section[0],
            section_name=section[1],
            section_type=section[2],
            render_logic_json={},
            section_order_default=order,
            narrative_template_ref=section[0],
            risk_inclusion_rule_json={},
            anomaly_inclusion_rule_json={},
            metric_inclusion_rule_json={},
            version_token=uuid.uuid4().hex,
            effective_from=effective_from,
            effective_to=None,
            supersedes_id=None,
            status="active",
            created_by=created_by,
        )
        sections.append(section_row)
    templates = []
    for code, template_type in (
        ("executive_summary", "executive_summary_template"),
        ("financial_performance", "metric_commentary_template"),
        ("key_risks", "risk_commentary_template"),
        ("anomaly_watchlist", "anomaly_commentary_template"),
    ):
        template = await repository.create_narrative_template(
            tenant_id=tenant_id,
            organisation_id=organisation_id,
            template_code=code,
            template_name=f"{code} template",
            template_type=template_type,
            template_text="{section_title}: {section_summary_text}",
            template_body_json={},
            placeholder_schema_json={},
            version_token=uuid.uuid4().hex,
            effective_from=effective_from,
            effective_to=None,
            supersedes_id=None,
            status="active",
            created_by=created_by,
        )
        templates.append(template)
    rule = await repository.create_inclusion_rule(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        rule_code=f"RULE_{uuid.uuid4().hex[:6]}",
        rule_name="Default Inclusion",
        rule_type="top_severity_issues",
        inclusion_logic_json={"top_limit": 5},
        version_token=uuid.uuid4().hex,
        effective_from=effective_from,
        effective_to=None,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    await session.flush()
    return {
        "board_pack_definition_id": str(definition.id),
        "section_definition_id": str(sections[0].id),
        "narrative_template_id": str(templates[0].id),
        "inclusion_rule_id": str(rule.id),
    }
