from __future__ import annotations

from fastapi import APIRouter, Depends

from financeops.api.v1 import (
    accounting_ingestion,
    accounting_layer,
    ai_cfo,
    analytics,
    anomaly_pattern_engine,
    auth,
    auditor,
    bank_recon,
    board_pack_narrative_engine,
    close,
    cash_flow_engine,
    consolidation,
    erp_sync,
    erp,
    erp_push,
    equity_engine,
    financial_risk_engine,
    fixed_assets,
    fx_translation_reporting,
    fx_rates,
    gst,
    health,
    industry_modules,
    lease,
    mis_manager,
    monthend,
    multi_entity_consolidation,
    observability_engine,
    ownership_consolidation,
    payment,
    payroll_gl_reconciliation,
    payroll_gl_normalization,
    ratio_variance_engine,
    prepaid,
    reconciliation_bridge,
    revenue,
    reconciliation,
    users,
    tenants,
    working_capital,
)
from financeops.platform.api.v1 import (
    router as platform_router,
    service_router as platform_service_router,
)
from financeops.api.deps import require_entitlement, require_org_setup

router = APIRouter()

org_setup_guard = Depends(require_org_setup)
analytics_entitlement_guard = Depends(require_entitlement("analytics", record_usage=True))
ai_entitlement_guard = Depends(require_entitlement("ai_cfo", record_usage=True))
erp_entitlement_guard = Depends(require_entitlement("erp_integration", record_usage=True))
industry_modules_entitlement_guard = Depends(require_entitlement("industry_modules"))
mis_entitlement_guard = Depends(require_entitlement("mis_manager"))
normalization_entitlement_guard = Depends(require_entitlement("payroll_gl_normalization"))
payroll_recon_entitlement_guard = Depends(require_entitlement("payroll_gl_reconciliation"))
ratio_variance_entitlement_guard = Depends(require_entitlement("ratio_variance_engine"))
financial_risk_entitlement_guard = Depends(require_entitlement("financial_risk_engine"))
anomaly_entitlement_guard = Depends(require_entitlement("anomaly_pattern_engine"))
board_pack_entitlement_guard = Depends(require_entitlement("board_pack_narrative_engine"))
reconciliation_bridge_entitlement_guard = Depends(require_entitlement("reconciliation_bridge"))
reconciliation_entitlement_guard = Depends(require_entitlement("reconciliation"))
bank_reconciliation_entitlement_guard = Depends(require_entitlement("bank_reconciliation"))
fx_translation_entitlement_guard = Depends(require_entitlement("fx_translation_reporting"))
fx_rates_entitlement_guard = Depends(require_entitlement("fx"))
consolidation_entitlement_guard = Depends(require_entitlement("consolidation"))
multi_entity_consolidation_entitlement_guard = Depends(
    require_entitlement("multi_entity_consolidation")
)
ownership_consolidation_entitlement_guard = Depends(
    require_entitlement("ownership_consolidation")
)
cash_flow_entitlement_guard = Depends(require_entitlement("cash_flow_engine"))
equity_entitlement_guard = Depends(require_entitlement("equity_engine"))
observability_entitlement_guard = Depends(require_entitlement("observability_engine"))
revenue_entitlement_guard = Depends(require_entitlement("revenue"))
lease_entitlement_guard = Depends(require_entitlement("lease"))
prepaid_entitlement_guard = Depends(require_entitlement("prepaid"))
fixed_assets_entitlement_guard = Depends(require_entitlement("fixed_assets"))
working_capital_entitlement_guard = Depends(require_entitlement("working_capital"))
gst_entitlement_guard = Depends(require_entitlement("gst"))
monthend_entitlement_guard = Depends(require_entitlement("monthend"))

# Phase 0
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(
    tenants.router,
    prefix="/tenants",
    tags=["Tenants"],
    dependencies=[org_setup_guard],
)
router.include_router(users.router, tags=["Users"], dependencies=[org_setup_guard])

