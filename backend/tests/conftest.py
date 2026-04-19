from __future__ import annotations

import asyncio
import re
import subprocess
import sys
import urllib.parse
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import asyncpg
from filelock import FileLock
import pytest
import pytest_asyncio
from alembic.config import Config
from alembic.script import ScriptDirectory

_DEFAULT_LOCAL_TEST_DATABASE_URL = (
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test"
)


def _initial_worker_database_url() -> str:
    raw_url = os.getenv("TEST_DATABASE_URL", _DEFAULT_LOCAL_TEST_DATABASE_URL)
    worker_id = os.getenv("PYTEST_XDIST_WORKER", "master").lower().replace("-", "_")
    worker_id = re.sub(r"[^a-z0-9_]", "_", worker_id)
    database_name = f"finos_test_{worker_id}"[:63]
    parts = urllib.parse.urlsplit(raw_url)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment)
    )


# On Windows, asyncpg's persistent IOCP socket readers cause GetQueuedCompletionStatus
# to block indefinitely between run_until_complete() calls (test â†’ teardown boundary).
# Switching to SelectorEventLoop (non-IOCP) avoids this issue entirely.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import os

if sys.platform == "win32":
    # Keep pytest temp dirs inside the workspace to avoid Windows temp-root
    # permission/locking issues under AppData\Local\Temp.
    _WINDOWS_PYTEST_TEMPROOT = Path(__file__).resolve().parents[1] / ".pytest_tmp_root"
    _WINDOWS_PYTEST_TEMPROOT.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(_WINDOWS_PYTEST_TEMPROOT))

