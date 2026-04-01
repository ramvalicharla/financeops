from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from financeops.core.exceptions import ValidationError
from financeops.db.models.erp_integration import (
    ErpAuthType,
    ErpConnectorStatus,
    ErpSyncModule,
    ErpSyncStatus,
    ErpSyncType,
)
from financeops.db.models.users import UserRole
from financeops.modules.erp_integration.api import routes as erp_routes
from financeops.modules.erp_integration.application import service as erp_service_module
from financeops.modules.erp_integration.application.service import ErpIntegrationService
from financeops.modules.erp_integration.connectors.registry import ManualConnector, get_connector
from financeops.modules.erp_integration.schemas import (
    CoaMapRequest,
    CoaMapItem,
    ConnectorCreateRequest,
    JournalExportRequest,
    JournalImportRequest,
    JournalImportTransaction,
    JournalImportLine,
    SyncRunRequest,
)


class _Result:
    def __init__(self, *, one_or_none: object | None = None, all_values: list[object] | None = None) -> None:
        self._one_or_none = one_or_none
        self._all_values = all_values or []

    def scalar_one_or_none(self) -> object | None:
        return self._one_or_none

    def scalars(self) -> _Result:
        return self

    def all(self) -> list[object]:
        return self._all_values


def _mock_connector() -> SimpleNamespace:
    return SimpleNamespace(
        fetch_transactions=AsyncMock(return_value=[]),
        push_journal=AsyncMock(return_value={"erp_journal_id": "erp-journal-1"}),
        fetch_chart_of_accounts=AsyncMock(return_value=[]),
        fetch_vendors=AsyncMock(return_value=[]),
        fetch_customers=AsyncMock(return_value=[]),
        authenticate=AsyncMock(return_value={"ok": True}),
    )


def test_registry_manual_connector() -> None:
    connector = get_connector("MANUAL")
    assert isinstance(connector, ManualConnector)


def test_registry_unsupported_connector() -> None:
    with pytest.raises(ValidationError):
        get_connector("NOT_A_REAL_ERP")


@pytest.mark.asyncio
async def test_import_journals_creates_draft_and_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result(all_values=[]))
    session.add = MagicMock()
    service = ErpIntegrationService(session)

    connector_row = SimpleNamespace(
        id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        erp_type="MANUAL",
        connection_config={},
    )
    actor = SimpleNamespace(id=uuid.uuid4())
    created_journal = SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(service, "_get_connector", AsyncMock(return_value=connector_row))
    monkeypatch.setattr(service, "_assert_account_code_scope", AsyncMock(return_value=None))
    monkeypatch.setattr(erp_service_module, "get_connector", lambda _: _mock_connector())
    monkeypatch.setattr(
        erp_service_module,
        "create_journal_draft",
        AsyncMock(return_value=created_journal),
    )

    request = JournalImportRequest(
        erp_connector_id=connector_row.id,
        transactions=[
            JournalImportTransaction(
                external_reference_id="ERP-TXN-001",
                journal_date="2026-04-01",
                reference="TXN-001",
                narration="ERP import",
                lines=[
                    JournalImportLine(account_code="1000", debit="100.00", credit="0"),
                    JournalImportLine(account_code="2000", debit="0", credit="100.00"),
                ],
            )
        ],
    )

    payload = await service.import_journals(
        tenant_id=uuid.uuid4(),
        actor=actor,
        body=request,
    )
    assert payload["imported_count"] == 1
    assert payload["failed_count"] == 0


@pytest.mark.asyncio
async def test_export_journals_tracks_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    line = SimpleNamespace(
        jv_version=1,
        line_number=1,
        account_code="1000",
        account_name="Cash",
        entry_type="DEBIT",
        amount="100.00",
        currency="INR",
    )
    line2 = SimpleNamespace(
        jv_version=1,
        line_number=2,
        account_code="2000",
        account_name="Revenue",
        entry_type="CREDIT",
        amount="100.00",
        currency="INR",
    )
    journal_ok = SimpleNamespace(
        id=uuid.uuid4(),
        jv_number="JV-1",
        period_date=SimpleNamespace(isoformat=lambda: "2026-04-01"),
        reference="REF-1",
        description="Ok",
        external_reference_id=None,
        version=1,
        lines=[line, line2],
    )
    journal_fail = SimpleNamespace(
        id=uuid.uuid4(),
        jv_number="JV-2",
        period_date=SimpleNamespace(isoformat=lambda: "2026-04-01"),
        reference="REF-2",
        description="Fail",
        external_reference_id=None,
        version=1,
        lines=[line, line2],
    )
    session.execute = AsyncMock(
        side_effect=[
            _Result(all_values=[journal_ok, journal_fail]),
            _Result(all_values=[]),
        ]
    )
    session.add = MagicMock()
    service = ErpIntegrationService(session)

    connector_row = SimpleNamespace(
        id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        erp_type="MANUAL",
        connection_config={},
    )
    actor = SimpleNamespace(id=uuid.uuid4())

    connector = _mock_connector()
    connector.push_journal = AsyncMock(
        side_effect=[{"erp_journal_id": "ERP-JV-1"}, RuntimeError("push failed")]
    )
    monkeypatch.setattr(service, "_get_connector", AsyncMock(return_value=connector_row))
    monkeypatch.setattr(erp_service_module, "get_connector", lambda _: connector)

    payload = await service.export_journals(
        tenant_id=uuid.uuid4(),
        actor=actor,
        body=JournalExportRequest(erp_connector_id=connector_row.id),
    )
    assert payload["exported_count"] == 1
    assert payload["failed_count"] == 1


