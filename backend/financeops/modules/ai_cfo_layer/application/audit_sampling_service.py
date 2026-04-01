from __future__ import annotations

import random
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.modules.ai_cfo_layer.schemas import (
    AuditSampleRow,
    AuditSamplesResponse,
)
from financeops.db.models.accounting_jv import AccountingJVAggregate, JVStatus
from financeops.modules.analytics_layer.application.common import resolve_scope


def _risk_score(row: AccountingJVAggregate) -> tuple[Decimal, str]:
    score = Decimal("0")
    reasons: list[str] = []
    amount = max(Decimal(str(row.total_debit)), Decimal(str(row.total_credit)))
    if amount >= Decimal("10000000"):
        score += Decimal("60")
        reasons.append("very_high_amount")
    elif amount >= Decimal("1000000"):
        score += Decimal("35")
        reasons.append("high_amount")
    elif amount >= Decimal("250000"):
        score += Decimal("20")
        reasons.append("material_amount")

    if row.status == JVStatus.PUSH_FAILED:
        score += Decimal("25")
        reasons.append("push_failed")
    if row.source.upper() == "MANUAL":
        score += Decimal("10")
        reasons.append("manual_source")
    if row.resubmission_count > 0:
        score += Decimal("10")
        reasons.append("resubmitted")
    if not row.reference:
        score += Decimal("5")
        reasons.append("missing_reference")

    if not reasons:
        reasons = ["random_population"]
    return score, ",".join(reasons)


async def get_audit_samples(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_entity_id: uuid.UUID | None,
    org_group_id: uuid.UUID | None,
    from_date: date,
    to_date: date,
    mode: str = "risk_based",
    sample_size: int = 25,
) -> AuditSamplesResponse:
    if mode not in {"random", "risk_based"}:
        mode = "risk_based"
    sample_size = max(1, min(sample_size, 250))

    scope = await resolve_scope(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        as_of_date=to_date,
        from_date=from_date,
        to_date=to_date,
    )

    population = (
        await db.execute(
            select(AccountingJVAggregate).where(
                and_(
                    AccountingJVAggregate.tenant_id == tenant_id,
                    AccountingJVAggregate.entity_id.in_(scope.entity_ids),
                    AccountingJVAggregate.period_date >= from_date,
                    AccountingJVAggregate.period_date <= to_date,
                    AccountingJVAggregate.status.in_(
                        [
                            JVStatus.APPROVED,
                            JVStatus.PUSHED,
                            JVStatus.PUSH_FAILED,
                        ]
                    ),
                )
            )
        )
    ).scalars().all()

    selected: list[AccountingJVAggregate]
    if mode == "random":
        rng = random.Random(f"{tenant_id}:{from_date}:{to_date}:{sample_size}")
        if len(population) <= sample_size:
            selected = population
        else:
            selected = rng.sample(population, sample_size)
    else:
        scored = sorted(
            population,
            key=lambda item: (_risk_score(item)[0], item.jv_number),
            reverse=True,
        )
        selected = scored[:sample_size]

    rows: list[AuditSampleRow] = []
    for item in selected:
        score, reason = _risk_score(item)
        rows.append(
            AuditSampleRow(
                journal_id=item.id,
                journal_number=item.jv_number,
                journal_date=item.period_date,
                total_debit=item.total_debit,
                total_credit=item.total_credit,
                status=item.status,
                source=item.source,
                external_reference_id=item.external_reference_id,
                risk_score=score,
                selection_reason=reason if mode == "risk_based" else "random_selection",
            )
        )

    return AuditSamplesResponse(
        mode=mode,  # type: ignore[arg-type]
        sample_size=sample_size,
        rows=rows,
        fact_basis={
            "population_size": len(population),
            "selected_size": len(rows),
            "from_date": str(from_date),
            "to_date": str(to_date),
        },
    )
