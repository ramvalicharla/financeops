from __future__ import annotations

from fastapi import APIRouter, Depends

from financeops.api.v1 import (
    anomaly_pattern_engine,
    auth,
    auditor,
    bank_recon,
    board_pack_narrative_engine,
    cash_flow_engine,
    consolidation,
    equity_engine,
    financial_risk_engine,
    fixed_assets,
    fx_translation_reporting,
    fx_rates,
    gst,
    health,
    lease,
    mis_manager,
    monthend,
    multi_entity_consolidation,
    observability_engine,
    ownership_consolidation,
    payroll_gl_reconciliation,
    payroll_gl_normalization,
    ratio_variance_engine,
    prepaid,
    reconciliation_bridge,
    revenue,
    reconciliation,
    tenants,
    working_capital,
)
from financeops.platform.api.v1 import router as platform_router
from financeops.platform.services.enforcement.interceptors import require_valid_context_token

router = APIRouter()

finance_control_plane_guard = Depends(require_valid_context_token())

# Phase 0
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(tenants.router, prefix="/tenants", tags=["Tenants"])

# Phase 1 - Core Finance Engine
router.include_router(
    mis_manager.router,
    prefix="/mis",
    tags=["MIS Manager"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    payroll_gl_normalization.router,
    prefix="/normalization",
    tags=["Payroll GL Normalization"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    payroll_gl_reconciliation.router,
    prefix="/payroll-gl-reconciliation",
    tags=["Payroll GL Reconciliation"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    ratio_variance_engine.router,
    prefix="/ratio-variance",
    tags=["Ratio Variance Engine"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    financial_risk_engine.router,
    prefix="/financial-risk",
    tags=["Financial Risk Engine"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    anomaly_pattern_engine.router,
    prefix="/anomaly-engine",
    tags=["Anomaly Pattern Engine"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    board_pack_narrative_engine.router,
    prefix="/board-pack",
    tags=["Board Pack Narrative Engine"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    reconciliation_bridge.router,
    prefix="/reconciliation",
    tags=["Reconciliation Bridge"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    reconciliation.router,
    prefix="/recon",
    tags=["GL/TB Reconciliation"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    bank_recon.router,
    prefix="/bank-recon",
    tags=["Bank Reconciliation"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    fx_translation_reporting.router,
    prefix="/fx",
    tags=["FX Translation Reporting"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    fx_rates.router,
    prefix="/fx",
    tags=["FX Rate Engine"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    consolidation.router,
    prefix="/consolidation",
    tags=["Multi-Currency Consolidation"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    multi_entity_consolidation.router,
    prefix="/consolidation",
    tags=["Multi-Entity Consolidation"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    ownership_consolidation.router,
    prefix="/ownership",
    tags=["Ownership Consolidation"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    cash_flow_engine.router,
    prefix="/cash-flow",
    tags=["Cash Flow Engine"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    equity_engine.router,
    prefix="/equity",
    tags=["Equity Engine"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    observability_engine.router,
    prefix="/observability",
    tags=["Observability Engine"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    revenue.router,
    prefix="/revenue",
    tags=["Revenue Recognition"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    lease.router,
    prefix="/lease",
    tags=["Lease Accounting"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    prepaid.router,
    prefix="/prepaid",
    tags=["Prepaid Amortization"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    fixed_assets.router,
    prefix="/fixed-assets",
    tags=["Fixed Assets Register"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    working_capital.router,
    prefix="/working-capital",
    tags=["Working Capital"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    gst.router,
    prefix="/gst",
    tags=["GST Reconciliation"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    monthend.router,
    prefix="/monthend",
    tags=["Month-End Checklist"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(
    auditor.router,
    prefix="/auditor",
    tags=["Auditor Access"],
    dependencies=[finance_control_plane_guard],
)
router.include_router(platform_router, prefix="/platform", tags=["Platform Control Plane"])
