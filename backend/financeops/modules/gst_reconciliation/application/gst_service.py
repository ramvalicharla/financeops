from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from financeops.db.models.gst import GstRateMaster
from financeops.modules.gst_reconciliation.domain.exceptions import GstRateMasterNotSeededError


async def get_gst_rate_master(db: AsyncSession) -> frozenset[Decimal]:
    rates = await db.scalars(select(GstRateMaster.rate))
    rate_set = frozenset(Decimal(str(value)) for value in rates.all())
    if not rate_set:
        raise GstRateMasterNotSeededError(
            "gst_rate_master table is empty. Run: alembic upgrade head to apply seed migration."
        )
    return rate_set


def validate_gst_rate(rate: Decimal | None, master: frozenset[Decimal]) -> bool:
    if rate is None:
        return False
    return Decimal(str(rate)) in master
