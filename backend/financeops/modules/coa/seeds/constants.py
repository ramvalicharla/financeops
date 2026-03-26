from __future__ import annotations

from typing import TypedDict


class IndustryTemplateSeed(TypedDict):
    code: str
    name: str
    description: str


class ScheduleSeed(TypedDict):
    gaap: str
    classification_code: str
    code: str
    name: str
    schedule_number: str | None
    sort_order: int


class LineItemSeed(TypedDict):
    schedule_code: str
    code: str
    name: str
    bs_pl_flag: str | None
    asset_liability_class: str | None
    sort_order: int


class SublineSeed(TypedDict):
    line_item_code: str
    code: str
    name: str
    sort_order: int


class GroupSeed(TypedDict):
    category: str
    code: str
    name: str
    subline_code: str
    sort_order: int


INDUSTRY_TEMPLATES: list[IndustryTemplateSeed] = [
    {"code": "SOFTWARE_SAAS", "name": "Software & SaaS", "description": "Template for software and subscription businesses."},
    {"code": "IT_SERVICES", "name": "IT Services & BPO", "description": "Template for IT services and BPO organisations."},
    {"code": "RETAIL", "name": "Retail & E-commerce", "description": "Template for retail and e-commerce organisations."},
    {"code": "MANUFACTURING", "name": "Manufacturing", "description": "Template for manufacturing organisations."},
    {"code": "TRADING", "name": "Trading & Distribution", "description": "Template for trading and distribution organisations."},
    {"code": "REAL_ESTATE", "name": "Real Estate & Construction", "description": "Template for real estate and construction organisations."},
    {"code": "FINANCIAL_SERVICES", "name": "Financial Services & NBFC", "description": "Template for financial services organisations."},
    {"code": "HOSPITALITY", "name": "Hospitality & F&B", "description": "Template for hospitality and food businesses."},
    {"code": "HEALTHCARE", "name": "Healthcare & Pharma", "description": "Template for healthcare and pharma organisations."},
    {"code": "INFRASTRUCTURE", "name": "Infrastructure & EPC", "description": "Template for infrastructure and EPC organisations."},
    {"code": "HOLDING", "name": "Holding & Investment", "description": "Template for holding and investment entities."},
]


FS_CLASSIFICATIONS: list[tuple[str, str, int]] = [
    ("BALANCE_SHEET", "Balance Sheet", 1),
    ("PROFIT_LOSS", "Profit & Loss", 2),
    ("CASH_FLOW", "Cash Flow", 3),
    ("NOTES_TO_ACCOUNTS", "Notes to Accounts", 4),
]


INDAS_SCHEDULES: list[ScheduleSeed] = [
    {
        "gaap": "INDAS",
        "classification_code": "BALANCE_SHEET",
        "code": "INDAS_BS_EQUITY_LIAB",
        "name": "Schedule III - Equity & Liabilities",
        "schedule_number": "Schedule III",
        "sort_order": 1,
    },
    {
        "gaap": "INDAS",
        "classification_code": "BALANCE_SHEET",
        "code": "INDAS_BS_ASSETS",
        "name": "Schedule III - Assets",
        "schedule_number": "Schedule III",
        "sort_order": 2,
    },
    {
        "gaap": "INDAS",
        "classification_code": "PROFIT_LOSS",
        "code": "INDAS_PL",
        "name": "Statement of Profit & Loss",
        "schedule_number": None,
        "sort_order": 1,
    },
]


IFRS_SCHEDULES: list[ScheduleSeed] = [
    {
        "gaap": "IFRS",
        "classification_code": "BALANCE_SHEET",
        "code": "IFRS_SFP",
        "name": "Statement of Financial Position",
        "schedule_number": None,
        "sort_order": 1,
    },
    {
        "gaap": "IFRS",
        "classification_code": "PROFIT_LOSS",
        "code": "IFRS_PLOCI",
        "name": "Statement of Profit or Loss and Other Comprehensive Income",
        "schedule_number": None,
        "sort_order": 2,
    },
    {
        "gaap": "IFRS",
        "classification_code": "CASH_FLOW",
        "code": "IFRS_CF",
        "name": "Statement of Cash Flows",
        "schedule_number": None,
        "sort_order": 3,
    },
    {
        "gaap": "IFRS",
        "classification_code": "NOTES_TO_ACCOUNTS",
        "code": "IFRS_SCE",
        "name": "Statement of Changes in Equity",
        "schedule_number": None,
        "sort_order": 4,
    },
]


