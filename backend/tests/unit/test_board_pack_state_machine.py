from __future__ import annotations

import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from financeops.modules.board_pack_generator.domain.enums import PackRunStatus
from financeops.modules.board_pack_generator.domain.pack_definition import PackDefinitionSchema, PackRunContext, SectionConfig


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t_030_transition_pending_to_complete_rejected() -> None:
    from financeops.modules.board_pack_generator.application.generate_service import (
        BoardPackGenerateService,
        InvalidRunStateError,
    )

    service = BoardPackGenerateService()
    run = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        definition_id=uuid.uuid4(),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        status=PackRunStatus.PENDING.value,
        triggered_by=uuid.uuid4(),
        run_metadata={"origin_run_id": str(uuid.uuid4())},
        started_at=None,
    )

    with pytest.raises(InvalidRunStateError):
        await service._transition_run_state(  # noqa: SLF001
            db=MagicMock(),
            source_run=run,
            to_status=PackRunStatus.COMPLETE,
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_t_031_transition_from_complete_rejected() -> None:
    from financeops.modules.board_pack_generator.application.generate_service import (
        BoardPackGenerateService,
        InvalidRunStateError,
    )

    service = BoardPackGenerateService()
    run = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        definition_id=uuid.uuid4(),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        status=PackRunStatus.COMPLETE.value,
        triggered_by=uuid.uuid4(),
        run_metadata={"origin_run_id": str(uuid.uuid4())},
        started_at=None,
    )

    with pytest.raises(InvalidRunStateError):
        await service._transition_run_state(  # noqa: SLF001
            db=MagicMock(),
            source_run=run,
            to_status=PackRunStatus.RUNNING,
        )


@pytest.mark.unit
def test_t_039_celery_task_does_not_retry_on_board_pack_generation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from financeops.modules.board_pack_generator.application.generate_service import (
        BoardPackGenerationError,
    )
    from financeops.modules.board_pack_generator.tasks import generate_board_pack_task

    run_row = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        definition_id=uuid.uuid4(),
        triggered_by=uuid.uuid4(),
        run_metadata={},
    )

    class _FakeService:
        async def generate(self, *, db, run_id, tenant_id):  # noqa: ANN001
            raise BoardPackGenerationError("hard failure")

    class _FakeResult:
        def scalar_one_or_none(self):
            return run_row

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        async def execute(self, statement):  # noqa: ANN001
            return _FakeResult()

    class _FakeSessionFactory:
        def __call__(self):
            return _FakeSession()

    async def _noop(*args, **kwargs):  # noqa: ANN002,ANN003
        return None

    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.tasks.BoardPackGenerateService",
        lambda: _FakeService(),
    )
    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.tasks.AsyncSessionLocal",
        _FakeSessionFactory(),
    )
    monkeypatch.setattr("financeops.modules.board_pack_generator.tasks.set_tenant_context", _noop)
    monkeypatch.setattr("financeops.modules.board_pack_generator.tasks.clear_tenant_context", _noop)

    retry_spy = MagicMock(side_effect=AssertionError("retry must not be called"))
    monkeypatch.setattr(generate_board_pack_task, "retry", retry_spy)

    with pytest.raises(BoardPackGenerationError):
        generate_board_pack_task.run(
            run_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
        )

    retry_spy.assert_not_called()


@pytest.mark.unit
def test_t_040_chunked_board_pack_dispatches_section_chord(monkeypatch: pytest.MonkeyPatch) -> None:
    from financeops.modules.board_pack_generator.domain.enums import PeriodType, SectionType
    from financeops.modules.board_pack_generator.tasks import generate_board_pack_task

    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    running_run_id = uuid.uuid4()
    run_row = SimpleNamespace(
        id=run_id,
        tenant_id=tenant_id,
        definition_id=uuid.uuid4(),
        triggered_by=uuid.uuid4(),
        run_metadata={},
    )
    running_run = SimpleNamespace(
        id=running_run_id,
        tenant_id=tenant_id,
        definition_id=run_row.definition_id,
        triggered_by=run_row.triggered_by,
    )
    context = PackRunContext(
        run_id=running_run_id,
        tenant_id=tenant_id,
        definition=PackDefinitionSchema(
            name="Board Pack",
            section_configs=[
                SectionConfig(section_type=SectionType.PROFIT_AND_LOSS, order=1),
                SectionConfig(section_type=SectionType.BALANCE_SHEET, order=2),
            ],
            entity_ids=[uuid.uuid4()],
            period_type=PeriodType.MONTHLY,
            config={},
        ),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        triggered_by=run_row.triggered_by,
    )

    class _FakeResult:
        def scalar_one_or_none(self):
            return run_row

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        async def execute(self, statement):  # noqa: ANN001
            return _FakeResult()

    class _FakeSessionFactory:
        def __call__(self):
            return _FakeSession()

    class _FakeService:
        async def start_generation(self, *, db, run_id, tenant_id):  # noqa: ANN001
            return running_run, context

    dispatched: dict[str, object] = {}

    def _fake_chord(section_tasks):
        dispatched["section_tasks"] = list(section_tasks)

        def _apply(callback):
            dispatched["callback"] = callback
            return None

        return _apply

    async def _noop(*args, **kwargs):  # noqa: ANN002,ANN003
        return None

    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.tasks.settings",
        SimpleNamespace(ENABLE_CHUNKED_TASKS=True),
    )
    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.tasks.AsyncSessionLocal",
        _FakeSessionFactory(),
    )
    monkeypatch.setattr(
        "financeops.modules.board_pack_generator.tasks.BoardPackGenerateService",
        lambda: _FakeService(),
    )
    monkeypatch.setattr("financeops.modules.board_pack_generator.tasks.set_tenant_context", _noop)
    monkeypatch.setattr("financeops.modules.board_pack_generator.tasks.clear_tenant_context", _noop)
    monkeypatch.setattr("financeops.modules.board_pack_generator.tasks.chord", _fake_chord)

    result = generate_board_pack_task.run(
        run_id=str(run_id),
        tenant_id=str(tenant_id),
    )

    assert result == {
        "run_id": str(run_id),
        "worker_run_id": str(running_run_id),
        "status": "RUNNING",
    }
    assert len(dispatched["section_tasks"]) == 2
    assert dispatched["callback"] is not None