@pytest.mark.asyncio
async def test_map_coa_upserts_all_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    service = ErpIntegrationService(session)

    connector_row = SimpleNamespace(id=uuid.uuid4())
    monkeypatch.setattr(service, "_get_connector", AsyncMock(return_value=connector_row))
    monkeypatch.setattr(service, "_assert_account_scope", AsyncMock(return_value=None))

    request = CoaMapRequest(
        erp_connector_id=connector_row.id,
        mappings=[
            CoaMapItem(erp_account_id="A-100", internal_account_id=uuid.uuid4()),
            CoaMapItem(erp_account_id="A-200", internal_account_id=uuid.uuid4()),
        ],
    )
    payload = await service.map_coa(tenant_id=uuid.uuid4(), body=request)
    assert payload["upserted"] == 2


@pytest.mark.asyncio
async def test_import_journals_is_idempotent_for_duplicate_external_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result(all_values=[]))
    session.add = MagicMock()
    service = ErpIntegrationService(session)

    connector_row = SimpleNamespace(
        id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        erp_type="MANUAL",
        connection_config={},
    )
    actor = SimpleNamespace(id=uuid.uuid4())
    create_draft_mock = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))

    monkeypatch.setattr(service, "_get_connector", AsyncMock(return_value=connector_row))
    monkeypatch.setattr(service, "_assert_account_code_scope", AsyncMock(return_value=None))
    monkeypatch.setattr(erp_service_module, "create_journal_draft", create_draft_mock)
    monkeypatch.setattr(erp_service_module, "get_connector", lambda _: _mock_connector())

    tx = JournalImportTransaction(
        external_reference_id="ERP-TXN-001",
        journal_date="2026-04-01",
        reference="TXN-001",
        narration="ERP import",
        lines=[
            JournalImportLine(account_code="1000", debit="100.00", credit="0"),
            JournalImportLine(account_code="2000", debit="0", credit="100.00"),
        ],
    )
    request = JournalImportRequest(
        erp_connector_id=connector_row.id,
        transactions=[tx, tx],
    )

    payload = await service.import_journals(
        tenant_id=uuid.uuid4(),
        actor=actor,
        body=request,
    )
    assert payload["imported_count"] == 1
    assert payload["skipped_duplicates"] == 1
    assert payload["failed_count"] == 0
    assert create_draft_mock.await_count == 1


@pytest.mark.asyncio
async def test_import_journals_with_unmapped_account_is_flagged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result(all_values=[]))
    session.add = MagicMock()
    service = ErpIntegrationService(session)

    connector_row = SimpleNamespace(
        id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        erp_type="MANUAL",
        connection_config={},
    )
    actor = SimpleNamespace(id=uuid.uuid4())
    create_draft_mock = AsyncMock()

    monkeypatch.setattr(service, "_get_connector", AsyncMock(return_value=connector_row))
    monkeypatch.setattr(
        service,
        "_assert_account_code_scope",
        AsyncMock(side_effect=ValidationError("account mapping missing")),
    )
    monkeypatch.setattr(erp_service_module, "create_journal_draft", create_draft_mock)
    monkeypatch.setattr(erp_service_module, "get_connector", lambda _: _mock_connector())

    request = JournalImportRequest(
        erp_connector_id=connector_row.id,
        transactions=[
            JournalImportTransaction(
                external_reference_id="ERP-TXN-404",
                journal_date="2026-04-01",
                reference="TXN-404",
                narration="Unmapped account",
                lines=[
                    JournalImportLine(account_code="9999", debit="100.00", credit="0"),
                    JournalImportLine(account_code="2000", debit="0", credit="100.00"),
                ],
            )
        ],
    )

    payload = await service.import_journals(
        tenant_id=uuid.uuid4(),
        actor=actor,
        body=request,
    )
    assert payload["imported_count"] == 0
    assert payload["failed_count"] == 1
    assert create_draft_mock.await_count == 0


