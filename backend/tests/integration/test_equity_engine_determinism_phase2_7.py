from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.equity_engine import (
    EquityLineDefinition,
    EquityLineResult,
    EquityRollforwardRuleDefinition,
    EquitySourceMapping,
    EquityStatementDefinition,
)
from financeops.db.models.fx_translation_reporting import FxTranslatedMetricResult, FxTranslationRun
from financeops.db.models.lease import LeaseJournalEntry
from financeops.db.models.multi_entity_consolidation import (
    ConsolidationScope,
    EntityHierarchy,
    MultiEntityConsolidationMetricResult,
    MultiEntityConsolidationRun,
)
from financeops.db.models.ownership_consolidation import (
    OwnershipConsolidationMetricResult,
    OwnershipConsolidationRun,
)
from financeops.db.models.revenue import RevenueJournalEntry
from financeops.db.rls import set_tenant_context
from financeops.modules.equity_engine.application.mapping_service import MappingService
from financeops.modules.equity_engine.application.rollforward_service import RollforwardService
from financeops.modules.equity_engine.application.run_service import RunService
from financeops.modules.equity_engine.application.validation_service import ValidationService
from financeops.modules.equity_engine.domain.value_objects import DefinitionVersionTokenInput
from financeops.modules.equity_engine.infrastructure.repository import EquityRepository
from financeops.modules.equity_engine.infrastructure.token_builder import (
    build_definition_version_token,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _build_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=EquityRepository(session),
        validation_service=ValidationService(),
        mapping_service=MappingService(),
        rollforward_service=RollforwardService(),
    )


async def _seed_active_equity_definitions(
    session: AsyncSession, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, created_by: uuid.UUID
) -> None:
    stmt_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[{"statement_code": "EQ_MAIN", "status": "active"}])
    )
    statement = await AuditWriter.insert_financial_record(
        session,
        model_class=EquityStatementDefinition,
        tenant_id=tenant_id,
        record_data={"statement_code": "EQ_MAIN"},
        values={
            "organisation_id": organisation_id,
            "statement_code": "EQ_MAIN",
            "statement_name": "Equity Main",
            "reporting_currency_basis": "reporting_currency",
            "ownership_basis_flag": True,
            "version_token": stmt_token,
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
            resource_type="equity_statement_definition",
            resource_name="EQ_MAIN",
        ),
    )

    line_rows = [
        ("retained_earnings", "retained_earnings", 1),
        ("cta_reserve", "cta_reserve", 2),
        ("minority_interest", "minority_interest", 3),
        ("total_equity", "total_equity", 4),
    ]
    for line_code, line_type, order in line_rows:
        token = build_definition_version_token(
            DefinitionVersionTokenInput(rows=[{"line_code": line_code, "order": order}])
        )
        await AuditWriter.insert_financial_record(
            session,
            model_class=EquityLineDefinition,
            tenant_id=tenant_id,
            record_data={"line_code": line_code},
            values={
                "organisation_id": organisation_id,
                "statement_definition_id": statement.id,
                "line_code": line_code,
                "line_name": line_code,
                "line_type": line_type,
                "presentation_order": order,
                "rollforward_required_flag": True,
                "version_token": token,
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
                resource_type="equity_line_definition",
                resource_name=line_code,
            ),
        )

    rules = [
        ("EQ_RE_BRIDGE", "retained_earnings_bridge_rule", {"pnl_metric_codes": ["net_income"]}),
        ("EQ_CTA", "cta_derivation_rule", {"metric_codes": ["net_income"]}),
        ("EQ_MI", "minority_interest_equity_rule", {"metric_codes": ["net_income"]}),
        ("EQ_CLOSE", "closing_balance_rule", {}),
    ]
    for code, rule_type, selector in rules:
        token = build_definition_version_token(
            DefinitionVersionTokenInput(rows=[{"rule_code": code, "rule_type": rule_type}])
        )
        await AuditWriter.insert_financial_record(
            session,
            model_class=EquityRollforwardRuleDefinition,
            tenant_id=tenant_id,
            record_data={"rule_code": code},
            values={
                "organisation_id": organisation_id,
                "rule_code": code,
                "rule_name": code,
                "rule_type": rule_type,
                "source_selector_json": selector,
                "derivation_logic_json": {},
                "fx_interaction_logic_json_nullable": None,
                "ownership_interaction_logic_json_nullable": None,
                "version_token": token,
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
                resource_type="equity_rollforward_rule_definition",
                resource_name=code,
            ),
        )

    mappings = [
        ("EQ_MAP_RE_OPEN", "retained_earnings", "consolidation_result", {"metric_codes": ["retained_earnings_opening"]}, {"phase": "opening"}),
        ("EQ_MAP_MI", "minority_interest", "ownership_result", {"metric_codes": ["net_income"]}, {"phase": "movement"}),
        ("EQ_MAP_TOTAL", "total_equity", "consolidation_result", {"metric_codes": ["equity_opening"]}, {"phase": "opening"}),
    ]
    for mapping_code, line_code, source_type, selector, transform in mappings:
        token = build_definition_version_token(
            DefinitionVersionTokenInput(rows=[{"mapping_code": mapping_code, "line_code": line_code}])
        )
        await AuditWriter.insert_financial_record(
            session,
            model_class=EquitySourceMapping,
            tenant_id=tenant_id,
            record_data={"mapping_code": mapping_code, "line_code": line_code},
            values={
                "organisation_id": organisation_id,
                "mapping_code": mapping_code,
                "line_code": line_code,
                "source_type": source_type,
                "source_selector_json": selector,
                "transformation_logic_json": transform,
                "version_token": token,
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
                resource_type="equity_source_mapping",
                resource_name=f"{mapping_code}:{line_code}",
            ),
        )


