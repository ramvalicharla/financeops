from __future__ import annotations

from fastapi import APIRouter

from financeops.api.v1 import (
    auth,
    auditor,
    bank_recon,
    gst,
    health,
    mis_manager,
    monthend,
    reconciliation,
    tenants,
    working_capital,
)

router = APIRouter()

# Phase 0
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(health.router, prefix="/health", tags=["Health"])
router.include_router(tenants.router, prefix="/tenants", tags=["Tenants"])

# Phase 1 — Core Finance Engine
router.include_router(mis_manager.router, prefix="/mis", tags=["MIS Manager"])
router.include_router(reconciliation.router, prefix="/recon", tags=["GL/TB Reconciliation"])
router.include_router(bank_recon.router, prefix="/bank-recon", tags=["Bank Reconciliation"])
router.include_router(working_capital.router, prefix="/working-capital", tags=["Working Capital"])
router.include_router(gst.router, prefix="/gst", tags=["GST Reconciliation"])
router.include_router(monthend.router, prefix="/monthend", tags=["Month-End Checklist"])
router.include_router(auditor.router, prefix="/auditor", tags=["Auditor Access"])
