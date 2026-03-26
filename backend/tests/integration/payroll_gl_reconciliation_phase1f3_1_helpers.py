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

from financeops.core.security import hash_password
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.modules.payroll_gl_normalization.application.gl_normalization_service import (
    GlNormalizationService,
)
from financeops.modules.payroll_gl_normalization.application.mapping_service import (
    MappingService as NormalizationMappingService,
)
from financeops.modules.payroll_gl_normalization.application.payroll_normalization_service import (
    PayrollNormalizationService,
)
from financeops.modules.payroll_gl_normalization.application.run_service import (
    NormalizationRunService,
)
from financeops.modules.payroll_gl_normalization.application.source_detection_service import (
    SourceDetectionService,
)
from financeops.modules.payroll_gl_normalization.application.validation_service import (
    ValidationService as NormalizationValidationService,
)
from financeops.modules.payroll_gl_normalization.infrastructure.repository import (
    PayrollGlNormalizationRepository,
)
from financeops.modules.payroll_gl_reconciliation.application.classification_service import (
    ClassificationService,
)
from financeops.modules.payroll_gl_reconciliation.application.mapping_service import MappingService
from financeops.modules.payroll_gl_reconciliation.application.matching_service import (
    MatchingService,
)
from financeops.modules.payroll_gl_reconciliation.application.rule_service import RuleService
from financeops.modules.payroll_gl_reconciliation.application.run_service import (
    PayrollGlReconciliationRunService,
)
from financeops.modules.payroll_gl_reconciliation.application.validation_service import (
    ValidationService,
)
from financeops.modules.payroll_gl_reconciliation.infrastructure.repository import (
    PayrollGlReconciliationRepository,
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
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
)

PAYROLL_GL_RECON_TABLES: tuple[str, ...] = (
    "payroll_gl_reconciliation_mappings",
    "payroll_gl_reconciliation_rules",
    "payroll_gl_reconciliation_runs",
    "payroll_gl_reconciliation_run_scopes",
)


def csv_b64(text: str) -> str:
    import base64

    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_database(raw_url: str, database: str) -> str:
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(scope="session")
async def payroll_gl_recon_phase1f3_1_db_url() -> AsyncGenerator[str, None]:
    base_url = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
    admin_db = os.getenv("TEST_DATABASE_ADMIN_DB", "postgres")
    suffix = uuid.uuid4().hex[:10]
    temp_db = f"financeops_payglrecon_{suffix}"
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
            "alembic upgrade head failed for payroll-gl reconciliation phase1f3_1 temp database\n"
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
async def payroll_gl_recon_phase1f3_1_engine(payroll_gl_recon_phase1f3_1_db_url: str):
    engine = create_async_engine(
        payroll_gl_recon_phase1f3_1_db_url, echo=False, poolclass=NullPool
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def payroll_gl_recon_phase1f3_1_session(
    payroll_gl_recon_phase1f3_1_engine,
) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        payroll_gl_recon_phase1f3_1_engine, expire_on_commit=False
    )
    async with session_factory() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()


def build_payroll_gl_reconciliation_service(
    session: AsyncSession,
) -> PayrollGlReconciliationRunService:
    return PayrollGlReconciliationRunService(
        repository=PayrollGlReconciliationRepository(session),
        mapping_service=MappingService(),
        rule_service=RuleService(),
        matching_service=MatchingService(),
        classification_service=ClassificationService(),
        validation_service=ValidationService(),
    )


