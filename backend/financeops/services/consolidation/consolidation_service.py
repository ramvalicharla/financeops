from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.services.audit_writer import AuditWriter
from financeops.services.consolidation.fx_application import resolve_expected_rate_for_entity
from financeops.services.consolidation.run_creation import create_or_get_run
from financeops.services.consolidation.run_events import mark_run_running
from financeops.services.consolidation.run_finalize import finalize_run
from financeops.services.consolidation.run_processing import (
    aggregate_results_for_run,
    apply_fx_for_run,
    compute_eliminations_for_run,
    match_intercompany_for_run,
    prepare_entities_for_run as _prepare_entities_for_run,
)
from financeops.services.consolidation.run_queries import (
    build_export,
    get_run_status,
    list_ic_differences,
    list_results,
)
from financeops.services.consolidation.service_types import ExportPayload, RunCreateResult


async def prepare_entities_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID | None,
    correlation_id: str | None,
) -> int:
    return await _prepare_entities_for_run(
        session,
        tenant_id=tenant_id,
        run_id=run_id,
        user_id=user_id,
        correlation_id=correlation_id,
        resolve_expected_rate_for_entity_fn=resolve_expected_rate_for_entity,
        insert_financial_record_fn=AuditWriter.insert_financial_record,
    )


__all__ = [
    "AuditWriter",
    "ExportPayload",
    "RunCreateResult",
    "aggregate_results_for_run",
    "apply_fx_for_run",
    "build_export",
    "compute_eliminations_for_run",
    "create_or_get_run",
    "finalize_run",
    "get_run_status",
    "list_ic_differences",
    "list_results",
    "mark_run_running",
    "match_intercompany_for_run",
    "prepare_entities_for_run",
    "resolve_expected_rate_for_entity",
]
