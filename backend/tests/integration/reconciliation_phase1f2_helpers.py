from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from financeops.core.security import hash_password
from financeops.db.models.reconciliation import GlEntry, TrialBalanceRow
from financeops.db.models.reconciliation_bridge import (
    ReconciliationLine,
    ReconciliationSession,
)
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.modules.reconciliation_bridge.application.exception_classification_service import (
    ExceptionClassificationService,
)
from financeops.modules.reconciliation_bridge.application.matching_service import (
    MatchingService,
)
from financeops.modules.reconciliation_bridge.application.run_service import (
    ReconciliationRunService,
)
from financeops.modules.reconciliation_bridge.infrastructure.repository import (
    ReconciliationBridgeRepository,
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
from financeops.platform.services.rbac.role_service import (
    assign_user_role,
    create_role,
)
from financeops.platform.services.tenancy.module_enablement import set_module_enablement
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
)

RECON_TABLES: tuple[str, ...] = (
    "reconciliation_sessions",
    "reconciliation_scopes",
    "reconciliation_lines",
    "reconciliation_exceptions",
    "reconciliation_resolution_events",
    "reconciliation_evidence_links",
)


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_database(raw_url: str, database: str) -> str:
    parts = urlsplit(raw_url)
    return urlunsplit(
        (parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment)
    )


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def hash64(seed: str) -> str:
    return sha256(seed.encode("utf-8")).hexdigest()


def deterministic_uuid(seed: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"recon-phase1f2:{seed}")


