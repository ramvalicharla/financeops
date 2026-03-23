from __future__ import annotations

import asyncio
import sys
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

pytest_plugins = (
    "tests.integration.mis_phase1f1_helpers",
    "tests.integration.reconciliation_phase1f2_helpers",
    "tests.integration.normalization_phase1f3_helpers",
    "tests.integration.payroll_gl_reconciliation_phase1f3_1_helpers",
    "tests.integration.ratio_variance_phase1f4_helpers",
    "tests.integration.financial_risk_phase1f5_helpers",
    "tests.integration.anomaly_pattern_phase1f6_helpers",
    "tests.integration.board_pack_phase1f7_helpers",
    "tests.integration.multi_entity_consolidation_phase2_3_helpers",
    "tests.integration.fx_translation_phase2_4_helpers",
    "tests.integration.ownership_consolidation_phase2_5_helpers",
    "tests.integration.cash_flow_phase2_6_helpers",
    "tests.integration.equity_phase2_7_helpers",
    "tests.integration.observability_phase3_helpers",
    "tests.integration.erp_sync_phase4c_helpers",
)

# On Windows, asyncpg's persistent IOCP socket readers cause GetQueuedCompletionStatus
# to block indefinitely between run_until_complete() calls (test → teardown boundary).
# Switching to SelectorEventLoop (non-IOCP) avoids this issue entirely.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import os