# Phase 1 - Core Finance Engine
router.include_router(
    accounting_ingestion.public_router,
    prefix="",
    tags=["Accounting Ingestion Public"],
)
router.include_router(
    accounting_ingestion.router,
    prefix="",
    tags=["Accounting Ingestion"],
    dependencies=[org_setup_guard],
)
router.include_router(
    accounting_layer.router,
    prefix="/accounting",
    tags=["Accounting Layer"],
    dependencies=[org_setup_guard],
)
router.include_router(
    analytics.router,
    prefix="",
    tags=["Analytics Layer"],
    dependencies=[org_setup_guard, analytics_entitlement_guard],
)
router.include_router(
    ai_cfo.router,
    prefix="",
    tags=["AI CFO Layer"],
    dependencies=[org_setup_guard, ai_entitlement_guard],
)
router.include_router(
    mis_manager.router,
    prefix="/mis",
    tags=["MIS Manager"],
    dependencies=[org_setup_guard, mis_entitlement_guard],
)
router.include_router(
    payroll_gl_normalization.router,
    prefix="/normalization",
    tags=["Payroll GL Normalization"],
    dependencies=[org_setup_guard, normalization_entitlement_guard],
)
router.include_router(
    payroll_gl_reconciliation.router,
    prefix="/payroll-gl-reconciliation",
    tags=["Payroll GL Reconciliation"],
    dependencies=[org_setup_guard, payroll_recon_entitlement_guard],
)
router.include_router(
    ratio_variance_engine.router,
    prefix="/ratio-variance",
    tags=["Ratio Variance Engine"],
    dependencies=[org_setup_guard, ratio_variance_entitlement_guard],
)
router.include_router(
    financial_risk_engine.router,
    prefix="/financial-risk",
    tags=["Financial Risk Engine"],
    dependencies=[org_setup_guard, financial_risk_entitlement_guard],
)
router.include_router(
    anomaly_pattern_engine.router,
    prefix="/anomaly-engine",
    tags=["Anomaly Pattern Engine"],
    dependencies=[org_setup_guard, anomaly_entitlement_guard],
)
router.include_router(
    board_pack_narrative_engine.router,
    prefix="/board-pack",
    tags=["Board Pack Narrative Engine"],
    dependencies=[org_setup_guard, board_pack_entitlement_guard],
)
router.include_router(
    reconciliation_bridge.router,
    prefix="/reconciliation",
    tags=["Reconciliation Bridge"],
    dependencies=[org_setup_guard, reconciliation_bridge_entitlement_guard],
)
router.include_router(
    reconciliation.router,
    prefix="/recon",
    tags=["GL/TB Reconciliation"],
    dependencies=[org_setup_guard, reconciliation_entitlement_guard],
)
router.include_router(
    bank_recon.router,
    prefix="/bank-recon",
    tags=["Bank Reconciliation"],
    dependencies=[org_setup_guard, bank_reconciliation_entitlement_guard],
)
router.include_router(
    fx_translation_reporting.router,
    prefix="/fx",
    tags=["FX Translation Reporting"],
    dependencies=[org_setup_guard, fx_translation_entitlement_guard],
)
router.include_router(
    fx_rates.router,
    prefix="/fx",
    tags=["FX Rate Engine"],
    dependencies=[org_setup_guard, fx_rates_entitlement_guard],
)
router.include_router(
    consolidation.router,
    prefix="/consolidation",
    tags=["Multi-Currency Consolidation"],
    dependencies=[org_setup_guard, consolidation_entitlement_guard],
)
router.include_router(
    multi_entity_consolidation.router,
    prefix="/consolidation",
    tags=["Multi-Entity Consolidation"],
    dependencies=[org_setup_guard, multi_entity_consolidation_entitlement_guard],
)
router.include_router(
    ownership_consolidation.router,
    prefix="/ownership",
    tags=["Ownership Consolidation"],
    dependencies=[org_setup_guard, ownership_consolidation_entitlement_guard],
)
router.include_router(
    cash_flow_engine.router,
    prefix="/cash-flow",
    tags=["Cash Flow Engine"],
    dependencies=[org_setup_guard, cash_flow_entitlement_guard],
)
router.include_router(
    equity_engine.router,
    prefix="/equity",
    tags=["Equity Engine"],
    dependencies=[org_setup_guard, equity_entitlement_guard],
)
router.include_router(
    observability_engine.router,
    prefix="/observability",
    tags=["Observability Engine"],
    dependencies=[org_setup_guard, observability_entitlement_guard],
)
router.include_router(
    erp.router,
    prefix="",
    tags=["ERP Integration"],
    dependencies=[org_setup_guard, erp_entitlement_guard],
)
router.include_router(
    erp_sync.router,
    prefix="/erp-sync",
    tags=["ERP Sync Kernel"],
    dependencies=[org_setup_guard, erp_entitlement_guard],
)
router.include_router(
    erp_push.webhook_router,
    prefix="/erp-push",
    tags=["ERP Webhooks"],
)
router.include_router(
    erp_push.router,
    prefix="/erp-push",
    tags=["ERP Push"],
    dependencies=[org_setup_guard],
)
router.include_router(
    payment.router,
    prefix="/billing",
    tags=["Billing"],
)
router.include_router(
    industry_modules.router,
    prefix="",
    tags=["Industry Modules"],
    dependencies=[org_setup_guard, industry_modules_entitlement_guard],
)
router.include_router(
    revenue.router,
    prefix="/revenue",
    tags=["Revenue Recognition"],
    dependencies=[org_setup_guard, revenue_entitlement_guard],
)
router.include_router(
    lease.router,
    prefix="/lease",
    tags=["Lease Accounting"],
    dependencies=[org_setup_guard, lease_entitlement_guard],
)
router.include_router(
    prepaid.router,
    prefix="/prepaid",
    tags=["Prepaid Amortization"],
    dependencies=[org_setup_guard, prepaid_entitlement_guard],
)
router.include_router(
    fixed_assets.router,
    prefix="/fixed-assets",
    tags=["Fixed Assets Register"],
    dependencies=[org_setup_guard, fixed_assets_entitlement_guard],
)
router.include_router(
    working_capital.router,
    prefix="/working-capital",
    tags=["Working Capital"],
    dependencies=[org_setup_guard, working_capital_entitlement_guard],
)
router.include_router(
    gst.router,
    prefix="/gst",
    tags=["GST Reconciliation"],
    dependencies=[org_setup_guard, gst_entitlement_guard],
)
router.include_router(
    monthend.router,
    prefix="/monthend",
    tags=["Month-End Checklist"],
    dependencies=[org_setup_guard, monthend_entitlement_guard],
)
router.include_router(
    close.router,
    tags=["Month-End Close Workflow"],
    dependencies=[org_setup_guard, monthend_entitlement_guard],
)
router.include_router(
    auditor.router,
    prefix="/auditor",
    tags=["Auditor Access"],
    dependencies=[org_setup_guard],
)
router.include_router(
    platform_router,
    prefix="/platform",
    tags=["Platform Control Plane"],
    dependencies=[org_setup_guard],
)
router.include_router(
    platform_service_router,
    prefix="/platform",
    tags=["Platform Services"],
)