async def _seed_source_runs(
    session: AsyncSession, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, created_by: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    hierarchy = await AuditWriter.insert_financial_record(
        session,
        model_class=EntityHierarchy,
        tenant_id=tenant_id,
        record_data={"hierarchy_code": "EQ_H"},
        values={
            "organisation_id": organisation_id,
            "hierarchy_code": "EQ_H",
            "hierarchy_name": "EQ H",
            "hierarchy_type": "legal",
            "version_token": "eq_h_v1",
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
            resource_name="EQ_H",
        ),
    )
    scope = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationScope,
        tenant_id=tenant_id,
        record_data={"scope_code": "EQ_S"},
        values={
            "organisation_id": organisation_id,
            "scope_code": "EQ_S",
            "scope_name": "EQ S",
            "hierarchy_id": hierarchy.id,
            "scope_selector_json": {"mode": "all"},
            "version_token": "eq_s_v1",
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
            resource_name="EQ_S",
        ),
    )
    consolidation_run = await AuditWriter.insert_financial_record(
        session,
        model_class=MultiEntityConsolidationRun,
        tenant_id=tenant_id,
        record_data={"run_token": "eq_src_run"},
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
            "run_token": "eq_src_run",
            "run_status": "completed",
            "validation_summary_json": {},
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="multi_entity_consolidation_run",
            resource_name="eq_src_run",
        ),
    )
    metric_values = [
        ("retained_earnings_opening", Decimal("100.000000")),
        ("equity_opening", Decimal("500.000000")),
        ("net_income", Decimal("40.000000")),
    ]
    source_metric_id = None
    for idx, (metric_code, value) in enumerate(metric_values, start=1):
        row = await AuditWriter.insert_financial_record(
            session,
            model_class=MultiEntityConsolidationMetricResult,
            tenant_id=tenant_id,
            record_data={"run_id": str(consolidation_run.id), "line_no": idx},
            values={
                "run_id": consolidation_run.id,
                "line_no": idx,
                "metric_code": metric_code,
                "scope_json": {"scope_code": "EQ_SCOPE"},
                "currency_code": "USD",
                "aggregated_value": value,
                "entity_count": 1,
                "materiality_flag": False,
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="test.seed",
                resource_type="multi_entity_consolidation_metric_result",
                resource_name=metric_code,
            ),
        )
        if metric_code == "net_income":
            source_metric_id = row.id

    fx_run = await AuditWriter.insert_financial_record(
        session,
        model_class=FxTranslationRun,
        tenant_id=tenant_id,
        record_data={"run_token": "eq_fx_run"},
        values={
            "organisation_id": organisation_id,
            "reporting_period": date(2026, 1, 31),
            "reporting_currency_code": "USD",
            "reporting_currency_version_token": "rc_v1",
            "translation_rule_version_token": "tr_v1",
            "rate_policy_version_token": "rp_v1",
            "rate_source_version_token": "rs_v1",
            "source_consolidation_run_refs_json": [{"source_type": "consolidation_run", "run_id": str(consolidation_run.id)}],
            "run_token": "eq_fx_run",
            "run_status": "completed",
            "validation_summary_json": {},
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="fx_translation_run",
            resource_name="eq_fx_run",
        ),
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=FxTranslatedMetricResult,
        tenant_id=tenant_id,
        record_data={"run_id": str(fx_run.id), "line_no": 1},
        values={
            "run_id": fx_run.id,
            "line_no": 1,
            "source_metric_result_id": source_metric_id,
            "metric_code": "net_income",
            "source_currency_code": "EUR",
            "reporting_currency_code": "USD",
            "applied_rate_type": "closing",
            "applied_rate_ref": "rate_ref",
            "applied_rate_value": Decimal("1.12500000"),
            "source_value": Decimal("40.000000"),
            "translated_value": Decimal("45.000000"),
            "lineage_json": {},
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="fx_translated_metric_result",
            resource_name="net_income",
        ),
    )

    ownership_run = await AuditWriter.insert_financial_record(
        session,
        model_class=OwnershipConsolidationRun,
        tenant_id=tenant_id,
        record_data={"run_token": "eq_own_run"},
        values={
            "organisation_id": organisation_id,
            "reporting_period": date(2026, 1, 31),
            "hierarchy_version_token": "h_v1",
            "scope_version_token": "s_v1",
            "ownership_structure_version_token": "os_v1",
            "ownership_rule_version_token": "or_v1",
            "minority_interest_rule_version_token": "mr_v1",
            "fx_translation_run_ref_nullable": None,
            "source_consolidation_run_refs_json": [{"source_type": "consolidation_run", "run_id": str(consolidation_run.id)}],
            "run_token": "eq_own_run",
            "run_status": "completed",
            "validation_summary_json": {},
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="ownership_consolidation_run",
            resource_name="eq_own_run",
        ),
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=OwnershipConsolidationMetricResult,
        tenant_id=tenant_id,
        record_data={"run_id": str(ownership_run.id), "line_no": 1},
        values={
            "ownership_consolidation_run_id": ownership_run.id,
            "line_no": 1,
            "scope_code": "OWN_SCOPE",
            "metric_code": "net_income",
            "source_consolidated_value": Decimal("40.000000"),
            "ownership_weight_applied": Decimal("0.800000"),
            "attributed_value": Decimal("32.000000"),
            "minority_interest_value_nullable": Decimal("8.000000"),
            "reporting_currency_code_nullable": "USD",
            "lineage_summary_json": {},
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="ownership_consolidation_metric_result",
            resource_name="net_income",
        ),
    )

    return consolidation_run.id, fx_run.id, ownership_run.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_equity_run_is_deterministic_and_no_upstream_mutation(
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    organisation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)

    await _seed_active_equity_definitions(
        async_session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=user_id,
    )
    consolidation_run_id, fx_run_id, ownership_run_id = await _seed_source_runs(
        async_session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=user_id,
    )
    await async_session.flush()

    source_metric_count_before = await async_session.scalar(
        select(func.count()).select_from(MultiEntityConsolidationMetricResult)
    )
    revenue_journal_before = await async_session.scalar(select(func.count()).select_from(RevenueJournalEntry))
    lease_journal_before = await async_session.scalar(select(func.count()).select_from(LeaseJournalEntry))

    service = _build_service(async_session)
    run_a = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        reporting_period=date(2026, 1, 31),
        consolidation_run_ref_nullable=consolidation_run_id,
        fx_translation_run_ref_nullable=fx_run_id,
        ownership_consolidation_run_ref_nullable=ownership_run_id,
        created_by=user_id,
    )
    run_b = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        reporting_period=date(2026, 1, 31),
        consolidation_run_ref_nullable=consolidation_run_id,
        fx_translation_run_ref_nullable=fx_run_id,
        ownership_consolidation_run_ref_nullable=ownership_run_id,
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
    assert execute_a["line_count"] >= 4
    assert execute_b["idempotent"] is True

    source_metric_count_after = await async_session.scalar(
        select(func.count()).select_from(MultiEntityConsolidationMetricResult)
    )
    revenue_journal_after = await async_session.scalar(select(func.count()).select_from(RevenueJournalEntry))
    lease_journal_after = await async_session.scalar(select(func.count()).select_from(LeaseJournalEntry))
    assert source_metric_count_before == source_metric_count_after
    assert revenue_journal_before == revenue_journal_after
    assert lease_journal_before == lease_journal_after

    rows = (
        await async_session.execute(
            select(EquityLineResult)
            .where(EquityLineResult.equity_run_id == uuid.UUID(run_a["run_id"]))
            .order_by(EquityLineResult.line_no.asc())
        )
    ).scalars().all()
    assert [row.line_no for row in rows] == sorted(row.line_no for row in rows)

    by_code = {str(row.line_code): row for row in rows}
    assert str(by_code["retained_earnings"].closing_balance) == "140.000000"
    assert str(by_code["cta_reserve"].closing_balance) == "5.000000"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_equity_run_fails_closed_when_cta_rule_active_without_fx(
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    organisation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)

    await _seed_active_equity_definitions(
        async_session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=user_id,
    )
    consolidation_run_id, _, ownership_run_id = await _seed_source_runs(
        async_session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=user_id,
    )
    await async_session.flush()

    service = _build_service(async_session)
    run = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        reporting_period=date(2026, 1, 31),
        consolidation_run_ref_nullable=consolidation_run_id,
        fx_translation_run_ref_nullable=None,
        ownership_consolidation_run_ref_nullable=ownership_run_id,
        created_by=user_id,
    )
    with pytest.raises(ValueError, match="Missing FX translation run"):
        await service.execute_run(
            tenant_id=tenant_id,
            run_id=uuid.UUID(run["run_id"]),
            created_by=user_id,
        )