# Ensure deterministic worker-local database URLs for every pytest process.
# xdist workers inherit the controller environment, so ``setdefault()`` would
# leave them pinned to ``finos_test_master``. Force the worker-specific URL
# before any app modules import ``settings.DATABASE_URL``.
_WORKER_DATABASE_URL = _initial_worker_database_url()
os.environ["DATABASE_URL"] = _WORKER_DATABASE_URL
os.environ["TEST_DATABASE_URL"] = _WORKER_DATABASE_URL
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
from sqlalchemy import select, text
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
from financeops.db.models.intent_pipeline import (  # noqa: F401
    CanonicalIntent,
    CanonicalIntentEvent,
    CanonicalJob,
)
from financeops.db.models.governance_control import (  # noqa: F401
    AirlockEvent,
    AirlockItem,
    CanonicalGovernanceEvent,
    GovernanceApprovalPolicy,
)
from financeops.db.models.ai_cfo_layer import (  # noqa: F401
    AiCfoAnomaly,
    AiCfoLedger,
    AiCfoNarrativeBlock,
    AiCfoRecommendation,
)
from financeops.db.models.control_plane_phase4 import (  # noqa: F401
    GovernanceSnapshot,
    GovernanceSnapshotInput,
    GovernanceSnapshotMetadata,
)
from financeops.db.models.accounting_vendor import (  # noqa: F401
    AccountingAttachment,
    AccountingDuplicateFingerprint,
    AccountingVendor,
    ErpAttachmentLink,
)
from financeops.db.models.accounting_notifications import (  # noqa: F401
    AccountingAPAgeingSnapshot,
    AccountingAuditExportRun,
    AccountingNotificationEvent,
    ApprovalReminderRun,
    ApprovalSLABreachRun,
)
from financeops.db.models.accounting_approvals import (  # noqa: F401
    AccountingJVApproval,
    ApprovalSLATimer,
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

# Phase 1 models â€” must be imported before Base.metadata.create_all()
from financeops.db.models.mis_manager import MisTemplate, MisUpload  # noqa: F401
from financeops.db.models.monthend import MonthEndChecklist, MonthEndTask  # noqa: F401
from financeops.db.models.prompts import AiPromptVersion  # noqa: F401
from financeops.db.models.custom_report_builder import (  # noqa: F401
    ReportDefinition,
    ReportResult,
    ReportRun,
)
from financeops.db.models.scheduled_delivery import (  # noqa: F401
    DeliveryLog,
    DeliverySchedule,
)
from financeops.db.models.board_pack_generator import (  # noqa: F401
    BoardPackGeneratorArtifact,
    BoardPackGeneratorDefinition,
    BoardPackGeneratorRun,
    BoardPackGeneratorSection,
)
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
from financeops.db.models.erp_integration import (  # noqa: F401
    ErpConnector,
    ErpSyncJob,
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
    BudgetVersionStatusEvent,
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
from financeops.modules.service_registry.models import ModuleRegistry, TaskRegistry  # noqa: F401
from financeops.modules.marketplace.models import (  # noqa: F401
    MarketplaceContributor,
    MarketplacePayout,
    MarketplacePurchase,
    MarketplaceRating,
    MarketplaceTemplate,
)
from financeops.modules.white_label.models import (  # noqa: F401
    WhiteLabelAuditLog,
    WhiteLabelConfig,
)
from financeops.modules.partner_program.models import (  # noqa: F401
    PartnerCommission,
    PartnerProfile,
    ReferralTracking,
)
from financeops.modules.notifications.models import (  # noqa: F401
    NotificationEvent,
    NotificationPreferences,
    NotificationReadState,
)
from financeops.modules.learning_engine.models import (  # noqa: F401
    AIBenchmarkResult,
    LearningCorrection,
    LearningSignal,
)
from financeops.modules.search.models import SearchIndexEntry  # noqa: F401
from financeops.modules.cash_flow_forecast.models import (  # noqa: F401
    CashFlowForecastAssumption,
    CashFlowForecastRun,
)
from financeops.modules.tax_provision.models import (  # noqa: F401
    TaxPosition,
    TaxProvisionRun,
)
from financeops.modules.debt_covenants.models import (  # noqa: F401
    CovenantBreachEvent,
    CovenantDefinition,
)
from financeops.modules.transfer_pricing.models import (  # noqa: F401
    ICTransaction,
    TPConfig,
    TransferPricingDoc,
)
from financeops.modules.digital_signoff.models import DirectorSignoff  # noqa: F401
from financeops.modules.statutory.models import (  # noqa: F401
    StatutoryFiling,
    StatutoryRegisterEntry,
)
from financeops.modules.multi_gaap.models import (  # noqa: F401
    MultiGAAPConfig,
    MultiGAAPRun,
)
from financeops.modules.auditor_portal.models import (  # noqa: F401
    AuditorPortalAccess,
    AuditorRequest,
)
from financeops.modules.coa.models import (  # noqa: F401
    CoaAccountGroup,
    CoaAccountSubgroup,
    CoaFsClassification,
    CoaFsLineItem,
    CoaFsSchedule,
    CoaFsSubline,
    CoaGaapMapping,
    CoaIndustryTemplate,
    CoaLedgerAccount,
    ErpAccountMapping,
    TenantCoaAccount,
)
from financeops.modules.org_setup.models import (  # noqa: F401
    OrgEntity,
    OrgEntityErpConfig,
    OrgGroup,
    OrgOwnership,
    OrgSetupProgress,
)
from financeops.modules.fixed_assets.models import (  # noqa: F401
    FaAsset,
    FaAssetClass,
    FaDepreciationRun,
    FaImpairment,
    FaRevaluation,
)
from financeops.modules.prepaid_expenses.models import (  # noqa: F401
    PrepaidAmortisationEntry,
    PrepaidSchedule,
)
from financeops.modules.invoice_classifier.models import (  # noqa: F401
    ClassificationRule,
    InvoiceClassification,
)
from financeops.modules.locations.models import (  # noqa: F401
    CpCostCentre,
    CpLocation,
)
from financeops.db.models.ai_cost import AICostEvent, TenantTokenBudget  # noqa: F401
from financeops.db.models.auth_tokens import MfaRecoveryCode, PasswordResetToken  # noqa: F401
from financeops.db.append_only import append_only_function_sql

# Import ALL models so Base.metadata.create_all() creates every table.
# Order matters: models with FK deps must be imported after their targets.
from financeops.db.models.tenants import IamTenant, TenantStatus, TenantType
from financeops.db.models.users import IamUser, UserRole
from financeops.db.models.working_capital import WorkingCapitalSnapshot  # noqa: F401
from financeops.platform.services.enforcement.context_token import issue_context_token
from financeops.platform.services.tenancy.module_enablement import set_module_enablement
from financeops.utils.chain_hash import GENESIS_HASH, compute_chain_hash

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://financeops_test:testpassword@localhost:5433/financeops_test",
)
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6380/0")
TEST_DATABASE_ADMIN_DB = os.getenv("TEST_DATABASE_ADMIN_DB", "postgres")
_VALID_TEST_DB_NAME = re.compile(r"[a-z0-9_]+")
_CACHED_TEST_PASSWORD_HASH = hash_password("TestPass123!")
_TEMPLATE_DATABASE_NAME = "finos_test_template"
_TEMPLATE_DATABASE_LOCK = Path(__file__).resolve().parents[1] / ".pytest-template-db.lock"

_INTEGRATION_PLUGIN_MODULES = (
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


def _should_load_integration_plugins(pytest_args: list[str]) -> bool:
    normalized = [str(arg).replace("\\", "/") for arg in pytest_args if str(arg).strip()]
    if not normalized:
        return True
    if any(arg in {".", "tests", "tests/"} for arg in normalized):
        return True
    return any(arg.startswith("tests/integration") for arg in normalized)


def pytest_configure(config: pytest.Config) -> None:
    if not _should_load_integration_plugins(list(getattr(config, "args", []))):
        return
    for plugin_name in _INTEGRATION_PLUGIN_MODULES:
        if not config.pluginmanager.has_plugin(plugin_name):
            config.pluginmanager.import_plugin(plugin_name)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    del config
    for item in items:
        nodeid = item.nodeid.replace("\\", "/")
        keywords = item.keywords
        if "tests/integration/" in nodeid and "integration" not in keywords:
            item.add_marker(pytest.mark.integration)
        elif "tests/integration/" not in nodeid and "integration" not in keywords and "unit" not in keywords:
            item.add_marker(pytest.mark.unit)
        if (
            "_append_only_" in nodeid
            or "test_append_only_enforcement.py" in nodeid
            or "test_consolidation_append_only.py" in nodeid
            or "test_fixed_assets_append_only.py" in nodeid
            or "test_lease_append_only.py" in nodeid
            or "test_prepaid_append_only.py" in nodeid
            or "test_revenue_append_only.py" in nodeid
        ) and "db_heavy" not in keywords:
            item.add_marker(pytest.mark.db_heavy)
        if "_migration_" in nodeid and "migration_heavy" not in keywords:
            item.add_marker(pytest.mark.migration_heavy)
        if "_migration_" in nodeid and "serial_only" not in keywords:
            item.add_marker(pytest.mark.serial_only)
        if (
            "test_schema_tower.py" in nodeid
            or "_append_only_" in nodeid
            or "_migration_" in nodeid
        ) and "slow" not in keywords:
            item.add_marker(pytest.mark.slow)


def pytest_xdist_auto_num_workers(config: pytest.Config) -> int:
    del config
    cpu_count = os.cpu_count() or 1
    if sys.platform == "win32":
        # Template-cloned worker databases remove the previous DDL lock storm;
        # nine workers is the best verified throughput point in this environment.
        return max(2, min(9, cpu_count))
    return max(2, min(8, cpu_count))


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _worker_id() -> str:
    worker_id = os.getenv("PYTEST_XDIST_WORKER", "master").lower().replace("-", "_")
    worker_id = re.sub(r"[^a-z0-9_]", "_", worker_id)
    if not _VALID_TEST_DB_NAME.fullmatch(worker_id):
        raise RuntimeError(f"Invalid pytest worker id for database isolation: {worker_id}")
    return worker_id


def _with_database(raw_url: str, database: str) -> str:
    parts = urllib.parse.urlsplit(raw_url)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment)
    )


