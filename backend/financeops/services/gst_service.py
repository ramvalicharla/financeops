from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.intent.context import apply_mutation_linkage, require_mutation_context
from financeops.db.models.gst import GstReconItem, GstReturn, GstReturnLineItem
from financeops.modules.gst_reconciliation.application.gst_service import (
    get_gst_rate_master as load_gst_rate_master,
)
from financeops.modules.gst_reconciliation.application.gstn_import_service import (
    ParsedGstReturnLineItem,
    parse_gstr1_json,
    parse_gstr2b_json,
)
from financeops.modules.gst_reconciliation.application.invoice_match_service import (
    GstMatchContext,
    build_recon_items,
)
from financeops.platform.db.models.entities import CpEntity
from financeops.platform.db.models.organisations import CpOrganisation
from financeops.utils.chain_hash import GENESIS_HASH
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


async def get_gst_rate_master(session: AsyncSession) -> frozenset[Decimal]:
    return await load_gst_rate_master(session)


async def _resolve_or_create_entity(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID | None,
    entity_name: str | None,
) -> tuple[uuid.UUID, str]:
    resolved_id = entity_id
    resolved_name = entity_name

    if resolved_id is not None:
        row = (
            await session.execute(
                select(CpEntity.entity_name).where(
                    CpEntity.tenant_id == tenant_id,
                    CpEntity.id == resolved_id,
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            return resolved_id, resolved_name or row

    first_entity = (
        await session.execute(
            select(CpEntity.id, CpEntity.entity_name)
            .where(CpEntity.tenant_id == tenant_id)
            .order_by(CpEntity.created_at.asc())
            .limit(1)
        )
    ).first()
    if first_entity is not None:
        return first_entity[0], resolved_name or first_entity[1]

    org = (
        await session.execute(
            select(CpOrganisation)
            .where(CpOrganisation.tenant_id == tenant_id)
            .order_by(CpOrganisation.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if org is None:
        org_code = f"AUTO_ORG_{str(tenant_id).replace('-', '')[:16].upper()}"
        org = CpOrganisation(
            tenant_id=tenant_id,
            organisation_code=org_code,
            organisation_name="Auto Organisation",
            parent_organisation_id=None,
            supersedes_id=None,
            is_active=True,
            correlation_id="gst-auto",
            chain_hash=compute_chain_hash({"organisation_code": org_code}, GENESIS_HASH),
            previous_hash=GENESIS_HASH,
        )
        session.add(org)
        await session.flush()

    entity_code = f"AUTO_ENT_{str(tenant_id).replace('-', '')[:16].upper()}"
    entity = CpEntity(
        tenant_id=tenant_id,
        entity_code=entity_code,
        entity_name=resolved_name or "Auto Entity",
        organisation_id=org.id,
        group_id=None,
        base_currency="INR",
        country_code="IN",
        status="active",
        deactivated_at=None,
        correlation_id="gst-auto",
        chain_hash=compute_chain_hash({"entity_code": entity_code}, GENESIS_HASH),
        previous_hash=GENESIS_HASH,
    )
    session.add(entity)
    await session.flush()
    return entity.id, entity.entity_name


async def create_gst_return(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_id: uuid.UUID | None = None,
    entity_name: str | None = None,
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
    location_id: uuid.UUID | None = None,
    cost_centre_id: uuid.UUID | None = None,
) -> GstReturn:
    """Create a GST return record (INSERT ONLY)."""
    require_mutation_context("GST return preparation")
    resolved_entity_id, resolved_entity_name = await _resolve_or_create_entity(
        session,
        tenant_id=tenant_id,
        entity_id=entity_id,
        entity_name=entity_name,
    )
    total_tax = igst_amount + cgst_amount + sgst_amount + cess_amount

    previous_hash = await get_previous_hash_locked(session, GstReturn, tenant_id)
    record_data = {
        "tenant_id": str(tenant_id),
        "period_year": period_year,
        "period_month": period_month,
        "entity_id": str(resolved_entity_id),
        "entity_name": resolved_entity_name,
        "gstin": gstin,
        "return_type": return_type,
        "total_tax": str(total_tax),
        "created_by": str(created_by),
    }
    chain_hash = compute_chain_hash(record_data, previous_hash)

    gst_return = apply_mutation_linkage(GstReturn(
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_id=resolved_entity_id,
        entity_name=resolved_entity_name,
        location_id=location_id,
        cost_centre_id=cost_centre_id,
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
    ))
    session.add(gst_return)
    await session.flush()
    return gst_return


async def run_gst_reconciliation(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_id: uuid.UUID | None = None,
    entity_name: str | None = None,
    return_type_a: str,
    return_type_b: str,
    run_by: uuid.UUID,
) -> list[GstReconItem]:
    """
    Compare two GST return types for the same period/entity.
    Creates GstReconItem for each field where values differ.
    """
    require_mutation_context("GST reconciliation run")
    return_a = await _latest_return(
        session,
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_id=entity_id,
        entity_name=entity_name,
        return_type=return_type_a,
    )
    return_b = await _latest_return(
        session,
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_id=entity_id,
        entity_name=entity_name,
        return_type=return_type_b,
    )

    if return_a is None or return_b is None:
        log.warning(
            "GST recon: one or both returns not found for period=%d/%d entity_id=%s",
            period_year,
            period_month,
            str(entity_id or entity_name or ""),
        )
        return []

    lines_a = await _list_return_line_items(session, tenant_id=tenant_id, gst_return_id=return_a.id)
    lines_b = await _list_return_line_items(session, tenant_id=tenant_id, gst_return_id=return_b.id)
    if lines_a or lines_b:
        return await _run_line_item_reconciliation(
            session,
            return_a=return_a,
            return_b=return_b,
            lines_a=lines_a,
            lines_b=lines_b,
            run_by=run_by,
        )

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
                "entity_id": str(return_a.entity_id),
                "entity_name": return_a.entity_name,
                "return_type_a": return_type_a,
                "return_type_b": return_type_b,
                "field_name": field_name,
                "difference": str(difference),
            }
            chain_hash = compute_chain_hash(record_data, previous_hash)

            item = apply_mutation_linkage(GstReconItem(
                tenant_id=tenant_id,
                period_year=period_year,
                period_month=period_month,
                entity_id=return_a.entity_id,
                entity_name=return_a.entity_name,
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
            ))
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


async def import_gst_return_json(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    gstin: str,
    return_type: str,
    json_data: dict[str, Any],
    created_by: uuid.UUID,
    entity_id: uuid.UUID | None = None,
    entity_name: str | None = None,
    location_id: uuid.UUID | None = None,
    cost_centre_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> GstReturn:
    require_mutation_context("GST return import")
    parsed_items = _parse_import_payload(return_type=return_type, json_data=json_data)
    totals = _aggregate_totals(parsed_items)
    gst_return = await create_gst_return(
        session,
        tenant_id=tenant_id,
        period_year=period_year,
        period_month=period_month,
        entity_id=entity_id,
        entity_name=entity_name,
        gstin=gstin,
        return_type=return_type,
        taxable_value=totals["taxable_value"],
        igst_amount=totals["igst_amount"],
        cgst_amount=totals["cgst_amount"],
        sgst_amount=totals["sgst_amount"],
        cess_amount=totals["cess_amount"],
        created_by=created_by,
        filing_date=None,
        notes=notes,
        location_id=location_id,
        cost_centre_id=cost_centre_id,
    )
    await _append_return_line_items(
        session,
        tenant_id=tenant_id,
        gst_return=gst_return,
        parsed_items=parsed_items,
    )
    return gst_return


async def submit_gst_return(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    return_id: uuid.UUID,
    filed_by: uuid.UUID,
    filing_date: date | None = None,
) -> GstReturn:
    require_mutation_context("GST return submission")
    row = (
        await session.execute(
            select(GstReturn).where(
                GstReturn.tenant_id == tenant_id,
                GstReturn.id == return_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("GST return not found")
    row.status = "filed"
    row.filed_by = filed_by
    row.filing_date = filing_date or date.today()
    apply_mutation_linkage(row)
    await session.flush()
    return row


async def list_gst_returns(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    period_year: int | None = None,
    period_month: int | None = None,
    entity_id: uuid.UUID | None = None,
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
    if entity_id is not None:
        stmt = stmt.where(GstReturn.entity_id == entity_id)
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
    entity_id: uuid.UUID | None = None,
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
    if entity_id is not None:
        stmt = stmt.where(GstReconItem.entity_id == entity_id)
    if status:
        stmt = stmt.where(GstReconItem.status == status)
    stmt = stmt.order_by(desc(GstReconItem.created_at)).limit(bounded_limit).offset(effective_skip)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _latest_return(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    period_year: int,
    period_month: int,
    entity_id: uuid.UUID | None,
    entity_name: str | None,
    return_type: str,
) -> GstReturn | None:
    criteria = [
        GstReturn.tenant_id == tenant_id,
        GstReturn.period_year == period_year,
        GstReturn.period_month == period_month,
        GstReturn.return_type == return_type,
    ]
    if entity_id is not None:
        criteria.append(GstReturn.entity_id == entity_id)
    elif entity_name:
        criteria.append(GstReturn.entity_name == entity_name)
    result = await session.execute(
        select(GstReturn).where(*criteria).order_by(desc(GstReturn.created_at)).limit(1)
    )
    return result.scalar_one_or_none()


async def _list_return_line_items(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    gst_return_id: uuid.UUID,
) -> list[GstReturnLineItem]:
    result = await session.execute(
        select(GstReturnLineItem)
        .where(
            GstReturnLineItem.tenant_id == tenant_id,
            GstReturnLineItem.gst_return_id == gst_return_id,
        )
        .order_by(GstReturnLineItem.created_at.asc())
    )
    return list(result.scalars().all())


async def _run_line_item_reconciliation(
    session: AsyncSession,
    *,
    return_a: GstReturn,
    return_b: GstReturn,
    lines_a: list[GstReturnLineItem],
    lines_b: list[GstReturnLineItem],
    run_by: uuid.UUID,
) -> list[GstReconItem]:
    rate_master = await get_gst_rate_master(session)
    pending_items = build_recon_items(
        return_a=return_a,
        return_b=return_b,
        lines_a=lines_a,
        lines_b=lines_b,
        run_by=run_by,
        context=GstMatchContext(rate_master=rate_master, today=date.today()),
    )
    if not pending_items:
        return []

    previous_hash = await get_previous_hash_locked(session, GstReconItem, return_a.tenant_id)
    items: list[GstReconItem] = []
    for pending in pending_items:
        record_data = {
            "tenant_id": str(return_a.tenant_id),
            "period_year": return_a.period_year,
            "period_month": return_a.period_month,
            "entity_id": str(return_a.entity_id),
            "supplier_gstin": pending.supplier_gstin,
            "invoice_number": pending.invoice_number,
            "match_type": pending.match_type,
            "difference": str(pending.difference),
        }
        chain_hash = compute_chain_hash(record_data, previous_hash)
        pending.chain_hash = chain_hash
        pending.previous_hash = previous_hash
        apply_mutation_linkage(pending)
        session.add(pending)
        items.append(pending)
        previous_hash = chain_hash

    await session.flush()
    return items


def _parse_import_payload(
    *,
    return_type: str,
    json_data: dict[str, Any],
) -> list[ParsedGstReturnLineItem]:
    normalized_type = str(return_type).strip().upper()
    if normalized_type == "GSTR1":
        return parse_gstr1_json(json_data)
    if normalized_type == "GSTR2B":
        return parse_gstr2b_json(json_data)
    return parse_gstr1_json(json_data)


def _aggregate_totals(parsed_items: list[ParsedGstReturnLineItem]) -> dict[str, Decimal]:
    totals = {
        "taxable_value": Decimal("0"),
        "igst_amount": Decimal("0"),
        "cgst_amount": Decimal("0"),
        "sgst_amount": Decimal("0"),
        "cess_amount": Decimal("0"),
    }
    for row in parsed_items:
        totals["taxable_value"] += row.taxable_value
        totals["igst_amount"] += row.igst_amount
        totals["cgst_amount"] += row.cgst_amount
        totals["sgst_amount"] += row.sgst_amount
        totals["cess_amount"] += row.cess_amount
    return totals


async def _append_return_line_items(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    gst_return: GstReturn,
    parsed_items: list[ParsedGstReturnLineItem],
) -> list[GstReturnLineItem]:
    if not parsed_items:
        return []
    previous_hash = await get_previous_hash_locked(session, GstReturnLineItem, tenant_id)
    rows: list[GstReturnLineItem] = []
    for parsed in parsed_items:
        record_data = {
            "tenant_id": str(tenant_id),
            "gst_return_id": str(gst_return.id),
            "supplier_gstin": parsed.supplier_gstin,
            "invoice_number": parsed.invoice_number,
            "taxable_value": str(parsed.taxable_value),
        }
        chain_hash = compute_chain_hash(record_data, previous_hash)
        row = apply_mutation_linkage(GstReturnLineItem(
            tenant_id=tenant_id,
            chain_hash=chain_hash,
            previous_hash=previous_hash,
            gst_return_id=gst_return.id,
            return_type=gst_return.return_type,
            supplier_gstin=parsed.supplier_gstin,
            invoice_number=parsed.invoice_number,
            invoice_date=parsed.invoice_date,
            taxable_value=parsed.taxable_value,
            igst_amount=parsed.igst_amount,
            cgst_amount=parsed.cgst_amount,
            sgst_amount=parsed.sgst_amount,
            cess_amount=parsed.cess_amount,
            total_tax=parsed.total_tax,
            gst_rate=parsed.gst_rate,
            payment_status=parsed.payment_status,
            expense_category=parsed.expense_category,
        ))
        session.add(row)
        rows.append(row)
        previous_hash = chain_hash
    await session.flush()
    return rows

