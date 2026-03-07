from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.fixed_assets import (
    Asset,
    AssetDepreciationSchedule,
    AssetDisposal,
    AssetImpairment,
    AssetJournalEntry,
)
from financeops.services.accounting_common.run_validation import LineageValidationResult


async def validate_fixed_assets_lineage(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    run_id: UUID,
) -> LineageValidationResult:
    missing_schedule_asset_links = int(
        await session.scalar(
            select(func.count())
            .select_from(AssetDepreciationSchedule)
            .outerjoin(Asset, AssetDepreciationSchedule.asset_id == Asset.id)
            .where(
                AssetDepreciationSchedule.tenant_id == tenant_id,
                AssetDepreciationSchedule.run_id == run_id,
                Asset.id.is_(None),
            )
        )
        or 0
    )

    missing_schedule_source_links = int(
        await session.scalar(
            select(func.count())
            .select_from(AssetDepreciationSchedule)
            .where(
                AssetDepreciationSchedule.tenant_id == tenant_id,
                AssetDepreciationSchedule.run_id == run_id,
                (
                    AssetDepreciationSchedule.source_reference_id.is_(None)
                    | (AssetDepreciationSchedule.source_acquisition_reference == "")
                ),
            )
        )
        or 0
    )

    missing_impairment_asset_links = int(
        await session.scalar(
            select(func.count())
            .select_from(AssetImpairment)
            .outerjoin(Asset, AssetImpairment.asset_id == Asset.id)
            .where(
                AssetImpairment.tenant_id == tenant_id,
                AssetImpairment.run_id == run_id,
                Asset.id.is_(None),
            )
        )
        or 0
    )

    missing_disposal_asset_links = int(
        await session.scalar(
            select(func.count())
            .select_from(AssetDisposal)
            .outerjoin(Asset, AssetDisposal.asset_id == Asset.id)
            .where(
                AssetDisposal.tenant_id == tenant_id,
                AssetDisposal.run_id == run_id,
                Asset.id.is_(None),
            )
        )
        or 0
    )

    invalid_journal_one_of_links = int(
        await session.scalar(
            select(func.count())
            .select_from(AssetJournalEntry)
            .where(
                AssetJournalEntry.tenant_id == tenant_id,
                AssetJournalEntry.run_id == run_id,
                (
                    (
                        AssetJournalEntry.depreciation_schedule_id.is_(None)
                        & AssetJournalEntry.impairment_id.is_(None)
                        & AssetJournalEntry.disposal_id.is_(None)
                    )
                    | (
                        AssetJournalEntry.depreciation_schedule_id.is_not(None)
                        & AssetJournalEntry.impairment_id.is_not(None)
                    )
                    | (
                        AssetJournalEntry.depreciation_schedule_id.is_not(None)
                        & AssetJournalEntry.disposal_id.is_not(None)
                    )
                    | (
                        AssetJournalEntry.impairment_id.is_not(None)
                        & AssetJournalEntry.disposal_id.is_not(None)
                    )
                ),
            )
        )
        or 0
    )

    details = {
        "missing_schedule_asset_links": missing_schedule_asset_links,
        "missing_schedule_source_links": missing_schedule_source_links,
        "missing_impairment_asset_links": missing_impairment_asset_links,
        "missing_disposal_asset_links": missing_disposal_asset_links,
        "invalid_journal_one_of_links": invalid_journal_one_of_links,
    }
    complete = all(value == 0 for value in details.values())
    return LineageValidationResult(is_complete=complete, details=details)
