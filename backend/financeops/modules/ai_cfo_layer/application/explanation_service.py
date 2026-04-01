from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from financeops.core.exceptions import ValidationError
from financeops.modules.ai_cfo_layer.application.validation_service import (
    validate_generated_text_against_facts,
)
from financeops.modules.ai_cfo_layer.schemas import (
    VarianceDriverRow,
    VarianceExplanationResponse,
)
from financeops.modules.analytics_layer.application.drilldown_service import (
    get_metric_drilldown,
)
from financeops.modules.analytics_layer.application.variance_service import compute_variance


async def explain_variance(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    metric_name: str,
    org_entity_id: uuid.UUID | None,
    org_group_id: uuid.UUID | None,
    from_date: date,
    to_date: date,
    comparison: str = "prev_month",
) -> VarianceExplanationResponse:
    variance = await compute_variance(
        db,
        tenant_id=tenant_id,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        comparison=comparison,
    )
    metric_row = next(
        (item for item in variance.metric_variances if item.metric_name == metric_name),
        None,
    )
    if metric_row is None:
        raise ValidationError(f"Metric {metric_name} is not available for selected scope.")

    driver_rows = sorted(
        variance.account_variances,
        key=lambda item: abs(Decimal(str(item.variance_value))),
        reverse=True,
    )[:3]
    drivers = [
        VarianceDriverRow(
            account_code=item.account_code,
            account_name=item.account_name,
            variance_value=item.variance_value,
            variance_percent=item.variance_percent,
        )
        for item in driver_rows
    ]

    drilldown = await get_metric_drilldown(
        db,
        tenant_id=tenant_id,
        metric_name=metric_name,
        org_entity_id=org_entity_id,
        org_group_id=org_group_id,
        from_date=from_date,
        to_date=to_date,
        as_of_date=to_date,
    )

    drilldown_accounts = {item.account_code for item in drilldown.accounts}
    for driver in drivers:
        if driver.account_code not in drilldown_accounts:
            raise ValidationError(
                f"Driver account {driver.account_code} missing from drilldown lineage."
            )

    top_driver_text = "no dominant account driver found"
    if drivers:
        top = drivers[0]
        pct = top.variance_percent if top.variance_percent is not None else Decimal("0")
        top_driver_text = (
            f"top driver {top.account_code} ({top.account_name}) changed by "
            f"{top.variance_value} ({pct}%)."
        )

    variance_percent = metric_row.variance_percent
    variance_percent_text = (
        f"{variance_percent}%"
        if variance_percent is not None
        else "N/A due to zero previous value"
    )
    entity_scope_text = ""
    entity_ids = drilldown.lineage.get("entity_ids") if isinstance(drilldown.lineage, dict) else None
    if isinstance(entity_ids, list) and entity_ids:
        entity_scope_text = f" across entities {', '.join(entity_ids)}"
    explanation = (
        f"{metric_name} moved from {metric_row.previous_value} to {metric_row.current_value}, "
        f"absolute variance {metric_row.variance_value}, variance percent {variance_percent_text}; "
        f"{top_driver_text}{entity_scope_text}"
    )

    allowed_numbers = [
        metric_row.current_value,
        metric_row.previous_value,
        metric_row.variance_value,
        variance_percent or Decimal("0"),
    ]
    for driver in drivers:
        allowed_numbers.append(driver.variance_value)
        allowed_numbers.append(driver.variance_percent or Decimal("0"))
    validate_generated_text_against_facts(
        text=explanation,
        allowed_numbers=allowed_numbers,
    )

    return VarianceExplanationResponse(
        metric_name=metric_name,
        comparison=comparison,
        current_value=metric_row.current_value,
        previous_value=metric_row.previous_value,
        variance_value=metric_row.variance_value,
        variance_percent=metric_row.variance_percent,
        explanation=explanation,
        top_drivers=drivers,
        fact_basis={
            "period": {
                "from_date": str(from_date),
                "to_date": str(to_date),
            },
            "drilldown": {
                "account_count": len(drilldown.accounts),
                "journal_count": len(drilldown.journals),
                "gl_entry_count": len(drilldown.gl_entries),
            },
        },
        validation_passed=True,
    )
