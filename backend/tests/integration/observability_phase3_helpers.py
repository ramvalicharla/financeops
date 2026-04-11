from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
from tests.integration.temp_db_helpers import create_migrated_temp_database, drop_temp_database

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
)

OBSERVABILITY_TABLES: tuple[str, ...] = (
    "observability_run_registry",
    "run_token_diff_definitions",
    "run_token_diff_results",
    "lineage_graph_snapshots",
    "governance_events",
    "run_performance_metrics",
    "observability_runs",
    "observability_results",
    "observability_evidence_links",
)


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def _with_database(raw_url: str, database: str) -> str:
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(scope="session")
async def observability_phase3_db_url() -> AsyncGenerator[str, None]:
    target_url, temp_db, admin_url = await create_migrated_temp_database(
        prefix="financeops_observability",
        error_context="observability phase3 temp database",
    )

    try:
        yield target_url
    finally:
        await drop_temp_database(admin_url=admin_url, database_name=temp_db)


async def seed_control_plane_for_observability(
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
            "correlation_id": "observability-phase3",
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
                CpModuleRegistry.module_code == "observability_engine"
            )
        )
    ).scalar_one_or_none()
    if module is None:
        module = CpModuleRegistry(
            module_code="observability_engine",
            module_name="Observability Engine",
            engine_context="finance",
            is_financial_impacting=False,
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
            correlation_id="observability-phase3",
            effective_from=now,
            effective_to=None,
        )
        await grant_boolean_entitlement(
            session,
            tenant_id=tenant_id,
            feature_name="observability_engine",
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
        correlation_id="observability-phase3",
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
        correlation_id="observability-phase3",
    )
    if not grant_permissions:
        await session.flush()
        return

    role = await create_role(
        session,
        tenant_id=tenant_id,
        role_code=f"OBS_ROLE_{uuid.uuid4().hex[:8]}",
        role_scope="tenant",
        inherits_role_id=None,
        is_active=True,
        actor_user_id=user_id,
        correlation_id="observability-phase3",
    )

    permissions = [
        ("observability_run_registry", "observability_view"),
        ("run_token_diff_result", "observability_diff"),
        ("observability_run", "observability_replay_validate"),
        ("lineage_graph_snapshot", "observability_graph_view"),
        ("governance_event", "observability_view"),
        ("run_performance_metric", "observability_view"),
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
                description="observability phase3 integration permission",
            )
        await grant_role_permission(
            session,
            tenant_id=tenant_id,
            role_id=role.id,
            permission_id=permission.id,
            effect="allow",
            actor_user_id=user_id,
            correlation_id="observability-phase3",
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
        correlation_id="observability-phase3",
    )
    await session.flush()


