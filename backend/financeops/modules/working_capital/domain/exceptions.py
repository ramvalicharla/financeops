from __future__ import annotations

from financeops.core.exceptions import FinanceOpsError


class WorkingCapitalError(FinanceOpsError):
    status_code = 500
    error_code = "working_capital_error"


class InsufficientGLDataError(WorkingCapitalError):
    status_code = 422
    error_code = "insufficient_gl_data"

    def __init__(self, tenant_id):
        super().__init__(
            f"No GL data for tenant {tenant_id}. "
            "Complete ERP sync first before accessing Working Capital."
        )
