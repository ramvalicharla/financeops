from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.lease import LeaseJournalEntry
from financeops.db.models.multi_entity_consolidation import (
    ConsolidationScope,
    EntityHierarchy,
    MultiEntityConsolidationMetricResult,
    MultiEntityConsolidationRun,
    MultiEntityConsolidationVarianceResult,
)
from financeops.db.models.ownership_consolidation import (
    MinorityInterestRuleDefinition,
    OwnershipConsolidationMetricResult,
    OwnershipConsolidationRuleDefinition,
    OwnershipRelationship,
    OwnershipStructureDefinition,
)
from financeops.db.models.revenue import RevenueJournalEntry
from financeops.db.rls import set_tenant_context
from financeops.modules.ownership_consolidation.application.mapping_service import MappingService
from financeops.modules.ownership_consolidation.application.rule_service import RuleService
from financeops.modules.ownership_consolidation.application.run_service import RunService
from financeops.modules.ownership_consolidation.application.validation_service import (
    ValidationService,
)
from financeops.modules.ownership_consolidation.infrastructure.repository import (
    OwnershipConsolidationRepository,
)
from financeops.modules.ownership_consolidation.infrastructure.token_builder import (
    build_definition_version_token,
)
from financeops.modules.ownership_consolidation.domain.value_objects import (
    DefinitionVersionTokenInput,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter


def _build_service(session: AsyncSession) -> RunService:
    return RunService(
        repository=OwnershipConsolidationRepository(session),
        validation_service=ValidationService(),
        mapping_service=MappingService(),
        rule_service=RuleService(),
    )


async def _seed_active_config(
    session: AsyncSession, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, created_by: uuid.UUID
) -> None:
    structure_token = build_definition_version_token(
        DefinitionVersionTokenInput(
            rows=[
                {
                    "organisation_id": str(organisation_id),
                    "ownership_structure_code": "GROUP_MAIN",
                    "effective_from": "2026-01-01",
                    "status": "active",
                }
            ]
        )
    )
    structure = await AuditWriter.insert_financial_record(
        session,
        model_class=OwnershipStructureDefinition,
        tenant_id=tenant_id,
        record_data={"ownership_structure_code": "GROUP_MAIN"},
        values={
            "organisation_id": organisation_id,
            "ownership_structure_code": "GROUP_MAIN",
            "ownership_structure_name": "Group Main",
            "hierarchy_scope_ref": "scope-main",
            "ownership_basis_type": "equity_percentage",
            "version_token": structure_token,
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
            resource_type="ownership_structure_definition",
            resource_name="GROUP_MAIN",
        ),
    )

    await AuditWriter.insert_financial_record(
        session,
        model_class=OwnershipRelationship,
        tenant_id=tenant_id,
        record_data={"ownership_structure_id": str(structure.id)},
        values={
            "organisation_id": organisation_id,
            "ownership_structure_id": structure.id,
            "parent_entity_id": uuid.UUID("00000000-0000-0000-0000-0000000000a1"),
            "child_entity_id": uuid.UUID("00000000-0000-0000-0000-0000000000b1"),
            "ownership_percentage": Decimal("80.000000"),
            "voting_percentage_nullable": None,
            "control_indicator": True,
            "minority_interest_indicator": True,
            "proportionate_consolidation_indicator": False,
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
            resource_type="ownership_relationship",
            resource_name="A->B",
        ),
    )

    own_rule_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[{"rule_code": "OWN_RULE_MAIN", "status": "active"}])
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=OwnershipConsolidationRuleDefinition,
        tenant_id=tenant_id,
        record_data={"rule_code": "OWN_RULE_MAIN"},
        values={
            "organisation_id": organisation_id,
            "rule_code": "OWN_RULE_MAIN",
            "rule_name": "Main Ownership Rule",
            "rule_type": "full_consolidation_rule",
            "rule_logic_json": {},
            "attribution_policy_json": {},
            "version_token": own_rule_token,
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
            resource_type="ownership_consolidation_rule_definition",
            resource_name="OWN_RULE_MAIN",
        ),
    )

    minority_rule_token = build_definition_version_token(
        DefinitionVersionTokenInput(rows=[{"rule_code": "MIN_RULE_MAIN", "status": "active"}])
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=MinorityInterestRuleDefinition,
        tenant_id=tenant_id,
        record_data={"rule_code": "MIN_RULE_MAIN"},
        values={
            "organisation_id": organisation_id,
            "rule_code": "MIN_RULE_MAIN",
            "rule_name": "Main Minority Rule",
            "attribution_basis_type": "ownership_share",
            "calculation_logic_json": {},
            "presentation_logic_json": {},
            "version_token": minority_rule_token,
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
            resource_type="minority_interest_rule_definition",
            resource_name="MIN_RULE_MAIN",
        ),
    )


