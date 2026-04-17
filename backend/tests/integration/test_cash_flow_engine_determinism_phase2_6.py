from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from financeops.db.models.cash_flow_engine import (
    CashFlowBridgeRuleDefinition,
    CashFlowLineMapping,
    CashFlowLineResult,
    CashFlowStatementDefinition,
)
from financeops.db.models.fx_translation_reporting import (
    FxTranslatedMetricResult,
    FxTranslationRun,
)
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
from financeops.modules.cash_flow_engine.application.bridge_service import BridgeService
from financeops.modules.cash_flow_engine.application.mapping_service import MappingService
from financeops.modules.cash_flow_engine.application.run_service import RunService
from financeops.modules.cash_flow_engine.application.validation_service import ValidationService
from financeops.modules.cash_flow_engine.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.modules.cash_flow_engine.infrastructure.repository import CashFlowRepository
from financeops.modules.cash_flow_engine.infrastructure.token_builder import (
    build_definition_version_token,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _build_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=CashFlowRepository(session),
        validation_service=ValidationService(),
        mapping_service=MappingService(),
        bridge_service=BridgeService(),
    )


async def _seed_active_cash_flow_definitions(
    session: AsyncSession, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, created_by: uuid.UUID
) -> None:
    statement_token = build_definition_version_token(
        DefinitionVersionTokenInput(
            rows=[
                {
                    "definition_code": "CF_MAIN",
                    "method_type": "indirect",
                    "effective_from": "2026-01-01",
                    "status": "active",
                }
            ]
        )
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=CashFlowStatementDefinition,
        tenant_id=tenant_id,
        record_data={"definition_code": "CF_MAIN"},
        values={
            "organisation_id": organisation_id,
            "definition_code": "CF_MAIN",
            "definition_name": "Cash Flow Main",
            "method_type": "indirect",
            "layout_json": {},
            "version_token": statement_token,
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
            resource_type="cash_flow_statement_definition",
            resource_name="CF_MAIN",
        ),
    )

    line_rows = [
        ("CF_STD_1", "L_NET_INCOME", "net_income", 1, Decimal("1.000000")),
        ("CF_STD_2", "L_DEPR", "depreciation", 2, Decimal("1.000000")),
        ("CF_STD_3", "L_WC", "working_capital_change", 3, Decimal("-1.000000")),
        ("CF_STD_4", "L_CFO", "derived:cash_from_operations", 4, Decimal("1.000000")),
    ]
    for mapping_code, line_code, source_metric_code, line_order, sign_multiplier in line_rows:
        token = build_definition_version_token(
            DefinitionVersionTokenInput(
                rows=[
                    {
                        "mapping_code": mapping_code,
                        "line_code": line_code,
                        "source_metric_code": source_metric_code,
                        "line_order": line_order,
                    }
                ]
            )
        )
        await AuditWriter.insert_financial_record(
            session,
            model_class=CashFlowLineMapping,
            tenant_id=tenant_id,
            record_data={"mapping_code": mapping_code, "line_code": line_code},
            values={
                "organisation_id": organisation_id,
                "mapping_code": mapping_code,
                "line_code": line_code,
                "line_name": line_code,
                "section_code": "operating",
                "line_order": line_order,
                "method_type": "indirect",
                "source_metric_code": source_metric_code,
                "sign_multiplier": sign_multiplier,
                "aggregation_type": "sum",
                "ownership_applicability": "any",
                "fx_applicability": "any",
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
                resource_type="cash_flow_line_mapping",
                resource_name=line_code,
            ),
        )

    bridge_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[{"rule_code": "CF_BRIDGE_STD", "status": "active"}])
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=CashFlowBridgeRuleDefinition,
        tenant_id=tenant_id,
        record_data={"rule_code": "CF_BRIDGE_STD"},
        values={
            "organisation_id": organisation_id,
            "rule_code": "CF_BRIDGE_STD",
            "rule_name": "Cash Bridge",
            "bridge_logic_json": {
                "derived_lines": [
                    {
                        "line_code": "cash_from_operations",
                        "line_order": 1,
                        "components": [
                            {"line_code": "L_NET_INCOME", "multiplier": "1"},
                            {"line_code": "L_DEPR", "multiplier": "1"},
                            {"line_code": "L_WC", "multiplier": "1"},
                        ],
                    }
                ]
            },
            "ownership_logic_json": {},
            "fx_logic_json": {},
            "version_token": bridge_token,
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
            resource_type="cash_flow_bridge_rule_definition",
            resource_name="CF_BRIDGE_STD",
        ),
    )


