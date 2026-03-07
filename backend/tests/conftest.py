from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

# On Windows, asyncpg's persistent IOCP socket readers cause GetQueuedCompletionStatus
# to block indefinitely between run_until_complete() calls (test → teardown boundary).
# Switching to SelectorEventLoop (non-IOCP) avoids this issue entirely.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import os

from fastapi import Request
from httpx import ASGITransport, AsyncClient, Request as HttpxRequest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from financeops.core.security import create_access_token, decode_token, hash_password
from financeops.db.base import Base
from financeops.db.models.audit import AuditTrail  # noqa: F401
from financeops.db.models.auditor import AuditorAccessLog, AuditorGrant  # noqa: F401
from financeops.db.models.bank_recon import (  # noqa: F401
    BankReconItem,
    BankStatement,
    BankTransaction,
)
from financeops.db.models.credits import (  # noqa: F401
    CreditBalance,
    CreditReservation,
    CreditTransaction,
)
from financeops.db.models.gst import GstReconItem, GstReturn  # noqa: F401
from financeops.db.models.fx_rates import (  # noqa: F401
    FxManualMonthlyRate,
    FxRateFetchRun,
    FxRateQuote,
    FxVarianceResult,
)
from financeops.db.models.consolidation import (  # noqa: F401
    ConsolidationElimination,
    ConsolidationEntity,
    ConsolidationLineItem,
    ConsolidationResult,
    ConsolidationRun,
    ConsolidationRunEvent,
    IntercompanyPair,
    NormalizedFinancialSnapshot,
    NormalizedFinancialSnapshotLine,
)
from financeops.db.models.revenue import (  # noqa: F401
    RevenueAdjustment,
    RevenueContract,
    RevenueContractLineItem,
    RevenueJournalEntry,
    RevenuePerformanceObligation,
    RevenueRun,
    RevenueRunEvent,
    RevenueSchedule,
)
from financeops.db.models.lease import (  # noqa: F401
    Lease,
    LeaseJournalEntry,
    LeaseLiabilitySchedule,
    LeaseModification,
    LeasePayment,
    LeaseRouSchedule,
    LeaseRun,
    LeaseRunEvent,
)
from financeops.db.models.prepaid import (  # noqa: F401
    Prepaid,
    PrepaidAdjustment,
    PrepaidAmortizationSchedule,
    PrepaidJournalEntry,
    PrepaidRun,
    PrepaidRunEvent,
)
from financeops.db.models.fixed_assets import (  # noqa: F401
    Asset,
    AssetDepreciationSchedule,
    AssetDisposal,
    AssetImpairment,
    AssetJournalEntry,
    FarRun,
    FarRunEvent,
)
from financeops.platform.db.models import (  # noqa: F401
    CpEntity,
    CpGroup,
    CpModuleFeatureFlag,
    CpModuleRegistry,
    CpOrganisation,
    CpPackage,
    CpPermission,
    CpQuotaPolicy,
    CpRole,
    CpRolePermission,
    CpTenant,
    CpTenantIsolationPolicy,
    CpTenantMigrationEvent,
    CpTenantModuleEnablement,
    CpTenantPackageAssignment,
    CpTenantQuotaAssignment,
    CpTenantQuotaUsageEvent,
    CpTenantQuotaWindow,
    CpUserEntityAssignment,
    CpUserOrganisationAssignment,
    CpUserRoleAssignment,
    CpWorkflowApproval,
    CpWorkflowInstance,
    CpWorkflowInstanceEvent,
    CpWorkflowStageEvent,
    CpWorkflowStageInstance,
    CpWorkflowStageRoleMap,
    CpWorkflowStageUserMap,
    CpWorkflowTemplate,
    CpWorkflowTemplateStage,
    CpWorkflowTemplateVersion,
)

# Phase 1 models — must be imported before Base.metadata.create_all()
from financeops.db.models.mis_manager import MisTemplate, MisUpload  # noqa: F401
from financeops.db.models.monthend import MonthEndChecklist, MonthEndTask  # noqa: F401
from financeops.db.models.prompts import AiPromptVersion  # noqa: F401
from financeops.db.models.reconciliation import (  # noqa: F401
    GlEntry,
    ReconItem,
    TrialBalanceRow,
)

# Import ALL models so Base.metadata.create_all() creates every table.
# Order matters: models with FK deps must be imported after their targets.
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.models.working_capital import WorkingCapitalSnapshot  # noqa: F401
from financeops.platform.services.enforcement.context_token import issue_context_token
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test",
)
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6380/0")


