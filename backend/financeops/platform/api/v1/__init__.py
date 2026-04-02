from __future__ import annotations

from fastapi import APIRouter

from financeops.platform.api.v1 import (
    entities,
    flags,
    isolation,
    modules,
    ops,
    organisations,
    plans,
    quotas,
    roles,
    tenants,
    workflows,
)

router = APIRouter()
router.include_router(tenants.router, prefix="/tenants", tags=["Platform Tenants"])
router.include_router(organisations.router, prefix="/org", tags=["Platform Hierarchy"])
router.include_router(entities.router, prefix="/entities", tags=["Platform Entities"])
router.include_router(modules.router, prefix="/modules", tags=["Platform Modules"])
router.include_router(plans.router, prefix="/plans", tags=["Platform Plans"])
router.include_router(roles.router, prefix="/rbac", tags=["Platform RBAC"])
router.include_router(workflows.router, prefix="/workflows", tags=["Platform Workflows"])
router.include_router(quotas.router, prefix="/quotas", tags=["Platform Quotas"])
router.include_router(flags.router, prefix="/flags", tags=["Platform Flags"])
router.include_router(isolation.router, prefix="/isolation", tags=["Platform Isolation"])
router.include_router(ops.router, prefix="/ops", tags=["Platform Ops"])