@pytest_asyncio.fixture(scope="session")
async def recon_phase1f2_db_url() -> AsyncGenerator[str, None]:
    base_url = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    admin_db = os.getenv("TEST_DATABASE_ADMIN_DB", "postgres")
    suffix = uuid.uuid4().hex[:10]
    temp_db = f"financeops_recon_{suffix}"
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
            "alembic upgrade head failed for reconciliation phase1f2 temp database\n"
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
async def recon_phase1f2_engine(recon_phase1f2_db_url: str):
    engine = create_async_engine(recon_phase1f2_db_url, echo=False, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def recon_phase1f2_session(
    recon_phase1f2_engine,
) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(recon_phase1f2_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()


def build_reconciliation_service(session: AsyncSession) -> ReconciliationRunService:
    return ReconciliationRunService(
        repository=ReconciliationBridgeRepository(session),
        matching_service=MatchingService(),
        exception_classification_service=ExceptionClassificationService(),
    )


async def ensure_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await set_tenant_context(session, tenant_id)


async def seed_identity_user(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    email: str,
    role: UserRole = UserRole.finance_leader,
) -> IamUser:
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name=f"Tenant {str(tenant_id)[:8]}",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=compute_chain_hash(
            {
                "display_name": f"Tenant {str(tenant_id)[:8]}",
                "tenant_type": TenantType.direct.value,
                "country": "US",
                "timezone": "UTC",
            },
            GENESIS_HASH,
        ),
        previous_hash=GENESIS_HASH,
    )
    session.add(tenant)
    user = IamUser(
        id=user_id,
        tenant_id=tenant_id,
        email=email,
        hashed_password=hash_password("TestPass123!"),
        full_name=email.split("@")[0],
        role=role,
        is_active=True,
        mfa_enabled=False,
    )
    session.add(user)
    await session.flush()
    return user


async def seed_control_plane_for_reconciliation_bridge(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    enable_module: bool = True,
    grant_permissions: bool = True,
    quota_max: int = 1000,
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
            "correlation_id": "recon-phase1f2",
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
        select(CpModuleRegistry).where(
            CpModuleRegistry.module_code == "reconciliation_bridge"
        )
    )
    module = module_result.scalar_one_or_none()
    if module is None:
        module = CpModuleRegistry(
            module_code="reconciliation_bridge",
            module_name="Reconciliation Bridge",
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
            correlation_id="recon-phase1f2",
            effective_from=now,
            effective_to=None,
        )

    await assign_quota_to_tenant(
        session,
        tenant_id=tenant_id,
        quota_type="api_requests",
        window_type="sliding",
        window_seconds=60,
        max_value=quota_max,
        enforcement_mode="reject",
        effective_from=now,
        effective_to=None,
        actor_user_id=user_id,
        correlation_id="recon-phase1f2",
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
        correlation_id="recon-phase1f2",
    )

    if not grant_permissions:
        await session.flush()
        return

    role = await create_role(
        session,
        tenant_id=tenant_id,
        role_code=f"RECON_ROLE_{uuid.uuid4().hex[:8]}",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=user_id,
        correlation_id="recon-phase1f2",
    )
    permissions = [
        ("reconciliation_session", "reconciliation_session_create"),
        ("reconciliation_session", "reconciliation_run"),
        ("reconciliation_session", "reconciliation_view"),
        ("reconciliation_line", "reconciliation_view"),
        ("reconciliation_line", "reconciliation_review"),
        ("reconciliation_exception", "reconciliation_view"),
        ("reconciliation_exception", "reconciliation_exception_resolve"),
        ("reconciliation_evidence_link", "reconciliation_evidence_attach"),
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
                description="reconciliation phase1f2 integration permission",
            )
        await grant_role_permission(
            session,
            tenant_id=tenant_id,
            role_id=role.id,
            permission_id=permission.id,
            effect="allow",
            actor_user_id=user_id,
            correlation_id="recon-phase1f2",
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
        correlation_id="recon-phase1f2",
    )
    await session.flush()


async def seed_gl_tb_pair(
    session: AsyncSession, *, tenant_id: uuid.UUID, created_by: uuid.UUID
) -> tuple[GlEntry, TrialBalanceRow]:
    gl = await AuditWriter.insert_financial_record(
        session,
        model_class=GlEntry,
        tenant_id=tenant_id,
        record_data={
            "account_code": "4000",
            "period_year": 2026,
            "period_month": 1,
        },
        values={
            "period_year": 2026,
            "period_month": 1,
            "entity_name": "HQ",
            "account_code": "4000",
            "account_name": "Revenue",
            "debit_amount": Decimal("1000"),
            "credit_amount": Decimal("0"),
            "description": "seed",
            "source_ref": "seed",
            "currency": "USD",
            "uploaded_by": created_by,
        },
    )
    tb = await AuditWriter.insert_financial_record(
        session,
        model_class=TrialBalanceRow,
        tenant_id=tenant_id,
        record_data={
            "account_code": "4000",
            "period_year": 2026,
            "period_month": 1,
        },
        values={
            "period_year": 2026,
            "period_month": 1,
            "entity_name": "HQ",
            "account_code": "4000",
            "account_name": "Revenue",
            "opening_balance": Decimal("0"),
            "period_debit": Decimal("0"),
            "period_credit": Decimal("0"),
            "closing_balance": Decimal("950"),
            "currency": "USD",
            "uploaded_by": created_by,
        },
    )
    return gl, tb


async def seed_recon_session(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    created_by: uuid.UUID,
    token_seed: str,
) -> ReconciliationSession:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=ReconciliationSession,
        tenant_id=tenant_id,
        record_data={"session_token": hash64(token_seed)},
        values={
            "organisation_id": organisation_id,
            "reconciliation_type": "gl_vs_trial_balance",
            "source_a_type": "gl_entries",
            "source_a_ref": "seed_gl",
            "source_b_type": "trial_balance_rows",
            "source_b_ref": "seed_tb",
            "period_start": datetime(2026, 1, 1, tzinfo=UTC).date(),
            "period_end": datetime(2026, 1, 31, tzinfo=UTC).date(),
            "matching_rule_version": "recon_match_v1",
            "tolerance_rule_version": "recon_tolerance_v1",
            "session_token": hash64(token_seed),
            "materiality_config_json": {"absolute_threshold": "0"},
            "status": "created",
            "created_by": created_by,
        },
    )


async def seed_recon_line(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    session_id: uuid.UUID,
    created_by: uuid.UUID,
    line_key: str,
) -> ReconciliationLine:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=ReconciliationLine,
        tenant_id=tenant_id,
        record_data={"session_id": str(session_id), "line_key": line_key},
        values={
            "session_id": session_id,
            "scope_id": None,
            "line_key": line_key,
            "comparison_dimension_json": {
                "account": "4000",
                "entity": "HQ",
                "period": "2026-01",
                "currency_code": "USD",
            },
            "source_a_value": Decimal("1000"),
            "source_b_value": Decimal("950"),
            "variance_value": Decimal("50"),
            "variance_abs": Decimal("50"),
            "variance_pct": Decimal("5.263158"),
            "currency_code": "USD",
            "reconciliation_status": "exception",
            "difference_type": "value_mismatch",
            "materiality_flag": True,
            "explanation_hint": "review_required",
            "created_by": created_by,
        },
    )

