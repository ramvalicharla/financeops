from __future__ import annotations

from decimal import Decimal
from typing import Any, Awaitable, Callable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.consolidation import (
    ConsolidationElimination,
    ConsolidationEntity,
    ConsolidationLineItem,
    ConsolidationResult,
    IntercompanyPair,
    NormalizedFinancialSnapshotLine,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.consolidation.consolidation_aggregator import (
    AggregationEliminationInput,
    AggregationLineInput,
    aggregate_consolidation,
)
from financeops.services.consolidation.entity_loader import load_entity_snapshots
from financeops.services.consolidation.fx_application import (
    apply_fx_to_snapshots,
    resolve_expected_rate_for_entity,
)
from financeops.services.consolidation.ic_matcher import MatchCandidateLine
from financeops.services.consolidation.run_queries import list_results
from financeops.services.consolidation.run_store import get_run_or_raise
from financeops.services.consolidation.service_types import config_mappings, config_tolerance

ResolveExpectedRateCallable = Callable[..., Awaitable[Decimal]]
InsertFinancialRecordCallable = Callable[..., Awaitable[Any]]


async def prepare_entities_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID | None,
    correlation_id: str | None,
    resolve_expected_rate_for_entity_fn: ResolveExpectedRateCallable = resolve_expected_rate_for_entity,
    insert_financial_record_fn: InsertFinancialRecordCallable = AuditWriter.insert_financial_record,
) -> int:
    existing_count = await session.scalar(
        select(func.count()).select_from(ConsolidationEntity).where(
            ConsolidationEntity.tenant_id == tenant_id,
            ConsolidationEntity.run_id == run_id,
        )
    )
    if int(existing_count or 0) > 0:
        return int(existing_count or 0)

    run = await get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    mappings = config_mappings(run.configuration_json)
    bundles = await load_entity_snapshots(
        session,
        tenant_id=tenant_id,
        period_year=run.period_year,
        period_month=run.period_month,
        mappings=mappings,
    )
    rate_mode = str(run.configuration_json["rate_mode"])
    for bundle in bundles:
        expected_rate = await resolve_expected_rate_for_entity_fn(
            session,
            tenant_id=tenant_id,
            period_year=run.period_year,
            period_month=run.period_month,
            base_currency=bundle.header.entity_currency,
            parent_currency=run.parent_currency,
            rate_mode=rate_mode,
        )
        await insert_financial_record_fn(
            session,
            model_class=ConsolidationEntity,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "entity_id": str(bundle.header.entity_id),
                "source_snapshot_reference": str(bundle.header.snapshot_id),
                "entity_currency": bundle.header.entity_currency,
            },
            values={
                "run_id": run_id,
                "entity_id": bundle.header.entity_id,
                "entity_currency": bundle.header.entity_currency,
                "source_snapshot_reference": bundle.header.snapshot_id,
                "expected_rate": expected_rate,
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="consolidation.entity.linked",
                resource_type="consolidation_entity",
                new_value={
                    "run_id": str(run_id),
                    "entity_id": str(bundle.header.entity_id),
                    "snapshot_id": str(bundle.header.snapshot_id),
                    "correlation_id": correlation_id,
                },
            ),
        )
    return len(bundles)


async def apply_fx_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID | None,
    correlation_id: str | None,
) -> int:
    existing_count = await session.scalar(
        select(func.count()).select_from(ConsolidationLineItem).where(
            ConsolidationLineItem.tenant_id == tenant_id,
            ConsolidationLineItem.run_id == run_id,
        )
    )
    if int(existing_count or 0) > 0:
        return int(existing_count or 0)

    run = await get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    mappings = config_mappings(run.configuration_json)
    bundles = await load_entity_snapshots(
        session,
        tenant_id=tenant_id,
        period_year=run.period_year,
        period_month=run.period_month,
        mappings=mappings,
    )
    applied_rows = await apply_fx_to_snapshots(
        session,
        tenant_id=tenant_id,
        period_year=run.period_year,
        period_month=run.period_month,
        parent_currency=run.parent_currency,
        rate_mode=str(run.configuration_json["rate_mode"]),
        bundles=bundles,
    )
    for row in applied_rows:
        await AuditWriter.insert_financial_record(
            session,
            model_class=ConsolidationLineItem,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "entity_id": str(row.entity_id),
                "snapshot_line_id": str(row.snapshot_line_id),
                "account_code": row.account_code,
                "parent_amount": str(row.parent_amount),
            },
            values={
                "run_id": run_id,
                "entity_id": row.entity_id,
                "snapshot_line_id": row.snapshot_line_id,
                "account_code": row.account_code,
                "local_currency": row.local_currency,
                "local_amount": row.local_amount,
                "fx_rate_used": row.fx_rate_used,
                "expected_rate": row.expected_rate,
                "parent_amount": row.parent_amount,
                "fx_delta_component": row.fx_delta_component,
                "ic_reference": row.ic_reference,
                "ic_counterparty_entity": row.ic_counterparty_entity,
                "transaction_date": row.transaction_date,
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="consolidation.line_item.created",
                resource_type="consolidation_line_item",
                new_value={
                    "run_id": str(run_id),
                    "snapshot_line_id": str(row.snapshot_line_id),
                    "account_code": row.account_code,
                    "correlation_id": correlation_id,
                },
            ),
        )
    return len(applied_rows)


