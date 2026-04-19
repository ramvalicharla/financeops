from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.committed_session

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.custom_report_builder import ReportResult, ReportRun
from financeops.db.rls import set_tenant_context
from financeops.modules.custom_report_builder.application.run_service import (
    ReportRunError,
    ReportRunService,
)
from financeops.modules.custom_report_builder.domain.filter_dsl import (
    FilterConfig,
    ReportDefinitionSchema,
)
from financeops.modules.custom_report_builder.infrastructure.repository import (
    ReportRepository,
)


class _StubExportService:
    def export_csv(self, rows: list[dict[str, Any]], report_name: str) -> tuple[bytes, str]:
        return (b"metric_key,metric_value\nmis.kpi.revenue,100.00\n", "report.csv")

    def export_excel(self, rows: list[dict[str, Any]], report_name: str) -> tuple[bytes, str]:
        return (b"PK\x03\x04excel", "report.xlsx")

    def export_pdf(self, rows: list[dict[str, Any]], report_name: str, generated_at: datetime) -> tuple[bytes, str]:
        return (b"%PDF-1.7\nreport\n", "report.pdf")


def _contains_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_float(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_float(v) for v in value)
    return False


async def _seed_definition_and_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    metric_keys: list[str] | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    repo = ReportRepository()
    schema = ReportDefinitionSchema(
        name="Revenue report",
        description="integration",
        metric_keys=metric_keys or ["mis.kpi.revenue"],
        filter_config=FilterConfig(),
        group_by=[],
        config={},
    )
    definition = await repo.create_definition(
        db=session,
        tenant_id=tenant_id,
        schema=schema,
        created_by=tenant_id,
    )
    run = await repo.create_run(
        db=session,
        tenant_id=tenant_id,
        definition_id=definition.id,
        triggered_by=tenant_id,
    )
    await session.commit()
    return definition.id, run.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_131_report_run_full_lifecycle_creates_three_state_rows(
    async_session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    _, run_id = await _seed_definition_and_run(async_session, tenant_id=tenant_id)

    service = ReportRunService(export_service=_StubExportService())
    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.application.run_service.settings",
        SimpleNamespace(ARTIFACTS_BASE_DIR=str(tmp_path)),
    )

    async def _fake_collect_rows(*, db, tenant_id, schema):  # noqa: ANN001
        return [{"metric_key": "mis.kpi.revenue", "metric_value": "100.00"}]

    monkeypatch.setattr(service, "_collect_rows", _fake_collect_rows)

    result = await service.run(db=async_session, run_id=run_id, tenant_id=tenant_id)
    assert result["status"] == "COMPLETE"

    rows = list(
        (
            await async_session.execute(
                select(ReportRun)
                .where(ReportRun.tenant_id == tenant_id)
                .order_by(ReportRun.created_at.asc(), ReportRun.id.asc())
            )
        ).scalars()
    )
    assert len(rows) == 3
    assert rows[-1].status == "COMPLETE"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_132_run_with_missing_run_id_raises_report_run_error(async_session: AsyncSession) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    service = ReportRunService(export_service=_StubExportService())
    with pytest.raises(ReportRunError, match="Report run not found"):
        await service.run(db=async_session, run_id=uuid.uuid4(), tenant_id=tenant_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_133_run_persists_report_result_with_result_hash(
    async_session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    _, run_id = await _seed_definition_and_run(async_session, tenant_id=tenant_id)
    service = ReportRunService(export_service=_StubExportService())
    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.application.run_service.settings",
        SimpleNamespace(ARTIFACTS_BASE_DIR=str(tmp_path)),
    )

    async def _fake_collect_rows(*, db, tenant_id, schema):  # noqa: ANN001
        return [{"metric_key": "mis.kpi.revenue", "metric_value": "100.00"}]

    monkeypatch.setattr(service, "_collect_rows", _fake_collect_rows)

    await service.run(db=async_session, run_id=run_id, tenant_id=tenant_id)
    result_row = (
        await async_session.execute(select(ReportResult).where(ReportResult.tenant_id == tenant_id))
    ).scalar_one()
    assert result_row.result_hash


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_134_result_hash_is_deterministic_for_same_input(
    async_session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    definition_id, run_id_1 = await _seed_definition_and_run(async_session, tenant_id=tenant_id)
    repo = ReportRepository()
    run_2 = await repo.create_run(
        db=async_session,
        tenant_id=tenant_id,
        definition_id=definition_id,
        triggered_by=tenant_id,
    )
    await async_session.commit()

    service = ReportRunService(export_service=_StubExportService())
    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.application.run_service.settings",
        SimpleNamespace(ARTIFACTS_BASE_DIR=str(tmp_path)),
    )

    async def _fake_collect_rows(*, db, tenant_id, schema):  # noqa: ANN001
        return [
            {"metric_key": "mis.kpi.revenue", "metric_value": "100.00"},
            {"metric_key": "mis.kpi.ebitda", "metric_value": "10.00"},
        ]

    monkeypatch.setattr(service, "_collect_rows", _fake_collect_rows)

    await service.run(db=async_session, run_id=run_id_1, tenant_id=tenant_id)
    await service.run(db=async_session, run_id=run_2.id, tenant_id=tenant_id)

    rows = list(
        (
            await async_session.execute(
                select(ReportResult)
                .where(ReportResult.tenant_id == tenant_id)
                .order_by(ReportResult.created_at.asc(), ReportResult.id.asc())
            )
        ).scalars()
    )
    assert len(rows) == 2
    assert rows[0].result_hash == rows[1].result_hash


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_135_complete_row_count_matches_result_data_length(
    async_session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    _, run_id = await _seed_definition_and_run(async_session, tenant_id=tenant_id)
    service = ReportRunService(export_service=_StubExportService())
    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.application.run_service.settings",
        SimpleNamespace(ARTIFACTS_BASE_DIR=str(tmp_path)),
    )

    async def _fake_collect_rows(*, db, tenant_id, schema):  # noqa: ANN001
        return [
            {"metric_key": "mis.kpi.revenue", "metric_value": "100.00"},
            {"metric_key": "mis.kpi.ebitda", "metric_value": "10.00"},
            {"metric_key": "mis.kpi.net_profit", "metric_value": "7.00"},
        ]

    monkeypatch.setattr(service, "_collect_rows", _fake_collect_rows)

    await service.run(db=async_session, run_id=run_id, tenant_id=tenant_id)
    latest_complete = (
        await async_session.execute(
            select(ReportRun)
            .where(ReportRun.tenant_id == tenant_id, ReportRun.status == "COMPLETE")
            .order_by(ReportRun.created_at.desc(), ReportRun.id.desc())
            .limit(1)
        )
    ).scalar_one()
    assert latest_complete.row_count == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_136_run_failure_appends_failed_row_with_error_message(
    async_session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    _, run_id = await _seed_definition_and_run(async_session, tenant_id=tenant_id)
    service = ReportRunService(export_service=_StubExportService())
    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.application.run_service.settings",
        SimpleNamespace(ARTIFACTS_BASE_DIR=str(tmp_path)),
    )

    async def _boom_collect_rows(*, db, tenant_id, schema):  # noqa: ANN001
        raise RuntimeError("forced-failure")

    monkeypatch.setattr(service, "_collect_rows", _boom_collect_rows)

    with pytest.raises(ReportRunError, match="forced-failure"):
        await service.run(db=async_session, run_id=run_id, tenant_id=tenant_id)

    rows = list(
        (
            await async_session.execute(
                select(ReportRun)
                .where(ReportRun.tenant_id == tenant_id)
                .order_by(ReportRun.created_at.asc(), ReportRun.id.asc())
            )
        ).scalars()
    )
    assert rows[-1].status == "FAILED"
    assert "forced-failure" in (rows[-1].error_message or "")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_137_all_state_rows_share_same_origin_run_id(
    async_session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    _, run_id = await _seed_definition_and_run(async_session, tenant_id=tenant_id)
    service = ReportRunService(export_service=_StubExportService())
    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.application.run_service.settings",
        SimpleNamespace(ARTIFACTS_BASE_DIR=str(tmp_path)),
    )

    async def _fake_collect_rows(*, db, tenant_id, schema):  # noqa: ANN001
        return [{"metric_key": "mis.kpi.revenue", "metric_value": "100.00"}]

    monkeypatch.setattr(service, "_collect_rows", _fake_collect_rows)
    await service.run(db=async_session, run_id=run_id, tenant_id=tenant_id)

    rows = list(
        (
            await async_session.execute(
                select(ReportRun)
                .where(ReportRun.tenant_id == tenant_id)
                .order_by(ReportRun.created_at.asc(), ReportRun.id.asc())
            )
        ).scalars()
    )
    origins = {str((row.run_metadata or {}).get("origin_run_id", "")) for row in rows}
    assert len(origins) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_t_138_result_data_contains_no_float_values(
    async_session: AsyncSession,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    _, run_id = await _seed_definition_and_run(async_session, tenant_id=tenant_id)
    service = ReportRunService(export_service=_StubExportService())
    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.application.run_service.settings",
        SimpleNamespace(ARTIFACTS_BASE_DIR=str(tmp_path)),
    )

    async def _fake_collect_rows(*, db, tenant_id, schema):  # noqa: ANN001
        return [
            {"metric_key": "mis.kpi.revenue", "metric_value": str(Decimal("100.00"))},
            {"metric_key": "mis.kpi.ebitda", "metric_value": str(Decimal("10.00"))},
        ]

    monkeypatch.setattr(service, "_collect_rows", _fake_collect_rows)
    await service.run(db=async_session, run_id=run_id, tenant_id=tenant_id)

    result_row = (
        await async_session.execute(select(ReportResult).where(ReportResult.tenant_id == tenant_id))
    ).scalar_one()
    assert not _contains_float(result_row.result_data)


@pytest.mark.integration
def test_t_139_celery_task_returns_complete_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    from financeops.modules.custom_report_builder.tasks import run_custom_report_task

    class _FakeService:
        async def run(self, *, db, run_id, tenant_id):  # noqa: ANN001
            return {"run_id": str(run_id), "status": "COMPLETE", "row_count": 1}

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    class _FakeSessionFactory:
        def __call__(self):
            return _FakeSession()

    async def _noop(*args, **kwargs):  # noqa: ANN002,ANN003
        return None

    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.tasks.ReportRunService",
        lambda: _FakeService(),
    )
    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.tasks.AsyncSessionLocal",
        _FakeSessionFactory(),
    )
    monkeypatch.setattr("financeops.modules.custom_report_builder.tasks.set_tenant_context", _noop)
    monkeypatch.setattr("financeops.modules.custom_report_builder.tasks.clear_tenant_context", _noop)
    retry_spy = MagicMock()
    monkeypatch.setattr(run_custom_report_task, "retry", retry_spy)

    run_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    result = run_custom_report_task.run(run_id=run_id, tenant_id=tenant_id)
    assert result == {"run_id": run_id, "status": "COMPLETE"}


@pytest.mark.integration
def test_t_140_celery_task_does_not_retry_on_report_run_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from financeops.modules.custom_report_builder.tasks import run_custom_report_task

    class _FakeService:
        async def run(self, *, db, run_id, tenant_id):  # noqa: ANN001
            raise ReportRunError("intentional-error")

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

    class _FakeSessionFactory:
        def __call__(self):
            return _FakeSession()

    async def _noop(*args, **kwargs):  # noqa: ANN002,ANN003
        return None

    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.tasks.ReportRunService",
        lambda: _FakeService(),
    )
    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.tasks.AsyncSessionLocal",
        _FakeSessionFactory(),
    )
    monkeypatch.setattr("financeops.modules.custom_report_builder.tasks.set_tenant_context", _noop)
    monkeypatch.setattr("financeops.modules.custom_report_builder.tasks.clear_tenant_context", _noop)
    retry_spy = MagicMock()
    monkeypatch.setattr(run_custom_report_task, "retry", retry_spy)

    with pytest.raises(ReportRunError):
        run_custom_report_task.run(run_id=str(uuid.uuid4()), tenant_id=str(uuid.uuid4()))
    retry_spy.assert_not_called()