async def _seed_consolidation_source_run(
    session: AsyncSession, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, created_by: uuid.UUID
) -> tuple[uuid.UUID, dict[str, uuid.UUID]]:
    hierarchy = await AuditWriter.insert_financial_record(
        session,
        model_class=EntityHierarchy,
        tenant_id=tenant_id,
        record_data={"hierarchy_code": "CF_H"},
        values={
            "organisation_id": organisation_id,
            "hierarchy_code": "CF_H",
            "hierarchy_name": "CF Hierarchy",
            "hierarchy_type": "legal",
            "version_token": "cf_h_v1",
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
            resource_name="CF_H",
        ),
    )
    scope = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationScope,
        tenant_id=tenant_id,
        record_data={"scope_code": "CF_S"},
        values={
            "organisation_id": organisation_id,
            "scope_code": "CF_S",
            "scope_name": "CF Scope",
            "hierarchy_id": hierarchy.id,
            "scope_selector_json": {"mode": "all"},
            "version_token": "cf_s_v1",
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
            resource_name="CF_S",
        ),
    )
    source_run = await AuditWriter.insert_financial_record(
        session,
        model_class=MultiEntityConsolidationRun,
        tenant_id=tenant_id,
        record_data={"run_token": "cf_src_run"},
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
            "run_token": "cf_src_run",
            "run_status": "completed",
            "validation_summary_json": {},
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="multi_entity_consolidation_run",
            resource_name="cf_src_run",
        ),
    )
    metric_rows = [
        ("net_income", Decimal("100.000000")),
        ("depreciation", Decimal("20.000000")),
        ("working_capital_change", Decimal("15.000000")),
    ]
    metric_result_ids: dict[str, uuid.UUID] = {}
    for line_no, (metric_code, amount) in enumerate(metric_rows, start=1):
        metric_row = await AuditWriter.insert_financial_record(
            session,
            model_class=MultiEntityConsolidationMetricResult,
            tenant_id=tenant_id,
            record_data={"run_id": str(source_run.id), "line_no": line_no},
            values={
                "run_id": source_run.id,
                "line_no": line_no,
                "metric_code": metric_code,
                "scope_json": {"scope_code": "CF_SCOPE"},
                "currency_code": "USD",
                "aggregated_value": amount,
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
        metric_result_ids[metric_code] = metric_row.id
    return source_run.id, metric_result_ids


async def _seed_fx_and_ownership_runs(
    session: AsyncSession, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, created_by: uuid.UUID, source_metric_ids: dict[str, uuid.UUID]
) -> tuple[uuid.UUID, uuid.UUID]:
    fx_run = await AuditWriter.insert_financial_record(
        session,
        model_class=FxTranslationRun,
        tenant_id=tenant_id,
        record_data={"run_token": "fx_cf_run"},
        values={
            "organisation_id": organisation_id,
            "reporting_period": date(2026, 1, 31),
            "reporting_currency_code": "USD",
            "reporting_currency_version_token": "rc_v1",
            "translation_rule_version_token": "tr_v1",
            "rate_policy_version_token": "rp_v1",
            "rate_source_version_token": "rs_v1",
            "source_consolidation_run_refs_json": [{"source_type": "consolidation_run", "run_id": str(uuid.uuid4())}],
            "run_token": "fx_cf_run",
            "run_status": "completed",
            "validation_summary_json": {},
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="fx_translation_run",
            resource_name="fx_cf_run",
        ),
    )
    for line_no, (metric_code, value) in enumerate(
        [("net_income", Decimal("120.000000")), ("depreciation", Decimal("24.000000")), ("working_capital_change", Decimal("18.000000"))],
        start=1,
    ):
        await AuditWriter.insert_financial_record(
            session,
            model_class=FxTranslatedMetricResult,
            tenant_id=tenant_id,
            record_data={"run_id": str(fx_run.id), "line_no": line_no},
            values={
                "run_id": fx_run.id,
                "line_no": line_no,
                "source_metric_result_id": source_metric_ids[metric_code],
                "metric_code": metric_code,
                "source_currency_code": "EUR",
                "reporting_currency_code": "USD",
                "applied_rate_type": "closing",
                "applied_rate_ref": "rate_ref",
                "applied_rate_value": Decimal("1.20000000"),
                "source_value": Decimal("100.000000"),
                "translated_value": value,
                "lineage_json": {},
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="test.seed",
                resource_type="fx_translated_metric_result",
                resource_name=metric_code,
            ),
        )
    own_run = await AuditWriter.insert_financial_record(
        session,
        model_class=OwnershipConsolidationRun,
        tenant_id=tenant_id,
        record_data={"run_token": "own_cf_run"},
        values={
            "organisation_id": organisation_id,
            "reporting_period": date(2026, 1, 31),
            "hierarchy_version_token": "h_v1",
            "scope_version_token": "s_v1",
            "ownership_structure_version_token": "os_v1",
            "ownership_rule_version_token": "or_v1",
            "minority_interest_rule_version_token": "mr_v1",
            "fx_translation_run_ref_nullable": None,
            "source_consolidation_run_refs_json": [{"source_type": "consolidation_run", "run_id": str(uuid.uuid4())}],
            "run_token": "own_cf_run",
            "run_status": "completed",
            "validation_summary_json": {},
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="ownership_consolidation_run",
            resource_name="own_cf_run",
        ),
    )
    for line_no, (metric_code, value) in enumerate(
        [("net_income", Decimal("80.000000")), ("depreciation", Decimal("16.000000")), ("working_capital_change", Decimal("12.000000"))],
        start=1,
    ):
        await AuditWriter.insert_financial_record(
            session,
            model_class=OwnershipConsolidationMetricResult,
            tenant_id=tenant_id,
            record_data={"run_id": str(own_run.id), "line_no": line_no},
            values={
                "ownership_consolidation_run_id": own_run.id,
                "line_no": line_no,
                "scope_code": "OWN_SCOPE",
                "metric_code": metric_code,
                "source_consolidated_value": value,
                "ownership_weight_applied": Decimal("0.800000"),
                "attributed_value": value,
                "minority_interest_value_nullable": None,
                "reporting_currency_code_nullable": "USD",
                "lineage_summary_json": {},
                "created_by": created_by,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=created_by,
                action="test.seed",
                resource_type="ownership_consolidation_metric_result",
                resource_name=metric_code,
            ),
        )
    return fx_run.id, own_run.id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cash_flow_run_is_deterministic_and_no_upstream_mutation(
    cash_flow_phase2_6_db_url: str,
) -> None:
    engine = create_async_engine(cash_flow_phase2_6_db_url, echo=False, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await session.begin()
            try:
                tenant_id = uuid.uuid4()
                organisation_id = uuid.uuid4()
                user_id = uuid.uuid4()
                await set_tenant_context(session, tenant_id)
                await _seed_active_cash_flow_definitions(
                    session,
                    tenant_id=tenant_id,
                    organisation_id=organisation_id,
                    created_by=user_id,
                )
                source_run_id, _ = await _seed_consolidation_source_run(
                    session,
                    tenant_id=tenant_id,
                    organisation_id=organisation_id,
                    created_by=user_id,
                )
                await session.flush()

                source_metric_count_before = await session.scalar(
                    select(func.count()).select_from(MultiEntityConsolidationMetricResult)
                )
                revenue_journal_before = await session.scalar(
                    select(func.count()).select_from(RevenueJournalEntry)
                )
                lease_journal_before = await session.scalar(
                    select(func.count()).select_from(LeaseJournalEntry)
                )

                service = _build_service(session)
                run_a = await service.create_run(
                    tenant_id=tenant_id,
                    organisation_id=organisation_id,
                    reporting_period=date(2026, 1, 31),
                    source_consolidation_run_ref=source_run_id,
                    source_fx_translation_run_ref_nullable=None,
                    source_ownership_consolidation_run_ref_nullable=None,
                    created_by=user_id,
                )
                run_b = await service.create_run(
                    tenant_id=tenant_id,
                    organisation_id=organisation_id,
                    reporting_period=date(2026, 1, 31),
                    source_consolidation_run_ref=source_run_id,
                    source_fx_translation_run_ref_nullable=None,
                    source_ownership_consolidation_run_ref_nullable=None,
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

                source_metric_count_after = await session.scalar(
                    select(func.count()).select_from(MultiEntityConsolidationMetricResult)
                )
                revenue_journal_after = await session.scalar(
                    select(func.count()).select_from(RevenueJournalEntry)
                )
                lease_journal_after = await session.scalar(
                    select(func.count()).select_from(LeaseJournalEntry)
                )
                assert source_metric_count_before == source_metric_count_after
                assert revenue_journal_before == revenue_journal_after
                assert lease_journal_before == lease_journal_after

                rows = (
                    await session.execute(
                        select(CashFlowLineResult)
                        .where(CashFlowLineResult.run_id == uuid.UUID(run_a["run_id"]))
                        .order_by(CashFlowLineResult.line_no.asc())
                    )
                ).scalars().all()
                assert [row.line_no for row in rows] == sorted(row.line_no for row in rows)
            finally:
                if session.in_transaction():
                    await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cash_flow_run_ownership_and_fx_paths_are_explicit_and_deterministic(
    cash_flow_phase2_6_db_url: str,
) -> None:
    engine = create_async_engine(cash_flow_phase2_6_db_url, echo=False, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await session.begin()
            try:
                tenant_id = uuid.uuid4()
                organisation_id = uuid.uuid4()
                user_id = uuid.uuid4()
                await set_tenant_context(session, tenant_id)
                await _seed_active_cash_flow_definitions(
                    session,
                    tenant_id=tenant_id,
                    organisation_id=organisation_id,
                    created_by=user_id,
                )
                source_run_id, source_metric_ids = await _seed_consolidation_source_run(
                    session,
                    tenant_id=tenant_id,
                    organisation_id=organisation_id,
                    created_by=user_id,
                )
                fx_run_id, ownership_run_id = await _seed_fx_and_ownership_runs(
                    session,
                    tenant_id=tenant_id,
                    organisation_id=organisation_id,
                    created_by=user_id,
                    source_metric_ids=source_metric_ids,
                )
                await session.flush()

                service = _build_service(session)
                fx_run = await service.create_run(
                    tenant_id=tenant_id,
                    organisation_id=organisation_id,
                    reporting_period=date(2026, 1, 31),
                    source_consolidation_run_ref=source_run_id,
                    source_fx_translation_run_ref_nullable=fx_run_id,
                    source_ownership_consolidation_run_ref_nullable=None,
                    created_by=user_id,
                )
                await service.execute_run(
                    tenant_id=tenant_id, run_id=uuid.UUID(fx_run["run_id"]), created_by=user_id
                )
                fx_rows = (
                    await session.execute(
                        select(CashFlowLineResult).where(
                            CashFlowLineResult.run_id == uuid.UUID(fx_run["run_id"])
                        )
                    )
                ).scalars().all()
                assert fx_rows
                assert all(bool(row.fx_basis_applied) for row in fx_rows)

                ownership_run = await service.create_run(
                    tenant_id=tenant_id,
                    organisation_id=organisation_id,
                    reporting_period=date(2026, 1, 31),
                    source_consolidation_run_ref=source_run_id,
                    source_fx_translation_run_ref_nullable=fx_run_id,
                    source_ownership_consolidation_run_ref_nullable=ownership_run_id,
                    created_by=user_id,
                )
                await service.execute_run(
                    tenant_id=tenant_id,
                    run_id=uuid.UUID(ownership_run["run_id"]),
                    created_by=user_id,
                )
                own_rows = (
                    await session.execute(
                        select(CashFlowLineResult).where(
                            CashFlowLineResult.run_id == uuid.UUID(ownership_run["run_id"])
                        )
                    )
                ).scalars().all()
                assert own_rows
                assert all(bool(row.ownership_basis_applied) for row in own_rows)
            finally:
                if session.in_transaction():
                    await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cash_flow_run_fails_closed_when_source_metric_missing(
    cash_flow_phase2_6_db_url: str,
) -> None:
    engine = create_async_engine(cash_flow_phase2_6_db_url, echo=False, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            await session.begin()
            try:
                tenant_id = uuid.uuid4()
                organisation_id = uuid.uuid4()
                user_id = uuid.uuid4()
                await set_tenant_context(session, tenant_id)
                await _seed_active_cash_flow_definitions(
                    session,
                    tenant_id=tenant_id,
                    organisation_id=organisation_id,
                    created_by=user_id,
                )
                source_run_id, _ = await _seed_consolidation_source_run(
                    session,
                    tenant_id=tenant_id,
                    organisation_id=organisation_id,
                    created_by=user_id,
                )
                await session.execute(select(CashFlowLineMapping))
                await AuditWriter.insert_financial_record(
                    session,
                    model_class=CashFlowLineMapping,
                    tenant_id=tenant_id,
                    record_data={"mapping_code": "CF_EXTRA", "line_code": "L_MISSING"},
                    values={
                        "organisation_id": organisation_id,
                        "mapping_code": "CF_EXTRA",
                        "line_code": "L_MISSING",
                        "line_name": "Missing",
                        "section_code": "operating",
                        "line_order": 100,
                        "method_type": "indirect",
                        "source_metric_code": "metric_missing_in_source",
                        "sign_multiplier": Decimal("1.000000"),
                        "aggregation_type": "sum",
                        "ownership_applicability": "any",
                        "fx_applicability": "any",
                        "version_token": build_definition_version_token(
                            DefinitionVersionTokenInput(rows=[{"line_code": "L_MISSING"}])
                        ),
                        "effective_from": date(2026, 1, 1),
                        "effective_to": None,
                        "supersedes_id": None,
                        "status": "active",
                        "created_by": user_id,
                    },
                    audit=AuditEvent(
                        tenant_id=tenant_id,
                        user_id=user_id,
                        action="test.seed",
                        resource_type="cash_flow_line_mapping",
                        resource_name="L_MISSING",
                    ),
                )
                await session.flush()

                service = _build_service(session)
                run = await service.create_run(
                    tenant_id=tenant_id,
                    organisation_id=organisation_id,
                    reporting_period=date(2026, 1, 31),
                    source_consolidation_run_ref=source_run_id,
                    source_fx_translation_run_ref_nullable=None,
                    source_ownership_consolidation_run_ref_nullable=None,
                    created_by=user_id,
                )
                with pytest.raises(ValueError, match="Missing source metrics"):
                    await service.execute_run(
                        tenant_id=tenant_id,
                        run_id=uuid.UUID(run["run_id"]),
                        created_by=user_id,
                    )
            finally:
                if session.in_transaction():
                    await session.rollback()
    finally:
        await engine.dispose()
