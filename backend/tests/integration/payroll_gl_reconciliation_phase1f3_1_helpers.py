from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, timezone
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
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash
from tests.integration.temp_db_helpers import create_migrated_temp_database, drop_temp_database

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


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def payroll_gl_recon_phase1f3_1_db_url() -> AsyncGenerator[str, None]:
    target_url, temp_db, admin_url = await create_migrated_temp_database(
        prefix="financeops_payglrecon",
        error_context="payroll-gl reconciliation phase1f3_1 temp database",
    )

    try:
        yield target_url
    finally:
        await drop_temp_database(admin_url=admin_url, database_name=temp_db)


@pytest_asyncio.fixture(scope="session", loop_scope="session")
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
    service = NormalizationRunService(
        repository=PayrollGlNormalizationRepository(session),
        source_detection_service=SourceDetectionService(),
        mapping_service=NormalizationMappingService(),
        payroll_normalization_service=PayrollNormalizationService(),
        gl_normalization_service=GlNormalizationService(),
        validation_service=NormalizationValidationService(),
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
                "organisation_name": "Payroll GL Recon Test Org",
                "parent_organisation_id": None,
                "supersedes_id": None,
                "is_active": True,
                "correlation_id": "paygl-recon-phase2-1-test",
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
                "entity_name": "Payroll GL Recon Test Entity",
                "organisation_id": organisation.id,
                "group_id": None,
                "base_currency": "USD",
                "country_code": "US",
                "status": "active",
                "correlation_id": "paygl-recon-phase2-1-test",
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
        await grant_boolean_entitlement(
            session,
            tenant_id=tenant_id,
            feature_name="payroll_gl_reconciliation",
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


