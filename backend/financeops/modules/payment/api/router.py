from __future__ import annotations

from fastapi import APIRouter, Depends

from financeops.modules.payment.api import (
    billing_portal,
    credits,
    invoices,
    payment_methods,
    plans,
    subscriptions,
    webhooks,
)
from financeops.platform.services.enforcement.interceptors import require_valid_context_token

router = APIRouter()

finance_control_plane_guard = Depends(require_valid_context_token())

router.include_router(plans.router, dependencies=[finance_control_plane_guard])
router.include_router(subscriptions.router, dependencies=[finance_control_plane_guard])
router.include_router(invoices.router, dependencies=[finance_control_plane_guard])
router.include_router(payment_methods.router, dependencies=[finance_control_plane_guard])
router.include_router(credits.router, dependencies=[finance_control_plane_guard])
router.include_router(billing_portal.router, dependencies=[finance_control_plane_guard])
router.include_router(webhooks.router)