def _to_asyncpg_dsn(raw_url: str) -> str:
    return raw_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _worker_test_database_name() -> str:
    return f"finos_test_{_worker_id()}"[:63]


async def _database_exists(conn: asyncpg.Connection, database_name: str) -> bool:
    existing = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", database_name)
    return existing == 1


async def _terminate_database_connections(
    conn: asyncpg.Connection,
    database_name: str,
) -> None:
    await conn.execute(
        """
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = $1
          AND pid <> pg_backend_pid()
        """,
        database_name,
    )


async def _create_database(
    conn: asyncpg.Connection,
    database_name: str,
    *,
    template_name: str | None = None,
) -> None:
    if not _VALID_TEST_DB_NAME.fullmatch(database_name):
        raise RuntimeError(f"Invalid pytest database name: {database_name}")
    if await _database_exists(conn, database_name):
        return
    try:
        if template_name is None:
            await conn.execute(f'CREATE DATABASE "{database_name}"')
            return
        if not _VALID_TEST_DB_NAME.fullmatch(template_name):
            raise RuntimeError(f"Invalid pytest template database name: {template_name}")
        await conn.execute(f'CREATE DATABASE "{database_name}" TEMPLATE "{template_name}"')
    except asyncpg.PostgresError:
        if await _database_exists(conn, database_name):
            return
        raise