def build_normalization_service(session: AsyncSession) -> NormalizationRunService:
    return NormalizationRunService(
        repository=PayrollGlNormalizationRepository(session),
        source_detection_service=SourceDetectionService(),
        mapping_service=NormalizationMappingService(),
        payroll_normalization_service=PayrollNormalizationService(),
        gl_normalization_service=GlNormalizationService(),
        validation_service=NormalizationValidationService(),
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


async def seed_control_plane_for_payroll_gl_reconciliation(
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
            "correlation_id": "payroll-gl-recon-phase1f3_1",
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
            CpModuleRegistry.module_code == "payroll_gl_reconciliation"
        )
    )
    module = module_result.scalar_one_or_none()
    if module is None:
        module = CpModuleRegistry(
            module_code="payroll_gl_reconciliation",
            module_name="Payroll GL Reconciliation",
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
            correlation_id="payroll-gl-recon-phase1f3_1",
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
        correlation_id="payroll-gl-recon-phase1f3_1",
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
        correlation_id="payroll-gl-recon-phase1f3_1",
    )
    if not grant_permissions:
        await session.flush()
        return
    role = await create_role(
        session,
        tenant_id=tenant_id,
        role_code=f"PAYGL_RECON_ROLE_{uuid.uuid4().hex[:8]}",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=user_id,
        correlation_id="payroll-gl-recon-phase1f3_1",
    )
    permissions = [
        ("payroll_gl_reconciliation_run", "payroll_gl_reconciliation_run"),
        ("payroll_gl_reconciliation_run", "payroll_gl_reconciliation_view"),
        (
            "payroll_gl_reconciliation_mapping",
            "payroll_gl_reconciliation_mapping_manage",
        ),
        ("payroll_gl_reconciliation_rule", "payroll_gl_reconciliation_rule_manage"),
        (
            "reconciliation_exception",
            "payroll_gl_reconciliation_exception_resolve",
        ),
        ("reconciliation_evidence_link", "payroll_gl_reconciliation_evidence_attach"),
        ("reconciliation_line", "payroll_gl_reconciliation_view"),
        ("reconciliation_exception", "payroll_gl_reconciliation_view"),
        ("payroll_gl_reconciliation_mapping", "payroll_gl_reconciliation_view"),
        ("payroll_gl_reconciliation_rule", "payroll_gl_reconciliation_view"),
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
                description="payroll_gl_reconciliation phase1f3_1 integration permission",
            )
        await grant_role_permission(
            session,
            tenant_id=tenant_id,
            role_id=role.id,
            permission_id=permission.id,
            effect="allow",
            actor_user_id=user_id,
            correlation_id="payroll-gl-recon-phase1f3_1",
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
        correlation_id="payroll-gl-recon-phase1f3_1",
    )
    await session.flush()


