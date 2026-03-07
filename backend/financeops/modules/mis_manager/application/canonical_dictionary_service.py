from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalDictionary:
    version: str
    metrics: tuple[str, ...]
    dimensions: tuple[str, ...]


class CanonicalDictionaryService:
    _DEFAULT = CanonicalDictionary(
        version="mis_canonical_v1",
        metrics=(
            "revenue_gross",
            "revenue_discounts",
            "revenue_net",
            "cogs_material",
            "cogs_service",
            "gross_profit",
            "employee_cost",
            "rent_expense",
            "software_subscription",
            "marketing_expense",
            "general_admin_expense",
            "ebitda",
            "depreciation",
            "finance_cost",
            "pbt",
            "tax_expense",
            "pat",
            "ar",
            "ap",
            "inventory",
            "capex",
            "cash",
            "debt",
        ),
        dimensions=(
            "business_unit",
            "cost_center",
            "department",
            "project",
            "customer",
            "vendor",
            "product_line",
            "geography",
            "legal_entity",
            "channel",
        ),
    )

    def get_dictionary(self) -> CanonicalDictionary:
        return self._DEFAULT