def _current_alembic_head() -> str:
    cfg = Config(str(_backend_dir() / "alembic.ini"))
    cfg.set_main_option("script_location", str(_backend_dir() / "migrations"))
    script_dir = ScriptDirectory.from_config(cfg)
    return script_dir.get_current_head() or ""


def _run_alembic_upgrade_head(database_url: str) -> None:
    env = os.environ.copy()
    env["MIGRATION_DATABASE_URL"] = database_url
    env["DATABASE_URL"] = database_url
    env["DEBUG"] = "false"
    env.setdefault("SECRET_KEY", "test-secret-key")
    env.setdefault("JWT_SECRET", "test-jwt-secret-32-characters-long-000")
    env.setdefault(
        "FIELD_ENCRYPTION_KEY",
        "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    )
    env.setdefault("REDIS_URL", TEST_REDIS_URL)
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
            "alembic upgrade head failed for the shared test database.\n"
            f"stdout:\n{migration.stdout}\n"
            f"stderr:\n{migration.stderr}"
        )


async def _reset_public_schema(conn) -> None:
    await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
    await conn.execute(text("CREATE SCHEMA public"))
    await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))


async def _ensure_pgvector_available(conn) -> None:
    try:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as exc:  # pragma: no cover - infrastructure guard
        message = str(exc).lower()
        if "pg_extension_name_index" in message or "already exists" in message:
            return
        # Shared/local test databases should already provide pgvector. Avoid
        # issuing follow-up commands inside a failed transaction context here.
        raise RuntimeError(
            "pgvector extension is required by FinanceOps tests/migrations but is unavailable. "
            "Start the test database with pgvector support (recommended: infra/docker-compose.test.yml)."
        ) from exc
    installed = await conn.execute(
        text("SELECT 1 FROM pg_extension WHERE extname = 'vector' LIMIT 1")
    )
    if installed.scalar_one_or_none() != 1:  # pragma: no cover - safety guard
        raise RuntimeError(
            "pgvector extension check failed after CREATE EXTENSION. "
            "Verify the PostgreSQL instance has pgvector installed."
        )


async def _table_has_column(conn, table_name: str, column_name: str) -> bool:
    return bool(
        await conn.scalar(
            text(
                """
                SELECT 1
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = :table_name
                   AND column_name = :column_name
                 LIMIT 1
                """
            ),
            {"table_name": table_name, "column_name": column_name},
        )
    )


