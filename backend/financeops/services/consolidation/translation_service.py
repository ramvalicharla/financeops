from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import NotFoundError, ValidationError
from financeops.db.models.fx_ias21 import (
    ConsolidationTranslationEntityResult,
    ConsolidationTranslationRun,
)
from financeops.modules.accounting_layer.application.financial_statements_service import (
    get_balance_sheet,
    get_profit_and_loss,
)
from financeops.modules.org_setup.models import OrgEntity, OrgGroup
from financeops.services.audit_writer import AuditWriter
from financeops.services.fx.ias21_math import (
    compute_translated_equity_and_cta,
    quantize_4,
)
from financeops.services.fx.rate_master_service import get_required_latest_fx_rate

_ZERO = Decimal("0")


async def _load_group_entities(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_group_id: uuid.UUID,
) -> tuple[OrgGroup, list[OrgEntity]]:
    group_result = await db.execute(
        select(OrgGroup).where(
            OrgGroup.id == org_group_id,
            OrgGroup.tenant_id == tenant_id,
        )
    )
    group = group_result.scalar_one_or_none()
    if group is None:
        raise NotFoundError("Organisation group not found.")

    entities_result = await db.execute(
        select(OrgEntity).where(
            OrgEntity.tenant_id == tenant_id,
            OrgEntity.org_group_id == org_group_id,
            OrgEntity.is_active.is_(True),
            OrgEntity.cp_entity_id.is_not(None),
        )
    )
    entities = list(entities_result.scalars().all())
    if not entities:
        raise ValidationError("No active entities with cp_entity_id mapping found under this group.")
    return group, entities


def _quantize(value: Decimal) -> Decimal:
    return quantize_4(value)


async def translate_group_financials(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_group_id: uuid.UUID,
    presentation_currency: str,
    as_of_date: date,
    initiated_by: uuid.UUID | None = None,
) -> dict[str, object]:
    target_currency = presentation_currency.upper().strip()
    group, entities = await _load_group_entities(
        db,
        tenant_id=tenant_id,
        org_group_id=org_group_id,
    )

    entity_rows: list[dict[str, object]] = []
    total_assets = _ZERO
    total_liabilities = _ZERO
    total_equity = _ZERO
    total_net_profit = _ZERO
    total_cta = _ZERO

    for entity in entities:
        if entity.cp_entity_id is None:
            continue
        functional_currency = entity.functional_currency.upper().strip()
        if functional_currency == target_currency:
            closing_rate = Decimal("1")
            average_rate = Decimal("1")
        else:
            closing = await get_required_latest_fx_rate(
                db,
                tenant_id=tenant_id,
                from_currency=functional_currency,
                to_currency=target_currency,
                rate_type="CLOSING",
                as_of_date=as_of_date,
            )
            average = await get_required_latest_fx_rate(
                db,
                tenant_id=tenant_id,
                from_currency=functional_currency,
                to_currency=target_currency,
                rate_type="AVERAGE",
                as_of_date=as_of_date,
            )
            closing_rate = Decimal(str(closing.rate))
            average_rate = Decimal(str(average.rate))

        balance_sheet = await get_balance_sheet(
            db,
            tenant_id=tenant_id,
            org_entity_id=uuid.UUID(str(entity.cp_entity_id)),
            as_of_date=as_of_date,
        )
        pnl = await get_profit_and_loss(
            db,
            tenant_id=tenant_id,
            org_entity_id=uuid.UUID(str(entity.cp_entity_id)),
            from_date=date(as_of_date.year, 1, 1),
            to_date=as_of_date,
        )

        translated_assets = _quantize(balance_sheet.totals.assets * closing_rate)
        translated_liabilities = _quantize(balance_sheet.totals.liabilities * closing_rate)
        retained_earnings = _quantize(balance_sheet.retained_earnings)
        translated_equity, cta_amount = compute_translated_equity_and_cta(
            assets=balance_sheet.totals.assets,
            liabilities=balance_sheet.totals.liabilities,
            equity_total=balance_sheet.totals.equity,
            retained_earnings=retained_earnings,
            closing_rate=closing_rate,
            average_rate=average_rate,
        )
        translated_net_profit = _quantize(pnl.net_profit * average_rate)

        total_assets += translated_assets
        total_liabilities += translated_liabilities
        total_equity += translated_equity
        total_net_profit += translated_net_profit
        total_cta += cta_amount

        entity_rows.append(
            {
                "org_entity_id": str(entity.id),
                "entity_name": entity.legal_name,
                "functional_currency": functional_currency,
                "presentation_currency": target_currency,
                "closing_rate": _quantize(closing_rate),
                "average_rate": _quantize(average_rate),
                "translated_assets": translated_assets,
                "translated_liabilities": translated_liabilities,
                "translated_equity": translated_equity,
                "translated_net_profit": translated_net_profit,
                "cta_amount": cta_amount,
            }
        )

    run_id: str | None = None
    if initiated_by is not None:
        run = await AuditWriter.insert_financial_record(
            db,
            model_class=ConsolidationTranslationRun,
            tenant_id=tenant_id,
            record_data={
                "org_group_id": str(org_group_id),
                "presentation_currency": target_currency,
                "as_of_date": as_of_date.isoformat(),
                "status": "COMPLETED",
            },
            values={
                "id": uuid.uuid4(),
                "org_group_id": org_group_id,
                "presentation_currency": target_currency,
                "as_of_date": as_of_date,
                "status": "COMPLETED",
                "initiated_by": initiated_by,
            },
        )
        run_id = str(run.id)

        for row in entity_rows:
            await AuditWriter.insert_financial_record(
                db,
                model_class=ConsolidationTranslationEntityResult,
                tenant_id=tenant_id,
                record_data={
                    "run_id": run_id,
                    "org_entity_id": row["org_entity_id"],
                    "cta_amount": str(row["cta_amount"]),
                },
                values={
                    "id": uuid.uuid4(),
                    "run_id": run.id,
                    "org_entity_id": uuid.UUID(str(row["org_entity_id"])),
                    "functional_currency": row["functional_currency"],
                    "presentation_currency": row["presentation_currency"],
                    "closing_rate": row["closing_rate"],
                    "average_rate": row["average_rate"],
                    "translated_assets": row["translated_assets"],
                    "translated_liabilities": row["translated_liabilities"],
                    "translated_equity": row["translated_equity"],
                    "translated_net_profit": row["translated_net_profit"],
                    "cta_amount": row["cta_amount"],
                },
            )

    await db.flush()
    return {
        "run_id": run_id,
        "org_group_id": str(org_group_id),
        "group_name": group.group_name,
        "presentation_currency": target_currency,
        "as_of_date": as_of_date.isoformat(),
        "cta_account_code": "CTA_FCTR",
        "entity_results": [
            {
                **row,
                "closing_rate": str(row["closing_rate"]),
                "average_rate": str(row["average_rate"]),
                "translated_assets": str(row["translated_assets"]),
                "translated_liabilities": str(row["translated_liabilities"]),
                "translated_equity": str(row["translated_equity"]),
                "translated_net_profit": str(row["translated_net_profit"]),
                "cta_amount": str(row["cta_amount"]),
            }
            for row in entity_rows
        ],
        "totals": {
            "translated_assets": str(_quantize(total_assets)),
            "translated_liabilities": str(_quantize(total_liabilities)),
            "translated_equity": str(_quantize(total_equity)),
            "translated_net_profit": str(_quantize(total_net_profit)),
            "total_cta": str(_quantize(total_cta)),
        },
    }
