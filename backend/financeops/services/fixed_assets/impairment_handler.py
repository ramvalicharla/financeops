from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.fixed_assets import AssetImpairment
from financeops.schemas.fixed_assets import AssetImpairmentInput
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
from financeops.services.accounting_common.supersession_validator import (
    SupersessionNode,
    ensure_append_targets_terminal,
    validate_linear_chain,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.fixed_assets.depreciation_engine import GeneratedDepreciationRow, build_schedule_version_token


@dataclass(frozen=True)
class ImpairmentApplicationResult:
    rows: list[GeneratedDepreciationRow]
    events: list[AssetImpairment]
    latest_schedule_version_token: str


def _event_sort_key(item: AssetImpairmentInput) -> tuple:
    return (item.impairment_date, item.idempotency_key)


async def apply_impairments(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    user_id: UUID,
    correlation_id: str,
    asset_id: UUID,
    source_acquisition_reference: str,
    parent_reference_id: UUID | None,
    source_reference_id: UUID | None,
    depreciation_method: str,
    useful_life_months: int | None,
    reducing_balance_rate_annual: Decimal | None,
    residual_value_reporting_currency: Decimal,
    reporting_currency: str,
    rate_mode: str,
    current_rows: Iterable[GeneratedDepreciationRow],
    events: Iterable[AssetImpairmentInput],
    prior_schedule_version_token: str,
) -> ImpairmentApplicationResult:
    rows = list(sorted(current_rows, key=lambda row: (row.depreciation_date, row.period_seq, row.schedule_version_token)))
    latest_token = prior_schedule_version_token
    existing_chain = (
        await session.execute(
            select(AssetImpairment)
            .where(
                AssetImpairment.tenant_id == tenant_id,
                AssetImpairment.run_id == run_id,
                AssetImpairment.asset_id == asset_id,
            )
            .order_by(AssetImpairment.created_at, AssetImpairment.id)
        )
    ).scalars().all()
    chain_events: list[AssetImpairment] = list(existing_chain)
    persisted_events: list[AssetImpairment] = []
    chain_nodes = [
        SupersessionNode(
            id=row.id,
            tenant_id=row.tenant_id,
            created_at=row.created_at,
            supersedes_id=row.supersedes_id,
        )
        for row in existing_chain
    ]
    validate_linear_chain(nodes=chain_nodes, tenant_id=tenant_id)

    for impairment in sorted(events, key=_event_sort_key):
        ensure_append_targets_terminal(
            nodes=chain_nodes,
            tenant_id=tenant_id,
            supersedes_id=chain_events[-1].id if chain_events else None,
        )
        existing_result = await session.execute(
            select(AssetImpairment).where(
                AssetImpairment.tenant_id == tenant_id,
                AssetImpairment.run_id == run_id,
                AssetImpairment.asset_id == asset_id,
                AssetImpairment.impairment_date == impairment.impairment_date,
                AssetImpairment.idempotency_key == impairment.idempotency_key,
            )
        )
        existing = existing_result.scalar_one_or_none()

        new_token = build_schedule_version_token(
            asset_id=asset_id,
            depreciation_method=depreciation_method,
            useful_life_months=useful_life_months,
            reducing_balance_rate_annual=reducing_balance_rate_annual,
            residual_value_reporting_currency=residual_value_reporting_currency,
            reporting_currency=reporting_currency,
            rate_mode=rate_mode,
            effective_date=impairment.impairment_date,
            prior_schedule_version_token_or_root=latest_token,
        )

        if existing is None:
            existing = await AuditWriter.insert_financial_record(
                session,
                model_class=AssetImpairment,
                tenant_id=tenant_id,
                record_data={
                    "run_id": str(run_id),
                    "asset_id": str(asset_id),
                    "impairment_date": impairment.impairment_date.isoformat(),
                    "idempotency_key": impairment.idempotency_key,
                },
                values={
                    "run_id": run_id,
                    "asset_id": asset_id,
                    "impairment_date": impairment.impairment_date,
                    "impairment_amount_reporting_currency": quantize_persisted_amount(
                        impairment.impairment_amount_reporting_currency
                    ),
                    "idempotency_key": impairment.idempotency_key,
                    "prior_schedule_version_token": latest_token,
                    "new_schedule_version_token": new_token,
                    "reason": impairment.reason,
                    "fx_rate_used": Decimal("1.000000"),
                    "fx_rate_date": impairment.impairment_date,
                    "fx_rate_source": "event_reporting_currency",
                    "source_acquisition_reference": source_acquisition_reference,
                    "parent_reference_id": parent_reference_id,
                    "source_reference_id": source_reference_id,
                    "correlation_id": correlation_id,
                    "supersedes_id": chain_events[-1].id if chain_events else None,
                },
                audit=AuditEvent(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="fixed_assets.impairment.created",
                    resource_type="asset_impairment",
                    new_value={
                        "run_id": str(run_id),
                        "asset_id": str(asset_id),
                        "impairment_date": impairment.impairment_date.isoformat(),
                        "correlation_id": correlation_id,
                    },
                ),
            )
            chain_nodes.append(
                SupersessionNode(
                    id=existing.id,
                    tenant_id=existing.tenant_id,
                    created_at=existing.created_at,
                    supersedes_id=existing.supersedes_id,
                )
            )
            chain_events.append(existing)

        persisted_events.append(existing)

        unaffected = [row for row in rows if row.depreciation_date < impairment.impairment_date]
        affected = [row for row in rows if row.depreciation_date >= impairment.impairment_date]

        if not affected:
            latest_token = existing.new_schedule_version_token
            continue

        impairment_amount = quantize_persisted_amount(existing.impairment_amount_reporting_currency)
        running = unaffected[-1].closing_carrying_amount_reporting_currency if unaffected else affected[0].opening_carrying_amount_reporting_currency
        running = quantize_persisted_amount(max(running - impairment_amount, residual_value_reporting_currency))
        cumulative = unaffected[-1].cumulative_depreciation_reporting_currency if unaffected else Decimal("0.000000")

        regenerated: list[GeneratedDepreciationRow] = []
        for item in affected:
            max_allowed = quantize_persisted_amount(max(running - residual_value_reporting_currency, Decimal("0.000000")))
            depreciation_amount = item.depreciation_amount_reporting_currency
            if depreciation_amount > max_allowed:
                depreciation_amount = max_allowed
            depreciation_amount = quantize_persisted_amount(max(depreciation_amount, Decimal("0.000000")))
            closing = quantize_persisted_amount(max(running - depreciation_amount, residual_value_reporting_currency))
            cumulative = quantize_persisted_amount(cumulative + depreciation_amount)
            regenerated.append(
                GeneratedDepreciationRow(
                    asset_id=item.asset_id,
                    period_seq=item.period_seq,
                    depreciation_date=item.depreciation_date,
                    depreciation_period_year=item.depreciation_period_year,
                    depreciation_period_month=item.depreciation_period_month,
                    schedule_version_token=existing.new_schedule_version_token,
                    opening_carrying_amount_reporting_currency=running,
                    depreciation_amount_reporting_currency=depreciation_amount,
                    cumulative_depreciation_reporting_currency=cumulative,
                    closing_carrying_amount_reporting_currency=closing,
                    fx_rate_used=item.fx_rate_used,
                    fx_rate_date=item.fx_rate_date,
                    fx_rate_source=item.fx_rate_source,
                    schedule_status="regenerated",
                    source_acquisition_reference=item.source_acquisition_reference,
                    parent_reference_id=item.parent_reference_id,
                    source_reference_id=item.source_reference_id,
                )
            )
            running = closing

        rows = unaffected + regenerated
        latest_token = existing.new_schedule_version_token

    rows.sort(key=lambda row: (row.depreciation_date, row.period_seq, row.schedule_version_token))
    return ImpairmentApplicationResult(
        rows=rows,
        events=persisted_events,
        latest_schedule_version_token=latest_token,
    )