async def _ensure_shared_schema_bootstrapped(conn) -> None:
    iam_tenants_exists = await conn.scalar(
        text("SELECT to_regclass('public.iam_tenants')")
    )
    delivery_schedules_exists = await conn.scalar(
        text("SELECT to_regclass('public.delivery_schedules')")
    )
    approval_sla_timers_exists = await conn.scalar(
        text("SELECT to_regclass('public.approval_sla_timers')")
    )
    ai_cfo_ledger_exists = await conn.scalar(
        text("SELECT to_regclass('public.ai_cfo_ledger')")
    )
    budget_status_events_has_chain_hash = await _table_has_column(
        conn, "budget_version_status_events", "chain_hash"
    )
    if (
        iam_tenants_exists is None
        or delivery_schedules_exists is None
        or approval_sla_timers_exists is None
        or ai_cfo_ledger_exists is None
        or budget_status_events_has_chain_hash
    ):
        await _ensure_pgvector_available(conn)
        if budget_status_events_has_chain_hash:
            await conn.execute(text("DROP TABLE IF EXISTS budget_version_status_events CASCADE"))
        await conn.run_sync(Base.metadata.create_all)
    await conn.execute(text(append_only_function_sql()))
    await conn.execute(text("ALTER TABLE audit_trail ENABLE ROW LEVEL SECURITY"))
    await conn.execute(text("ALTER TABLE audit_trail FORCE ROW LEVEL SECURITY"))
    await conn.execute(
        text(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1
                  FROM pg_policies
                 WHERE schemaname = 'public'
                   AND tablename = 'audit_trail'
                   AND policyname = 'audit_trail_tenant_isolation'
              ) THEN
                CREATE POLICY audit_trail_tenant_isolation
                  ON audit_trail
               USING (
                    tenant_id = COALESCE(
                        current_setting('app.tenant_id', true),
                        current_setting('app.current_tenant_id', true)
                    )::uuid
               );
              END IF;
            END $$;
            """
        )
    )
    alembic_table_exists = await conn.scalar(
        text("SELECT to_regclass('public.alembic_version')")
    )
    if alembic_table_exists is None:
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num varchar(32) NOT NULL)"
            )
        )
    await conn.execute(text("DELETE FROM alembic_version"))
    await conn.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:version_num)"),
        {"version_num": _current_alembic_head()},
    )


async def _ensure_template_database(admin_url: str) -> None:
    template_url = _with_database(TEST_DATABASE_URL, _TEMPLATE_DATABASE_NAME)
    with FileLock(str(_TEMPLATE_DATABASE_LOCK)):
        conn = await asyncpg.connect(_to_asyncpg_dsn(admin_url))
        try:
            template_exists = await _database_exists(conn, _TEMPLATE_DATABASE_NAME)
            if template_exists:
                template_version = None
                delivery_schedule_table = None
                budget_status_events_has_chain_hash = True
                verify_engine = create_async_engine(template_url, echo=False)
                try:
                    async with verify_engine.connect() as verify_conn:
                        template_version = await verify_conn.scalar(
                            text("SELECT version_num FROM alembic_version LIMIT 1")
                        )
                        delivery_schedule_table = await verify_conn.scalar(
                            text("SELECT to_regclass('public.delivery_schedules')")
                        )
                        approval_sla_timers_table = await verify_conn.scalar(
                            text("SELECT to_regclass('public.approval_sla_timers')")
                        )
                        ai_cfo_ledger_table = await verify_conn.scalar(
                            text("SELECT to_regclass('public.ai_cfo_ledger')")
                        )
                        budget_status_events_has_chain_hash = await _table_has_column(
                            verify_conn, "budget_version_status_events", "chain_hash"
                        )
                        audit_trail_policy = await verify_conn.scalar(
                            text(
                                """
                                SELECT 1
                                  FROM pg_policies
                                 WHERE schemaname = 'public'
                                   AND tablename = 'audit_trail'
                                   AND policyname = 'audit_trail_tenant_isolation'
                                """
                            )
                        )
                except Exception:
                    template_version = None
                    delivery_schedule_table = None
                    approval_sla_timers_table = None
                    ai_cfo_ledger_table = None
                    budget_status_events_has_chain_hash = True
                    audit_trail_policy = None
                finally:
                    await verify_engine.dispose()

                if (
                    template_version == _current_alembic_head()
                    and delivery_schedule_table is not None
                    and approval_sla_timers_table is not None
                    and ai_cfo_ledger_table is not None
                    and not budget_status_events_has_chain_hash
                    and audit_trail_policy is not None
                ):
                    return
                await _terminate_database_connections(conn, _TEMPLATE_DATABASE_NAME)
                await conn.execute(f'DROP DATABASE IF EXISTS "{_TEMPLATE_DATABASE_NAME}"')

            await _create_database(conn, _TEMPLATE_DATABASE_NAME)
        finally:
            await conn.close()

        bootstrap_engine = create_async_engine(template_url, echo=False)
        try:
            async with bootstrap_engine.begin() as bootstrap_conn:
                await _ensure_pgvector_available(bootstrap_conn)
                await _reset_public_schema(bootstrap_conn)
                await bootstrap_conn.run_sync(Base.metadata.create_all)
                await _ensure_shared_schema_bootstrapped(bootstrap_conn)
        finally:
            await bootstrap_engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
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


@pytest.fixture(autouse=True)
def _pin_session_event_loop(_session_scoped_runner) -> None:  # type: ignore[return]
    """
    Pin asyncio.get_event_loop() to the session runner's loop immediately
    before each test body executes.

    pytest-asyncio's wrap_in_sync() calls _get_event_loop_no_warn() (which
    resolves to asyncio.get_event_loop() in a sync context) to choose which
    loop runs the test coroutine.  All async fixtures use runner.run() with
    the session-scoped Runner, so their asyncpg connections have futures
    bound to that runner's loop.  If _local._loop is anything else when
    wrap_in_sync fires, asyncio raises "Future attached to a different loop".

    The async_client fixture captures the current loop via
    asyncio.get_event_loop_policy().get_event_loop() (bypassing
    asyncio.set_event_loop()) and restores it in teardown.  That path can
    silently leave _local._loop pointing at the temporary "wrap loop" that
    _temporary_event_loop_policy created before the session Runner was
    initialised.  This sync autouse fixture corrects that by explicitly
    re-pinning _local._loop to the session Runner's loop right before the
    test body runs, regardless of what prior fixture teardown left behind.
    """
    asyncio.set_event_loop(_session_scoped_runner._loop)
    yield


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_database_url() -> AsyncGenerator[str, None]:
    """
    Create a worker-isolated database so pytest-xdist can run without schema races.
    Each worker clones a prebuilt template database once for the session.
    """
    database_name = _worker_test_database_name()
    database_url = _with_database(TEST_DATABASE_URL, database_name)
    admin_url = _with_database(TEST_DATABASE_URL, TEST_DATABASE_ADMIN_DB)

    await _ensure_template_database(admin_url)

    conn = await asyncpg.connect(_to_asyncpg_dsn(admin_url))
    try:
        if await _database_exists(conn, database_name):
            await _terminate_database_connections(conn, database_name)
            await conn.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
        await _create_database(conn, database_name, template_name=_TEMPLATE_DATABASE_NAME)
    finally:
        await conn.close()

    try:
        yield database_url
    finally:
        # Keep the serial-run master database in place for the rest of the
        # process. Several legacy suites still assume ``finos_test_master``
        # remains available for late-bound setup helpers.
        if database_name == "finos_test_master":
            return
        cleanup_conn = await asyncpg.connect(_to_asyncpg_dsn(admin_url))
        try:
            await _terminate_database_connections(cleanup_conn, database_name)
            await cleanup_conn.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
        finally:
            await cleanup_conn.close()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine(test_database_url: str):
    """
    Create a shared test engine once per session.
    The worker database is pre-bootstrapped once and cloned from a template.
    """
    admin_url = _with_database(TEST_DATABASE_URL, TEST_DATABASE_ADMIN_DB)
    database_name = _worker_test_database_name()
    await _ensure_template_database(admin_url)
    conn = await asyncpg.connect(_to_asyncpg_dsn(admin_url))
    try:
        await _create_database(conn, database_name, template_name=_TEMPLATE_DATABASE_NAME)
    finally:
        await conn.close()
    test_engine = create_async_engine(test_database_url, echo=False, poolclass=NullPool)
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _bind_worker_database_to_runtime_session_factories(engine) -> AsyncGenerator[None, None]:
    """
    Rebind modules that manage their own sessions so xdist workers do not fall
    back to the process-startup ``finos_test_master`` database.
    """
    from financeops.db import session as db_session_module

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    original_engine = db_session_module.engine
    original_session_factory = db_session_module.AsyncSessionLocal
    patched_attrs: list[tuple[object, str, object]] = []

    for module in list(sys.modules.values()):
        if module is None:
            continue
        module_name = getattr(module, "__name__", "")
        if not module_name.startswith("financeops"):
            continue

        if getattr(module, "engine", object()) is original_engine:
            patched_attrs.append((module, "engine", original_engine))
            setattr(module, "engine", engine)

        if getattr(module, "AsyncSessionLocal", object()) is original_session_factory:
            patched_attrs.append((module, "AsyncSessionLocal", original_session_factory))
            setattr(module, "AsyncSessionLocal", session_factory)

    db_session_module.engine = engine
    db_session_module.AsyncSessionLocal = session_factory
    try:
        yield
    finally:
        for module, attr_name, original_value in reversed(patched_attrs):
            setattr(module, attr_name, original_value)
        db_session_module.engine = original_engine
        db_session_module.AsyncSessionLocal = original_session_factory




@pytest.fixture
def api_session_factory(engine):
    """
    Session factory for API-oriented tests.
    Setup data written through these sessions must be committed for request
    handlers to observe it through their own request-scoped sessions.
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture
async def api_db_session(api_session_factory) -> AsyncGenerator[AsyncSession, None]:
    """
    TYPE A â€” committed setup/assertion session for API tests.
    Data seeded through this fixture is committed so request-scoped sessions can
    observe it without sharing a live session object.
    """
    async with api_session_factory() as session:
        original_flush = session.flush

        async def _flush_and_commit(*args, **kwargs):
            await original_flush(*args, **kwargs)
            await session.commit()

        session.flush = _flush_and_commit  # type: ignore[method-assign]
        try:
            yield session
        finally:
            session.flush = original_flush  # type: ignore[method-assign]
            if session.in_transaction():
                await session.rollback()


