from __future__ import annotations

from fastapi import APIRouter

from financeops.modules.erp_sync.api import (
    bootstrap,
    coa_mappings,
    connections,
    datasets,
    drift,
    export_journals,
    health,
    mappings,
    oauth,
    publish,
    sync_definitions,
    sync_runs,
)

router = APIRouter()
router.include_router(bootstrap.router)
router.include_router(connections.router)
router.include_router(sync_definitions.router)
# export_journals must be registered before sync_runs to avoid /{id} catching the literal path
router.include_router(export_journals.router)
router.include_router(sync_runs.router)
router.include_router(oauth.router)
router.include_router(datasets.router)
router.include_router(mappings.router)
router.include_router(coa_mappings.router)
router.include_router(publish.router)
router.include_router(health.router)
router.include_router(drift.router)