async def match_intercompany_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID | None,
    correlation_id: str | None,
) -> int:
    # DEPRECATED: routed to legacy engine via intercompany_service.py
    from financeops.modules.multi_entity_consolidation.application.intercompany_service import (
        IntercompanyService,
    )

    existing_count = await session.scalar(
        select(func.count()).select_from(IntercompanyPair).where(
            IntercompanyPair.tenant_id == tenant_id,
            IntercompanyPair.run_id == run_id,
        )
    )
    if int(existing_count or 0) > 0:
        return int(existing_count or 0)

    run = await get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    tolerance = config_tolerance(run.configuration_json)
    lines_result = await session.execute(
        select(
            ConsolidationLineItem,
            NormalizedFinancialSnapshotLine.ic_account_class,
        )
        .join(
            NormalizedFinancialSnapshotLine,
            ConsolidationLineItem.snapshot_line_id == NormalizedFinancialSnapshotLine.id,
        )
        .where(
            ConsolidationLineItem.tenant_id == tenant_id,
            ConsolidationLineItem.run_id == run_id,
        )
        .order_by(
            ConsolidationLineItem.entity_id,
            ConsolidationLineItem.account_code,
            ConsolidationLineItem.snapshot_line_id,
        )
    )
    candidates = [
        MatchCandidateLine(
            snapshot_line_id=line_item.snapshot_line_id,
            entity_id=line_item.entity_id,
            account_code=line_item.account_code,
            local_amount=line_item.local_amount,
            expected_rate=line_item.expected_rate,
            parent_amount=line_item.parent_amount,
            ic_reference=line_item.ic_reference,
            ic_counterparty_entity=line_item.ic_counterparty_entity,
            transaction_date=line_item.transaction_date,
            ic_account_class=ic_account_class,
        )
        for line_item, ic_account_class in lines_result.all()
    ]
    contract = IntercompanyService().match_candidates(candidates=candidates, tolerance=tolerance)
    for decision in contract["matched_pairs"] + contract["unmatched_items"]:
        await AuditWriter.insert_financial_record(
            session,
            model_class=IntercompanyPair,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "match_key_hash": decision["match_key_hash"],
                "entity_from": str(decision["entity_from"]),
                "entity_to": str(decision["entity_to"]),
                "account_code": decision["account_code"],
                "classification": decision["classification"],
            },
            values={
                "run_id": run_id,
                "match_key_hash": decision["match_key_hash"],
                "entity_from": UUID(str(decision["entity_from"])),
                "entity_to": UUID(str(decision["entity_to"])),
                "account_code": decision["account_code"],
                "ic_reference": decision["ic_reference"],
                "amount_local_from": Decimal(str(decision["amount_local_from"])),
                "amount_local_to": Decimal(str(decision["amount_local_to"])),
                "amount_parent_from": Decimal(str(decision["amount_parent_from"])),
                "amount_parent_to": Decimal(str(decision["amount_parent_to"])),
                "expected_difference": Decimal(str(decision["expected_difference"])),
                "actual_difference": Decimal(str(decision["actual_difference"])),
                "fx_explained": Decimal(str(decision["fx_explained"])),
                "unexplained_difference": Decimal(str(decision["unexplained_difference"])),
                "classification": decision["classification"],
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="consolidation.ic_pair.created",
                resource_type="intercompany_pair",
                new_value={
                    "run_id": str(run_id),
                    "classification": decision["classification"],
                    "match_key_hash": decision["match_key_hash"],
                    "correlation_id": correlation_id,
                },
            ),
        )
    return len(contract["matched_pairs"]) + len(contract["unmatched_items"])


