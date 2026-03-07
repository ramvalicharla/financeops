from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.consolidation import (
    ConsolidationElimination,
    ConsolidationLineItem,
    ConsolidationResult,
    ConsolidationRun,
    ConsolidationRunEvent,
    IntercompanyPair,
    NormalizedFinancialSnapshot,
    NormalizedFinancialSnapshotLine,
)
from financeops.services.audit_writer import AuditWriter


async def seed_consolidation_drill_dataset(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    user_id: UUID,
    correlation_id: str = "corr-drill-seed",
) -> dict[str, Any]:
    entity_a = uuid.uuid4()
    entity_b = uuid.uuid4()

    snapshot_a = await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshot,
        tenant_id=tenant_id,
        record_data={
            "entity_id": str(entity_a),
            "period_year": 2026,
            "period_month": 3,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": "USD",
            "source_artifact_reference": "seed-A",
        },
        values={
            "entity_id": entity_a,
            "period_year": 2026,
            "period_month": 3,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": "USD",
            "produced_by_module": "mis_manager",
            "source_artifact_reference": "seed-A",
            "supersedes_snapshot_id": None,
            "correlation_id": correlation_id,
        },
    )
    snapshot_b = await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshot,
        tenant_id=tenant_id,
        record_data={
            "entity_id": str(entity_b),
            "period_year": 2026,
            "period_month": 3,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": "USD",
            "source_artifact_reference": "seed-B",
        },
        values={
            "entity_id": entity_b,
            "period_year": 2026,
            "period_month": 3,
            "snapshot_type": "normalized_pnl_v1",
            "entity_currency": "USD",
            "produced_by_module": "mis_manager",
            "source_artifact_reference": "seed-B",
            "supersedes_snapshot_id": None,
            "correlation_id": correlation_id,
        },
    )

    snapshot_line_a = await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshotLine,
        tenant_id=tenant_id,
        record_data={
            "snapshot_id": str(snapshot_a.id),
            "account_code": "4000",
            "local_amount": "100.000000",
            "currency": "USD",
        },
        values={
            "snapshot_id": snapshot_a.id,
            "account_code": "4000",
            "local_amount": Decimal("100.000000"),
            "currency": "USD",
            "ic_reference": "IC-4000",
            "counterparty_entity": entity_b,
            "transaction_date": None,
            "ic_account_class": "IC_RECEIVABLE",
            "correlation_id": correlation_id,
        },
    )
    snapshot_line_b = await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshotLine,
        tenant_id=tenant_id,
        record_data={
            "snapshot_id": str(snapshot_b.id),
            "account_code": "4000",
            "local_amount": "-100.000000",
            "currency": "USD",
        },
        values={
            "snapshot_id": snapshot_b.id,
            "account_code": "4000",
            "local_amount": Decimal("-100.000000"),
            "currency": "USD",
            "ic_reference": "IC-4000",
            "counterparty_entity": entity_a,
            "transaction_date": None,
            "ic_account_class": "IC_PAYABLE",
            "correlation_id": correlation_id,
        },
    )
    snapshot_line_c = await AuditWriter.insert_financial_record(
        session,
        model_class=NormalizedFinancialSnapshotLine,
        tenant_id=tenant_id,
        record_data={
            "snapshot_id": str(snapshot_a.id),
            "account_code": "5000",
            "local_amount": "50.000000",
            "currency": "USD",
        },
        values={
            "snapshot_id": snapshot_a.id,
            "account_code": "5000",
            "local_amount": Decimal("50.000000"),
            "currency": "USD",
            "ic_reference": None,
            "counterparty_entity": None,
            "transaction_date": None,
            "ic_account_class": None,
            "correlation_id": correlation_id,
        },
    )

    run = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationRun,
        tenant_id=tenant_id,
        record_data={
            "period_year": 2026,
            "period_month": 3,
            "parent_currency": "USD",
            "request_signature": f"seed-{uuid.uuid4().hex}",
            "workflow_id": f"wf-seed-{uuid.uuid4().hex[:8]}",
        },
        values={
            "period_year": 2026,
            "period_month": 3,
            "parent_currency": "USD",
            "initiated_by": user_id,
            "request_signature": f"seed-{uuid.uuid4().hex}",
            "configuration_json": {
                "period_year": 2026,
                "period_month": 3,
                "parent_currency": "USD",
                "rate_mode": "daily",
                "entity_snapshots": [
                    {"entity_id": str(entity_a), "snapshot_id": str(snapshot_a.id)},
                    {"entity_id": str(entity_b), "snapshot_id": str(snapshot_b.id)},
                ],
                "tolerances": {
                    "amount_tolerance_parent": "0.010000",
                    "fx_explained_tolerance_parent": "0.500000",
                    "timing_tolerance_days": 3,
                },
            },
            "workflow_id": f"wf-seed-{uuid.uuid4().hex[:8]}",
            "correlation_id": correlation_id,
        },
    )
    await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationRunEvent,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "event_seq": 1,
            "event_type": "accepted",
            "idempotency_key": "seed",
        },
        values={
            "run_id": run.id,
            "event_seq": 1,
            "event_type": "accepted",
            "event_time": run.created_at,
            "idempotency_key": "seed",
            "metadata_json": {"seed": True},
            "correlation_id": correlation_id,
        },
    )

    line_item_a = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationLineItem,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "entity_id": str(entity_a),
            "snapshot_line_id": str(snapshot_line_a.id),
            "account_code": "4000",
        },
        values={
            "run_id": run.id,
            "entity_id": entity_a,
            "snapshot_line_id": snapshot_line_a.id,
            "account_code": "4000",
            "local_currency": "USD",
            "local_amount": Decimal("100.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "expected_rate": Decimal("1.000000"),
            "parent_amount": Decimal("100.000000"),
            "fx_delta_component": Decimal("0.000000"),
            "ic_reference": "IC-4000",
            "ic_counterparty_entity": entity_b,
            "transaction_date": None,
            "correlation_id": correlation_id,
        },
    )
    line_item_b = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationLineItem,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "entity_id": str(entity_b),
            "snapshot_line_id": str(snapshot_line_b.id),
            "account_code": "4000",
        },
        values={
            "run_id": run.id,
            "entity_id": entity_b,
            "snapshot_line_id": snapshot_line_b.id,
            "account_code": "4000",
            "local_currency": "USD",
            "local_amount": Decimal("-100.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "expected_rate": Decimal("1.000000"),
            "parent_amount": Decimal("-100.000000"),
            "fx_delta_component": Decimal("0.000000"),
            "ic_reference": "IC-4000",
            "ic_counterparty_entity": entity_a,
            "transaction_date": None,
            "correlation_id": correlation_id,
        },
    )
    line_item_c = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationLineItem,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "entity_id": str(entity_a),
            "snapshot_line_id": str(snapshot_line_c.id),
            "account_code": "5000",
        },
        values={
            "run_id": run.id,
            "entity_id": entity_a,
            "snapshot_line_id": snapshot_line_c.id,
            "account_code": "5000",
            "local_currency": "USD",
            "local_amount": Decimal("50.000000"),
            "fx_rate_used": Decimal("1.000000"),
            "expected_rate": Decimal("1.000000"),
            "parent_amount": Decimal("50.000000"),
            "fx_delta_component": Decimal("0.000000"),
            "ic_reference": None,
            "ic_counterparty_entity": None,
            "transaction_date": None,
            "correlation_id": correlation_id,
        },
    )

    pair = await AuditWriter.insert_financial_record(
        session,
        model_class=IntercompanyPair,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "match_key_hash": f"pair-{uuid.uuid4().hex}",
            "entity_from": str(entity_a),
            "entity_to": str(entity_b),
            "account_code": "4000",
            "classification": "matched",
        },
        values={
            "run_id": run.id,
            "match_key_hash": f"pair-{uuid.uuid4().hex}",
            "entity_from": entity_a,
            "entity_to": entity_b,
            "account_code": "4000",
            "ic_reference": "IC-4000",
            "amount_local_from": Decimal("100.000000"),
            "amount_local_to": Decimal("-100.000000"),
            "amount_parent_from": Decimal("100.000000"),
            "amount_parent_to": Decimal("-100.000000"),
            "expected_difference": Decimal("0.000000"),
            "actual_difference": Decimal("0.000000"),
            "fx_explained": Decimal("0.000000"),
            "unexplained_difference": Decimal("0.000000"),
            "classification": "matched",
            "correlation_id": correlation_id,
        },
    )
    elimination = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationElimination,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "intercompany_pair_id": str(pair.id),
            "classification_at_time": "matched",
            "elimination_status": "applied",
            "rule_code": "ELIM.APPLY.MATCHED",
        },
        values={
            "run_id": run.id,
            "intercompany_pair_id": pair.id,
            "entity_from": entity_a,
            "entity_to": entity_b,
            "account_code": "4000",
            "classification_at_time": "matched",
            "elimination_status": "applied",
            "eliminated_amount_parent": Decimal("0.000000"),
            "fx_component_impact_parent": Decimal("0.000000"),
            "residual_difference_parent": Decimal("0.000000"),
            "rule_code": "ELIM.APPLY.MATCHED",
            "reason": "seed elimination",
            "correlation_id": correlation_id,
        },
    )
    result_4000 = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationResult,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "consolidated_account_code": "4000",
            "consolidated_amount_parent": "0.000000",
            "fx_impact_total": "0.000000",
        },
        values={
            "run_id": run.id,
            "consolidated_account_code": "4000",
            "consolidated_amount_parent": Decimal("0.000000"),
            "fx_impact_total": Decimal("0.000000"),
            "correlation_id": correlation_id,
        },
    )
    result_5000 = await AuditWriter.insert_financial_record(
        session,
        model_class=ConsolidationResult,
        tenant_id=tenant_id,
        record_data={
            "run_id": str(run.id),
            "consolidated_account_code": "5000",
            "consolidated_amount_parent": "50.000000",
            "fx_impact_total": "0.000000",
        },
        values={
            "run_id": run.id,
            "consolidated_account_code": "5000",
            "consolidated_amount_parent": Decimal("50.000000"),
            "fx_impact_total": Decimal("0.000000"),
            "correlation_id": correlation_id,
        },
    )
    return {
        "run_id": run.id,
        "entity_a_id": entity_a,
        "entity_b_id": entity_b,
        "line_item_a_id": line_item_a.id,
        "line_item_b_id": line_item_b.id,
        "line_item_c_id": line_item_c.id,
        "snapshot_line_a_id": snapshot_line_a.id,
        "snapshot_line_b_id": snapshot_line_b.id,
        "snapshot_line_c_id": snapshot_line_c.id,
        "pair_id": pair.id,
        "elimination_id": elimination.id,
        "result_4000_id": result_4000.id,
        "result_5000_id": result_5000.id,
    }
