from __future__ import annotations

import uuid
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError
from financeops.db.models.fixed_assets import (
    Asset,
    AssetDepreciationSchedule,
    AssetDisposal,
    AssetImpairment,
    AssetJournalEntry,
    FarRun,
)


def _correlation_uuid(value: str | None) -> UUID:
    if not value:
        return uuid.UUID("00000000-0000-0000-0000-000000000000")
    try:
        return UUID(str(value))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, str(value))


def _decimal_text(value: Decimal) -> str:
    return f"{value:.6f}"


async def _get_run_or_raise(session: AsyncSession, *, tenant_id: UUID, run_id: UUID) -> FarRun:
    run_result = await session.execute(
        select(FarRun).where(
            FarRun.tenant_id == tenant_id,
            FarRun.id == run_id,
        )
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        raise NotFoundError("Fixed-assets run not found")
    return run


async def get_asset_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    asset_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)

    result = await session.execute(
        select(Asset).where(
            Asset.tenant_id == tenant_id,
            Asset.id == asset_id,
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise NotFoundError("Asset not found")

    child_ids = (
        await session.execute(
            select(AssetDepreciationSchedule.id)
            .where(
                AssetDepreciationSchedule.tenant_id == tenant_id,
                AssetDepreciationSchedule.run_id == run_id,
                AssetDepreciationSchedule.asset_id == asset_id,
            )
            .order_by(
                AssetDepreciationSchedule.depreciation_date,
                AssetDepreciationSchedule.period_seq,
                AssetDepreciationSchedule.id,
            )
        )
    ).scalars().all()

    return {
        "id": asset.id,
        "parent_reference_id": asset.parent_reference_id,
        "source_reference_id": asset.source_reference_id,
        "correlation_id": _correlation_uuid(asset.correlation_id),
        "child_ids": list(child_ids),
        "metadata": {
            "run_id": str(run_id),
            "source_acquisition_reference": asset.source_acquisition_reference,
            "asset_class": asset.asset_class,
        },
        "asset_code": asset.asset_code,
        "depreciation_method": asset.depreciation_method,
        "useful_life_months": asset.useful_life_months,
        "reducing_balance_rate_annual": (
            _decimal_text(asset.reducing_balance_rate_annual)
            if asset.reducing_balance_rate_annual is not None
            else None
        ),
        "residual_value_reporting_currency": _decimal_text(asset.residual_value_reporting_currency),
    }


async def get_depreciation_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    line_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)

    result = await session.execute(
        select(AssetDepreciationSchedule).where(
            AssetDepreciationSchedule.tenant_id == tenant_id,
            AssetDepreciationSchedule.run_id == run_id,
            AssetDepreciationSchedule.id == line_id,
        )
    )
    line = result.scalar_one_or_none()
    if line is None:
        raise NotFoundError("Depreciation line not found")

    child_ids = [line.source_reference_id] if line.source_reference_id is not None else []
    return {
        "id": line.id,
        "parent_reference_id": line.parent_reference_id,
        "source_reference_id": line.source_reference_id,
        "correlation_id": _correlation_uuid(line.correlation_id),
        "child_ids": child_ids,
        "metadata": {
            "run_id": str(run_id),
            "source_acquisition_reference": line.source_acquisition_reference,
            "schedule_status": line.schedule_status,
        },
        "asset_id": line.asset_id,
        "period_seq": line.period_seq,
        "depreciation_date": line.depreciation_date,
        "schedule_version_token": line.schedule_version_token,
        "opening_carrying_amount_reporting_currency": _decimal_text(
            line.opening_carrying_amount_reporting_currency
        ),
        "depreciation_amount_reporting_currency": _decimal_text(
            line.depreciation_amount_reporting_currency
        ),
        "closing_carrying_amount_reporting_currency": _decimal_text(
            line.closing_carrying_amount_reporting_currency
        ),
        "fx_rate_used": _decimal_text(line.fx_rate_used),
        "fx_rate_date": line.fx_rate_date,
        "fx_rate_source": line.fx_rate_source,
    }


async def get_impairment_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    impairment_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)

    result = await session.execute(
        select(AssetImpairment).where(
            AssetImpairment.tenant_id == tenant_id,
            AssetImpairment.run_id == run_id,
            AssetImpairment.id == impairment_id,
        )
    )
    impairment = result.scalar_one_or_none()
    if impairment is None:
        raise NotFoundError("Impairment row not found")

    return {
        "id": impairment.id,
        "parent_reference_id": impairment.parent_reference_id,
        "source_reference_id": impairment.source_reference_id,
        "correlation_id": _correlation_uuid(impairment.correlation_id),
        "child_ids": [impairment.asset_id],
        "metadata": {
            "run_id": str(run_id),
            "source_acquisition_reference": impairment.source_acquisition_reference,
        },
        "asset_id": impairment.asset_id,
        "impairment_date": impairment.impairment_date,
        "impairment_amount_reporting_currency": _decimal_text(
            impairment.impairment_amount_reporting_currency
        ),
        "prior_schedule_version_token": impairment.prior_schedule_version_token,
        "new_schedule_version_token": impairment.new_schedule_version_token,
    }


async def get_disposal_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    disposal_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)

    result = await session.execute(
        select(AssetDisposal).where(
            AssetDisposal.tenant_id == tenant_id,
            AssetDisposal.run_id == run_id,
            AssetDisposal.id == disposal_id,
        )
    )
    disposal = result.scalar_one_or_none()
    if disposal is None:
        raise NotFoundError("Disposal row not found")

    return {
        "id": disposal.id,
        "parent_reference_id": disposal.parent_reference_id,
        "source_reference_id": disposal.source_reference_id,
        "correlation_id": _correlation_uuid(disposal.correlation_id),
        "child_ids": [disposal.asset_id],
        "metadata": {
            "run_id": str(run_id),
            "source_acquisition_reference": disposal.source_acquisition_reference,
        },
        "asset_id": disposal.asset_id,
        "disposal_date": disposal.disposal_date,
        "proceeds_reporting_currency": _decimal_text(disposal.proceeds_reporting_currency),
        "disposal_cost_reporting_currency": _decimal_text(disposal.disposal_cost_reporting_currency),
        "carrying_amount_reporting_currency": _decimal_text(disposal.carrying_amount_reporting_currency),
        "gain_loss_reporting_currency": _decimal_text(disposal.gain_loss_reporting_currency),
        "prior_schedule_version_token": disposal.prior_schedule_version_token,
        "new_schedule_version_token": disposal.new_schedule_version_token,
    }


async def get_journal_drill(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
    journal_id: UUID,
) -> dict:
    await _get_run_or_raise(session, tenant_id=tenant_id, run_id=run_id)

    result = await session.execute(
        select(AssetJournalEntry).where(
            AssetJournalEntry.tenant_id == tenant_id,
            AssetJournalEntry.run_id == run_id,
            AssetJournalEntry.id == journal_id,
        )
    )
    journal = result.scalar_one_or_none()
    if journal is None:
        raise NotFoundError("Asset journal row not found")

    child_ids = [
        item
        for item in [journal.depreciation_schedule_id, journal.impairment_id, journal.disposal_id]
        if item is not None
    ]

    return {
        "id": journal.id,
        "parent_reference_id": journal.parent_reference_id,
        "source_reference_id": journal.source_reference_id,
        "correlation_id": _correlation_uuid(journal.correlation_id),
        "child_ids": child_ids,
        "metadata": {
            "run_id": str(run_id),
            "source_acquisition_reference": journal.source_acquisition_reference,
        },
        "asset_id": journal.asset_id,
        "depreciation_schedule_id": journal.depreciation_schedule_id,
        "impairment_id": journal.impairment_id,
        "disposal_id": journal.disposal_id,
        "journal_reference": journal.journal_reference,
        "line_seq": journal.line_seq,
        "entry_date": journal.entry_date,
        "debit_account": journal.debit_account,
        "credit_account": journal.credit_account,
        "amount_reporting_currency": _decimal_text(journal.amount_reporting_currency),
    }