@pytest_asyncio.fixture(scope="session")
async def engine():
    """
    Create test database engine and tables once per session.
    NullPool ensures each test's session gets a fresh connection,
    avoiding 'another operation is in progress' asyncpg errors.
    """
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def async_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transactional test session that rolls back after each test.
    loop_scope="session" ensures setup AND teardown both run on the session
    event loop, preventing asyncpg 'Future attached to a different loop' errors
    that occur in pytest-asyncio 0.24.0 with function-scoped async fixtures.
    """
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.begin()
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture
async def test_tenant(async_session: AsyncSession) -> IamTenant:
    """Create a test IamTenant for use in tests."""
    tenant_id = uuid.uuid4()
    record_data = {
        "display_name": "Test Tenant",
        "tenant_type": TenantType.direct.value,
        "country": "US",
        "timezone": "UTC",
    }
    chain_hash = compute_chain_hash(record_data, GENESIS_HASH)
    tenant = IamTenant(
        id=tenant_id,
        tenant_id=tenant_id,
        display_name="Test Tenant",
        tenant_type=TenantType.direct,
        country="US",
        timezone="UTC",
        status=TenantStatus.active,
        chain_hash=chain_hash,
        previous_hash=GENESIS_HASH,
    )
    async_session.add(tenant)
    await async_session.flush()
    return tenant


@pytest_asyncio.fixture
async def test_user(async_session: AsyncSession, test_tenant: IamTenant) -> IamUser:
    """Create a test IamUser with finance_leader role."""
    user = IamUser(
        tenant_id=test_tenant.id,
        email="testuser@example.com",
        hashed_password=hash_password("TestPass123!"),
        full_name="Test User",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    async_session.add(user)
    await async_session.flush()
    return user


@pytest.fixture
def test_access_token(test_user: IamUser) -> str:
    """Return a valid JWT access token for the test user."""
    return create_access_token(test_user.id, test_user.tenant_id, test_user.role.value)


@pytest_asyncio.fixture(loop_scope="session")
async def async_client(
    async_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Return an httpx AsyncClient configured against the test FastAPI app.
    Overrides the DB session dependency to use the test session.

    session.commit() is patched to session.flush() so that application code
    calling commit() does not break the outer rollback-based test isolation.
    loop_scope="session" ensures the AsyncClient teardown uses the same loop.
    """
    from financeops.api.deps import get_async_session
    from financeops.db.rls import clear_tenant_context, set_tenant_context
    from financeops.main import app

    finance_prefix_modules = (
        ("/api/v1/mis", "mis"),
        ("/api/v1/recon", "reconciliation"),
        ("/api/v1/bank-recon", "bank_reconciliation"),
        ("/api/v1/fx", "fx"),
        ("/api/v1/consolidation", "consolidation"),
        ("/api/v1/revenue", "revenue"),
        ("/api/v1/lease", "lease"),
        ("/api/v1/prepaid", "prepaid"),
        ("/api/v1/fixed-assets", "fixed_assets"),
        ("/api/v1/working-capital", "working_capital"),
        ("/api/v1/gst", "gst"),
        ("/api/v1/monthend", "monthend"),
        ("/api/v1/auditor", "auditor"),
    )

    async def _inject_control_plane_token(request: HttpxRequest) -> None:
        if "X-Control-Plane-Token" in request.headers:
            return
        module_code = ""
        for prefix, candidate_module in finance_prefix_modules:
            if request.url.path.startswith(prefix):
                module_code = candidate_module
                break
        if not module_code:
            return
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return
        token = auth_header[7:]
        try:
            payload = decode_token(token)
        except Exception:
            return
        tenant_id = str(payload.get("tenant_id", "") or "")
        if not tenant_id:
            return
        issued_at = datetime.now(UTC)
        claims = {
            "tenant_id": tenant_id,
            "module_code": module_code,
            "decision": "allow",
            "policy_snapshot_version": 1,
            "quota_check_id": str(uuid.uuid4()),
            "isolation_route_version": 1,
            "issued_at": issued_at.isoformat(),
            "expires_at": (issued_at + timedelta(minutes=10)).isoformat(),
            "correlation_id": str(uuid.uuid4()),
        }
        request.headers["X-Control-Plane-Token"] = issue_context_token(claims)

    # Redirect commit() to flush() — keeps data in the outer transaction so
    # session.rollback() in async_session can undo everything after the test.
    original_commit = async_session.commit
    async_session.commit = async_session.flush  # type: ignore[method-assign]

    async def override_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
        tenant_id = str(getattr(request.state, "tenant_id", "") or "")
        if tenant_id:
            await set_tenant_context(async_session, tenant_id)
        try:
            yield async_session
        finally:
            if tenant_id:
                await clear_tenant_context(async_session)

    app.dependency_overrides[get_async_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        event_hooks={"request": [_inject_control_plane_token]},
    ) as client:
        yield client
    app.dependency_overrides.clear()
    async_session.commit = original_commit  # restore original method


@pytest_asyncio.fixture(loop_scope="session")
async def redis_client():
    """Return a test Redis connection."""
    import redis.asyncio as aioredis
    client = aioredis.from_url(TEST_REDIS_URL, encoding="utf-8", decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()
