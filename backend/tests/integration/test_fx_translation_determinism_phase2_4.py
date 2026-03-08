from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.fx_rates import FxManualMonthlyRate
from financeops.db.models.multi_entity_consolidation import (
    ConsolidationScope,
    EntityHierarchy,
    MultiEntityConsolidationMetricResult,
    MultiEntityConsolidationRun,
    MultiEntityConsolidationVarianceResult,
)
from financeops.db.rls import set_tenant_context
from financeops.modules.fx_translation_reporting.application.rate_selection_service import (
    RateSelectionService,
)
from financeops.modules.fx_translation_reporting.application.run_service import RunService
from financeops.modules.fx_translation_reporting.application.validation_service import (
    ValidationService,
)
from financeops.modules.fx_translation_reporting.infrastructure.repository import (
    FxTranslationReportingRepository,
)
from financeops.modules.fx_translation_reporting.infrastructure.token_builder import (
    build_definition_version_token,
)
from financeops.modules.fx_translation_reporting.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _build_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=FxTranslationReportingRepository(session),
        validation_service=ValidationService(),
        rate_selection_service=RateSelectionService(),
    )


async def _seed_active_fx_config(
    session: AsyncSession, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, created_by: uuid.UUID
) -> None:
    repo = FxTranslationReportingRepository(session)
    reporting_payload = {
        "organisation_id": str(organisation_id),
        "reporting_currency_code": "USD",
        "reporting_currency_name": "US Dollar",
        "reporting_scope_type": "organisation",
        "reporting_scope_ref": str(organisation_id),
        "effective_from": "2026-01-01",
        "status": "active",
    }
    reporting_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[reporting_payload])
    )
    await repo.create_reporting_currency_definition(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        reporting_currency_code="USD",
        reporting_currency_name="US Dollar",
        reporting_scope_type="organisation",
        reporting_scope_ref=str(organisation_id),
        version_token=reporting_token,
        effective_from=date(2026, 1, 1),
        effective_to=None,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    policy_payload = {
        "organisation_id": str(organisation_id),
        "policy_code": "POL_CLOSE_LOCKED",
        "policy_name": "Closing Locked",
        "rate_type": "closing",
        "effective_from": "2026-01-01",
        "status": "active",
    }
    policy_token = build_definition_version_token(DefinitionVersionTokenInput(rows=[policy_payload]))
    await repo.create_rate_selection_policy(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        policy_code="POL_CLOSE_LOCKED",
        policy_name="Closing Locked",
        rate_type="closing",
        date_selector_logic_json={"mode": "period_end"},
        fallback_behavior_json={},
        locked_rate_requirement_flag=True,
        source_rate_provider_ref="fx_rate_tables_v1",
        version_token=policy_token,
        effective_from=date(2026, 1, 1),
        effective_to=None,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )
    rule_payload = {
        "organisation_id": str(organisation_id),
        "rule_code": "RULE_DEFAULT",
        "rule_name": "Default Rule",
        "translation_scope_type": "organisation",
        "translation_scope_ref": str(organisation_id),
        "target_reporting_currency_code": "USD",
        "rate_policy_ref": "POL_CLOSE_LOCKED",
        "effective_from": "2026-01-01",
        "status": "active",
    }
    rule_token = build_definition_version_token(DefinitionVersionTokenInput(rows=[rule_payload]))
    await repo.create_translation_rule_definition(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        rule_code="RULE_DEFAULT",
        rule_name="Default Rule",
        translation_scope_type="organisation",
        translation_scope_ref=str(organisation_id),
        source_currency_selector_json={},
        target_reporting_currency_code="USD",
        rule_logic_json={"metric_type": "all"},
        rate_policy_ref="POL_CLOSE_LOCKED",
        version_token=rule_token,
        effective_from=date(2026, 1, 1),
        effective_to=None,
        supersedes_id=None,
        status="active",
        created_by=created_by,
    )


async def _seed_source_consolidation_rows(
    session: AsyncSession, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, created_by: uuid.UUID
) -> uuid.UUID:
    hierarchy = await AuditWriter.insert_financial_record(
        session,
        model_class=EntityHierarchy,
        tenant_id=tenant_id,
        record_data={"hierarchy_code": "SRC_H1"},
        values={
            "organisation_id": organisation_id,
            "hierarchy_code": "SRC_H1",
            "hierarchy_name": "Source Hierarchy",
            "hierarchy_type": "legal",
            "version_token": "src_h1",
            "effective_from": date(2026, 1, 1),
            "effective_to": None,
            "supersedes_id": None,
            "status": "active",
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="entity_hierarchy",
            resource_name="SRC_H1",
        ),
    )
    scope = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationScope,
        tenant_id=tenant_id,
        record_data={"scope_code": "SRC_S1"},
        values={
            "organisation_id": organisation_id,
            "scope_code": "SRC_S1",
            "scope_name": "Source Scope",
            "hierarchy_id": hierarchy.id,
            "scope_selector_json": {"mode": "all"},
            "version_token": "src_s1",
            "effective_from": date(2026, 1, 1),
            "effective_to": None,
            "supersedes_id": None,
            "status": "active",
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="consolidation_scope",
            resource_name="SRC_S1",
        ),
    )
    source_run = await AuditWriter.insert_financial_record(
        session,
        model_class=MultiEntityConsolidationRun,
        tenant_id=tenant_id,
        record_data={"run_token": "src_run_token_1"},
        values={
            "organisation_id": organisation_id,
            "reporting_period": date(2026, 1, 31),
            "hierarchy_id": hierarchy.id,
            "scope_id": scope.id,
            "hierarchy_version_token": "h_v1",
            "scope_version_token": "s_v1",
            "rule_version_token": "r_v1",
            "intercompany_version_token": "i_v1",
            "adjustment_version_token": "a_v1",
            "source_run_refs_json": [{"source_type": "metric_run", "run_id": str(uuid.uuid4())}],
            "run_token": "src_run_token_1",
            "run_status": "completed",
            "validation_summary_json": {},
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="multi_entity_consolidation_run",
            resource_name="src_run_token_1",
        ),
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=MultiEntityConsolidationMetricResult,
        tenant_id=tenant_id,
        record_data={"run_id": str(source_run.id), "line_no": 1},
        values={
            "run_id": source_run.id,
            "line_no": 1,
            "metric_code": "revenue",
            "scope_json": {"entity_ids": ["E1"]},
            "currency_code": "EUR",
            "aggregated_value": Decimal("100.000000"),
            "entity_count": 1,
            "materiality_flag": False,
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="multi_entity_consolidation_metric_result",
            resource_name="revenue",
        ),
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=MultiEntityConsolidationVarianceResult,
        tenant_id=tenant_id,
        record_data={"run_id": str(source_run.id), "line_no": 1},
        values={
            "run_id": source_run.id,
            "line_no": 1,
            "metric_code": "revenue",
            "comparison_type": "mom",
            "base_value": Decimal("90.000000"),
            "current_value": Decimal("100.000000"),
            "variance_value": Decimal("10.000000"),
            "variance_pct": Decimal("11.111111"),
            "materiality_flag": False,
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="multi_entity_consolidation_variance_result",
            resource_name="revenue",
        ),
    )
    return source_run.id


