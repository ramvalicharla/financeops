from __future__ import annotations

ERP_SYNC_PERMISSIONS: tuple[str, ...] = (
    "erp_sync:connection:manage",
    "erp_sync:connection:view",
    "erp_sync:sync_definition:manage",
    "erp_sync:sync_run:trigger",
    "erp_sync:sync_run:view",
    "erp_sync:sync_run:resume",
    "erp_sync:mapping:manage",
    "erp_sync:mapping:view",
    "erp_sync:publish:approve",
    "erp_sync:publish:view",
    "erp_sync:health:view",
    "erp_sync:drift:view",
    "erp_sync:drift:acknowledge",
    "erp_sync:period_lock:manage",
    "erp_sync:consent:view",
    "erp_sync:connector_version:manage",
)