@pytest_asyncio.fixture
async def async_session(
    request: pytest.FixtureRequest,
    engine,
    api_session_factory,
) -> AsyncGenerator[AsyncSession, None]:
    """
    TYPE B â€” direct DB tests:
      rollback-isolated session bound to a single connection.

    TYPE A â€” tests that also request ``async_client``:
      committed setup/verification session so API requests can observe data
      through their own fresh request-scoped sessions.
    """
    # Routing decision:
    #   async_client in fixturenames → committed (API test, data must be visible
    #     across request-scoped sessions)
    #   @pytest.mark.committed_session on the test → committed (service test
    #     that calls code which opens its own sessions)
    #   otherwise → rollback-isolated (pure unit/DB test)
    uses_committed_session = "async_client" in request.fixturenames or any(
        m.name == "committed_session" for m in request.node.iter_markers()
    )

    if uses_committed_session:
        async with api_session_factory() as session:
            original_flush = session.flush

            async def _flush_and_commit(*args, **kwargs):
                await original_flush(*args, **kwargs)
                await session.commit()

            session.flush = _flush_and_commit  # type: ignore[method-assign]
            try:
                yield session
            finally:
                session.flush = original_flush  # type: ignore[method-assign]
                if session.in_transaction():
                    await session.rollback()
        return

    async with engine.connect() as connection:
        if connection.in_transaction():
            await connection.rollback()
        outer_tx = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            try:
                if session.in_transaction():
                    await session.rollback()
            finally:
                await session.close()
                if outer_tx.is_active:
                    await outer_tx.rollback()