@pytest.mark.asyncio
async def test_imported_journals_are_created_as_draft_with_erp_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_Result(all_values=[]))
    session.add = MagicMock()
    service = ErpIntegrationService(session)

    connector_row = SimpleNamespace(
        id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        erp_type="MANUAL",
        connection_config={},
    )
    actor = SimpleNamespace(id=uuid.uuid4())
    create_draft_mock = AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))

    monkeypatch.setattr(service, "_get_connector", AsyncMock(return_value=connector_row))
    monkeypatch.setattr(service, "_assert_account_code_scope", AsyncMock(return_value=None))
    monkeypatch.setattr(erp_service_module, "create_journal_draft", create_draft_mock)
    monkeypatch.setattr(erp_service_module, "get_connector", lambda _: _mock_connector())

    request = JournalImportRequest(
        erp_connector_id=connector_row.id,
        transactions=[
            JournalImportTransaction(
                external_reference_id="ERP-TXN-DRAFT",
                journal_date="2026-04-01",
                reference="TXN-DRAFT",
                narration="Draft import",
                lines=[
                    JournalImportLine(account_code="1000", debit="100.00", credit="0"),
                    JournalImportLine(account_code="2000", debit="0", credit="100.00"),
                ],
            )
        ],
    )

    payload = await service.import_journals(
        tenant_id=uuid.uuid4(),
        actor=actor,
        body=request,
    )
    assert payload["imported_count"] == 1
    kwargs = create_draft_mock.await_args.kwargs
    assert kwargs["source"] == "ERP"
    assert kwargs["external_reference_id"] == "ERP-TXN-DRAFT"


@pytest.mark.asyncio
async def test_run_sync_job_marks_failed_and_increments_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock(return_value=_Result(all_values=[]))
    service = ErpIntegrationService(session)

    connector_row = SimpleNamespace(
        id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        erp_type="MANUAL",
        connection_config={},
        last_sync_at=None,
    )
    actor = SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(service, "_get_connector", AsyncMock(return_value=connector_row))
    monkeypatch.setattr(service, "get_job", AsyncMock(return_value=SimpleNamespace(retry_count=2)))
    monkeypatch.setattr(
        service,
        "_import_coa",
        AsyncMock(side_effect=RuntimeError("connector auth failed")),
    )
    monkeypatch.setattr(erp_service_module, "get_connector", lambda _: _mock_connector())

    job = await service.run_sync_job(
        tenant_id=uuid.uuid4(),
        actor=actor,
        body=SyncRunRequest(
            erp_connector_id=connector_row.id,
            sync_type=ErpSyncType.IMPORT,
            module=ErpSyncModule.COA,
            payload={},
            retry_of_job_id=uuid.uuid4(),
        ),
    )
    assert job.status == ErpSyncStatus.FAILED
    assert job.retry_count == 3
    assert "connector auth failed" in (job.error_message or "")


@pytest.mark.asyncio
async def test_create_connector_route_commits_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AsyncMock()
    session.commit = AsyncMock()

    row = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        org_entity_id=uuid.uuid4(),
        erp_type="TALLY",
        auth_type=ErpAuthType.API_KEY,
        status=ErpConnectorStatus.ACTIVE,
        last_sync_at=None,
        created_at=datetime.now(tz=timezone.utc),
    )

    class _FakeService:
        def __init__(self, _session: object) -> None:
            self._session = _session

        async def create_connector(
            self,
            *,
            tenant_id: uuid.UUID,
            user_id: uuid.UUID,
            body: ConnectorCreateRequest,
        ) -> object:
            return row

    user = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=row.tenant_id,
        role=UserRole.finance_leader,
    )
    request = SimpleNamespace(state=SimpleNamespace(request_id="req-1"))

    monkeypatch.setattr(erp_routes, "ErpIntegrationService", _FakeService)

    await erp_routes.create_connector(
        request=request,
        body=ConnectorCreateRequest(
            org_entity_id=row.org_entity_id,
            erp_type="TALLY",
            auth_type=ErpAuthType.API_KEY,
            connection_config={"credentials": {"api_key": "x"}},
        ),
        session=session,
        user=user,
    )

    assert session.commit.await_count == 1
