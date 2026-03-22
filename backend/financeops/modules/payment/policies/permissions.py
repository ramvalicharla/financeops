from __future__ import annotations

PAYMENT_PERMISSIONS: tuple[str, ...] = (
    "billing:plan:view",
    "billing:subscription:manage",
    "billing:subscription:view",
    "billing:invoice:view",
    "billing:invoice:pay",
    "billing:payment_method:manage",
    "billing:credits:view",
    "billing:credits:purchase",
    "billing:portal:access",
    "billing:admin:activate",
    "billing:admin:adjust_credits",
    "billing:admin:override_provider",
    "billing:webhook:receive",
)