INDAS_LINE_ITEMS: list[LineItemSeed] = [
    {"schedule_code": "INDAS_BS_EQUITY_LIAB", "code": "SHAREHOLDERS_FUNDS", "name": "Shareholders' Funds", "bs_pl_flag": "EQUITY", "asset_liability_class": None, "sort_order": 1},
    {"schedule_code": "INDAS_BS_EQUITY_LIAB", "code": "SHARE_APP_MONEY", "name": "Share Application Money Pending Allotment", "bs_pl_flag": "EQUITY", "asset_liability_class": None, "sort_order": 2},
    {"schedule_code": "INDAS_BS_EQUITY_LIAB", "code": "NON_CURRENT_LIABILITIES", "name": "Non-Current Liabilities", "bs_pl_flag": "LIABILITY", "asset_liability_class": "NON_CURRENT", "sort_order": 3},
    {"schedule_code": "INDAS_BS_EQUITY_LIAB", "code": "CURRENT_LIABILITIES", "name": "Current Liabilities", "bs_pl_flag": "LIABILITY", "asset_liability_class": "CURRENT", "sort_order": 4},
    {"schedule_code": "INDAS_BS_ASSETS", "code": "NON_CURRENT_ASSETS", "name": "Non-Current Assets", "bs_pl_flag": "ASSET", "asset_liability_class": "NON_CURRENT", "sort_order": 5},
    {"schedule_code": "INDAS_BS_ASSETS", "code": "CURRENT_ASSETS", "name": "Current Assets", "bs_pl_flag": "ASSET", "asset_liability_class": "CURRENT", "sort_order": 6},
    {"schedule_code": "INDAS_PL", "code": "REV_FROM_OPERATIONS", "name": "Revenue from Operations", "bs_pl_flag": "REVENUE", "asset_liability_class": None, "sort_order": 1},
    {"schedule_code": "INDAS_PL", "code": "OTHER_INCOME", "name": "Other Income", "bs_pl_flag": "REVENUE", "asset_liability_class": None, "sort_order": 2},
    {"schedule_code": "INDAS_PL", "code": "TOTAL_REVENUE", "name": "Total Revenue (I + II)", "bs_pl_flag": "REVENUE", "asset_liability_class": None, "sort_order": 3},
    {"schedule_code": "INDAS_PL", "code": "EXPENSES", "name": "Expenses", "bs_pl_flag": "EXPENSE", "asset_liability_class": None, "sort_order": 4},
    {"schedule_code": "INDAS_PL", "code": "PBT_EXCEPTIONAL_TAX", "name": "Profit Before Exceptional & Tax", "bs_pl_flag": "REVENUE", "asset_liability_class": None, "sort_order": 5},
    {"schedule_code": "INDAS_PL", "code": "EXCEPTIONAL_ITEMS", "name": "Exceptional Items", "bs_pl_flag": "EXPENSE", "asset_liability_class": None, "sort_order": 6},
    {"schedule_code": "INDAS_PL", "code": "PROFIT_BEFORE_TAX", "name": "Profit Before Tax", "bs_pl_flag": "REVENUE", "asset_liability_class": None, "sort_order": 7},
    {"schedule_code": "INDAS_PL", "code": "TAX_EXPENSE", "name": "Tax Expense", "bs_pl_flag": "EXPENSE", "asset_liability_class": None, "sort_order": 8},
    {"schedule_code": "INDAS_PL", "code": "PROFIT_FOR_PERIOD", "name": "Profit for the Period", "bs_pl_flag": "REVENUE", "asset_liability_class": None, "sort_order": 9},
    {"schedule_code": "INDAS_PL", "code": "OCI", "name": "Other Comprehensive Income", "bs_pl_flag": "OCI", "asset_liability_class": None, "sort_order": 10},
    {"schedule_code": "INDAS_PL", "code": "TOTAL_COMPREHENSIVE_INCOME", "name": "Total Comprehensive Income", "bs_pl_flag": "OCI", "asset_liability_class": None, "sort_order": 11},
]


IFRS_LINE_ITEMS: list[LineItemSeed] = [
    {"schedule_code": "IFRS_SFP", "code": "IFRS_ASSETS", "name": "Assets", "bs_pl_flag": "ASSET", "asset_liability_class": None, "sort_order": 1},
    {"schedule_code": "IFRS_SFP", "code": "IFRS_LIABILITIES", "name": "Liabilities", "bs_pl_flag": "LIABILITY", "asset_liability_class": None, "sort_order": 2},
    {"schedule_code": "IFRS_SFP", "code": "IFRS_EQUITY", "name": "Equity", "bs_pl_flag": "EQUITY", "asset_liability_class": None, "sort_order": 3},
    {"schedule_code": "IFRS_PLOCI", "code": "IFRS_PROFIT_LOSS", "name": "Profit or Loss", "bs_pl_flag": "REVENUE", "asset_liability_class": None, "sort_order": 1},
    {"schedule_code": "IFRS_PLOCI", "code": "IFRS_OCI", "name": "Other Comprehensive Income", "bs_pl_flag": "OCI", "asset_liability_class": None, "sort_order": 2},
    {"schedule_code": "IFRS_CF", "code": "IFRS_CF_OPERATING", "name": "Operating Activities", "bs_pl_flag": None, "asset_liability_class": None, "sort_order": 1},
    {"schedule_code": "IFRS_CF", "code": "IFRS_CF_INVESTING", "name": "Investing Activities", "bs_pl_flag": None, "asset_liability_class": None, "sort_order": 2},
    {"schedule_code": "IFRS_CF", "code": "IFRS_CF_FINANCING", "name": "Financing Activities", "bs_pl_flag": None, "asset_liability_class": None, "sort_order": 3},
    {"schedule_code": "IFRS_SCE", "code": "IFRS_OPENING_EQUITY", "name": "Opening Equity", "bs_pl_flag": "EQUITY", "asset_liability_class": None, "sort_order": 1},
    {"schedule_code": "IFRS_SCE", "code": "IFRS_MOVEMENTS", "name": "Movements in Equity", "bs_pl_flag": "EQUITY", "asset_liability_class": None, "sort_order": 2},
    {"schedule_code": "IFRS_SCE", "code": "IFRS_CLOSING_EQUITY", "name": "Closing Equity", "bs_pl_flag": "EQUITY", "asset_liability_class": None, "sort_order": 3},
]


INDAS_SUBLINES: list[SublineSeed] = [
    {"line_item_code": "SHAREHOLDERS_FUNDS", "code": "SHARE_CAPITAL", "name": "Share Capital", "sort_order": 1},
    {"line_item_code": "SHAREHOLDERS_FUNDS", "code": "RESERVES_SURPLUS", "name": "Reserves & Surplus", "sort_order": 2},
    {"line_item_code": "SHAREHOLDERS_FUNDS", "code": "MONEY_WARRANTS", "name": "Money Received Against Share Warrants", "sort_order": 3},
    {"line_item_code": "NON_CURRENT_LIABILITIES", "code": "LONG_TERM_BORROWINGS", "name": "Long-Term Borrowings", "sort_order": 1},
    {"line_item_code": "NON_CURRENT_LIABILITIES", "code": "DTL_NET", "name": "Deferred Tax Liabilities (Net)", "sort_order": 2},
    {"line_item_code": "NON_CURRENT_LIABILITIES", "code": "OTHER_LT_LIAB", "name": "Other Long-Term Liabilities", "sort_order": 3},
    {"line_item_code": "NON_CURRENT_LIABILITIES", "code": "LONG_TERM_PROVISIONS", "name": "Long-Term Provisions", "sort_order": 4},
    {"line_item_code": "CURRENT_LIABILITIES", "code": "SHORT_TERM_BORROWINGS", "name": "Short-Term Borrowings", "sort_order": 1},
    {"line_item_code": "CURRENT_LIABILITIES", "code": "TRADE_PAYABLES_MSME", "name": "Trade Payables - Dues to MSME", "sort_order": 2},
    {"line_item_code": "CURRENT_LIABILITIES", "code": "TRADE_PAYABLES_OTHERS", "name": "Trade Payables - Dues to Others", "sort_order": 3},
    {"line_item_code": "CURRENT_LIABILITIES", "code": "OTHER_CURRENT_LIAB", "name": "Other Current Liabilities", "sort_order": 4},
    {"line_item_code": "CURRENT_LIABILITIES", "code": "SHORT_TERM_PROVISIONS", "name": "Short-Term Provisions", "sort_order": 5},
    {"line_item_code": "NON_CURRENT_ASSETS", "code": "FIXED_ASSETS_TANGIBLE", "name": "Fixed Assets - Tangible", "sort_order": 1},
    {"line_item_code": "NON_CURRENT_ASSETS", "code": "FIXED_ASSETS_INTANGIBLE", "name": "Fixed Assets - Intangible", "sort_order": 2},
    {"line_item_code": "NON_CURRENT_ASSETS", "code": "CAPITAL_WIP", "name": "Capital Work-in-Progress", "sort_order": 3},
    {"line_item_code": "NON_CURRENT_ASSETS", "code": "INTANGIBLE_UNDER_DEV", "name": "Intangible Assets Under Development", "sort_order": 4},
    {"line_item_code": "NON_CURRENT_ASSETS", "code": "NON_CURRENT_INVESTMENTS", "name": "Non-Current Investments", "sort_order": 5},
    {"line_item_code": "NON_CURRENT_ASSETS", "code": "DTA_NET", "name": "Deferred Tax Assets (Net)", "sort_order": 6},
    {"line_item_code": "NON_CURRENT_ASSETS", "code": "LONG_TERM_LOANS_ADVANCES", "name": "Long-Term Loans & Advances", "sort_order": 7},
    {"line_item_code": "NON_CURRENT_ASSETS", "code": "OTHER_NON_CURRENT_ASSETS", "name": "Other Non-Current Assets", "sort_order": 8},
    {"line_item_code": "CURRENT_ASSETS", "code": "CURRENT_INVESTMENTS", "name": "Current Investments", "sort_order": 1},
    {"line_item_code": "CURRENT_ASSETS", "code": "INVENTORIES", "name": "Inventories", "sort_order": 2},
    {"line_item_code": "CURRENT_ASSETS", "code": "TRADE_RECEIVABLES", "name": "Trade Receivables", "sort_order": 3},
    {"line_item_code": "CURRENT_ASSETS", "code": "CASH_EQUIVALENTS", "name": "Cash & Cash Equivalents", "sort_order": 4},
    {"line_item_code": "CURRENT_ASSETS", "code": "SHORT_TERM_LOANS_ADVANCES", "name": "Short-Term Loans & Advances", "sort_order": 5},
    {"line_item_code": "CURRENT_ASSETS", "code": "OTHER_CURRENT_ASSETS", "name": "Other Current Assets", "sort_order": 6},
    {"line_item_code": "REV_FROM_OPERATIONS", "code": "OPERATING_REVENUE", "name": "Revenue from Operations", "sort_order": 1},
    {"line_item_code": "OTHER_INCOME", "code": "OTHER_INCOME_SUBLINE", "name": "Other Income", "sort_order": 1},
    {"line_item_code": "EXPENSES", "code": "COGS_SUBLINE", "name": "Cost of Materials / Direct Costs", "sort_order": 1},
    {"line_item_code": "EXPENSES", "code": "EMPLOYEE_BENEFITS", "name": "Employee Benefits Expense", "sort_order": 2},
    {"line_item_code": "EXPENSES", "code": "FINANCE_COSTS", "name": "Finance Costs", "sort_order": 3},
    {"line_item_code": "EXPENSES", "code": "DEPR_AMORT", "name": "Depreciation & Amortisation", "sort_order": 4},
    {"line_item_code": "EXPENSES", "code": "OTHER_EXPENSES", "name": "Other Expenses", "sort_order": 5},
    {"line_item_code": "TAX_EXPENSE", "code": "CURRENT_TAX", "name": "Current Tax", "sort_order": 1},
    {"line_item_code": "TAX_EXPENSE", "code": "DEFERRED_TAX", "name": "Deferred Tax", "sort_order": 2},
    {"line_item_code": "OCI", "code": "OCI_ITEMS", "name": "Other Comprehensive Income Items", "sort_order": 1},
]


