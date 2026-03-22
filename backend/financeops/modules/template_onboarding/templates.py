from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OnboardingTemplate:
    id: str
    name: str
    industry: str
    description: str
    board_pack_sections: list[dict[str, Any]]
    report_definitions: list[dict[str, Any]]
    delivery_schedule: dict[str, Any]


TEMPLATE_REGISTRY: dict[str, OnboardingTemplate] = {
    "saas": OnboardingTemplate(
        id="saas",
        name="SaaS / Subscription",
        industry="saas",
        description="Template for subscription-led SaaS businesses.",
        board_pack_sections=[
            {"section_type": "PROFIT_AND_LOSS", "title": "P&L"},
            {"section_type": "CASH_FLOW", "title": "Cash Flow"},
            {"section_type": "KPI_SUMMARY", "title": "KPI (MRR/ARR/Churn)"},
            {"section_type": "RATIO_ANALYSIS", "title": "Ratios"},
        ],
        report_definitions=[
            {"name": "MRR trend", "metric_keys": ["mis.kpi.revenue"]},
            {"name": "Churn analysis", "metric_keys": ["variance.revenue_variance_pct"]},
            {"name": "CAC/LTV", "metric_keys": ["mis.kpi.ebitda", "mis.kpi.gross_profit"]},
        ],
        delivery_schedule={
            "cron_expression": "0 8 1 * *",
            "channel_type": "EMAIL",
            "recipients": [{"type": "EMAIL", "address": "finance@example.com"}],
            "export_format": "PDF",
        },
    ),
    "manufacturing": OnboardingTemplate(
        id="manufacturing",
        name="Manufacturing",
        industry="manufacturing",
        description="Template tuned for manufacturing and inventory-heavy operations.",
        board_pack_sections=[
            {"section_type": "PROFIT_AND_LOSS", "title": "P&L"},
            {"section_type": "BALANCE_SHEET", "title": "Balance Sheet"},
            {"section_type": "CASH_FLOW", "title": "Cash Flow"},
            {"section_type": "RATIO_ANALYSIS", "title": "Ratios"},
        ],
        report_definitions=[
            {"name": "COGS breakdown", "metric_keys": ["mis.kpi.operating_expenses"]},
            {"name": "Inventory turns", "metric_keys": ["mis.kpi.total_assets"]},
            {"name": "Gross margin", "metric_keys": ["mis.kpi.gross_profit"]},
        ],
        delivery_schedule={
            "cron_expression": "0 8 1 * *",
            "channel_type": "EMAIL",
            "recipients": [{"type": "EMAIL", "address": "finance@example.com"}],
            "export_format": "PDF",
        },
    ),
    "retail": OnboardingTemplate(
        id="retail",
        name="Retail",
        industry="retail",
        description="Template optimised for retail with category and margin focus.",
        board_pack_sections=[
            {"section_type": "PROFIT_AND_LOSS", "title": "P&L"},
            {"section_type": "CASH_FLOW", "title": "Cash Flow"},
            {"section_type": "KPI_SUMMARY", "title": "KPI"},
            {"section_type": "FX_SUMMARY", "title": "FX"},
        ],
        report_definitions=[
            {"name": "Revenue by category", "metric_keys": ["mis.kpi.revenue"]},
            {"name": "Margin analysis", "metric_keys": ["variance.gross_margin_variance_bps"]},
        ],
        delivery_schedule={
            "cron_expression": "0 8 * * 1",
            "channel_type": "EMAIL",
            "recipients": [{"type": "EMAIL", "address": "finance@example.com"}],
            "export_format": "PDF",
        },
    ),
    "professional_services": OnboardingTemplate(
        id="professional_services",
        name="Professional Services",
        industry="professional_services",
        description="Template for consulting and services-led organizations.",
        board_pack_sections=[
            {"section_type": "PROFIT_AND_LOSS", "title": "P&L"},
            {"section_type": "CASH_FLOW", "title": "Cash Flow"},
            {"section_type": "KPI_SUMMARY", "title": "KPI"},
            {"section_type": "NARRATIVE", "title": "Narrative"},
        ],
        report_definitions=[
            {"name": "Utilisation", "metric_keys": ["payroll.headcount"]},
            {"name": "Revenue per head", "metric_keys": ["mis.kpi.revenue", "payroll.headcount"]},
            {"name": "Pipeline", "metric_keys": ["mis.kpi.net_profit"]},
        ],
        delivery_schedule={
            "cron_expression": "0 8 1 * *",
            "channel_type": "EMAIL",
            "recipients": [{"type": "EMAIL", "address": "finance@example.com"}],
            "export_format": "PDF",
        },
    ),
    "healthcare": OnboardingTemplate(
        id="healthcare",
        name="Healthcare",
        industry="healthcare",
        description="Template for healthcare providers and operator groups.",
        board_pack_sections=[
            {"section_type": "PROFIT_AND_LOSS", "title": "P&L"},
            {"section_type": "BALANCE_SHEET", "title": "Balance Sheet"},
            {"section_type": "CASH_FLOW", "title": "Cash Flow"},
            {"section_type": "RATIO_ANALYSIS", "title": "Ratios"},
        ],
        report_definitions=[
            {"name": "Revenue cycle", "metric_keys": ["mis.kpi.revenue", "variance.revenue_variance_pct"]},
            {"name": "Cost per patient", "metric_keys": ["mis.kpi.operating_expenses"]},
        ],
        delivery_schedule={
            "cron_expression": "0 8 1 * *",
            "channel_type": "EMAIL",
            "recipients": [{"type": "EMAIL", "address": "finance@example.com"}],
            "export_format": "PDF",
        },
    ),
    "general": OnboardingTemplate(
        id="general",
        name="General / Other",
        industry="general",
        description="Baseline finance setup for general use cases.",
        board_pack_sections=[
            {"section_type": "PROFIT_AND_LOSS", "title": "P&L"},
            {"section_type": "BALANCE_SHEET", "title": "Balance Sheet"},
            {"section_type": "CASH_FLOW", "title": "Cash Flow"},
            {"section_type": "RATIO_ANALYSIS", "title": "Ratios"},
        ],
        report_definitions=[
            {"name": "MIS summary", "metric_keys": ["mis.kpi.revenue", "mis.kpi.ebitda", "mis.kpi.net_profit"]},
            {"name": "Variance analysis", "metric_keys": ["variance.revenue_variance_pct", "variance.ebitda_variance_pct"]},
        ],
        delivery_schedule={
            "cron_expression": "0 8 1 * *",
            "channel_type": "EMAIL",
            "recipients": [{"type": "EMAIL", "address": "finance@example.com"}],
            "export_format": "PDF",
        },
    ),
    "it_services": OnboardingTemplate(
        id="it_services",
        name="IT Services",
        industry="it_services",
        description="For IT service companies including managed services, system integrators, software resellers, and support providers.",
        board_pack_sections=[
            {"section_type": "PROFIT_AND_LOSS", "title": "P&L"},
            {"section_type": "CASH_FLOW", "title": "Cash Flow"},
            {"section_type": "KPI_SUMMARY", "title": "KPI"},
            {"section_type": "RATIO_ANALYSIS", "title": "Ratios"},
            {"section_type": "NARRATIVE", "title": "Narrative"},
        ],
        report_definitions=[
            {"name": "Project margin analysis", "metric_keys": ["mis.kpi.gross_profit", "mis.kpi.revenue"]},
            {"name": "Support contract revenue", "metric_keys": ["mis.kpi.revenue"]},
            {"name": "Billable vs non-billable headcount", "metric_keys": ["payroll.headcount"]},
            {"name": "Hardware/software resale margin", "metric_keys": ["variance.gross_margin_variance_bps"]},
            {"name": "Maintenance revenue trend", "metric_keys": ["variance.revenue_variance_pct"]},
        ],
        delivery_schedule={
            "cron_expression": "0 8 1 * *",
            "channel_type": "EMAIL",
            "recipients": [{"type": "EMAIL", "address": "finance@example.com"}],
            "export_format": "PDF",
        },
    ),
}


def get_template(template_id: str) -> OnboardingTemplate | None:
    return TEMPLATE_REGISTRY.get(str(template_id).strip().lower())


__all__ = ["OnboardingTemplate", "TEMPLATE_REGISTRY", "get_template"]