async def compute_eliminations_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID | None,
    correlation_id: str | None,
) -> int:
    # DEPRECATED: routed to legacy engine via intercompany_service.py
    from financeops.modules.multi_entity_consolidation.application.intercompany_service import (
        IntercompanyService,
    )

    existing_count = await session.scalar(
        select(func.count()).select_from(ConsolidationElimination).where(
            ConsolidationElimination.tenant_id == tenant_id,
            ConsolidationElimination.run_id == run_id,
        )
    )
    if int(existing_count or 0) > 0:
        return int(existing_count or 0)

    pairs_result = await session.execute(
        select(IntercompanyPair)
        .where(
            IntercompanyPair.tenant_id == tenant_id,
            IntercompanyPair.run_id == run_id,
        )
        .order_by(IntercompanyPair.match_key_hash)
    )
    pair_rows = list(pairs_result.scalars().all())
    run = await get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)
    tolerance = config_tolerance(run.configuration_json)
    contract = IntercompanyService().build_eliminations_from_pairs(
        pair_rows=pair_rows,
        tolerance=tolerance,
    )
    for decision in contract["elimination_entries"]:
        await AuditWriter.insert_financial_record(
            session,
            model_class=ConsolidationElimination,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "intercompany_pair_id": str(decision["intercompany_pair_id"]),
                "classification_at_time": decision["classification_at_time"],
                "elimination_status": decision["elimination_status"],
                "rule_code": decision["rule_code"],
            },
            values={
                "run_id": run_id,
                "intercompany_pair_id": UUID(str(decision["intercompany_pair_id"])),
                "entity_from": UUID(str(decision["entity_from"])),
                "entity_to": UUID(str(decision["entity_to"])),
                "account_code": decision["account_code"],
                "classification_at_time": decision["classification_at_time"],
                "elimination_status": decision["elimination_status"],
                "eliminated_amount_parent": Decimal(str(decision["eliminated_amount_parent"])),
                "fx_component_impact_parent": Decimal(str(decision["fx_component_impact_parent"])),
                "residual_difference_parent": Decimal(str(decision["residual_difference_parent"])),
                "rule_code": decision["rule_code"],
                "reason": decision["reason"],
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="consolidation.elimination.created",
                resource_type="consolidation_elimination",
                new_value={
                    "run_id": str(run_id),
                    "intercompany_pair_id": str(decision["intercompany_pair_id"]),
                    "elimination_status": decision["elimination_status"],
                    "correlation_id": correlation_id,
                },
            ),
        )
    return len(contract["elimination_entries"])


async def aggregate_results_for_run(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID | None,
    correlation_id: str | None,
) -> dict[str, Any]:
    existing_result_count = await session.scalar(
        select(func.count()).select_from(ConsolidationResult).where(
            ConsolidationResult.tenant_id == tenant_id,
            ConsolidationResult.run_id == run_id,
        )
    )
    if int(existing_result_count or 0) > 0:
        rows = await list_results(session, tenant_id=tenant_id, run_id=run_id)
        unexplained_count = await session.scalar(
            select(func.count()).select_from(IntercompanyPair).where(
                IntercompanyPair.tenant_id == tenant_id,
                IntercompanyPair.run_id == run_id,
                IntercompanyPair.classification.in_(["timing_difference", "unexplained"]),
            )
        )
        return {
            "result_count": rows["count"],
            "unexplained_count": int(unexplained_count or 0),
            "total_consolidated_amount_parent": rows["total_consolidated_amount_parent"],
            "total_fx_impact_parent": rows["total_fx_impact_parent"],
        }

    line_result = await session.execute(
        select(ConsolidationLineItem).where(
            ConsolidationLineItem.tenant_id == tenant_id,
            ConsolidationLineItem.run_id == run_id,
        )
    )
    elimination_result = await session.execute(
        select(ConsolidationElimination).where(
            ConsolidationElimination.tenant_id == tenant_id,
            ConsolidationElimination.run_id == run_id,
        )
    )
    aggregate_output = aggregate_consolidation(
        lines=[
            AggregationLineInput(
                account_code=row.account_code,
                parent_amount=row.parent_amount,
                fx_delta_component=row.fx_delta_component,
            )
            for row in line_result.scalars().all()
        ],
        eliminations=[
            AggregationEliminationInput(
                account_code=row.account_code,
                elimination_status=row.elimination_status,
                eliminated_amount_parent=row.eliminated_amount_parent,
                fx_component_impact_parent=row.fx_component_impact_parent,
            )
            for row in elimination_result.scalars().all()
        ],
    )

    for row in aggregate_output.rows:
        await AuditWriter.insert_financial_record(
            session,
            model_class=ConsolidationResult,
            tenant_id=tenant_id,
            record_data={
                "run_id": str(run_id),
                "consolidated_account_code": row.consolidated_account_code,
                "consolidated_amount_parent": str(row.consolidated_amount_parent),
                "fx_impact_total": str(row.fx_impact_total),
            },
            values={
                "run_id": run_id,
                "consolidated_account_code": row.consolidated_account_code,
                "consolidated_amount_parent": row.consolidated_amount_parent,
                "fx_impact_total": row.fx_impact_total,
                "correlation_id": correlation_id,
            },
            audit=AuditEvent(
                tenant_id=tenant_id,
                user_id=user_id,
                action="consolidation.result.created",
                resource_type="consolidation_result",
                new_value={
                    "run_id": str(run_id),
                    "consolidated_account_code": row.consolidated_account_code,
                    "correlation_id": correlation_id,
                },
            ),
        )

    unexplained_count = await session.scalar(
        select(func.count()).select_from(IntercompanyPair).where(
            IntercompanyPair.tenant_id == tenant_id,
            IntercompanyPair.run_id == run_id,
            IntercompanyPair.classification.in_(["timing_difference", "unexplained"]),
        )
    )
    return {
        "result_count": len(aggregate_output.rows),
        "unexplained_count": int(unexplained_count or 0),
        "total_consolidated_amount_parent": str(aggregate_output.total_consolidated_amount_parent),
        "total_fx_impact_parent": str(aggregate_output.total_fx_impact_parent),
    }

