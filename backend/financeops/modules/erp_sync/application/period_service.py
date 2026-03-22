from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from financeops.modules.erp_sync.domain.enums import PeriodGranularity
from financeops.shared_kernel.tokens import build_token


AS_AT_DATASETS: frozenset[str] = frozenset(
    {
        "trial_balance",
        "balance_sheet",
        "fixed_asset_register",
        "prepaid_register",
        "ar_ageing",
        "ap_ageing",
        "inventory_register",
        "staff_advances",
        "vendor_advances",
        "customer_advances",
        "opening_balances",
    }
)

NO_PERIOD_DATASETS: frozenset[str] = frozenset(
    {
        "chart_of_accounts",
        "vendor_master",
        "customer_master",
        "dimension_master",
        "currency_master",
    }
)


@dataclass(frozen=True)
class PeriodResolutionResult:
    granularity: PeriodGranularity
    period_start: date | None
    period_end: date | None
    as_at_date: date | None
    period_label: str
    period_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "granularity": self.granularity.value,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "as_at_date": self.as_at_date.isoformat() if self.as_at_date else None,
            "period_label": self.period_label,
            "period_hash": self.period_hash,
        }


class PeriodService:
    def resolve_period(
        self,
        *,
        dataset_type: str,
        granularity: PeriodGranularity,
        period_start: date | None = None,
        period_end: date | None = None,
        as_at_date: date | None = None,
        fiscal_year_start_month: int = 4,
    ) -> PeriodResolutionResult:
        normalized = dataset_type.strip().lower()

        if granularity == PeriodGranularity.NO_PERIOD or normalized in NO_PERIOD_DATASETS:
            payload = {
                "dataset_type": normalized,
                "granularity": PeriodGranularity.NO_PERIOD.value,
                "period_start": None,
                "period_end": None,
                "as_at_date": None,
            }
            return PeriodResolutionResult(
                granularity=PeriodGranularity.NO_PERIOD,
                period_start=None,
                period_end=None,
                as_at_date=None,
                period_label="NO_PERIOD",
                period_hash=build_token(payload),
            )

        if granularity == PeriodGranularity.AS_AT or normalized in AS_AT_DATASETS:
            resolved_as_at = as_at_date or period_end or period_start
            if resolved_as_at is None:
                raise ValueError("AS_AT period requires as_at_date, period_start, or period_end")
            payload = {
                "dataset_type": normalized,
                "granularity": PeriodGranularity.AS_AT.value,
                "period_start": None,
                "period_end": None,
                "as_at_date": resolved_as_at.isoformat(),
            }
            return PeriodResolutionResult(
                granularity=PeriodGranularity.AS_AT,
                period_start=None,
                period_end=None,
                as_at_date=resolved_as_at,
                period_label=f"AS_AT:{resolved_as_at.isoformat()}",
                period_hash=build_token(payload),
            )

        effective_date = period_start or period_end or as_at_date
        if effective_date is None:
            raise ValueError("period_start or period_end is required for ranged granularities")

        if granularity == PeriodGranularity.MONTHLY:
            start, end = self._month_range(effective_date)
            label = start.strftime("%Y-%m")
        elif granularity == PeriodGranularity.QUARTERLY:
            start, end, quarter_label = self._quarter_range(
                effective_date, fiscal_year_start_month=fiscal_year_start_month
            )
            label = quarter_label
        elif granularity == PeriodGranularity.YEARLY:
            start, end, year_label = self._year_range(
                effective_date, fiscal_year_start_month=fiscal_year_start_month
            )
            label = year_label
        else:
            if period_start is None or period_end is None:
                raise ValueError("CUSTOM period requires explicit period_start and period_end")
            start, end = period_start, period_end
            label = f"{start.isoformat()}_{end.isoformat()}"

        if start > end:
            raise ValueError("Resolved period_start cannot be after period_end")

        payload = {
            "dataset_type": normalized,
            "granularity": granularity.value,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "as_at_date": None,
            "fiscal_year_start_month": fiscal_year_start_month,
        }
        return PeriodResolutionResult(
            granularity=granularity,
            period_start=start,
            period_end=end,
            as_at_date=None,
            period_label=label,
            period_hash=build_token(payload),
        )

    @staticmethod
    def _month_range(target: date) -> tuple[date, date]:
        month_start = target.replace(day=1)
        if target.month == 12:
            next_month_start = date(target.year + 1, 1, 1)
        else:
            next_month_start = date(target.year, target.month + 1, 1)
        month_end = next_month_start.fromordinal(next_month_start.toordinal() - 1)
        return month_start, month_end

    @staticmethod
    def _quarter_range(
        target: date,
        *,
        fiscal_year_start_month: int,
    ) -> tuple[date, date, str]:
        shifted = (target.month - fiscal_year_start_month) % 12
        quarter_index = shifted // 3
        quarter_start_month = ((quarter_index * 3 + fiscal_year_start_month - 1) % 12) + 1
        start_year = target.year
        if quarter_start_month > target.month:
            start_year -= 1
        start = date(start_year, quarter_start_month, 1)
        end_month = ((quarter_start_month + 1) % 12) + 1
        end_month = ((quarter_start_month + 2 - 1) % 12) + 1
        end_year = start_year + 1 if end_month < quarter_start_month else start_year
        if end_month == 12:
            end = date(end_year, 12, 31)
        else:
            next_month_start = date(end_year, end_month + 1, 1)
            end = next_month_start.fromordinal(next_month_start.toordinal() - 1)
        fiscal_year = start_year if fiscal_year_start_month == 1 else start_year + 1
        return start, end, f"FY{fiscal_year}-Q{quarter_index + 1}"

    @staticmethod
    def _year_range(
        target: date,
        *,
        fiscal_year_start_month: int,
    ) -> tuple[date, date, str]:
        if fiscal_year_start_month == 1:
            start = date(target.year, 1, 1)
            end = date(target.year, 12, 31)
            return start, end, f"FY{target.year}"
        if target.month >= fiscal_year_start_month:
            start_year = target.year
        else:
            start_year = target.year - 1
        start = date(start_year, fiscal_year_start_month, 1)
        end_year = start_year + 1
        end_month = fiscal_year_start_month - 1
        if end_month == 12:
            end = date(end_year, 12, 31)
        else:
            next_month_start = date(end_year, end_month + 1, 1)
            end = next_month_start.fromordinal(next_month_start.toordinal() - 1)
        return start, end, f"FY{end_year}"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        granularity = kwargs.get("granularity", PeriodGranularity.MONTHLY)
        if isinstance(granularity, str):
            granularity = PeriodGranularity(granularity)
        result = self.resolve_period(
            dataset_type=str(kwargs.get("dataset_type", "")).strip(),
            granularity=granularity,
            period_start=kwargs.get("period_start"),
            period_end=kwargs.get("period_end"),
            as_at_date=kwargs.get("as_at_date"),
            fiscal_year_start_month=int(kwargs.get("fiscal_year_start_month", 4)),
        )
        return result.to_dict()
