from __future__ import annotations

from fastapi import APIRouter

from financeops.modules.payment.api import (
    billing_portal,
    credits,
    invoices,
    payment_methods,
    plans,
    saas,
    subscriptions,
    webhooks,
)
router = APIRouter()
router.include_router(plans.router)
router.include_router(subscriptions.router)
router.include_router(invoices.router)
router.include_router(payment_methods.router)
router.include_router(credits.router)
router.include_router(billing_portal.router)
router.include_router(saas.router)
router.include_router(webhooks.router)
router.include_router(saas.public_router)