async def _seed_locked_rate(
    session: AsyncSession, *, tenant_id: uuid.UUID, created_by: uuid.UUID
) -> None:
    await AuditWriter.insert_financial_record(
        session,
        model_class=FxManualMonthlyRate,
        tenant_id=tenant_id,
        record_data={"period_year": 2026, "period_month": 1, "base_currency": "EUR", "quote_currency": "USD"},
        values={
            "period_year": 2026,
            "period_month": 1,
            "base_currency": "EUR",
            "quote_currency": "USD",
            "rate": Decimal("1.200000"),
            "entered_by": created_by,
            "reason": "locked month end",
            "supersedes_rate_id": None,
            "source_type": "locked_selection",
            "is_month_end_locked": True,
            "correlation_id": "test-fx-translation",
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="fx_manual_monthly_rate",
            resource_name="EURUSD",
        ),
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fx_translation_run_is_deterministic_and_source_is_unchanged(
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    await _seed_active_fx_config(
        async_session, tenant_id=tenant_id, organisation_id=org_id, created_by=user_id
    )
    source_run_id = await _seed_source_consolidation_rows(
        async_session, tenant_id=tenant_id, organisation_id=org_id, created_by=user_id
    )
    await _seed_locked_rate(async_session, tenant_id=tenant_id, created_by=user_id)
    await async_session.flush()

    source_metric_count_before = await async_session.scalar(
        select(func.count()).select_from(MultiEntityConsolidationMetricResult)
    )
    source_variance_count_before = await async_session.scalar(
        select(func.count()).select_from(MultiEntityConsolidationVarianceResult)
    )

    service = _build_service(async_session)
    run_a = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=org_id,
        reporting_period=date(2026, 1, 31),
        reporting_currency_code="USD",
        source_consolidation_run_refs=[
            {"source_type": "consolidation_run", "run_id": str(source_run_id)}
        ],
        created_by=user_id,
    )
    run_b = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=org_id,
        reporting_period=date(2026, 1, 31),
        reporting_currency_code="USD",
        source_consolidation_run_refs=[
            {"source_type": "consolidation_run", "run_id": str(source_run_id)}
        ],
        created_by=user_id,
    )
    assert run_a["run_token"] == run_b["run_token"]
    assert run_b["idempotent"] is True

    execute_a = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(run_a["run_id"]),
        created_by=user_id,
    )
    execute_b = await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(run_a["run_id"]),
        created_by=user_id,
    )
    assert execute_a["metric_count"] == 1
    assert execute_a["variance_count"] == 1
    assert execute_b["idempotent"] is True

    metrics = await service.list_metrics(tenant_id=tenant_id, run_id=uuid.UUID(run_a["run_id"]))
    variances = await service.list_variances(tenant_id=tenant_id, run_id=uuid.UUID(run_a["run_id"]))
    assert [row["line_no"] for row in metrics] == [1]
    assert [row["line_no"] for row in variances] == [1]
    assert metrics[0]["translated_value"] == "120.000000"
    assert variances[0]["translated_variance_value"] == "12.000000"

    source_metric_count_after = await async_session.scalar(
        select(func.count()).select_from(MultiEntityConsolidationMetricResult)
    )
    source_variance_count_after = await async_session.scalar(
        select(func.count()).select_from(MultiEntityConsolidationVarianceResult)
    )
    assert source_metric_count_after == source_metric_count_before
    assert source_variance_count_after == source_variance_count_before

