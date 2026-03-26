from __future__ import annotations

import base64
import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from financeops.core.security import hash_password
from financeops.db.models.mis_manager import (
    MisDataSnapshot,
    MisDriftEvent,
    MisIngestionException,
    MisNormalizedLine,
    MisTemplate,
    MisTemplateVersion,
)
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.modules.mis_manager.application.canonical_dictionary_service import (
    CanonicalDictionaryService,
)
from financeops.modules.mis_manager.application.drift_detection_service import (
    DriftDetectionService,
)
from financeops.modules.mis_manager.application.ingest_service import MisIngestService
from financeops.modules.mis_manager.application.mapping_service import MappingService
from financeops.modules.mis_manager.application.snapshot_service import SnapshotService
from financeops.modules.mis_manager.application.template_detection_service import (
    TemplateDetectionService,
)
from financeops.modules.mis_manager.application.validation_service import (
    ValidationService,
)
from financeops.modules.mis_manager.infrastructure.repository import (
    MisManagerRepository,
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

MIS_TABLES: tuple[str, ...] = (
    "mis_templates",
    "mis_template_versions",
    "mis_template_sections",
    "mis_template_columns",
    "mis_template_row_mappings",
    "mis_data_snapshots",
    "mis_normalized_lines",
    "mis_ingestion_exceptions",
    "mis_drift_events",
)


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_database(raw_url: str, database: str) -> str:
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def hash64(seed: str) -> str:
    return sha256(seed.encode("utf-8")).hexdigest()


def deterministic_uuid(seed: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"mis-phase1f1:{seed}")


def csv_b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


@pytest_asyncio.fixture(scope="session")
async def mis_phase1f1_db_url() -> AsyncGenerator[str, None]:
    base_url = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    admin_db = os.getenv("TEST_DATABASE_ADMIN_DB", "postgres")
    suffix = uuid.uuid4().hex[:10]
    temp_db = f"financeops_mis_{suffix}"
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
            "alembic upgrade head failed for MIS phase1f1 temp database\n"
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
async def mis_phase1f1_engine(mis_phase1f1_db_url: str):
    engine = create_async_engine(mis_phase1f1_db_url, echo=False, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def mis_phase1f1_session(
    mis_phase1f1_engine,
) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(mis_phase1f1_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()


def build_ingest_service(session: AsyncSession) -> MisIngestService:
    dictionary_service = CanonicalDictionaryService()
    mapping_service = MappingService(dictionary_service)
    return MisIngestService(
        repository=MisManagerRepository(session),
        template_detection_service=TemplateDetectionService(DriftDetectionService()),
        mapping_service=mapping_service,
        snapshot_service=SnapshotService(mapping_service),
        validation_service=ValidationService(),
    )


async def ensure_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await set_tenant_context(session, tenant_id)


async def seed_mis_template(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID | None = None,
    template_code: str,
    template_name: str = "MIS Template",
    template_type: str = "pnl_monthly",
    created_by: uuid.UUID | None = None,
) -> MisTemplate:
    created_by = created_by or tenant_id
    organisation_id = organisation_id or tenant_id
    return await AuditWriter.insert_financial_record(
        session,
        model_class=MisTemplate,
        tenant_id=tenant_id,
        record_data={
            "template_code": template_code,
            "template_name": template_name,
            "template_type": template_type,
        },
        values={
            "organisation_id": organisation_id,
            "template_code": template_code,
            "template_name": template_name,
            "template_type": template_type,
            "description": None,
            "status": "active",
            "created_by": created_by,
            "name": template_name,
            "entity_name": str(organisation_id),
            "version": 1,
            "is_master": False,
            "is_active": True,
            "template_data": {"phase": "1f1"},
            "sheet_count": 0,
        },
    )


async def seed_mis_template_version(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    version_no: int,
    version_token_seed: str,
    structure_seed: str,
    status: str = "candidate",
    supersedes_id: uuid.UUID | None = None,
    based_on_version_id: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
    row_id: uuid.UUID | None = None,
) -> MisTemplateVersion:
    created_by = created_by or tenant_id
    return await AuditWriter.insert_financial_record(
        session,
        model_class=MisTemplateVersion,
        tenant_id=tenant_id,
        record_data={
            "template_id": str(template_id),
            "version_no": version_no,
            "version_token": hash64(version_token_seed),
        },
        values={
            "id": row_id or uuid.uuid4(),
            "template_id": template_id,
            "version_no": version_no,
            "version_token": hash64(version_token_seed),
            "based_on_version_id": based_on_version_id,
            "supersedes_id": supersedes_id,
            "structure_hash": hash64(f"{structure_seed}:structure"),
            "header_hash": hash64(f"{structure_seed}:header"),
            "row_signature_hash": hash64(f"{structure_seed}:row"),
            "column_signature_hash": hash64(f"{structure_seed}:col"),
            "detection_summary_json": {"seed": structure_seed},
            "drift_reason": None,
            "status": status,
            "effective_from": None,
            "created_by": created_by,
        },
    )


async def seed_mis_snapshot(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    template_version_id: uuid.UUID,
    reporting_period,
    snapshot_token_seed: str,
    created_by: uuid.UUID | None = None,
) -> MisDataSnapshot:
    created_by = created_by or tenant_id
    return await AuditWriter.insert_financial_record(
        session,
        model_class=MisDataSnapshot,
        tenant_id=tenant_id,
        record_data={
            "template_version_id": str(template_version_id),
            "snapshot_token": hash64(snapshot_token_seed),
        },
        values={
            "organisation_id": tenant_id,
            "template_id": template_id,
            "template_version_id": template_version_id,
            "reporting_period": reporting_period,
            "upload_artifact_id": uuid.uuid4(),
            "snapshot_token": hash64(snapshot_token_seed),
            "source_file_hash": hash64(f"{snapshot_token_seed}:file"),
            "sheet_name": "Sheet1",
            "snapshot_status": "pending",
            "validation_summary_json": {"status": "pending"},
            "created_by": created_by,
        },
    )


async def seed_mis_normalized_line(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    line_no: int,
    created_by: uuid.UUID | None = None,
) -> MisNormalizedLine:
    created_by = created_by or tenant_id
    return await AuditWriter.insert_financial_record(
        session,
        model_class=MisNormalizedLine,
        tenant_id=tenant_id,
        record_data={"snapshot_id": str(snapshot_id), "line_no": line_no},
        values={
            "snapshot_id": snapshot_id,
            "line_no": line_no,
            "canonical_metric_code": "revenue_net",
            "canonical_dimension_json": {},
            "source_row_ref": "Sheet1:r1",
            "source_column_ref": "Sheet1:Period_2026_01",
            "period_value": "100.000000",
            "currency_code": "USD",
            "sign_applied": "as_is",
            "validation_status": "valid",
            "created_by": created_by,
        },
    )


async def seed_mis_exception(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    code: str = "NON_NUMERIC_VALUE",
    created_by: uuid.UUID | None = None,
) -> MisIngestionException:
    created_by = created_by or tenant_id
    return await AuditWriter.insert_financial_record(
        session,
        model_class=MisIngestionException,
        tenant_id=tenant_id,
        record_data={"snapshot_id": str(snapshot_id), "exception_code": code},
        values={
            "snapshot_id": snapshot_id,
            "exception_code": code,
            "severity": "warning",
            "source_ref": "Sheet1:r2c3",
            "message": "warning",
            "resolution_status": "open",
            "created_by": created_by,
        },
    )


async def seed_mis_drift_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    prior_template_version_id: uuid.UUID,
    candidate_template_version_id: uuid.UUID,
    created_by: uuid.UUID | None = None,
) -> MisDriftEvent:
    created_by = created_by or tenant_id
    return await AuditWriter.insert_financial_record(
        session,
        model_class=MisDriftEvent,
        tenant_id=tenant_id,
        record_data={"template_id": str(template_id), "drift_type": "HEADER_CHANGE"},
        values={
            "template_id": template_id,
            "prior_template_version_id": prior_template_version_id,
            "candidate_template_version_id": candidate_template_version_id,
            "drift_type": "HEADER_CHANGE",
            "drift_details_json": {"before": "A", "after": "B"},
            "decision_status": "pending_review",
            "decided_by": None,
            "decided_at": None,
            "created_by": created_by,
        },
    )


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
        org_setup_complete=True,
        org_setup_step=7,
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


async def seed_control_plane_for_mis(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    enable_module: bool = True,
    grant_permissions: bool = True,
    quota_max: int = 1000,
    with_route: bool = True,
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
            "correlation_id": "mis-phase1f1",
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
        select(CpModuleRegistry).where(CpModuleRegistry.module_code == "mis_manager")
    )
    module = module_result.scalar_one_or_none()
    if module is None:
        module = CpModuleRegistry(
            module_code="mis_manager",
            module_name="MIS Manager",
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
            correlation_id="mis-phase1f1",
            effective_from=now,
            effective_to=None,
        )

    await assign_quota_to_tenant(
        session,
        tenant_id=tenant_id,
        quota_type="api_requests",
        window_type="tumbling",
        window_seconds=60,
        max_value=quota_max,
        enforcement_mode="reject",
        effective_from=now,
        effective_to=None,
        actor_user_id=user_id,
        correlation_id="mis-phase1f1",
    )

    if with_route:
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
            correlation_id="mis-phase1f1",
        )

    if not grant_permissions:
        await session.flush()
        return

    role = await create_role(
        session,
        tenant_id=tenant_id,
        role_code=f"MIS_ROLE_{uuid.uuid4().hex[:8]}",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=user_id,
        correlation_id="mis-phase1f1",
    )
    permissions = [
        ("mis_template", "mis_template_create"),
        ("mis_template_version", "mis_template_review"),
        ("mis_snapshot", "mis_snapshot_upload"),
        ("mis_snapshot", "mis_snapshot_finalize"),
        ("mis_snapshot", "mis_snapshot_view"),
        ("mis_ingestion_exception", "mis_snapshot_view"),
        ("mis_drift_event", "mis_template_review"),
        ("mis_normalized_line", "mis_snapshot_view"),
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
                description="mis phase1f1 integration permission",
            )
        await grant_role_permission(
            session,
            tenant_id=tenant_id,
            role_id=role.id,
            permission_id=permission.id,
            effect="allow",
            actor_user_id=user_id,
            correlation_id="mis-phase1f1",
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
        correlation_id="mis-phase1f1",
    )
    await session.flush()

