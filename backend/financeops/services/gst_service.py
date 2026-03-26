from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.gst import GstReturn, GstReconItem
from financeops.utils.chain_hash import compute_chain_hash, get_previous_hash_locked

log = logging.getLogger(__name__)

VALID_RETURN_TYPES = {"GSTR1", "GSTR3B", "GSTR2A", "GSTR2B"}
RECONCILABLE_FIELDS = [
    "taxable_value",
    "igst_amount",
    "cgst_amount",
    "sgst_amount",
    "cess_amount",
    "total_tax",
]


async def create_gst_return(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_name: str,
    gstin: str,
    return_type: str,
    taxable_value: Decimal,
    igst_amount: Decimal,
    cgst_amount: Decimal,
    sgst_amount: Decimal,
    cess_amount: Decimal,
    created_by: uuid.UUID,
    filing_date: date | None = None,
    notes: str | None = None,
) -> GstReturn:
    """Create a GST return record (INSERT ONLY)."""
    total_tax = igst_amount + cgst_amount + sgst_amount + cess_amount

    previous_hash = await get_previous_hash_locked(session, GstReturn, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "period_year": period_year,
        "period_month": period_month,
        "entity_name": entity_name,
        "gstin": gstin,
        "return_type": return_type,
        "total_tax": str(total_tax),
        "created_by": str(created_by),
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    gst_return = GstReturn(
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_name=entity_name,
        gstin=gstin,
        return_type=return_type,
        taxable_value=taxable_value,
        igst_amount=igst_amount,
        cgst_amount=cgst_amount,
        sgst_amount=sgst_amount,
        cess_amount=cess_amount,
        total_tax=total_tax,
        filing_date=filing_date,
        status="draft",
        created_by=created_by,
        notes=notes,
        chain_hash=chain_hash,
        previous_hash=previous_hash,
    )
    session.add(gst_return)
    await session.flush()
    return gst_return


async def run_gst_reconciliation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_name: str,
    return_type_a: str,
    return_type_b: str,
    run_by: uuid.UUID,
) -> list[GstReconItem]:
    """
    Compare two GST return types for the same period/entity.
    Creates GstReconItem for each field where values differ.
    """
    # Fetch the two returns
    result_a = await session.execute(
        select(GstReturn).where(
            GstReturn.tenant_id == tenant_id,
            GstReturn.period_year == period_year,
            GstReturn.period_month == period_month,
            GstReturn.entity_name == entity_name,
            GstReturn.return_type == return_type_a,
        ).order_by(desc(GstReturn.created_at)).limit(1)
    )
    return_a = result_a.scalar_one_or_none()

    result_b = await session.execute(
        select(GstReturn).where(
            GstReturn.tenant_id == tenant_id,
            GstReturn.period_year == period_year,
            GstReturn.period_month == period_month,
            GstReturn.entity_name == entity_name,
            GstReturn.return_type == return_type_b,
        ).order_by(desc(GstReturn.created_at)).limit(1)
    )
    return_b = result_b.scalar_one_or_none()

    if return_a is None or return_b is None:
        log.warning(
            "GST recon: one or both returns not found for period=%d/%d entity=%s",
            period_year, period_month, entity_name,
        )
        return []

    items: list[GstReconItem] = []
    for field_name in RECONCILABLE_FIELDS:
        val_a: Decimal = getattr(return_a, field_name)
        val_b: Decimal = getattr(return_b, field_name)
        difference = val_b - val_a

        if difference != Decimal("0"):
            previous_hash = await get_previous_hash_locked(session, GstReconItem, tenant_id)
            record_data = {
                "tenant_id": str(tenant_id),
                "period_year": period_year,
                "period_month": period_month,
                "entity_name": entity_name,
                "return_type_a": return_type_a,
                "return_type_b": return_type_b,
                "field_name": field_name,
                "difference": str(difference),
            }
            chain_hash = compute_chain_hash(record_data, previous_hash)

            item = GstReconItem(
                tenant_id=tenant_id,
                period_year=period_year,
                period_month=period_month,
                entity_name=entity_name,
                return_type_a=return_type_a,
                return_type_b=return_type_b,
                return_a_id=return_a.id,
                return_b_id=return_b.id,
                field_name=field_name,
                value_a=val_a,
                value_b=val_b,
                difference=difference,
                status="open",
                run_by=run_by,
                chain_hash=chain_hash,
                previous_hash=previous_hash,
            )
            session.add(item)
            items.append(item)

    if items:
        await session.flush()

    log.info(
        "GST recon: tenant=%s %s vs %s period=%d/%d breaks=%d",
        str(tenant_id)[:8], return_type_a, return_type_b,
        period_year, period_month, len(items),
    )
    return items


async def list_gst_returns(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period_year: int | None = None,
    period_month: int | None = None,
    entity_name: str | None = None,
    return_type: str | None = None,
    skip: int = 0,
    limit: int = 100,
    offset: int | None = None,
) -> list[GstReturn]:
    effective_skip = offset if offset is not None else skip
    bounded_limit = max(1, min(limit, 1000))
    stmt = select(GstReturn).where(GstReturn.tenant_id == tenant_id)
    if period_year is not None:
        stmt = stmt.where(GstReturn.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(GstReturn.period_month == period_month)
    if entity_name:
        stmt = stmt.where(GstReturn.entity_name == entity_name)
    if return_type:
        stmt = stmt.where(GstReturn.return_type == return_type)
    stmt = stmt.order_by(desc(GstReturn.created_at)).limit(bounded_limit).offset(effective_skip)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_gst_recon_items(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period_year: int | None = None,
    period_month: int | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 100,
    offset: int | None = None,
) -> list[GstReconItem]:
    effective_skip = offset if offset is not None else skip
    bounded_limit = max(1, min(limit, 1000))
    stmt = select(GstReconItem).where(GstReconItem.tenant_id == tenant_id)
    if period_year is not None:
        stmt = stmt.where(GstReconItem.period_year == period_year)
    if period_month is not None:
        stmt = stmt.where(GstReconItem.period_month == period_month)
    if status:
        stmt = stmt.where(GstReconItem.status == status)
    stmt = stmt.order_by(desc(GstReconItem.created_at)).limit(bounded_limit).offset(effective_skip)
    result = await session.execute(stmt)
    return list(result.scalars().all())

