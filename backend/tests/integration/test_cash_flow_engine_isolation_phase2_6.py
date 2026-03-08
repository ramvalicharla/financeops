from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.cash_flow_engine import (
    CashFlowBridgeRuleDefinition,
    CashFlowLineMapping,
    CashFlowStatementDefinition,
)
from financeops.db.models.lease import LeaseJournalEntry
from financeops.db.models.multi_entity_consolidation import (
    ConsolidationScope,
    EntityHierarchy,
    MultiEntityConsolidationMetricResult,
    MultiEntityConsolidationRun,
)
from financeops.db.models.prepaid import PrepaidJournalEntry
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


def _service(session: AsyncSession) -> RunService:
    return RunService(
        repository=CashFlowRepository(session),
        validation_service=ValidationService(),
        mapping_service=MappingService(),
        bridge_service=BridgeService(),
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cash_flow_execution_has_no_accounting_engine_side_effects(
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)

    hierarchy = await AuditWriter.insert_financial_record(
        async_session,
        model_class=EntityHierarchy,
        tenant_id=tenant_id,
        record_data={"hierarchy_code": "CFISO_H"},
        values={
            "organisation_id": org_id,
            "hierarchy_code": "CFISO_H",
            "hierarchy_name": "CF ISO H",
            "hierarchy_type": "legal",
            "version_token": "h",
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
            resource_type="entity_hierarchy",
            resource_name="CFISO_H",
        ),
    )
    scope = await AuditWriter.insert_financial_record(
        async_session,
        model_class=ConsolidationScope,
        tenant_id=tenant_id,
        record_data={"scope_code": "CFISO_S"},
        values={
            "organisation_id": org_id,
            "scope_code": "CFISO_S",
            "scope_name": "CF ISO S",
            "hierarchy_id": hierarchy.id,
            "scope_selector_json": {"mode": "all"},
            "version_token": "s",
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
            resource_type="consolidation_scope",
            resource_name="CFISO_S",
        ),
    )
    source_run = await AuditWriter.insert_financial_record(
        async_session,
        model_class=MultiEntityConsolidationRun,
        tenant_id=tenant_id,
        record_data={"run_token": "cfiso_src"},
        values={
            "organisation_id": org_id,
            "reporting_period": date(2026, 1, 31),
            "hierarchy_id": hierarchy.id,
            "scope_id": scope.id,
            "hierarchy_version_token": "h",
            "scope_version_token": "s",
            "rule_version_token": "r",
            "intercompany_version_token": "i",
            "adjustment_version_token": "a",
            "source_run_refs_json": [{"source_type": "metric_run", "run_id": str(uuid.uuid4())}],
            "run_token": "cfiso_src",
            "run_status": "completed",
            "validation_summary_json": {},
            "created_by": user_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action="test.seed",
            resource_type="multi_entity_consolidation_run",
            resource_name="cfiso_src",
        ),
    )
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=MultiEntityConsolidationMetricResult,
        tenant_id=tenant_id,
        record_data={"run_id": str(source_run.id), "line_no": 1},
        values={
            "run_id": source_run.id,
            "line_no": 1,
            "metric_code": "net_income",
            "scope_json": {},
            "currency_code": "USD",
            "aggregated_value": Decimal("100.000000"),
            "entity_count": 1,
            "materiality_flag": False,
            "created_by": user_id,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=user_id,
            action="test.seed",
            resource_type="multi_entity_consolidation_metric_result",
            resource_name="net_income",
        ),
    )
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=CashFlowStatementDefinition,
        tenant_id=tenant_id,
        record_data={"definition_code": "CFISO"},
        values={
            "organisation_id": org_id,
            "definition_code": "CFISO",
            "definition_name": "CF ISO",
            "method_type": "indirect",
            "layout_json": {},
            "version_token": build_definition_version_token(
                DefinitionVersionTokenInput(rows=[{"definition_code": "CFISO"}])
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
            resource_type="cash_flow_statement_definition",
            resource_name="CFISO",
        ),
    )
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=CashFlowLineMapping,
        tenant_id=tenant_id,
        record_data={"mapping_code": "CFISO_MAP", "line_code": "L1"},
        values={
            "organisation_id": org_id,
            "mapping_code": "CFISO_MAP",
            "line_code": "L1",
            "line_name": "Line 1",
            "section_code": "operating",
            "line_order": 1,
            "method_type": "indirect",
            "source_metric_code": "net_income",
            "sign_multiplier": Decimal("1.000000"),
            "aggregation_type": "sum",
            "ownership_applicability": "any",
            "fx_applicability": "any",
            "version_token": build_definition_version_token(
                DefinitionVersionTokenInput(rows=[{"line_code": "L1"}])
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
            resource_name="L1",
        ),
    )
    await AuditWriter.insert_financial_record(
        async_session,
        model_class=CashFlowBridgeRuleDefinition,
        tenant_id=tenant_id,
        record_data={"rule_code": "CFISO_BRIDGE"},
        values={
            "organisation_id": org_id,
            "rule_code": "CFISO_BRIDGE",
            "rule_name": "CF ISO Bridge",
            "bridge_logic_json": {},
            "ownership_logic_json": {},
            "fx_logic_json": {},
            "version_token": build_definition_version_token(
                DefinitionVersionTokenInput(rows=[{"rule_code": "CFISO_BRIDGE"}])
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
            resource_type="cash_flow_bridge_rule_definition",
            resource_name="CFISO_BRIDGE",
        ),
    )
    await async_session.flush()

    revenue_before = await async_session.scalar(select(func.count()).select_from(RevenueJournalEntry))
    lease_before = await async_session.scalar(select(func.count()).select_from(LeaseJournalEntry))
    prepaid_before = await async_session.scalar(select(func.count()).select_from(PrepaidJournalEntry))

    service = _service(async_session)
    run = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=org_id,
        reporting_period=date(2026, 1, 31),
        source_consolidation_run_ref=source_run.id,
        source_fx_translation_run_ref_nullable=None,
        source_ownership_consolidation_run_ref_nullable=None,
        created_by=user_id,
    )
    await service.execute_run(
        tenant_id=tenant_id,
        run_id=uuid.UUID(run["run_id"]),
        created_by=user_id,
    )

    revenue_after = await async_session.scalar(select(func.count()).select_from(RevenueJournalEntry))
    lease_after = await async_session.scalar(select(func.count()).select_from(LeaseJournalEntry))
    prepaid_after = await async_session.scalar(select(func.count()).select_from(PrepaidJournalEntry))
    assert revenue_before == revenue_after
    assert lease_before == lease_after
    assert prepaid_before == prepaid_after