async def seed_finalized_normalization_pair(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    created_by: uuid.UUID,
    reporting_period: date,
) -> dict[str, str]:
    service = build_normalization_service(session)
    payroll_source = await service.commit_source_version(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        source_family="payroll",
        source_code=f"payroll_src_{uuid.uuid4().hex[:8]}",
        source_name="Payroll Source",
        structure_hash="a" * 64,
        header_hash="b" * 64,
        row_signature_hash="c" * 64,
        source_detection_summary_json={
            "headers": [
                "Employee ID",
                "Employee Name",
                "Gross Pay",
                "Net Pay",
                "Employer PF",
                "Currency",
                "Legal Entity",
                "Department",
                "Cost Center",
            ]
        },
        activate=True,
        created_by=created_by,
    )
    payroll_uploaded = await service.upload_run(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        source_id=uuid.UUID(payroll_source["source_id"]),
        source_version_id=uuid.UUID(payroll_source["source_version_id"]),
        run_type="payroll_normalization",
        reporting_period=reporting_period,
        source_artifact_id=uuid.uuid4(),
        file_name="payroll.csv",
        file_content_base64=csv_b64(
            "Employee ID,Employee Name,Gross Pay,Net Pay,Employer PF,Currency,Legal Entity,Department,Cost Center\n"
            "E001,Alice,1000,800,120,USD,LE1,Ops,CC1\n"
        ),
        sheet_name="csv",
        created_by=created_by,
    )
    payroll_validated = await service.validate_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(payroll_uploaded["run_id"]),
        created_by=created_by,
    )
    payroll_finalized = await service.finalize_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(payroll_validated["run_id"]),
        created_by=created_by,
    )

    gl_source = await service.commit_source_version(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        source_family="gl",
        source_code=f"gl_src_{uuid.uuid4().hex[:8]}",
        source_name="GL Source",
        structure_hash="d" * 64,
        header_hash="e" * 64,
        row_signature_hash="f" * 64,
        source_detection_summary_json={
            "headers": [
                "Account Code",
                "Debit",
                "Credit",
                "Currency",
                "Posting Date",
                "Legal Entity",
                "Department",
                "Cost Center",
            ]
        },
        activate=True,
        created_by=created_by,
    )
    gl_uploaded = await service.upload_run(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        source_id=uuid.UUID(gl_source["source_id"]),
        source_version_id=uuid.UUID(gl_source["source_version_id"]),
        run_type="gl_normalization",
        reporting_period=reporting_period,
        source_artifact_id=uuid.uuid4(),
        file_name="gl.csv",
        file_content_base64=csv_b64(
            "Account Code,Debit,Credit,Currency,Posting Date,Legal Entity,Department,Cost Center\n"
            "5000,1000,0,USD,2026-01-31,LE1,Ops,CC1\n"
            "2100,120,0,USD,2026-01-31,LE1,Ops,CC1\n"
            "2200,800,0,USD,2026-01-31,LE1,Ops,CC1\n"
        ),
        sheet_name="csv",
        created_by=created_by,
    )
    gl_validated = await service.validate_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(gl_uploaded["run_id"]),
        created_by=created_by,
    )
    gl_finalized = await service.finalize_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(gl_validated["run_id"]),
        created_by=created_by,
    )
    return {
        "payroll_run_id": payroll_finalized["run_id"],
        "gl_run_id": gl_finalized["run_id"],
        "reporting_period": reporting_period.isoformat(),
    }


async def seed_mapping_and_rule(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    created_by: uuid.UUID,
    effective_from: date,
) -> None:
    repo = PayrollGlReconciliationRepository(session)
    await repo.create_mapping(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        mapping_code=f"MAP_GROSS_{uuid.uuid4().hex[:6]}",
        mapping_name="Gross to Salary",
        payroll_metric_code="gross_pay",
        gl_account_selector_json={"account_codes": ["5000"]},
        cost_center_rule_json={"mode": "strict"},
        department_rule_json={"mode": "strict"},
        entity_rule_json={"mode": "strict"},
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    await repo.create_mapping(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        mapping_code=f"MAP_NET_{uuid.uuid4().hex[:6]}",
        mapping_name="Net Pay to Clearing",
        payroll_metric_code="net_pay",
        gl_account_selector_json={"account_codes": ["2200"]},
        cost_center_rule_json={"mode": "strict"},
        department_rule_json={"mode": "strict"},
        entity_rule_json={"mode": "strict"},
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    await repo.create_mapping(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        mapping_code=f"MAP_PF_{uuid.uuid4().hex[:6]}",
        mapping_name="Employer PF to Liability",
        payroll_metric_code="employer_pf",
        gl_account_selector_json={"account_codes": ["2100"]},
        cost_center_rule_json={"mode": "strict"},
        department_rule_json={"mode": "strict"},
        entity_rule_json={"mode": "strict"},
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    await repo.create_rule(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        rule_code=f"RULE_PAYGL_{uuid.uuid4().hex[:6]}",
        rule_name="Payroll GL Baseline Rule",
        rule_type="aggregate_tie_rule",
        tolerance_json={"absolute_threshold": "1", "percentage_threshold": "0.10"},
        materiality_json={
            "absolute_threshold": "10",
            "percentage_threshold": "0.25",
            "statutory_metrics": ["employer_pf", "employer_esi", "payroll_tax"],
            "rounding_threshold": "1",
        },
        timing_window_json={"max_lag_days": 5},
        classification_behavior_json={"default_difference_type": "value_mismatch"},
        effective_from=effective_from,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )


