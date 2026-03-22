from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.custom_report_builder import ReportRun
from financeops.modules.custom_report_builder.application.run_service import (
    InvalidReportRunStateError,
    ReportRunService,
)
from financeops.modules.custom_report_builder.domain.enums import ReportRunStatus


def _make_run(status: str) -> ReportRun:
    tenant_id = uuid.uuid4()
    return ReportRun(
        tenant_id=tenant_id,
        definition_id=uuid.uuid4(),
        status=status,
        triggered_by=tenant_id,
        run_metadata={"origin_run_id": str(uuid.uuid4())},
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t_122_pending_to_complete_direct_transition_is_rejected(
    async_session: AsyncSession,
) -> None:
    service = ReportRunService()
    with pytest.raises(InvalidReportRunStateError):
        await service._transition_run_state(
            db=async_session,
            source_run=_make_run("PENDING"),
            to_status=ReportRunStatus.COMPLETE,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t_123_complete_to_running_transition_is_rejected(
    async_session: AsyncSession,
) -> None:
    service = ReportRunService()
    with pytest.raises(InvalidReportRunStateError):
        await service._transition_run_state(
            db=async_session,
            source_run=_make_run("COMPLETE"),
            to_status=ReportRunStatus.RUNNING,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t_124_failed_to_running_transition_is_rejected(
    async_session: AsyncSession,
) -> None:
    service = ReportRunService()
    with pytest.raises(InvalidReportRunStateError):
        await service._transition_run_state(
            db=async_session,
            source_run=_make_run("FAILED"),
            to_status=ReportRunStatus.RUNNING,
        )
