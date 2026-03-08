from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from financeops.modules.fx_translation_reporting.domain.entities import SelectedRate
from financeops.modules.fx_translation_reporting.domain.invariants import q8
from financeops.modules.fx_translation_reporting.infrastructure.repository import (
    FxTranslationReportingRepository,
)


class RateSelectionService:
    async def resolve_selected_rate(
        self,
        *,
        repository: FxTranslationReportingRepository,
        tenant_id: uuid.UUID,
        source_currency: str,
        reporting_currency: str,
        reporting_period: date,
        rate_type: str,
        locked_rate_required: bool,
        fallback_behavior_json: dict[str, Any],
    ) -> SelectedRate:
        src = source_currency.upper()
        tgt = reporting_currency.upper()
        if src == tgt:
            return SelectedRate(
                multiplier=Decimal("1"),
                rate_type="identity",
                rate_ref=f"identity:{src}/{tgt}",
                source_currency=src,
                reporting_currency=tgt,
            )

        if locked_rate_required:
            locked = await self._select_locked_manual(
                repository=repository,
                tenant_id=tenant_id,
                reporting_period=reporting_period,
                source_currency=src,
                reporting_currency=tgt,
            )
            if locked is not None:
                return locked

            allow_unlocked_manual = bool(
                fallback_behavior_json.get("allow_unlocked_manual", False)
            )
            if allow_unlocked_manual:
                manual = await self._select_manual(
                    repository=repository,
                    tenant_id=tenant_id,
                    reporting_period=reporting_period,
                    source_currency=src,
                    reporting_currency=tgt,
                )
                if manual is not None:
                    return manual
            raise ValueError(
                f"Missing required locked FX rate for {src}/{tgt} at {reporting_period.isoformat()}"
            )

        manual = await self._select_manual(
            repository=repository,
            tenant_id=tenant_id,
            reporting_period=reporting_period,
            source_currency=src,
            reporting_currency=tgt,
        )
        if manual is not None:
            return manual

        selected = await self._select_quote_rate(
            repository=repository,
            tenant_id=tenant_id,
            reporting_period=reporting_period,
            source_currency=src,
            reporting_currency=tgt,
            rate_type=rate_type,
            fallback_behavior_json=fallback_behavior_json,
        )
        if selected is None:
            raise ValueError(
                f"Missing FX rate for {src}/{tgt} at {reporting_period.isoformat()} with rate_type={rate_type}"
            )
        return selected

    async def _select_locked_manual(
        self,
        *,
        repository: FxTranslationReportingRepository,
        tenant_id: uuid.UUID,
        reporting_period: date,
        source_currency: str,
        reporting_currency: str,
    ) -> SelectedRate | None:
        direct = await repository.get_latest_locked_manual_rate(
            tenant_id=tenant_id,
            period_year=reporting_period.year,
            period_month=reporting_period.month,
            base_currency=source_currency,
            quote_currency=reporting_currency,
        )
        if direct is not None:
            return SelectedRate(
                multiplier=q8(direct.rate),
                rate_type="locked_manual",
                rate_ref=f"fx_manual_monthly_rates:{direct.id}",
                source_currency=source_currency,
                reporting_currency=reporting_currency,
            )
        inverse = await repository.get_latest_locked_manual_rate(
            tenant_id=tenant_id,
            period_year=reporting_period.year,
            period_month=reporting_period.month,
            base_currency=reporting_currency,
            quote_currency=source_currency,
        )
        if inverse is None:
            return None
        if inverse.rate == 0:
            raise ValueError("Inverse FX rate cannot be zero")
        return SelectedRate(
            multiplier=q8(Decimal("1") / inverse.rate),
            rate_type="locked_manual_inverse",
            rate_ref=f"fx_manual_monthly_rates:{inverse.id}",
            source_currency=source_currency,
            reporting_currency=reporting_currency,
        )

    async def _select_manual(
        self,
        *,
        repository: FxTranslationReportingRepository,
        tenant_id: uuid.UUID,
        reporting_period: date,
        source_currency: str,
        reporting_currency: str,
    ) -> SelectedRate | None:
        direct = await repository.get_latest_manual_rate(
            tenant_id=tenant_id,
            period_year=reporting_period.year,
            period_month=reporting_period.month,
            base_currency=source_currency,
            quote_currency=reporting_currency,
        )
        if direct is not None:
            return SelectedRate(
                multiplier=q8(direct.rate),
                rate_type="manual_monthly",
                rate_ref=f"fx_manual_monthly_rates:{direct.id}",
                source_currency=source_currency,
                reporting_currency=reporting_currency,
            )
        inverse = await repository.get_latest_manual_rate(
            tenant_id=tenant_id,
            period_year=reporting_period.year,
            period_month=reporting_period.month,
            base_currency=reporting_currency,
            quote_currency=source_currency,
        )
        if inverse is None:
            return None
        if inverse.rate == 0:
            raise ValueError("Inverse FX rate cannot be zero")
        return SelectedRate(
            multiplier=q8(Decimal("1") / inverse.rate),
            rate_type="manual_monthly_inverse",
            rate_ref=f"fx_manual_monthly_rates:{inverse.id}",
            source_currency=source_currency,
            reporting_currency=reporting_currency,
        )

    async def _select_quote_rate(
        self,
        *,
        repository: FxTranslationReportingRepository,
        tenant_id: uuid.UUID,
        reporting_period: date,
        source_currency: str,
        reporting_currency: str,
        rate_type: str,
        fallback_behavior_json: dict[str, Any],
    ) -> SelectedRate | None:
        normalized_type = str(rate_type).strip().lower()
        if normalized_type not in {"closing", "average", "historical"}:
            raise ValueError(f"Unsupported rate_type: {rate_type}")

        if normalized_type in {"closing", "historical"}:
            selected = await self._select_quote_closing_like(
                repository=repository,
                tenant_id=tenant_id,
                reporting_period=reporting_period,
                source_currency=source_currency,
                reporting_currency=reporting_currency,
                label=normalized_type,
            )
            return selected

        average = await self._select_quote_average(
            repository=repository,
            tenant_id=tenant_id,
            reporting_period=reporting_period,
            source_currency=source_currency,
            reporting_currency=reporting_currency,
        )
        if average is not None:
            return average

        allow_closing_fallback = bool(
            fallback_behavior_json.get("allow_closing_when_average_missing", False)
        )
        if not allow_closing_fallback:
            return None
        return await self._select_quote_closing_like(
            repository=repository,
            tenant_id=tenant_id,
            reporting_period=reporting_period,
            source_currency=source_currency,
            reporting_currency=reporting_currency,
            label="average_fallback_closing",
        )

    async def _select_quote_closing_like(
        self,
        *,
        repository: FxTranslationReportingRepository,
        tenant_id: uuid.UUID,
        reporting_period: date,
        source_currency: str,
        reporting_currency: str,
        label: str,
    ) -> SelectedRate | None:
        direct = await repository.get_latest_quote_on_or_before(
            tenant_id=tenant_id,
            base_currency=source_currency,
            quote_currency=reporting_currency,
            as_of_date=reporting_period,
        )
        if direct is not None:
            return SelectedRate(
                multiplier=q8(direct.rate),
                rate_type=label,
                rate_ref=f"fx_rate_quotes:{direct.id}",
                source_currency=source_currency,
                reporting_currency=reporting_currency,
            )
        inverse = await repository.get_latest_quote_on_or_before(
            tenant_id=tenant_id,
            base_currency=reporting_currency,
            quote_currency=source_currency,
            as_of_date=reporting_period,
        )
        if inverse is None:
            return None
        if inverse.rate == 0:
            raise ValueError("Inverse FX quote cannot be zero")
        return SelectedRate(
            multiplier=q8(Decimal("1") / inverse.rate),
            rate_type=f"{label}_inverse",
            rate_ref=f"fx_rate_quotes:{inverse.id}",
            source_currency=source_currency,
            reporting_currency=reporting_currency,
        )

    async def _select_quote_average(
        self,
        *,
        repository: FxTranslationReportingRepository,
        tenant_id: uuid.UUID,
        reporting_period: date,
        source_currency: str,
        reporting_currency: str,
    ) -> SelectedRate | None:
        direct = await repository.get_average_quote_for_month(
            tenant_id=tenant_id,
            period_year=reporting_period.year,
            period_month=reporting_period.month,
            base_currency=source_currency,
            quote_currency=reporting_currency,
        )
        if direct is not None:
            return SelectedRate(
                multiplier=q8(direct),
                rate_type="average",
                rate_ref=(
                    "fx_rate_quotes:average:"
                    f"{reporting_period.year:04d}-{reporting_period.month:02d}:{source_currency}/{reporting_currency}"
                ),
                source_currency=source_currency,
                reporting_currency=reporting_currency,
            )
        inverse = await repository.get_average_quote_for_month(
            tenant_id=tenant_id,
            period_year=reporting_period.year,
            period_month=reporting_period.month,
            base_currency=reporting_currency,
            quote_currency=source_currency,
        )
        if inverse is None:
            return None
        if inverse == 0:
            raise ValueError("Inverse FX average quote cannot be zero")
        return SelectedRate(
            multiplier=q8(Decimal("1") / inverse),
            rate_type="average_inverse",
            rate_ref=(
                "fx_rate_quotes:average:"
                f"{reporting_period.year:04d}-{reporting_period.month:02d}:{reporting_currency}/{source_currency}"
            ),
            source_currency=source_currency,
            reporting_currency=reporting_currency,
        )

