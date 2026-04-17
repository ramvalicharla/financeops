from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from financeops.db.models.custom_report_builder import ReportRun
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
from financeops.services.reconciliation_service import (
    create_gl_entry,
    create_tb_row,
    run_gl_tb_reconciliation,
)


class _StubExportService:
    def export_csv(self, rows, report_name):  # noqa: ANN001
        return (b"metric_key,metric_value\nmis.kpi.revenue,100.00\n", "report.csv")

    def export_excel(self, rows, report_name):  # noqa: ANN001
        return (b"PK\x03\x04excel", "report.xlsx")

    def export_pdf(self, rows, report_name, generated_at):  # noqa: ANN001
        return (b"%PDF-1.7\nreport\n", "report.pdf")


async def _seed_definition_and_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
) -> uuid.UUID:
    repo = ReportRepository()
    schema = ReportDefinitionSchema(
        name="Revenue report",
        description="integration",
        metric_keys=["mis.kpi.revenue"],
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
    return run.id


@pytest.mark.asyncio
async def test_reconciliation_warning_does_not_block(
    api_session_factory: async_sessionmaker[AsyncSession],
    test_tenant,
) -> None:
    entity = "DQ_Recon_Warn"
    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        await create_gl_entry(
            session,
            tenant_id=test_tenant.id,
            period_year=2026,
            period_month=2,
            entity_name=entity,
            account_code="1000",
            account_name="Cash",
            debit_amount=Decimal("100.00"),
            credit_amount=Decimal("0.00"),
            uploaded_by=test_tenant.id,
            currency="USD",
        )
        await create_gl_entry(
            session,
            tenant_id=test_tenant.id,
            period_year=2026,
            period_month=2,
            entity_name=entity,
            account_code="2000",
            account_name="Bank",
            debit_amount=Decimal("50.00"),
            credit_amount=Decimal("0.00"),
            uploaded_by=test_tenant.id,
            currency="INR",
        )
        await create_tb_row(
            session,
            tenant_id=test_tenant.id,
            period_year=2026,
            period_month=2,
            entity_name=entity,
            account_code="1000",
            account_name="Cash",
            opening_balance=Decimal("0.00"),
            period_debit=Decimal("100.00"),
            period_credit=Decimal("0.00"),
            closing_balance=Decimal("100.00"),
            uploaded_by=test_tenant.id,
            currency="USD",
        )
        await create_tb_row(
            session,
            tenant_id=test_tenant.id,
            period_year=2026,
            period_month=2,
            entity_name=entity,
            account_code="2000",
            account_name="Bank",
            opening_balance=Decimal("0.00"),
            period_debit=Decimal("50.00"),
            period_credit=Decimal("0.00"),
            closing_balance=Decimal("50.00"),
            uploaded_by=test_tenant.id,
            currency="USD",
        )
        await session.commit()

    async with api_session_factory() as session:
        await set_tenant_context(session, test_tenant.id)
        items = await run_gl_tb_reconciliation(
            session,
            tenant_id=test_tenant.id,
            period_year=2026,
            period_month=2,
            entity_name=entity,
            run_by=test_tenant.id,
        )

    assert items == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_report_run_persists_data_quality_reports(
    api_session_factory: async_sessionmaker[AsyncSession],
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tenant_id = uuid.uuid4()
    async with api_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        run_id = await _seed_definition_and_run(session, tenant_id=tenant_id)
    service = ReportRunService(export_service=_StubExportService())
    monkeypatch.setattr(
        "financeops.modules.custom_report_builder.application.run_service.settings",
        SimpleNamespace(ARTIFACTS_BASE_DIR=str(tmp_path)),
    )

    async def _fake_query_metric_rows(**_: object) -> list[dict[str, object]]:
        return [
            {"metric_value": "100.00", "reporting_period": date(2026, 1, 31), "currency_code": "USD"},
            {"metric_value": "120.00", "reporting_period": date(2026, 1, 31), "currency_code": "INR"},
        ]

    monkeypatch.setattr(service, "_query_metric_rows", _fake_query_metric_rows)

    async with api_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        result = await service.run(db=session, run_id=run_id, tenant_id=tenant_id)
        await session.commit()
    assert result["status"] == "COMPLETE"

    async with api_session_factory() as session:
        await set_tenant_context(session, tenant_id)
        latest_complete = (
            await session.execute(
                select(ReportRun)
                .where(ReportRun.tenant_id == tenant_id, ReportRun.status == "COMPLETE")
                .order_by(ReportRun.created_at.desc(), ReportRun.id.desc())
                .limit(1)
            )
        ).scalar_one()
    reports = list((latest_complete.run_metadata or {}).get("data_quality_validation_reports", []))
    assert reports
    assert reports[0]["status"] == "WARN"
