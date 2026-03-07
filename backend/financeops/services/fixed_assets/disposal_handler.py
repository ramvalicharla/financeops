from __future__ import annotations

import calendar
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.fixed_assets import AssetDisposal
from financeops.schemas.fixed_assets import AssetDisposalInput
from financeops.services.accounting_common.accounting_errors import AccountingValidationError
from financeops.services.accounting_common.error_codes import INVALID_EVENT_SEQUENCE
from financeops.services.accounting_common.quantization_policy import quantize_persisted_amount
from financeops.services.accounting_common.supersession_validator import (
    SupersessionNode,
    ensure_append_targets_terminal,
    validate_linear_chain,
)
from financeops.services.audit_writer import AuditEvent, AuditWriter
from financeops.services.fixed_assets.depreciation_engine import GeneratedDepreciationRow, build_schedule_version_token


@dataclass(frozen=True)
class DisposalApplicationResult:
    rows: list[GeneratedDepreciationRow]
    events: list[AssetDisposal]
    latest_schedule_version_token: str


def _event_sort_key(item: AssetDisposalInput) -> tuple:
    return (item.disposal_date, item.idempotency_key)


def _days_in_month(value) -> int:
    return calendar.monthrange(value.year, value.month)[1]


async def apply_disposals(
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
    disposals: Iterable[AssetDisposalInput],
    prior_schedule_version_token: str,
) -> DisposalApplicationResult:
    rows = list(sorted(current_rows, key=lambda row: (row.depreciation_date, row.period_seq, row.schedule_version_token)))
    latest_token = prior_schedule_version_token
    existing_chain = (
        await session.execute(
            select(AssetDisposal)
            .where(
                AssetDisposal.tenant_id == tenant_id,
                AssetDisposal.run_id == run_id,
                AssetDisposal.asset_id == asset_id,
            )
            .order_by(AssetDisposal.created_at, AssetDisposal.id)
        )
    ).scalars().all()
    chain_events: list[AssetDisposal] = list(existing_chain)
    persisted_events: list[AssetDisposal] = []
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

    disposal_date_guard = None
    for disposal in sorted(disposals, key=_event_sort_key):
        ensure_append_targets_terminal(
            nodes=chain_nodes,
            tenant_id=tenant_id,
            supersedes_id=chain_events[-1].id if chain_events else None,
        )
        if disposal_date_guard is not None and disposal.disposal_date > disposal_date_guard:
            raise AccountingValidationError(
                error_code=INVALID_EVENT_SEQUENCE,
                message="disposal on date D blocks subsequent impairment/disposal events with date > D",
            )

        existing_result = await session.execute(
            select(AssetDisposal).where(
                AssetDisposal.tenant_id == tenant_id,
                AssetDisposal.run_id == run_id,
                AssetDisposal.asset_id == asset_id,
                AssetDisposal.disposal_date == disposal.disposal_date,
                AssetDisposal.idempotency_key == disposal.idempotency_key,
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
            effective_date=disposal.disposal_date,
            prior_schedule_version_token_or_root=latest_token,
        )

        prior_rows = list(rows)
        pre_rows = [row for row in prior_rows if row.depreciation_date < disposal.disposal_date]
        same_or_after = [row for row in prior_rows if row.depreciation_date >= disposal.disposal_date]

        carrying_amount = pre_rows[-1].closing_carrying_amount_reporting_currency if pre_rows else (
            same_or_after[0].opening_carrying_amount_reporting_currency if same_or_after else Decimal("0.000000")
        )

        partial_row = None
        if same_or_after:
            first = same_or_after[0]
            if first.depreciation_date.month == disposal.disposal_date.month and first.depreciation_date.year == disposal.disposal_date.year:
                ratio = Decimal(str(disposal.disposal_date.day)) / Decimal(str(_days_in_month(disposal.disposal_date)))
                depreciation_amount = quantize_persisted_amount(first.depreciation_amount_reporting_currency * ratio)
                max_allowed = quantize_persisted_amount(max(first.opening_carrying_amount_reporting_currency - residual_value_reporting_currency, Decimal("0.000000")))
                if depreciation_amount > max_allowed:
                    depreciation_amount = max_allowed
                closing = quantize_persisted_amount(first.opening_carrying_amount_reporting_currency - depreciation_amount)
                partial_row = GeneratedDepreciationRow(
                    asset_id=first.asset_id,
                    period_seq=first.period_seq,
                    depreciation_date=disposal.disposal_date,
                    depreciation_period_year=disposal.disposal_date.year,
                    depreciation_period_month=disposal.disposal_date.month,
                    schedule_version_token=new_token,
                    opening_carrying_amount_reporting_currency=first.opening_carrying_amount_reporting_currency,
                    depreciation_amount_reporting_currency=depreciation_amount,
                    cumulative_depreciation_reporting_currency=(
                        pre_rows[-1].cumulative_depreciation_reporting_currency + depreciation_amount
                        if pre_rows
                        else depreciation_amount
                    ),
                    closing_carrying_amount_reporting_currency=closing,
                    fx_rate_used=first.fx_rate_used,
                    fx_rate_date=disposal.disposal_date,
                    fx_rate_source=first.fx_rate_source,
                    schedule_status="disposed_partial",
                    source_acquisition_reference=first.source_acquisition_reference,
                    parent_reference_id=first.parent_reference_id,
                    source_reference_id=first.source_reference_id,
                )
                carrying_amount = closing

        gain_loss = quantize_persisted_amount(
            disposal.proceeds_reporting_currency
            - disposal.disposal_cost_reporting_currency
            - carrying_amount
        )

        if existing is None:
            existing = await AuditWriter.insert_financial_record(
                session,
                model_class=AssetDisposal,
                tenant_id=tenant_id,
                record_data={
                    "run_id": str(run_id),
                    "asset_id": str(asset_id),
                    "disposal_date": disposal.disposal_date.isoformat(),
                    "idempotency_key": disposal.idempotency_key,
                },
                values={
                    "run_id": run_id,
                    "asset_id": asset_id,
                    "disposal_date": disposal.disposal_date,
                    "proceeds_reporting_currency": quantize_persisted_amount(disposal.proceeds_reporting_currency),
                    "disposal_cost_reporting_currency": quantize_persisted_amount(disposal.disposal_cost_reporting_currency),
                    "carrying_amount_reporting_currency": carrying_amount,
                    "gain_loss_reporting_currency": gain_loss,
                    "idempotency_key": disposal.idempotency_key,
                    "prior_schedule_version_token": latest_token,
                    "new_schedule_version_token": new_token,
                    "fx_rate_used": Decimal("1.000000"),
                    "fx_rate_date": disposal.disposal_date,
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
                    action="fixed_assets.disposal.created",
                    resource_type="asset_disposal",
                    new_value={
                        "run_id": str(run_id),
                        "asset_id": str(asset_id),
                        "disposal_date": disposal.disposal_date.isoformat(),
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

        updated_rows: list[GeneratedDepreciationRow] = [
            GeneratedDepreciationRow(
                asset_id=row.asset_id,
                period_seq=row.period_seq,
                depreciation_date=row.depreciation_date,
                depreciation_period_year=row.depreciation_period_year,
                depreciation_period_month=row.depreciation_period_month,
                schedule_version_token=new_token,
                opening_carrying_amount_reporting_currency=row.opening_carrying_amount_reporting_currency,
                depreciation_amount_reporting_currency=row.depreciation_amount_reporting_currency,
                cumulative_depreciation_reporting_currency=row.cumulative_depreciation_reporting_currency,
                closing_carrying_amount_reporting_currency=row.closing_carrying_amount_reporting_currency,
                fx_rate_used=row.fx_rate_used,
                fx_rate_date=row.fx_rate_date,
                fx_rate_source=row.fx_rate_source,
                schedule_status=row.schedule_status,
                source_acquisition_reference=row.source_acquisition_reference,
                parent_reference_id=row.parent_reference_id,
                source_reference_id=row.source_reference_id,
            )
            for row in pre_rows
        ]
        if partial_row is not None:
            updated_rows.append(partial_row)

        rows = updated_rows
        latest_token = existing.new_schedule_version_token
        disposal_date_guard = disposal.disposal_date

    rows.sort(key=lambda row: (row.depreciation_date, row.period_seq, row.schedule_version_token))
    return DisposalApplicationResult(rows=rows, events=persisted_events, latest_schedule_version_token=latest_token)