async def _seed_test_tenant(session: AsyncSession) -> IamTenant:
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
        org_setup_complete=True,
        org_setup_step=7,
    )
    session.add(tenant)
    await session.flush()
    return tenant


async def _seed_test_user(session: AsyncSession, tenant: IamTenant) -> IamUser:
    user = IamUser(
        tenant_id=tenant.id,
        email=f"testuser_{uuid.uuid4().hex[:12]}@example.com",
        hashed_password=_CACHED_TEST_PASSWORD_HASH,
        full_name="Test User",
        role=UserRole.finance_leader,
        is_active=True,
        mfa_enabled=False,
    )
    session.add(user)
    await session.flush()

    module = (
        await session.execute(
            select(CpModuleRegistry).where(CpModuleRegistry.module_code == "custom_report_builder")
        )
    ).scalar_one_or_none()
    if module is None:
        module = CpModuleRegistry(
            module_code="custom_report_builder",
            module_name="Custom Report Builder",
            engine_context="finance",
            is_financial_impacting=True,
            is_active=True,
        )
        session.add(module)
        await session.flush()
    await set_module_enablement(
        session,
        tenant_id=tenant.id,
        module_id=module.id,
        enabled=True,
        enablement_source="test",
        actor_user_id=user.id,
        correlation_id=f"seed-custom-report-builder-{tenant.id}",
        effective_from=datetime.now(UTC),
        effective_to=None,
    )
    await session.flush()

    org_payload = {
        "tenant_id": str(tenant.id),
        "organisation_code": "ORG_DEFAULT",
        "organisation_name": "Default Org",
    }
    org = CpOrganisation(
        tenant_id=tenant.id,
        organisation_code="ORG_DEFAULT",
        organisation_name="Default Org",
        parent_organisation_id=None,
        supersedes_id=None,
        is_active=True,
        correlation_id="test-default-org",
        chain_hash=compute_chain_hash(org_payload, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    session.add(org)
    await session.flush()

    entity_payload = {
        "tenant_id": str(tenant.id),
        "entity_code": "ENT_DEFAULT",
        "entity_name": "Default Entity",
        "organisation_id": str(org.id),
    }
    entity = CpEntity(
        tenant_id=tenant.id,
        organisation_id=org.id,
        group_id=None,
        entity_code="ENT_DEFAULT",
        entity_name="Default Entity",
        base_currency="INR",
        country_code="IN",
        status="active",
        deactivated_at=None,
        correlation_id="test-default-entity",
        chain_hash=compute_chain_hash(entity_payload, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    session.add(entity)
    await session.flush()
    return user


@pytest_asyncio.fixture
async def test_tenant(api_session_factory) -> IamTenant:
    """Create a committed test tenant in its own short-lived seed session."""
    async with api_session_factory() as session:
        tenant = await _seed_test_tenant(session)
        await session.commit()
        return tenant


@pytest_asyncio.fixture
async def test_user(
    api_session_factory,
    test_tenant: IamTenant,
    request: pytest.FixtureRequest,
) -> IamUser:
    """Create a committed test user in its own short-lived seed session."""
    _ = request
    async with api_session_factory() as session:
        user = await _seed_test_user(session, test_tenant)
        await session.commit()
        return user


@pytest_asyncio.fixture
async def api_test_tenant(api_db_session: AsyncSession) -> IamTenant:
    return await _seed_test_tenant(api_db_session)


@pytest_asyncio.fixture
async def api_test_user(
    api_db_session: AsyncSession,
    api_test_tenant: IamTenant,
) -> IamUser:
    return await _seed_test_user(api_db_session, api_test_tenant)


@pytest.fixture
def test_access_token(test_user: IamUser) -> str:
    """Return a valid JWT access token for the test user."""
    return create_access_token(test_user.id, test_user.tenant_id, test_user.role.value)


@pytest.fixture
def api_test_access_token(api_test_user: IamUser) -> str:
    """Return a valid JWT access token for the API-seeded test user."""
    return create_access_token(
        api_test_user.id,
        api_test_user.tenant_id,
        api_test_user.role.value,
    )


@pytest_asyncio.fixture
async def async_client(
    api_session_factory,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Return an httpx AsyncClient configured against the test FastAPI app.
    API requests always receive fresh request-scoped DB sessions and never
    reuse the direct fixture session object.
    """
    from financeops.api.deps import get_async_session
    from financeops.config import settings
    from financeops.db.rls import clear_tenant_context, set_tenant_context
    from financeops.db.session import finalize_session_success
    from financeops.main import app

    finance_prefix_modules = (
        ("/api/v1/analytics", "analytics"),
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

    # Redirect commit() to flush() â€” keeps data in the outer transaction so
    # session.rollback() in async_session can undo everything after the test.
    # Redirect commit() to flush() so application code calling commit() does
    # not break the outer rollback-based test isolation.
    original_startup_errors = getattr(app.state, "startup_errors", [])
    original_migration_state = getattr(app.state, "migration_state", None)
    app.state.startup_errors = []
    app.state.migration_state = {
        "status": "ok",
        "current_revision": "test",
        "head_revision": "test",
        "detail": None,
    }

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
        # The worker database is already provisioned by the session-scoped `engine`
        # fixture before any test runs. No per-request database setup is needed.
        async with api_session_factory() as session:
            if tenant_id:
                await set_tenant_context(session, tenant_id)
            try:
                yield session
                await finalize_session_success(session)
            except Exception:
                await session.rollback()
                raise
            finally:
                if tenant_id and session.in_transaction():
                    try:
                        await clear_tenant_context(session)
                    except Exception:
                        await session.rollback()

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
    app.state.startup_errors = original_startup_errors
    app.state.migration_state = original_migration_state


@pytest_asyncio.fixture
async def redis_client():
    """Return a test Redis connection."""
    import redis.asyncio as aioredis
    client = aioredis.from_url(TEST_REDIS_URL, encoding="utf-8", decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()