async def _seed_source_run(
    session: AsyncSession, *, tenant_id: uuid.UUID, organisation_id: uuid.UUID, created_by: uuid.UUID
) -> uuid.UUID:
    hierarchy = await AuditWriter.insert_financial_record(
        session,
        model_class=EntityHierarchy,
        tenant_id=tenant_id,
        record_data={"hierarchy_code": "SRC_H_OWN_1"},
        values={
            "organisation_id": organisation_id,
            "hierarchy_code": "SRC_H_OWN_1",
            "hierarchy_name": "Source Hierarchy",
            "hierarchy_type": "legal",
            "version_token": "src_h_own_1",
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
            resource_name="SRC_H_OWN_1",
        ),
    )
    scope = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationScope,
        tenant_id=tenant_id,
        record_data={"scope_code": "SRC_S_OWN_1"},
        values={
            "organisation_id": organisation_id,
            "scope_code": "SRC_S_OWN_1",
            "scope_name": "Source Scope",
            "hierarchy_id": hierarchy.id,
            "scope_selector_json": {"mode": "all"},
            "version_token": "src_s_own_1",
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
            resource_name="SRC_S_OWN_1",
        ),
    )
    source_run = await AuditWriter.insert_financial_record(
        session,
        model_class=MultiEntityConsolidationRun,
        tenant_id=tenant_id,
        record_data={"run_token": "src_multientity_run_1"},
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
            "run_token": "src_multientity_run_1",
            "run_status": "completed",
            "validation_summary_json": {},
            "created_by": created_by,
        },
        audit=AuditEvent(
            tenant_id=tenant_id,
            user_id=created_by,
            action="test.seed",
            resource_type="multi_entity_consolidation_run",
            resource_name="src_multientity_run_1",
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
            "scope_json": {
                "entity_id": "00000000-0000-0000-0000-0000000000b1",
                "scope_code": "group_scope",
            },
            "currency_code": "USD",
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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_ownership_run_is_deterministic_and_no_upstream_mutation(
    async_session: AsyncSession,
) -> None:
    tenant_id = uuid.uuid4()
    organisation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await set_tenant_context(async_session, tenant_id)
    await _seed_active_config(
        async_session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=user_id,
    )
    source_run_id = await _seed_source_run(
        async_session,
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        created_by=user_id,
    )
    await async_session.flush()

    source_metric_count_before = await async_session.scalar(
        select(func.count()).select_from(MultiEntityConsolidationMetricResult)
    )
    source_variance_count_before = await async_session.scalar(
        select(func.count()).select_from(MultiEntityConsolidationVarianceResult)
    )
    revenue_journal_count_before = await async_session.scalar(
        select(func.count()).select_from(RevenueJournalEntry)
    )
    lease_journal_count_before = await async_session.scalar(
        select(func.count()).select_from(LeaseJournalEntry)
    )

    service = _build_service(async_session)
    run_a = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        reporting_period=date(2026, 1, 31),
        source_consolidation_run_refs=[
            {"source_type": "consolidation_run", "run_id": str(source_run_id)}
        ],
        fx_translation_run_ref_nullable=None,
        created_by=user_id,
    )
    run_b = await service.create_run(
        tenant_id=tenant_id,
        organisation_id=organisation_id,
        reporting_period=date(2026, 1, 31),
        source_consolidation_run_refs=[
            {"source_type": "consolidation_run", "run_id": str(source_run_id)}
        ],
        fx_translation_run_ref_nullable=None,
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

    source_metric_count_after = await async_session.scalar(
        select(func.count()).select_from(MultiEntityConsolidationMetricResult)
    )
    source_variance_count_after = await async_session.scalar(
        select(func.count()).select_from(MultiEntityConsolidationVarianceResult)
    )
    revenue_journal_count_after = await async_session.scalar(
        select(func.count()).select_from(RevenueJournalEntry)
    )
    lease_journal_count_after = await async_session.scalar(
        select(func.count()).select_from(LeaseJournalEntry)
    )
    assert source_metric_count_before == source_metric_count_after
    assert source_variance_count_before == source_variance_count_after
    assert revenue_journal_count_before == revenue_journal_count_after
    assert lease_journal_count_before == lease_journal_count_after

    rows = (
        await async_session.execute(
            select(OwnershipConsolidationMetricResult).order_by(
                OwnershipConsolidationMetricResult.line_no.asc(),
                OwnershipConsolidationMetricResult.id.asc(),
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert str(rows[0].attributed_value) == "100.000000"
    assert str(rows[0].minority_interest_value_nullable) == "20.000000"