# Ensure deterministic local integration endpoints for host-run pytest.
# These defaults are only applied when not explicitly provided by the environment.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test",
)
os.environ.setdefault(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("TEST_REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("TEMPORAL_ADDRESS", "localhost:7233")
os.environ.setdefault("TEMPORAL_NAMESPACE", "default")
if os.environ.get("DEBUG", "").strip().lower() not in {
    "",
    "0",
    "1",
    "true",
    "false",
    "yes",
    "no",
    "on",
    "off",
}:
    os.environ["DEBUG"] = "false"

from fastapi import Request
from httpx import ASGITransport, AsyncClient, Request as HttpxRequest
from itsdangerous import URLSafeSerializer
from sqlalchemy import text
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
from financeops.db.models.reconciliation_bridge import (  # noqa: F401
    ReconciliationEvidenceLink,
    ReconciliationException,
    ReconciliationLine,
    ReconciliationResolutionEvent,
    ReconciliationScope,
    ReconciliationSession,
)
from financeops.db.models.payroll_gl_normalization import (  # noqa: F401
    GlNormalizedLine,
    NormalizationEvidenceLink,
    NormalizationException,
    NormalizationMapping,
    NormalizationRun,
    NormalizationSource,
    NormalizationSourceVersion,
    PayrollNormalizedLine,
)
from financeops.db.models.payroll_gl_reconciliation import (  # noqa: F401
    PayrollGlReconciliationMapping,
    PayrollGlReconciliationRule,
    PayrollGlReconciliationRun,
    PayrollGlReconciliationRunScope,
)
from financeops.db.models.ratio_variance_engine import (  # noqa: F401
    MaterialityRule,
    MetricDefinition,
    MetricDefinitionComponent,
    MetricEvidenceLink,
    MetricResult,
    MetricRun,
    TrendDefinition,
    TrendResult,
    VarianceDefinition,
    VarianceResult,
)
from financeops.db.models.financial_risk_engine import (  # noqa: F401
    RiskContributingSignal,
    RiskDefinition,
    RiskDefinitionDependency,
    RiskEvidenceLink,
    RiskMaterialityRule,
    RiskResult,
    RiskRollforwardEvent,
    RiskRun,
    RiskWeightConfiguration,
)
from financeops.db.models.anomaly_pattern_engine import (  # noqa: F401
    AnomalyContributingSignal,
    AnomalyCorrelationRule,
    AnomalyDefinition,
    AnomalyEvidenceLink,
    AnomalyPatternRule,
    AnomalyPersistenceRule,
    AnomalyResult,
    AnomalyRollforwardEvent,
    AnomalyRun,
    AnomalyStatisticalRule,
)
from financeops.db.models.multi_entity_consolidation import (  # noqa: F401
    ConsolidationAdjustmentDefinition,
    ConsolidationRuleDefinition,
    ConsolidationScope,
    EntityHierarchy,
    EntityHierarchyNode,
    IntercompanyMappingRule,
    MultiEntityConsolidationEvidenceLink,
    MultiEntityConsolidationMetricResult,
    MultiEntityConsolidationRun,
    MultiEntityConsolidationVarianceResult,
)
from financeops.db.models.fx_translation_reporting import (  # noqa: F401
    FxRateSelectionPolicy,
    FxTranslatedMetricResult,
    FxTranslatedVarianceResult,
    FxTranslationEvidenceLink,
    FxTranslationRun,
    FxTranslationRuleDefinition,
    ReportingCurrencyDefinition,
)
from financeops.db.models.ownership_consolidation import (  # noqa: F401
    MinorityInterestRuleDefinition,
    OwnershipConsolidationEvidenceLink,
    OwnershipConsolidationMetricResult,
    OwnershipConsolidationRuleDefinition,
    OwnershipConsolidationRun,
    OwnershipConsolidationVarianceResult,
    OwnershipRelationship,
    OwnershipStructureDefinition,
)
from financeops.db.models.cash_flow_engine import (  # noqa: F401
    CashFlowBridgeRuleDefinition,
    CashFlowEvidenceLink,
    CashFlowLineMapping,
    CashFlowLineResult,
    CashFlowRun,
    CashFlowStatementDefinition,
)
from financeops.db.models.equity_engine import (  # noqa: F401
    EquityEvidenceLink,
    EquityLineDefinition,
    EquityLineResult,
    EquityRollforwardRuleDefinition,
    EquityRun,
    EquitySourceMapping,
    EquityStatementDefinition,
    EquityStatementResult,
)
from financeops.db.models.observability_engine import (  # noqa: F401
    GovernanceEvent,
    LineageGraphSnapshot,
    ObservabilityEvidenceLink,
    ObservabilityResult,
    ObservabilityRun,
    ObservabilityRunRegistry,
    RunPerformanceMetric,
    RunTokenDiffDefinition,
    RunTokenDiffResult,
)
from financeops.db.models.erp_sync import (  # noqa: F401
    ExternalBackdatedModificationAlert,
    ExternalConnection,
    ExternalConnectionVersion,
    ExternalConnectorCapabilityRegistry,
    ExternalConnectorVersionRegistry,
    ExternalDataConsentLog,
    ExternalMappingDefinition,
    ExternalMappingVersion,
    ExternalNormalizedSnapshot,
    ExternalPeriodLock,
    ExternalRawSnapshot,
    ExternalSyncDefinition,
    ExternalSyncDefinitionVersion,
    ExternalSyncDriftReport,
    ExternalSyncError,
    ExternalSyncEvidenceLink,
    ExternalSyncHealthAlert,
    ExternalSyncPublishEvent,
    ExternalSyncRun,
    ExternalSyncSLAConfig,
)
from financeops.db.models.payment import (  # noqa: F401
    BillingInvoice,
    BillingPlan,
    CreditLedger,
    CreditTopUp,
    GracePeriodLog,
    PaymentMethod,
    ProrationRecord,
    SubscriptionEvent,
    TenantSubscription,
    WebhookEvent,
)
from financeops.modules.auto_trigger.models import (  # noqa: F401
    PipelineRun,
    PipelineStepLog,
)
from financeops.modules.secret_rotation.models import SecretRotationLog  # noqa: F401
from financeops.modules.template_onboarding.models import OnboardingState  # noqa: F401
from financeops.modules.compliance.models import ErasureLog, UserPiiKey  # noqa: F401
from financeops.modules.compliance.models import ComplianceControl, ComplianceEvent  # noqa: F401
from financeops.modules.compliance.gdpr_models import (  # noqa: F401
    GDPRBreachRecord,
    GDPRConsentRecord,
    GDPRDataRequest,
)
from financeops.modules.closing_checklist.models import (  # noqa: F401
    ChecklistRun,
    ChecklistRunTask,
    ChecklistTemplate,
    ChecklistTemplateTask,
)
from financeops.modules.working_capital.models import APLineItem, ARLineItem, WCSnapshot  # noqa: F401
from financeops.modules.expense_management.models import (  # noqa: F401
    ExpenseApproval,
    ExpenseClaim,
    ExpensePolicy,
)
from financeops.modules.budgeting.models import (  # noqa: F401
    BudgetLineItem,
    BudgetVersion,
)
from financeops.modules.forecasting.models import (  # noqa: F401
    ForecastAssumption,
    ForecastLineItem,
    ForecastRun,
)
from financeops.modules.scenario_modelling.models import (  # noqa: F401
    ScenarioDefinition,
    ScenarioLineItem,
    ScenarioResult,
    ScenarioSet,
)
from financeops.modules.backup.models import BackupRunLog  # noqa: F401
from financeops.modules.fdd.models import (  # noqa: F401
    FDDEngagement,
    FDDFinding,
    FDDSection,
)
from financeops.modules.ppa.models import (  # noqa: F401
    PPAAllocation,
    PPAEngagement,
    PPAIntangible,
)
from financeops.modules.ma_workspace.models import (  # noqa: F401
    MADDItem,
    MADocument,
    MAValuation,
    MAWorkspace,
    MAWorkspaceMember,
)
from financeops.db.models.ai_cost import AICostEvent, TenantTokenBudget  # noqa: F401

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


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _close_global_redis_clients() -> AsyncGenerator[None, None]:
    """Close module-level Redis pools before the event loop is torn down."""
    yield
    from financeops.api import deps as api_deps
    pool = api_deps._redis_pool
    if pool is not None:
        try:
            await pool.aclose()
        except Exception:
            pass
        finally:
            api_deps._redis_pool = None


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
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        await conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        await conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('0031_anomaly_ui_layer')")
        )
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
    from financeops.config import settings
    from financeops.db.rls import clear_tenant_context, set_tenant_context
    from financeops.main import app

    finance_prefix_modules = (
        ("/api/v1/mis", "mis_manager"),
        ("/api/v1/normalization", "payroll_gl_normalization"),
        ("/api/v1/payroll-gl-reconciliation", "payroll_gl_reconciliation"),
        ("/api/v1/ratio-variance", "ratio_variance_engine"),
        ("/api/v1/financial-risk", "financial_risk_engine"),
        ("/api/v1/anomaly-engine", "anomaly_pattern_engine"),
        ("/api/v1/board-pack", "board_pack_narrative_engine"),
        ("/api/v1/billing", "payment"),
        ("/api/v1/erp-sync", "erp_sync"),
        ("/api/v1/reconciliation", "reconciliation_bridge"),
        ("/api/v1/recon", "reconciliation"),
        ("/api/v1/bank-recon", "bank_reconciliation"),
        ("/api/v1/fx/reporting-currencies", "fx_translation_reporting"),
        ("/api/v1/fx/translation-rules", "fx_translation_reporting"),
        ("/api/v1/fx/rate-policies", "fx_translation_reporting"),
        ("/api/v1/fx/runs", "fx_translation_reporting"),
        ("/api/v1/ownership", "ownership_consolidation"),
        ("/api/v1/cash-flow", "cash_flow_engine"),
        ("/api/v1/equity", "equity_engine"),
        ("/api/v1/observability", "observability_engine"),
        ("/api/v1/fx", "fx"),
        ("/api/v1/consolidation/hierarchies", "multi_entity_consolidation"),
        ("/api/v1/consolidation/scopes", "multi_entity_consolidation"),
        ("/api/v1/consolidation/rules", "multi_entity_consolidation"),
        ("/api/v1/consolidation/intercompany-rules", "multi_entity_consolidation"),
        ("/api/v1/consolidation/adjustment-definitions", "multi_entity_consolidation"),
        ("/api/v1/consolidation/runs", "multi_entity_consolidation"),
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

    csrf_serializer = URLSafeSerializer(settings.SECRET_KEY, "csrftoken")

    async def _inject_csrf_token(request: HttpxRequest) -> None:
        if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
            return
        if "x-csrftoken" in request.headers:
            return

        existing_cookie = request.headers.get("cookie", "")
        if "csrftoken=" in existing_cookie:
            for cookie_part in existing_cookie.split(";"):
                part = cookie_part.strip()
                if part.startswith("csrftoken="):
                    request.headers["x-csrftoken"] = part.split("=", 1)[1]
                    return
            return
        token = csrf_serializer.dumps("test-csrf")
        request.headers["x-csrftoken"] = token
        csrf_cookie = f"csrftoken={token}"
        if existing_cookie:
            request.headers["cookie"] = f"{existing_cookie}; {csrf_cookie}"
        else:
            request.headers["cookie"] = csrf_cookie

    async def _consume_response(response) -> None:
        await response.aread()

    # Redirect commit() to flush() — keeps data in the outer transaction so
    # session.rollback() in async_session can undo everything after the test.
    original_commit = async_session.commit
    async_session.commit = async_session.flush  # type: ignore[method-assign]

    async def override_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
        tenant_id = str(getattr(request.state, "tenant_id", "") or "")
        if not tenant_id:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                try:
                    payload = decode_token(token)
                except Exception:
                    payload = {}
                tenant_id = str(payload.get("tenant_id", "") or "")
        if tenant_id:
            await set_tenant_context(async_session, tenant_id)
        try:
            yield async_session
        finally:
            if tenant_id:
                try:
                    await clear_tenant_context(async_session)
                except Exception:
                    await async_session.rollback()

    app.dependency_overrides[get_async_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
        event_hooks={
            "request": [_inject_control_plane_token, _inject_csrf_token],
            "response": [_consume_response],
        },
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
