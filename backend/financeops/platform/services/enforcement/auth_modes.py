from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuthMode(str, Enum):
    PUBLIC = "public"
    USER = "user"
    CONTROL_PLANE = "control_plane"
    SERVICE = "service"


@dataclass(frozen=True)
class RouteGroupAuthPolicy:
    route_group: str
    auth_mode: AuthMode
    tenant_scoped: bool
    entitlement_scoped: bool
    permission_style: str
    notes: str = ""


PUBLIC_AUTH_BOOTSTRAP_PATHS = frozenset(
    {
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/accept-invite",
        "/api/v1/auth/mfa/verify",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
    }
)

PUBLIC_WEBHOOK_PATHS = frozenset(
    {
        "/api/v1/billing/webhook",
        "/api/v1/billing/webhooks/stripe",
        "/api/v1/billing/webhooks/razorpay",
    }
)

PUBLIC_ROUTE_PATHS = PUBLIC_AUTH_BOOTSTRAP_PATHS | PUBLIC_WEBHOOK_PATHS

ROUTE_GROUP_AUTH_POLICIES = {
    "auth_routes": RouteGroupAuthPolicy(
        route_group="auth_routes",
        auth_mode=AuthMode.PUBLIC,
        tenant_scoped=False,
        entitlement_scoped=False,
        permission_style="bootstrap",
        notes="Public authentication bootstrap endpoints only.",
    ),
    "platform_admin_routes": RouteGroupAuthPolicy(
        route_group="platform_admin_routes",
        auth_mode=AuthMode.USER,
        tenant_scoped=True,
        entitlement_scoped=False,
        permission_style="platform.resource.action",
        notes="Browser session required; platform role gates apply.",
    ),
    "browser_finance_routes": RouteGroupAuthPolicy(
        route_group="browser_finance_routes",
        auth_mode=AuthMode.USER,
        tenant_scoped=True,
        entitlement_scoped=True,
        permission_style="module.action",
        notes="Normal browser/user plane routes. Never require control-plane token.",
    ),
    "control_plane_routes": RouteGroupAuthPolicy(
        route_group="control_plane_routes",
        auth_mode=AuthMode.CONTROL_PLANE,
        tenant_scoped=True,
        entitlement_scoped=False,
        permission_style="platform.control.action",
        notes="Dedicated control operations authenticated by control-plane token only.",
    ),
    "service_routes": RouteGroupAuthPolicy(
        route_group="service_routes",
        auth_mode=AuthMode.SERVICE,
        tenant_scoped=True,
        entitlement_scoped=False,
        permission_style="service.scope",
        notes="Backend or worker calls with service identity.",
    ),
    "webhook_routes": RouteGroupAuthPolicy(
        route_group="webhook_routes",
        auth_mode=AuthMode.PUBLIC,
        tenant_scoped=False,
        entitlement_scoped=False,
        permission_style="provider_signature",
        notes="Webhook endpoints remain public and rely on provider verification.",
    ),
}
