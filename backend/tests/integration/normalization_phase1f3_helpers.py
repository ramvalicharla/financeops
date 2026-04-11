from __future__ import annotations

import base64
import hashlib
import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timezone
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from financeops.core.governance.airlock import AirlockActor, AirlockAdmissionService
from financeops.core.intent.context import MutationContext, governed_mutation_context
from financeops.core.intent.enums import JobRunnerType, JobStatus, IntentStatus
from financeops.core.security import hash_password
from financeops.db.models.intent_pipeline import CanonicalIntent, CanonicalJob
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.rls import set_tenant_context
from financeops.db.models.payroll_gl_normalization import (
    NormalizationSource,
    NormalizationSourceVersion,
)
from financeops.modules.payroll_gl_normalization.application.gl_normalization_service import (
    GlNormalizationService,
)
from financeops.modules.payroll_gl_normalization.application.mapping_service import (
    MappingService,
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
    ValidationService,
)
from financeops.modules.payroll_gl_normalization.infrastructure.repository import (
    PayrollGlNormalizationRepository,
)
from financeops.platform.db.models.modules import CpModuleRegistry
from financeops.platform.db.models.organisations import CpOrganisation
from financeops.platform.db.models.permissions import CpPermission
from financeops.platform.db.models.tenants import CpTenant
from financeops.platform.db.models.entities import CpEntity
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
from tests.integration.temp_db_helpers import (
    create_migrated_temp_database,
    drop_temp_database,
)
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
)