SOFTWARE_SAAS_GROUPS: list[GroupSeed] = [
    {"category": "EQUITY_RESERVES", "code": "EQUITY_RESERVES", "name": "Equity & Reserves", "subline_code": "RESERVES_SURPLUS", "sort_order": 1},
    {"category": "LONG_TERM_BORROWINGS", "code": "LONG_TERM_BORROWINGS", "name": "Long-Term Borrowings", "subline_code": "LONG_TERM_BORROWINGS", "sort_order": 2},
    {"category": "SHORT_TERM_BORROWINGS", "code": "SHORT_TERM_BORROWINGS", "name": "Short-Term Borrowings", "subline_code": "SHORT_TERM_BORROWINGS", "sort_order": 3},
    {"category": "TRADE_PAYABLES", "code": "TRADE_PAYABLES", "name": "Trade Payables", "subline_code": "TRADE_PAYABLES_OTHERS", "sort_order": 4},
    {"category": "OTHER_CURRENT_LIABILITIES", "code": "OTHER_CURRENT_LIABILITIES", "name": "Other Current Liabilities", "subline_code": "OTHER_CURRENT_LIAB", "sort_order": 5},
    {"category": "TANGIBLE_ASSETS", "code": "TANGIBLE_ASSETS", "name": "Fixed Assets - Tangible", "subline_code": "FIXED_ASSETS_TANGIBLE", "sort_order": 6},
    {"category": "INTANGIBLE_ASSETS", "code": "INTANGIBLE_ASSETS", "name": "Fixed Assets - Intangible", "subline_code": "FIXED_ASSETS_INTANGIBLE", "sort_order": 7},
    {"category": "CAPITAL_WIP", "code": "CAPITAL_WIP", "name": "Capital Work-in-Progress", "subline_code": "CAPITAL_WIP", "sort_order": 8},
    {"category": "NON_CURRENT_INVESTMENTS", "code": "NON_CURRENT_INVESTMENTS", "name": "Non-Current Investments", "subline_code": "NON_CURRENT_INVESTMENTS", "sort_order": 9},
    {"category": "LONG_TERM_LOANS_ADVANCES", "code": "LONG_TERM_LOANS_ADVANCES", "name": "Long-Term Loans & Advances", "subline_code": "LONG_TERM_LOANS_ADVANCES", "sort_order": 10},
    {"category": "CURRENT_INVESTMENTS", "code": "CURRENT_INVESTMENTS", "name": "Current Investments", "subline_code": "CURRENT_INVESTMENTS", "sort_order": 11},
    {"category": "INVENTORIES", "code": "INVENTORIES", "name": "Inventories", "subline_code": "INVENTORIES", "sort_order": 12},
    {"category": "TRADE_RECEIVABLES", "code": "TRADE_RECEIVABLES", "name": "Trade Receivables", "subline_code": "TRADE_RECEIVABLES", "sort_order": 13},
    {"category": "CASH_EQUIVALENTS", "code": "CASH_EQUIVALENTS", "name": "Cash & Cash Equivalents", "subline_code": "CASH_EQUIVALENTS", "sort_order": 14},
    {"category": "SHORT_TERM_LOANS_ADVANCES", "code": "SHORT_TERM_LOANS_ADVANCES", "name": "Short-Term Loans & Advances", "subline_code": "SHORT_TERM_LOANS_ADVANCES", "sort_order": 15},
    {"category": "REVENUE", "code": "REVENUE", "name": "Revenue from Operations", "subline_code": "OPERATING_REVENUE", "sort_order": 16},
    {"category": "OTHER_INCOME", "code": "OTHER_INCOME", "name": "Other Income", "subline_code": "OTHER_INCOME_SUBLINE", "sort_order": 17},
    {"category": "COGS", "code": "COGS", "name": "Direct Costs", "subline_code": "COGS_SUBLINE", "sort_order": 18},
    {"category": "EMPLOYEE_BENEFITS", "code": "EMPLOYEE_BENEFITS", "name": "Employee Benefits", "subline_code": "EMPLOYEE_BENEFITS", "sort_order": 19},
    {"category": "FINANCE_COSTS", "code": "FINANCE_COSTS", "name": "Finance Costs", "subline_code": "FINANCE_COSTS", "sort_order": 20},
    {"category": "DEPRECIATION_AMORTISATION", "code": "DEPRECIATION_AMORTISATION", "name": "Depreciation & Amortisation", "subline_code": "DEPR_AMORT", "sort_order": 21},
    {"category": "OTHER_EXPENSES", "code": "OTHER_EXPENSES", "name": "Other Expenses", "subline_code": "OTHER_EXPENSES", "sort_order": 22},
    {"category": "TAX", "code": "TAX", "name": "Tax Expense", "subline_code": "CURRENT_TAX", "sort_order": 23},
    {"category": "OCI", "code": "OCI", "name": "Other Comprehensive Income", "subline_code": "OCI_ITEMS", "sort_order": 24},
]