NORMALIZATION_TABLES: tuple[str, ...] = (
    "normalization_sources",
    "normalization_source_versions",
    "normalization_mappings",
    "normalization_runs",
    "payroll_normalized_lines",
    "gl_normalized_lines",
    "normalization_exceptions",
    "normalization_evidence_links",
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


def csv_b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


@pytest_asyncio.fixture(scope="session")
async def normalization_phase1f3_db_url() -> AsyncGenerator[str, None]:
    target_url, temp_db, admin_url = await create_migrated_temp_database(
        prefix="financeops_norm",
        error_context="normalization phase1f3 temp database",
    )

    try:
        yield target_url
    finally:
        await drop_temp_database(admin_url=admin_url, database_name=temp_db)


@pytest_asyncio.fixture(scope="session")
async def normalization_phase1f3_engine(normalization_phase1f3_db_url: str):
    engine = create_async_engine(normalization_phase1f3_db_url, echo=False, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def normalization_phase1f3_session(
    normalization_phase1f3_engine,
) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(normalization_phase1f3_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()


def build_normalization_service(session: AsyncSession) -> NormalizationRunService:
    service = NormalizationRunService(
        repository=PayrollGlNormalizationRepository(session),
        source_detection_service=SourceDetectionService(),
        mapping_service=MappingService(),
        payroll_normalization_service=PayrollNormalizationService(),
        gl_normalization_service=GlNormalizationService(),
        validation_service=ValidationService(),
    )
    raw_upload_run = service.upload_run

    async def governed_upload_run(**kwargs):
        created_by = uuid.UUID(str(kwargs["created_by"]))
        user = (
            await session.execute(select(IamUser).where(IamUser.id == created_by))
        ).scalar_one_or_none()
        if user is None:
            user = await seed_identity_user(
                session,
                tenant_id=kwargs["tenant_id"],
                user_id=created_by,
                email=f"{created_by.hex[:12]}@example.com",
            )
        admitted_airlock_item_id = kwargs.get("admitted_airlock_item_id")
        if admitted_airlock_item_id is None:
            import base64

            actor = AirlockActor(user_id=user.id, tenant_id=kwargs["tenant_id"], role=user.role.value)
            airlock_service = AirlockAdmissionService()
            submitted = await airlock_service.submit_external_input(
                session,
                source_type=str(kwargs.get("source_type") or "normalization_upload"),
                actor=actor,
                metadata={
                    "source_id": str(kwargs["source_id"]),
                    "source_version_id": str(kwargs["source_version_id"]),
                    "run_type": str(kwargs["run_type"]),
                    "reporting_period": str(kwargs["reporting_period"]),
                },
                content=base64.b64decode(str(kwargs["file_content_base64"])),
                file_name=str(kwargs["file_name"]),
                source_reference=str(kwargs.get("source_external_ref") or kwargs["source_id"]),
                idempotency_key=hashlib.sha256(
                    (
                        f"{kwargs['tenant_id']}:{kwargs['source_id']}:{kwargs['source_version_id']}:"
                        f"{kwargs['reporting_period']}:{kwargs['file_name']}"
                    ).encode("utf-8")
                ).hexdigest(),
            )
            admitted = await airlock_service.admit_airlock_item(
                session,
                item_id=submitted.item_id,
                actor=actor,
            )
            admitted_airlock_item_id = admitted.item_id
        kwargs.setdefault("source_type", "normalization_upload")
        kwargs.setdefault("source_external_ref", str(kwargs["source_id"]))
        kwargs["admitted_airlock_item_id"] = admitted_airlock_item_id
        mutation_context = await _create_test_mutation_context(
            session,
            tenant_id=kwargs["tenant_id"],
            actor_user_id=user.id,
            actor_role=user.role.value,
            module_key="normalization",
            intent_type="TEST_NORMALIZATION_UPLOAD",
        )
        with governed_mutation_context(
            mutation_context
        ):
            return await raw_upload_run(**kwargs)

    service.upload_run = governed_upload_run  # type: ignore[method-assign]
    return service


async def ensure_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await set_tenant_context(session, tenant_id)


async def seed_normalization_source(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    organisation_id: uuid.UUID,
    source_family: str,
    source_code: str,
    source_name: str,
    created_by: uuid.UUID,
) -> NormalizationSource:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizationSource,
        tenant_id=tenant_id,
        record_data={"source_code": source_code, "source_family": source_family},
        values={
            "organisation_id": organisation_id,
            "source_family": source_family,
            "source_code": source_code,
            "source_name": source_name,
            "status": "active",
            "created_by": created_by,
        },
    )


async def seed_normalization_source_version(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    source_id: uuid.UUID,
    version_no: int,
    version_token_seed: str,
    structure_seed: str,
    status: str = "candidate",
    supersedes_id: uuid.UUID | None = None,
    row_id: uuid.UUID | None = None,
    created_by: uuid.UUID,
) -> NormalizationSourceVersion:
    return await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizationSourceVersion,
        tenant_id=tenant_id,
        record_data={"source_id": str(source_id), "version_no": version_no},
        values={
            "id": row_id,
            "source_id": source_id,
            "version_no": version_no,
            "version_token": hash64(f"{version_token_seed}:token"),
            "structure_hash": hash64(f"{structure_seed}:structure"),
            "header_hash": hash64(f"{structure_seed}:header"),
            "row_signature_hash": hash64(f"{structure_seed}:row"),
            "source_detection_summary_json": {
                "headers": ["Employee ID", "Gross Pay", "Currency"]
            },
            "supersedes_id": supersedes_id,
            "status": status,
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


async def _ensure_intent_scope(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> tuple[CpOrganisation, CpEntity]:
    organisation = (
        await session.execute(
            select(CpOrganisation).where(CpOrganisation.tenant_id == tenant_id)
        )
    ).scalars().first()
    if organisation is None:
        organisation = await AuditWriter.insert_financial_record(
            session,
            model_class=CpOrganisation,
            tenant_id=tenant_id,
            record_data={"organisation_code": f"ORG-{str(tenant_id)[:8]}"},
            values={
                "organisation_code": f"ORG-{str(tenant_id)[:8]}",
                "organisation_name": "Normalization Test Org",
                "parent_organisation_id": None,
                "supersedes_id": None,
                "is_active": True,
                "correlation_id": "normalization-phase2-1-test",
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=actor_user_id,
                action="platform.test.cp_org.seed",
                resource_type="cp_organisation",
            ),
        )
    entity = (
        await session.execute(
            select(CpEntity).where(CpEntity.tenant_id == tenant_id)
        )
    ).scalars().first()
    if entity is None:
        entity = await AuditWriter.insert_financial_record(
            session,
            model_class=CpEntity,
            tenant_id=tenant_id,
            record_data={"entity_code": f"ENT-{str(tenant_id)[:8]}"},
            values={
                "entity_code": f"ENT-{str(tenant_id)[:8]}",
                "entity_name": "Normalization Test Entity",
                "organisation_id": organisation.id,
                "group_id": None,
                "base_currency": "USD",
                "country_code": "US",
                "status": "active",
                "correlation_id": "normalization-phase2-1-test",
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=actor_user_id,
                action="platform.test.cp_entity.seed",
                resource_type="cp_entity",
            ),
        )
    return organisation, entity


async def _create_test_mutation_context(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    module_key: str,
    intent_type: str,
) -> MutationContext:
    organisation, entity = await _ensure_intent_scope(
        session,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
    )
    now = datetime.now(timezone.utc)
    intent = CanonicalIntent(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        org_id=organisation.id,
        entity_id=entity.id,
        intent_type=intent_type,
        module_key=module_key,
        target_type="test_request",
        target_id=None,
        status=IntentStatus.APPROVED.value,
        requested_by_user_id=actor_user_id,
        requested_by_role=actor_role,
        requested_at=now,
        approved_at=now,
        payload_json={},
        idempotency_key=uuid.uuid4().hex,
        source_channel="test",
    )
    session.add(intent)
    await session.flush()
    job = CanonicalJob(
        id=uuid.uuid4(),
        intent_id=intent.id,
        job_type=intent_type,
        status=JobStatus.RUNNING.value,
        runner_type=JobRunnerType.INLINE.value,
        queue_name="test-governed-mutations",
        idempotency_key=intent.idempotency_key,
        requested_at=now,
        retry_count=0,
        max_retries=0,
    )
    session.add(job)
    await session.flush()
    return MutationContext(
        intent_id=intent.id,
        job_id=job.id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        intent_type=intent_type,
    )


async def seed_control_plane_for_normalization(
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
            "correlation_id": "normalization-phase1f3",
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
            CpModuleRegistry.module_code == "payroll_gl_normalization"
        )
    )
    module = module_result.scalar_one_or_none()
    if module is None:
        module = CpModuleRegistry(
            module_code="payroll_gl_normalization",
            module_name="Payroll GL Normalization",
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
            correlation_id="normalization-phase1f3",
            effective_from=now,
            effective_to=None,
        )
        await grant_boolean_entitlement(
            session,
            tenant_id=tenant_id,
            feature_name="payroll_gl_normalization",
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
        correlation_id="normalization-phase1f3",
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
        correlation_id="normalization-phase1f3",
    )
    if not grant_permissions:
        await session.flush()
        return
    role = await create_role(
        session,
        tenant_id=tenant_id,
        role_code=f"NORM_ROLE_{uuid.uuid4().hex[:8]}",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=user_id,
        correlation_id="normalization-phase1f3",
    )
    permissions = [
        ("normalization_source", "normalization_source_create"),
        ("normalization_mapping", "normalization_mapping_review"),
        ("normalization_run", "normalization_run_create"),
        ("normalization_run", "normalization_run_view"),
        ("normalization_run", "normalization_extract_view"),
        ("normalization_exception", "normalization_exception_resolve"),
        ("payroll_normalized_line", "normalization_extract_view"),
        ("gl_normalized_line", "normalization_extract_view"),
        ("normalization_source", "normalization_extract_view"),
        ("normalization_source_version", "normalization_extract_view"),
        ("normalization_exception", "normalization_run_view"),
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
                description="normalization phase1f3 integration permission",
            )
        await grant_role_permission(
            session,
            tenant_id=tenant_id,
            role_id=role.id,
            permission_id=permission.id,
            effect="allow",
            actor_user_id=user_id,
            correlation_id="normalization-phase1f3",
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
        correlation_id="normalization-phase1f3",
    )
    await session.flush()

